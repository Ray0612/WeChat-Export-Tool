import frida, psutil, time, os, re

PID = None
for p in sorted(psutil.process_iter(['pid','name']), key=lambda x: x.info['pid']):
    if p.info['name'] != 'Weixin.exe': continue
    try:
        sess = frida.attach(p.info['pid'])
        sc = sess.create_script("send(Process.findModuleByName('Weixin.dll')?'yes':'no');")
        r=[]
        def m(msg,d):
            if msg['type']=='send': r.append(msg['payload'])
        sc.on('message', m)
        sc.load()
        time.sleep(0.2)
        sess.detach()
        if r and r[0]=='yes':
            PID = p.info['pid']
            break
    except: pass

if not PID:
    print("No Weixin.exe with Weixin.dll found")
    exit(1)

outfile = r'C:\Users\OK\Desktop\m13_caller1.txt'
dump_dir = r'C:\Users\OK\Desktop\m13_dumps'
os.makedirs(dump_dir, exist_ok=True)
open(outfile, 'w').close()

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
var caller1Addr = mod.base.add(0x01683b08);
var hitCount = 0;

send('Caller1 @ ' + caller1Addr.toString());

Interceptor.attach(caller1Addr, {
    onEnter: function(args) {
        hitCount++;
        var a0 = args[0] ? args[0].toString() : 'null';
        var a1 = args[1] ? args[1].toString() : 'null';
        var a2 = args[2] ? args[2].toString() : 'null';
        var a3 = args[3] ? args[3].toString() : 'null';
        var a4 = args[4] ? args[4].toString() : 'null';
        var a5 = args[5] ? args[5].toString() : 'null';

        this.hitNum = hitCount;
        this.arg0 = args[0];
        this.arg1 = args[1];
        this.arg2 = args[2];

        send('[ENTER #' + hitCount + ']'
            + ' a0=' + a0
            + ' a1=' + a1
            + ' a2=' + a2
            + ' a3=' + a3
            + ' a4=' + a4
            + ' a5=' + a5);

        // Verify a3 = a2 + 0x20
        if (args[2] && args[3]) {
            var diff = args[3].sub(args[2]).toInt32();
            send('  a3-a2=' + diff);
        }
        if (args[4] && args[2]) {
            var diff2 = args[4].sub(args[2]).toInt32();
            send('  a4-a2=' + diff2);
        }

        // Dump PagingContext (arg2) header - 64 bytes
        if (args[2]) {
            try {
                var data = args[2].readByteArray(64);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 64; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('[ARG2_HEX #' + hitCount + '] ' + hex);
                }
            } catch(e) {
                send('[ARG2_ERR] ' + e.toString().substring(0,60));
            }

            // Read wxid at +0x000
            try {
                var wxidPtr = args[2].readPointer();
                if (wxidPtr) {
                    var str = wxidPtr.readUtf8String();
                    if (str) send('  wxid=' + str.substring(0, 40));
                }
            } catch(e) {}

            // Read cursor at +0x028 (u64)
            try {
                var cursor = args[2].add(0x28).readU64();
                send('  cursor=' + cursor.toString());
            } catch(e) {}

            // Read counter at +0x030 (u32)
            try {
                var counter = args[2].add(0x30).readU32();
                send('  counter=' + counter);
            } catch(e) {}
        }
    },

    onLeave: function(retval) {
        send('[LEAVE #' + this.hitNum + '] retval=' + (retval ? retval.toString() : 'null'));

        // Dump PagingContext AFTER call
        if (this.arg2) {
            try {
                var data = this.arg2.readByteArray(64);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 64; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('[ARG2_AFTER #' + this.hitNum + '] ' + hex);
                }
            } catch(e) {}

            try {
                var cursor = this.arg2.add(0x28).readU64();
                send('  cursor_after=' + cursor.toString());
            } catch(e) {}
            try {
                var counter = this.arg2.add(0x30).readU32();
                send('  counter_after=' + counter);
            } catch(e) {}
        }
    }
});
'''

session = frida.attach(PID)
script = session.create_script(jscode)
dump_idx = [0]

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(outfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        print(line, flush=True)
    elif msg['type'] == 'error':
        print('ERR:', str(msg), flush=True)

script.on('message', on_msg)
script.load()

print(f'M13 Caller1 Analysis (PID={PID})', flush=True)
print('PageUp 5-10 times (45s)', flush=True)

try:
    time.sleep(45)
except:
    pass
session.detach()
print('\nDone.', flush=True)
