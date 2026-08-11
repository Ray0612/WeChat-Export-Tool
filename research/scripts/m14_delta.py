import frida, psutil, time, os, re

PID = None
for p in sorted(psutil.process_iter(['pid','name']), key=lambda x: x.info['pid']):
    if p.info['name'] != 'Weixin.exe': continue
    try:
        sess = frida.attach(p.info['pid'])
        sc = sess.create_script("send(Process.findModuleByName('Weixin.dll')?'yes':'no');")
        r = []
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

outfile = r'C:\Users\OK\Desktop\m14_delta.txt'
dump_dir = r'C:\Users\OK\Desktop\m14_dumps'
os.makedirs(dump_dir, exist_ok=True)
open(outfile, 'w').close()

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var caller1Addr = mod.base.add(0x01683b08);
var hit = 0;
var beforeData = {};
var beforeHex = {};

Interceptor.attach(caller1Addr, {
    onEnter: function(args) {
        hit++;
        this.h = hit;
        var a2 = args[2];
        if (!a2) return;
        this.a2 = a2;
        send('HIT#' + hit + ' a2=' + a2.toString());

        try {
            var data = a2.readByteArray(512);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 512; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                beforeHex[hit] = hex;
                send('BEFORE#' + hit + ' ' + hex);
            }
        } catch(e) {
            send('ERR_BEFORE ' + e.toString().substring(0,40));
        }

        try {
            var p = a2.readPointer();
            if (p) send('  wxid=' + p.readUtf8String().substring(0,40));
        } catch(e) {}
        try { send('  cursor=' + a2.add(0x28).readU64()); } catch(e) {}
        try { send('  counter=' + a2.add(0x30).readU32()); } catch(e) {}
    },
    onLeave: function(retval) {
        var h = this.h;
        if (!this.a2) return;
        send('LEAVE#' + h + ' retval=' + (retval ? retval.toString() : 'null'));

        try {
            var data = this.a2.readByteArray(512);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 512; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                send('AFTER#' + h + ' ' + hex);

                // Compute diff on the fly
                var before = beforeHex[h];
                if (before) {
                    var changes = [];
                    for (var i = 0; i < 512; i += 8) {
                        var b = before.substr(i*2, 16);
                        var a = hex.substr(i*2, 16);
                        if (b !== a) {
                            var bv = parseInt(b, 16);
                            var av = parseInt(a, 16);
                            var tag = '';
                            if (bv === 0 && av > 0x100000000) tag = ' NEW_PTR';
                            else if (bv > 0x100000000 && av === 0) tag = ' CLEARED';
                            else if (bv > 0x100000000 && av > 0x100000000) tag = ' CHANGED';
                            changes.push('+0x' + i.toString(16).padStart(3,'0') + ' ' + b + ' -> ' + a + tag);
                        }
                    }
                    if (changes.length > 0) {
                        send('DIFF#' + h + ' ' + changes.length + ' changes');
                        for (var j = 0; j < changes.length; j++) {
                            send('  ' + changes[j]);
                        }
                    }
                }
            }
        } catch(e) {
            send('ERR_AFTER ' + e.toString().substring(0,40));
        }

        try { send('  cursor_after=' + this.a2.add(0x28).readU64()); } catch(e) {}
        try { send('  counter_after=' + this.a2.add(0x30).readU32()); } catch(e) {}
        send('');
    }
});
'''

session = frida.attach(PID)
script = session.create_script(js)

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(outfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        print(line, flush=True)
script.on('message', on_msg)
script.load()

print(f'M14 Delta PID={PID} - PageUp 5 times (30s)', flush=True)
try:
    time.sleep(30)
except:
    pass
session.detach()
print('Done.', flush=True)
