import frida, psutil, time, os

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

dump_dir = r'C:\Users\OK\Desktop\m16_dumps'
os.makedirs(dump_dir, exist_ok=True)

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var funcAddr = mod.base.add(0x016c2a20);
var callCount = 0;

Interceptor.attach(funcAddr, {
    onEnter: function(args) {
        callCount++;
        if (callCount > 50) return;  // Limit to first 50

        if (!args[1]) return;

        // Dump 0x2d8 bytes from a1
        try {
            var data = args[1].readByteArray(0x2d8);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 0x2d8; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                send('M' + callCount + ' ' + hex);
            }
        } catch(e) {}
    }
});
send('R');
'''

session = frida.attach(PID)
script = session.create_script(js)

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        if line == 'R':
            print('READY', flush=True)
            return
        if line.startswith('M'):
            parts = line.split(' ', 1)
            if len(parts) == 2:
                idx = int(parts[0][1:])
                bin_path = os.path.join(dump_dir, f'msg_{idx:03d}.bin')
                with open(bin_path, 'wb') as f:
                    f.write(bytes.fromhex(parts[1]))
                if idx <= 3 or idx % 10 == 0:
                    print(f'Captured msg_{idx:03d}.bin', flush=True)

script.on('message', on_msg)
script.load()

print('READY - PageUp for 30s', flush=True)
time.sleep(30)
session.detach()

# Quick analysis
print(f'\nAnalyzing {len(os.listdir(dump_dir))} samples...', flush=True)
for fname in sorted(os.listdir(dump_dir))[:5]:
    data = open(os.path.join(dump_dir, fname), 'rb').read()
    # Search for UTF8 strings >= 4 chars
    strings = []
    i = 0
    while i < len(data):
        if 0x20 <= data[i] < 0x7f:
            j = i
            while j < len(data) and 0x20 <= data[j] < 0x7f:
                j += 1
            if j - i >= 4:
                strings.append(data[i:j].decode('ascii', errors='replace'))
            i = j
        else:
            i += 1

    # Check for wxid patterns
    wxids = [s for s in strings if 'wxid_' in s or 'filehelper' in s or '@chatroom' in s]
    if wxids:
        print(f'{fname}: wxid={wxids}')
    elif strings:
        print(f'{fname}: {strings[:3]}')
    else:
        print(f'{fname}: (no ASCII strings)')

print('Done.', flush=True)
