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

dump_dir = r'C:\Users\OK\Desktop\m17_dumps'
os.makedirs(dump_dir, exist_ok=True)

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var funcAddr = mod.base.add(0x016c2a20);
var callCount = 0;

Interceptor.attach(funcAddr, {
    onEnter: function(args) {
        callCount++;
        if (callCount > 80) return;
        this.c = callCount;
        if (!args[1]) return;

        // Dump 0x2d8 from a1
        try {
            var data = args[1].readByteArray(0x2d8);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 0x2d8; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                send('D ' + callCount + ' H ' + hex);
            }
        } catch(e) {
            send('E ' + callCount + ' D ' + e.toString().substring(0,30));
        }

        // Walk pointers in a1 (first 32 qwords)
        try {
            for (var off = 0; off < 0x100; off += 8) {
                var ptr = args[1].add(off).readPointer();
                if (!ptr || ptr.isNull()) continue;
                var val = ptr.toInt32();
                if (val < 0x10000 || val > 0x7fffffff) continue;

                // Try reading as string
                try {
                    var str = ptr.readUtf8String();
                    if (str && str.length > 2 && str.length < 500) {
                        // Check for marker content
                        var hasMarker = str.indexOf('RAY_TEST') >= 0;
                        if (hasMarker) {
                            send('! ' + callCount + ' FOUND at a1+' + off.toString(16) + ' = ' + ptr.toString());
                            send('! ' + callCount + ' CONTENT: ' + str);
                        } else if (str.indexOf('wxid_') >= 0 || str.indexOf('@chatroom') >= 0) {
                            // Skip common IDs
                        } else if (callCount <= 3) {
                            send('S ' + callCount + ' +' + off.toString(16) + ' "' + str.substring(0,60).replace(/"/g, '\\"') + '"');
                        }
                    }
                } catch(e) {}

                // Also try UTF-16
                try {
                    var str16 = ptr.readUtf16String();
                    if (str16 && str16.length > 2 && str16.length < 500 && str16.indexOf('RAY_TEST') >= 0) {
                        send('! ' + callCount + ' UTF16 FOUND at a1+' + off.toString(16) + ' = ' + ptr.toString());
                        send('! ' + callCount + ' CONTENT16: ' + str16);
                    }
                } catch(e) {}
            }
        } catch(e) {}
    }
});
send('R');
'''

session = frida.attach(PID)
script = session.create_script(js)
found_markers = []

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)

        # Save dumps
        m = re.match(r'D (\d+) H ([0-9a-fA-F]+)', line)
        if m:
            bin_path = os.path.join(dump_dir, f'msg_{int(m.group(1)):03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m.group(2)))

        if 'RAY_TEST' in line:
            found_markers.append(line)

script.on('message', on_msg)
script.load()

print('READY - Go to 文件传输助手 and PageUp until you see the test messages', flush=True)
time.sleep(45)
session.detach()

print(f'\n=== Search Results ===', flush=True)
if found_markers:
    for line in found_markers:
        print(line, flush=True)
else:
    print('NOT FOUND in a1 pointer walk. Checking binary dumps for markers...', flush=True)
    # Check all dump files
    for fname in sorted(os.listdir(dump_dir)):
        data = open(os.path.join(dump_dir, fname), 'rb').read()
        for marker in [b'RAY_TEST_AAA', b'RAY_TEST_BBB', b'RAY_TEST_CCC']:
            pos = data.find(marker)
            if pos >= 0:
                print(f'FOUND {marker.decode()} in {fname} at offset +0x{pos:x}', flush=True)
            pos16 = data.find(marker.replace(b'_', b'\x00_\x00'))
            if pos16 >= 0:
                print(f'FOUND {marker.decode()} UTF16 in {fname} at offset +0x{pos16:x}', flush=True)

    # If still not found, search pointed-to memory
    print('Not in struct itself. Need to follow deeper pointers.', flush=True)

print('Done.', flush=True)
