import frida, psutil, time, os, re

logfile = r'C:\Users\OK\Desktop\m9_file_trace.txt'
resultfile = r'C:\Users\OK\Desktop\m9_results.txt'
open(logfile, 'w').close()

jscode = r'''
'use strict';

var allPaths = {};
var totalOpens = 0;
var totalReads = 0;
var readCounts = {};

function addPath(path) {
    if (!path || path.length < 5) return;
    if (!allPaths[path]) {
        allPaths[path] = {open: 0, read: 0, firstSeen: Date.now()};
    }
    allPaths[path].open++;
}

// ---- NtCreateFile ----
try {
    var mod = Process.findModuleByName('ntdll.dll');
    var func = mod.findExportByName('NtCreateFile');
    if (func) {
        Interceptor.attach(func, {
            onEnter: function(args) {
                try {
                    var objAttr = args[4];
                    if (!objAttr || objAttr.isNull()) return;
                    var nameInfo = objAttr.add(0x8);
                    var len = nameInfo.readU16();
                    if (len < 4 || len > 2000) return;
                    var bufPtr = nameInfo.add(0x8).readPointer();
                    if (!bufPtr || bufPtr.isNull()) return;
                    var path = bufPtr.readUtf16String();
                    if (path) {
                        this.filePath = path;
                        this.handlePtr = args[0];
                        totalOpens++;
                        addPath(path);
                    }
                } catch(e) {}
            },
            onLeave: function(retval) {
                if (this.filePath && this.handlePtr && retval.toInt32() >= 0) {
                    try {
                        var hStr = this.handlePtr.readPointer().toString();
                        if (!readCounts[hStr]) readCounts[hStr] = {path: this.filePath, reads: 0};
                    } catch(e) {}
                }
            }
        });
    }
} catch(e) {}

// ---- NtReadFile ----
try {
    var mod = Process.findModuleByName('ntdll.dll');
    var func = mod.findExportByName('NtReadFile');
    if (func) {
        Interceptor.attach(func, {
            onEnter: function(args) {
                try {
                    var hStr = args[0].toString();
                    var info = readCounts[hStr];
                    if (info) {
                        info.reads++;
                        totalReads++;
                    }
                } catch(e) {}
            }
        });
    }
} catch(e) {}

// ---- CreateFileW ----
['KERNELBASE.dll', 'kernel32.dll'].forEach(function(mn) {
    try {
        var m = Process.findModuleByName(mn);
        if (!m) return;
        var f = m.findExportByName('CreateFileW');
        if (f) {
            Interceptor.attach(f, {
                onEnter: function(args) {
                    try {
                        var path = args[0].readUtf16String();
                        if (path) this.filePath = path;
                    } catch(e) {}
                },
                onLeave: function(retval) {
                    if (this.filePath && retval && retval.toInt32() > 0 && retval.toInt32() !== -1) {
                        var hStr = retval.toString();
                        if (!readCounts[hStr]) readCounts[hStr] = {path: this.filePath, reads: 0};
                        addPath(this.filePath);
                        totalOpens++;
                    }
                }
            });
        }
    } catch(e) {}
});

// ---- CreateFileMappingW ----
try {
    var mod = Process.findModuleByName('KERNELBASE.dll');
    if (mod) {
        var func = mod.findExportByName('CreateFileMappingW');
        if (func) {
            Interceptor.attach(func, {
                onEnter: function(args) {
                    try {
                        var h = args[0];
                        if (h && h.toInt32() !== -1 && h.toInt32() !== 0) {
                            var info = readCounts[h.toString()];
                            if (info) {
                                send('[FILEMAPPING] ' + info.path);
                            }
                        }
                    } catch(e) {}
                }
            });
        }
    }
} catch(e) {}

// ---- MapViewOfFile ----
['KERNELBASE.dll', 'kernel32.dll'].forEach(function(mn) {
    try {
        var m = Process.findModuleByName(mn);
        if (!m) return;
        var f = m.findExportByName('MapViewOfFile');
        if (f) {
            Interceptor.attach(f, {
                onEnter: function(args) {
                    try {
                        var hStr = args[0].toString();
                        var info = readCounts[hStr];
                        if (info) {
                            send('[MAPVIEW] ' + info.path);
                        }
                    } catch(e) {}
                }
            });
        }
    } catch(e) {}
});

// ---- Periodic log of unique paths ----
setInterval(function() {
    var paths = Object.keys(allPaths);
    var count = paths.length;
    send('[STATS] totalOpens=' + totalOpens + ' totalReads=' + totalReads + ' uniqueFiles=' + count);

    // Log unique paths sorted by open count
    var sorted = paths.sort(function(a,b) { return allPaths[b].open - allPaths[a].open; });
    for (var i = 0; i < Math.min(sorted.length, 10); i++) {
        var p = sorted[i];
        send('  [' + allPaths[p].open + '] ' + p);
    }
}, 30000);  // every 30 seconds

send('### M9 File trace with MapViewOfFile ###');
'''

procs = [p for p in psutil.process_iter(['pid','name','create_time']) if p.info['name'] == 'Weixin.exe']
if not procs:
    print("Weixin.exe not running")
    exit(1)
procs.sort(key=lambda x: x.info['create_time'])
pid = procs[0].info['pid']

session = frida.attach(pid)
script = session.create_script(jscode)

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        print(line)
    elif msg['type'] == 'error':
        print('ERR:', str(msg))

script.on('message', on_msg)
script.load()

time.sleep(1)

print('=' * 60)
print('M9: File Trace + CreateFileMapping/MapViewOfFile')
print('PID:', pid)
print('=' * 60)
print()
print('去微信翻页 10+ 次, 90秒自动停止')
print()

time.sleep(90)

# Final stats dump via script message
session.detach()

# Parse results
with open(logfile) as f:
    content = f.read()

# Find unique paths
path_stats = {}
for line in content.split('\n'):
    m = re.match(r'^\s+\[(\d+)\]\s+(.+)', line)
    if m:
        path_stats[m.group(2)] = int(m.group(1))

with open(resultfile, 'w', encoding='utf-8') as f:
    f.write('M9 File Access Trace (with MapViewOfFile)\n')
    f.write('=' * 60 + '\n')
    sorted_paths = sorted(path_stats.keys(), key=lambda p: path_stats[p], reverse=True)
    f.write(f'Total unique files: {len(sorted_paths)}\n\n')
    f.write(f'{"OPENS":>8} | FILE\n')
    f.write('-' * 60 + '\n')
    for p in sorted_paths[:50]:
        f.write(f'{path_stats[p]:>8} | {p}\n')

    # Highlight WeChat-related paths
    wechat_paths = [p for p in sorted_paths if 'tencent' in p.lower() or 'xwechat' in p.lower() or 'wechat' in p.lower() or 'radium' in p.lower()]
    if wechat_paths:
        f.write('\n\n=== WeChat/Tencent related files ===\n\n')
        for p in wechat_paths:
            f.write(f'  {path_stats[p]:>6} | {p}\n')

print(f'\nResults: {resultfile}')
