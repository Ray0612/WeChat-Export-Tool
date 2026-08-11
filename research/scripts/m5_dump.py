import frida, psutil, time, os, struct

logfile = r'C:\Users\OK\Desktop\m5_dump.txt'
dump_dir = r'C:\Users\OK\Desktop\m5_dumps'
os.makedirs(dump_dir, exist_ok=True)
open(logfile, 'w').close()

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
if (!mod) {
    send('ERROR');
} else {
    var funcAddr = mod.base.add(0x016ade70);
    var dumpCount = 0;

    Interceptor.attach(funcAddr, {
        onEnter: function(args) {
            dumpCount++;
            var arg2 = args[2];
            if (!arg2) return;

            send('HIT#' + dumpCount + ' arg2=' + arg2.toString());

            // Read 512 bytes from arg2
            try {
                var data = arg2.readByteArray(512);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 512; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('DUMP#' + dumpCount + ' ' + hex);
                }
            } catch(e) {
                send('READ_ERROR: ' + e.toString());
            }
        }
    });
    send('Ready');
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
dump_idx = [0]

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        if line.startswith('DUMP#'):
            parts = line.split(' ', 1)
            if len(parts) == 2:
                idx = dump_idx[0]
                hex_data = parts[1]
                bin_path = os.path.join(dump_dir, f'dump_{idx:03d}.bin')
                with open(bin_path, 'wb') as f:
                    f.write(bytes.fromhex(hex_data))
                dump_idx[0] += 1

        print(line)

script.on('message', on_msg)
script.load()

print(f'Hook running. 翻页后数据保存到 {dump_dir}')
print('Ctrl+C 停止')
try:
    time.sleep(9999)
except:
    pass
session.detach()
