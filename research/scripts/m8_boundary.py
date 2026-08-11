import frida, psutil, time, os

logfile = r'C:\Users\OK\Desktop\m8_boundary.txt'
open(logfile, 'w').close()

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
if (!mod) {
    send('ERROR: Weixin.dll not found');
} else {
    var funcAddr = mod.base.add(0x016ade70);
    var hitCount = 0;

    Interceptor.attach(funcAddr, {
        onEnter: function(args) {
            hitCount++;
            var arg2 = args[2];
            send('[HIT #' + hitCount + ']');

            // Read wxid + cursor from arg2
            if (arg2) {
                try {
                    var wxidPtr = arg2.readPointer();
                    if (wxidPtr) {
                        var wxidStr = wxidPtr.readUtf8String();
                        send('  wxid=' + wxidStr.substring(0, 50));
                    }
                } catch(e) {
                    // inline filehelper
                    try {
                        var raw = arg2.readCString();
                        if (raw) send('  inline=' + raw.substring(0, 20));
                    } catch(e2) {}
                }

                try {
                    var cursor = arg2.add(0x28).readU64();
                    var cursorStr = cursor.toString();
                    var dateStr = '?';
                    // Unix ms timestamp -> readable
                    if (cursorStr.length >= 13) {
                        var ts = cursor.toNumber() / 1000;
                        var d = new Date(ts * 1000);
                        dateStr = d.getFullYear() + '-' +
                            ('0'+(d.getMonth()+1)).slice(-2) + '-' +
                            ('0'+d.getDate()).slice(-2) + ' ' +
                            ('0'+d.getHours()).slice(-2) + ':' +
                            ('0'+d.getMinutes()).slice(-2);
                    }
                    send('  cursor=' + cursorStr + ' (' + dateStr + ')');
                } catch(e) {}

                try {
                    var counter = arg2.add(0x30).readU32();
                    send('  counter=' + counter);
                } catch(e) {}
            }
        }
    });
    send('### M8 Boundary Test ready ###');
}
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

print('=' * 60)
print('M8: Offline History Boundary Test')
print('=' * 60)
print(f'PID: {pid}')
print(f'Log: {logfile}')
print()
print('操作步骤:')
print('1. 在线: 翻到最早 → 记录当前最早时间')
print('2. 退出微信 → 断网')
print('3. 重新打开微信 → 进入同一聊天')
print('4. 持续翻页直到不能继续')
print('5. 告诉我最早能翻到的时间')
print()
print('Ctrl+C 停止')
print('=' * 60)

try:
    time.sleep(99999)
except:
    pass
session.detach()
