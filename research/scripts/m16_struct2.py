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

dump_dir = r'C:\Users\OK\Desktop\m16_dumps2'
os.makedirs(dump_dir, exist_ok=True)

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var funcAddr = mod.base.add(0x016c2a20);
var callCount = 0;

Interceptor.attach(funcAddr, {
    onEnter: function(args) {
        callCount++;
        if (callCount > 30) return;
        this.c = callCount;

        send('C' + callCount);

        // a1 changes each call - try reading it as pointer array
        if (args[1]) {
            // Try to read a1 itself as a small struct
            try {
                var inner = args[1].readPointer();  // first qword of a1
                if (inner) {
                    send('P1 ' + inner.toString());

                    // Try to read the pointed-to data
                    try {
                        var data = inner.readByteArray(0x2d8);
                        if (data) {
                            var hex = '';
                            var bytes = new Uint8Array(data);
                            for (var i = 0; i < 0x2d8; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                            send('D ' + callCount + ' ' + hex);
                        }
                    } catch(e2) {
                        send('E1 ' + e2.toString().substring(0,30));
                    }
                }
            } catch(e) {}

            // Try a1+8, a1+16 etc
            for (var off = 0; off < 0x40; off += 8) {
                try {
                    var ptr = args[1].add(off).readPointer();
                    if (ptr && ptr.toInt32() > 0x10000) {
                        try {
                            var str = ptr.readUtf8String();
                            if (str && str.length > 3 && str.length < 200) {
                                send('S+' + off.toString(16) + ' \"' + str.substring(0,60).replace(/\"/g, '\\\"') + '\"');
                            }
                        } catch(e) {}
                    }
                } catch(e) {}
            }
        }
    }
});
send('R');
'''

session = frida.attach(PID)
script = session.create_script(js)

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)

        m = re.match(r'D (\d+) ([0-9a-fA-F]+)', line)
        if m:
            bin_path = os.path.join(dump_dir, f'msg_{int(m.group(1)):03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m.group(2)))

script.on('message', on_msg)
script.load()

print('READY - PageUp for 30s', flush=True)
time.sleep(30)
session.detach()

print(f'\nSamples: {len(os.listdir(dump_dir))}', flush=True)
for fname in sorted(os.listdir(dump_dir))[:10]:
    data = open(os.path.join(dump_dir, fname), 'rb').read()
    strs = []
    i = 0
    while i < len(data):
        if 0x20 <= data[i] < 0x7f:
            j = i
            while j < len(data) and 0x20 <= data[j] < 0x7f:
                j += 1
            if j - i >= 4:
                strs.append(data[i:j].decode('ascii', errors='replace'))
            i = j
        else:
            i += 1
    print(f'{fname}: {strs[:3]}', flush=True)

print('Done.', flush=True)
