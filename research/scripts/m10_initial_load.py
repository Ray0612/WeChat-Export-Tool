import frida, psutil, time, os, re, threading, sys

WEIXIN_PATH = r'D:\Program Files\Tencent\Weixin\Weixin.exe'
logfile = r'C:\Users\OK\Desktop\m10_trace.txt'
resultfile = r'C:\Users\OK\Desktop\m10_results.txt'
dump_dir = r'C:\Users\OK\Desktop\m10_dumps'
open(logfile, 'w').close()
os.makedirs(dump_dir, exist_ok=True)

jscode = r'''
'use strict';

// Tracking structures
var allFiles = {};        // path -> {opens, reads, bytes, firstOpen}
var handleMap = {};       // handleStr -> {path, bytesRead}
var totalOpens = 0;
var totalReads = 0;
var active = true;

function recordOpen(path) {
    if (!path || path.length < 4) return;
    // Normalize long paths
    if (path.length > 300) path = path.substring(0, 300) + '...';
    if (!allFiles[path]) {
        allFiles[path] = {opens: 0, reads: 0, bytes: 0};
    }
    allFiles[path].opens++;
    totalOpens++;
}

function recordRead(path, bytes) {
    if (!path || path.length < 4) return;
    if (path.length > 300) path = path.substring(0, 300) + '...';
    if (!allFiles[path]) {
        allFiles[path] = {opens: 0, reads: 0, bytes: 0};
    }
    allFiles[path].reads++;
    allFiles[path].bytes += (bytes || 0);
    totalReads++;
}

// ---- NtCreateFile (ntdll) ----
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
                        recordOpen(path);
                    }
                } catch(e) {}
            },
            onLeave: function(retval) {
                if (this.filePath && this.handlePtr && retval.toInt32() >= 0) {
                    try {
                        var h = this.handlePtr.readPointer();
                        if (h) handleMap[h.toString()] = {path: this.filePath, bytesRead: 0};
                    } catch(e) {}
                }
            }
        });
    }
} catch(e) {}

// ---- NtReadFile (ntdll) ----
try {
    var mod = Process.findModuleByName('ntdll.dll');
    var func = mod.findExportByName('NtReadFile');
    if (func) {
        Interceptor.attach(func, {
            onEnter: function(args) {
                try {
                    var hStr = args[0].toString();
                    var info = handleMap[hStr];
                    if (info) {
                        // Get buffer length from args[2] (Length)
                        var bufLen = 0;
                        try { bufLen = args[2].toInt32(); } catch(e) {}
                        info.bytesRead += bufLen;
                        recordRead(info.path, bufLen);
                    }
                } catch(e) {}
            }
        });
    }
} catch(e) {}

// ---- CreateFileW (kernelbase) ----
try {
    var km = Process.findModuleByName('KERNELBASE.dll');
    var func = km.findExportByName('CreateFileW');
    if (func) {
        Interceptor.attach(func, {
            onEnter: function(args) {
                try {
                    var path = args[0].readUtf16String();
                    if (path) this.filePath = path;
                } catch(e) {}
            },
            onLeave: function(retval) {
                if (this.filePath && retval && retval.toInt32() > 0 && retval.toInt32() !== -1) {
                    var hStr = retval.toString();
                    if (!handleMap[hStr]) handleMap[hStr] = {path: this.filePath, bytesRead: 0};
                    recordOpen(this.filePath);
                }
            }
        });
    }
} catch(e) {}

// ---- MapViewOfFile (kernelbase) ----
try {
    var km = Process.findModuleByName('KERNELBASE.dll');
    var func = km.findExportByName('MapViewOfFile');
    if (func) {
        Interceptor.attach(func, {
            onEnter: function(args) {
                try {
                    var hStr = args[0].toString();
                    var info = handleMap[hStr];
                    if (info) {
                        send('[MMAP] ' + info.path);
                    }
                } catch(e) {}
            }
        });
    }
} catch(e) {}

// ---- CreateFileMappingW (kernelbase) ----
try {
    var km = Process.findModuleByName('KERNELBASE.dll');
    var func = km.findExportByName('CreateFileMappingW');
    if (func) {
        Interceptor.attach(func, {
            onEnter: function(args) {
                try {
                    var h = args[0];
                    if (h && h.toInt32() !== -1 && h.toInt32() !== 0) {
                        var info = handleMap[h.toString()];
                        if (info) {
                            send('[FILEMAPPING] ' + info.path);
                        }
                    }
                } catch(e) {}
            }
        });
    }
} catch(e) {}

// ---- Periodic report ----
var reportCount = 0;
var startTime = Date.now();

function generateReport() {
    var elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
    var paths = Object.keys(allFiles).sort(function(a, b) {
        return (allFiles[b].reads * 1024 + allFiles[b].opens) - (allFiles[a].reads * 1024 + allFiles[a].opens);
    });

    send('');
    send('=== REPORT t+' + elapsed + 's ===');
    send('Opens=' + totalOpens + ' Reads=' + totalReads + ' UniqueFiles=' + paths.length);

    // Top 15 files by total activity
    var limit = Math.min(paths.length, 15);
    for (var i = 0; i < limit; i++) {
        var p = paths[i];
        var f = allFiles[p];
        send('  R=' + f.reads + ' O=' + f.opens + ' B=' + f.bytes + ' ' + p);
    }
}

// Auto-report every 20 seconds
setInterval(generateReport, 20000);

recv('report', function() {
    generateReport();
    send('=== REPORT_DONE ===');
});

send('### M10 Initial Load Analysis ready ###');
'''

# ---- Check if WeChat is running ----
running = [p for p in psutil.process_iter(['pid','name']) if p.info['name'] == 'Weixin.exe']
if running:
    print(f"WARNING: Weixin.exe is already running (PID {running[0].info['pid']})")
    print("请先完全退出微信，再按 Enter 继续")
    input()

print("正在启动微信并注入 Frida Hook...")
print("微信启动后请扫码登录，然后打开一个聊天窗口")

try:
    # Spawn Weixin.exe with Frida
    pid = frida.spawn([WEIXIN_PATH])
    session = frida.attach(pid)
    script = session.create_script(jscode)

    all_lines = []
    report_done = threading.Event()

    def on_msg(msg, data):
        if msg['type'] == 'send':
            line = msg['payload']
            all_lines.append(line)
            with open(logfile, 'a', encoding='utf-8') as f:
                f.write(line + '\n')

            # Print notable events
            if line.startswith('[MMAP]') or line.startswith('[FILEMAPPING]'):
                print(f'  >>> {line}')
            elif line.startswith('=== REPORT'):
                print(line)
                if 'REPORT_DONE' in line:
                    report_done.set()
            elif line.startswith('  R='):
                print(line)
        elif msg['type'] == 'error':
            print('ERR:', str(msg))

    script.on('message', on_msg)
    script.load()

    # Resume the process (WeChat starts running)
    session.resume()
    print(f"\n[+] 微信已启动 (PID {pid})，Hook 已注入")
    print("[+] 请扫码登录")
    print()
    print("操作流程:")
    print("  1. 扫码登录微信")
    print("  2. 观察启动阶段文件读取")
    print("  3. 等登录完成，不要打开聊天窗口")
    print("  4. 输入 'chat' 回车 → 然后打开一个聊天窗口")
    print("  5. 观察打开聊天时的文件读取")
    print("  6. 输入 'page' 回车 → 翻页 10 次")
    print("  7. 输入 'report' 回车 → 输出统计")
    print("  8. 输入 'quit' 回车 → 结束")
    print()

    while True:
        cmd = input('> ').strip().lower()
        if cmd == 'quit' or cmd == 'q':
            break
        elif cmd == 'report' or cmd == 'r':
            script.post({'type': 'report'})
            report_done.wait(timeout=5)
        elif cmd == 'chat' or cmd == 'c':
            print("现在请打开一个聊天窗口")
        elif cmd == 'page' or cmd == 'p':
            print("现在请翻页 10 次")
        elif cmd == 'stats' or cmd == 's':
            # Print summary
            reads_dict = {}
            opens_dict = {}
            bytes_dict = {}
            for line in all_lines:
                m = re.match(r'^\s+R=(\d+) O=(\d+) B=(\d+) (.+)', line)
                if m:
                    reads_dict[m.group(4)] = int(m.group(1))
                    opens_dict[m.group(4)] = int(m.group(2))
                    bytes_dict[m.group(4)] = int(m.group(3))

            sorted_paths = sorted(reads_dict.keys(), key=lambda p: reads_dict[p], reverse=True)
            print(f'\n--- Current Stats ({len(sorted_paths)} files) ---')
            for p in sorted_paths[:20]:
                print(f'  {reads_dict[p]:>6} reads | {opens_dict[p]:>4} opens | {bytes_dict[p]:>8}B | {p}')

    # Final report
    script.post({'type': 'report'})
    report_done.wait(timeout=5)
    time.sleep(1)

except Exception as e:
    print(f"\nError: {e}")
    print("Trying attach instead...")
    # Fallback: try to attach if spawn fails
    try:
        for p in psutil.process_iter(['pid','name']):
            if p.info['name'] == 'Weixin.exe':
                pid = p.info['pid']
                break
        session = frida.attach(pid)
        script = session.create_script(jscode)
        # ... same as above
    except Exception as e2:
        print(f"Attach also failed: {e2}")
        sys.exit(1)

# ---- Generate final results ----
with open(logfile) as f:
    content = f.read()

# Parse stats
reads = {}
opens_ = {}
bytes_ = {}
for line in content.split('\n'):
    m = re.match(r'^\s+R=(\d+) O=(\d+) B=(\d+) (.+)', line)
    if m:
        reads[m.group(4)] = int(m.group(1))
        opens_[m.group(4)] = int(m.group(2))
        bytes_[m.group(4)] = int(m.group(3))

with open(resultfile, 'w', encoding='utf-8') as f:
    f.write('M10 — Initial Message Load Analysis\n')
    f.write('=' * 60 + '\n\n')
    sorted_paths = sorted(reads.keys(), key=lambda p: reads[p], reverse=True)
    f.write(f'Total unique files: {len(sorted_paths)}\n\n')
    f.write(f'{"READS":>8} | {"OPENS":>6} | {"BYTES":>10} | FILE\n')
    f.write('-' * 80 + '\n')
    for p in sorted_paths:
        f.write(f'{reads[p]:>8} | {opens_.get(p,0):>6} | {bytes_.get(p,0):>10} | {p}\n')

    # Files with >10 reads
    high_files = {p: reads[p] for p in reads if reads[p] > 10}
    if high_files:
        sorted_high = sorted(high_files.keys(), key=lambda p: high_files[p], reverse=True)
        f.write('\n\n=== High read count files (>10 reads) ===\n\n')
        f.write(f'{"READS":>8} | {"BYTES":>10} | FILE\n')
        f.write('-' * 70 + '\n')
        for p in sorted_high:
            f.write(f'{reads[p]:>8} | {bytes_.get(p,0):>10} | {p}\n')

    # WeChat/Tencent related
    wx_paths = [p for p in sorted_paths if ('tencent' in p.lower() or 'xwechat' in p.lower() or 'radium' in p.lower()) and reads.get(p,0) > 0]
    if wx_paths:
        f.write('\n\n=== WeChat-related files with reads ===\n\n')
        for p in wx_paths:
            f.write(f'{reads[p]:>6} reads | {opens_.get(p,0):>4} opens | {bytes_.get(p,0):>8}B | {p}\n')

print(f'\nResults: {resultfile}')
session.detach()
