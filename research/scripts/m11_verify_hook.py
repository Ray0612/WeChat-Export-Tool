import frida, psutil, time

PID = 16460
NEW_OFFSET = 0x016feab0  # New GetPagedMessages offset in 4.1.10.29

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
if (!mod) {
    send('ERROR: Weixin.dll not found');
} else {
    var funcAddr = mod.base.add(''' + hex(NEW_OFFSET) + ''');
    var count = 0;

    send('Weixin.dll base=' + mod.base.toString());
    send('Target function=' + funcAddr.toString());

    // Verify first byte
    try {
        var b = funcAddr.readU8();
        send('First byte: 0x' + b.toString(16) + (b === 0x55 ? ' (PUSH RBP - OK)' : ' (UNEXPECTED)'));
    } catch(e) {
        send('Cannot read first byte: ' + e.toString());
    }

    Interceptor.attach(funcAddr, {
        onEnter: function(args) {
            count++;
            var a0 = args[0] ? args[0].toString() : 'null';
            var a1 = args[1] ? args[1].toString() : 'null';
            var a2 = args[2] ? args[2].toString() : 'null';
            var a3 = args[3] ? args[3].toString() : 'null';
            send('[HIT #' + count + '] arg0=' + a0 + ' arg1=' + a1 + ' arg2=' + a2 + ' arg3=' + a3);
        }
    });
    send('### Hook installed - 翻页试试 ###');
}
'''

session = frida.attach(PID)
script = session.create_script(jscode)

def on_msg(msg, data):
    if msg['type'] == 'send':
        print(msg['payload'])
    elif msg['type'] == 'error':
        print('ERR:', str(msg))

script.on('message', on_msg)
script.load()

print(f'PID={PID} offset=0x{NEW_OFFSET:08x}')
print('按 PageUp 翻页，Ctrl+C 停止')

try:
    time.sleep(99999)
except:
    pass
session.detach()
