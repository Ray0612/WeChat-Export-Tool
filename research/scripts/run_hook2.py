import frida, psutil, time, os

logfile = r'C:\Users\OK\Desktop\hook_result.txt'

# 清空旧日志
open(logfile, 'w').close()

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
if (!mod) {
    send('ERROR: Weixin.dll not found');
} else {
    var funcAddr = mod.base.add(0x016ade70);

    var count = 0;
    Interceptor.attach(funcAddr, {
        onEnter: function(args) {
            count++;
            var a0 = args[0] ? args[0].toString() : 'null';
            var a1 = args[1] ? args[1].toString() : 'null';
            var a2 = args[2] ? args[2].toString() : 'null';
            var a3 = args[3] ? args[3].toString() : 'null';
            send('[HIT #' + count + ']'
                + ' arg0=' + a0
                + ' arg1=' + a1
                + ' arg2=' + a2
                + ' arg3=' + a3
            );
        }
    });
    send('Hook ready');
}
'''

procs = [p for p in psutil.process_iter(['pid','name','create_time']) if p.info['name'] == 'Weixin.exe']
procs.sort(key=lambda x: x.info['create_time'])
pid = procs[0].info['pid']

with open(logfile, 'a') as f:
    f.write('PID: ' + str(pid) + '\n')

session = frida.attach(pid)
script = session.create_script(jscode)

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(logfile, 'a') as f:
            f.write(line + '\n')
    elif msg['type'] == 'error':
        with open(logfile, 'a') as f:
            f.write('ERR: ' + str(msg) + '\n')

script.on('message', on_msg)
script.load()

with open(logfile, 'a') as f:
    f.write('Hook running. 翻页试试...\n')

print('Hook running. Press Ctrl+C to stop.')
try:
    time.sleep(9999)
except:
    pass
session.detach()
