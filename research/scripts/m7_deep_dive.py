import frida, psutil, time, os, re

logfile = r'C:\Users\OK\Desktop\m7_deep.txt'
dump_dir = r'C:\Users\OK\Desktop\m7_deep_dumps'
os.makedirs(dump_dir, exist_ok=True)
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
            var arg1 = args[1];
            if (!arg1) return;
            this.hitNum = hitCount;
            this.arg1 = arg1;
        },
        onLeave: function(retval) {
            var arg1 = this.arg1;
            if (!arg1) return;

            send('=== HIT #' + this.hitNum + ' ===');

            // Read 3 pointers at +0x000, +0x008, +0x010
            try {
                var p0 = arg1.readPointer();
                var p8 = arg1.add(0x8).readPointer();
                var p10 = arg1.add(0x10).readPointer();
                send('arg1+0x000=' + (p0 ? p0.toString() : 'null'));
                send('arg1+0x008=' + (p8 ? p8.toString() : 'null'));
                send('arg1+0x010=' + (p10 ? p10.toString() : 'null'));

                // Dump memory at +0x000 pointer (0x200 bytes)
                if (p0 && p0.toString() !== '0xaaaaaaaaaaaaaaaa') {
                    try {
                        var data = p0.readByteArray(512);
                        if (data) {
                            var hex = '';
                            var bytes = new Uint8Array(data);
                            for (var i = 0; i < 512; i++) {
                                hex += ('0' + bytes[i].toString(16)).slice(-2);
                            }
                            send('[PTR0_HEX] ' + hex);
                        }
                    } catch(e) {
                        send('[PTR0_ERR] ' + e.toString());
                    }

                    // Try to read strings at p0
                    try {
                        var str = p0.readCString();
                        if (str && str.length > 2) send('[PTR0_STR] ' + str.substring(0, 100));
                    } catch(e) {}
                    try {
                        var str16 = p0.add(0x100).readCString();
                        if (str16 && str16.length > 2) send('[PTR0_STR+0x100] ' + str16.substring(0, 100));
                    } catch(e) {}
                }

                // Dump memory at +0x008 pointer (0x200 bytes)
                if (p8 && p8.toString() !== '0xaaaaaaaaaaaaaaaa' && p8.toString() !== p0.toString()) {
                    try {
                        var data = p8.readByteArray(512);
                        if (data) {
                            var hex = '';
                            var bytes = new Uint8Array(data);
                            for (var i = 0; i < 512; i++) {
                                hex += ('0' + bytes[i].toString(16)).slice(-2);
                            }
                            send('[PTR8_HEX] ' + hex);
                        }
                    } catch(e) {
                        send('[PTR8_ERR] ' + e.toString());
                    }

                    try {
                        var str = p8.readCString();
                        if (str && str.length > 2) send('[PTR8_STR] ' + str.substring(0, 100));
                    } catch(e) {}
                }

                // Also dump the wptr that p0 might point to
                if (p0 && p0.toString() !== '0xaaaaaaaaaaaaaaaa') {
                    try {
                        var inner0 = p0.readPointer();
                        if (inner0) send('[PTR0_INNER0] ' + inner0.toString());
                    } catch(e) {}
                    try {
                        var inner8 = p0.add(0x8).readPointer();
                        if (inner8) send('[PTR0_INNER8] ' + inner8.toString());
                    } catch(e) {}
                    try {
                        var inner16 = p0.add(0x10).readPointer();
                        if (inner16) send('[PTR0_INNER16] ' + inner16.toString());
                    } catch(e) {}
                }

            } catch(e) {
                send('[READ_ERR] ' + e.toString());
            }
            send('');
        }
    });
    send('### M7 Deep Dive ready ###');
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

        if line.startswith('[PTR0_HEX]') or line.startswith('[PTR8_HEX]'):
            m = re.match(r'\[(PTR0_HEX|PTR8_HEX)\]\s+([0-9a-fA-F]+)', line)
            if m:
                tag = m.group(1)
                hex_data = m.group(2)
                name = 'ptr0' if 'PTR0' in tag else 'ptr8'
                existing = [f for f in os.listdir(dump_dir) if f.startswith(name)]
                idx = len(existing)
                bin_path = os.path.join(dump_dir, f'{name}_{idx:03d}.bin')
                with open(bin_path, 'wb') as f:
                    f.write(bytes.fromhex(hex_data))

        print(line)
    elif msg['type'] == 'error':
        print('ERR:', str(msg))

script.on('message', on_msg)
script.load()

print('M7 Deep Dive running. Press PageUp, Ctrl+C to stop.')
try:
    time.sleep(99999)
except:
    pass
session.detach()
