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

dump_dir = r'C:\Users\OK\Desktop\m16_dumps'
os.makedirs(dump_dir, exist_ok=True)

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var funcAddr = mod.base.add(0x016c2a20);
var callCount = 0;

Interceptor.attach(funcAddr, {
    onEnter: function(args) {
        callCount++;
        this.c = callCount;

        var a0 = args[0] ? args[0].toString() : 'null';
        var a1 = args[1] ? args[1].toString() : 'null';
        var a2 = args[2] ? args[2].toString() : 'null';
        send('CALL #' + callCount + ' a0=' + a0 + ' a1=' + a1 + ' a2=' + a2);

        // Try dumping a1's content (likely the message array or iterator)
        if (args[1]) {
            try {
                var data = args[1].readByteArray(0x2d8);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 0x2d8; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('DUMP_A1 0x2d8 ' + hex);
                }
            } catch(e) {
                send('ERR_A1 ' + e.toString().substring(0,40));
            }

            // Try reading as UTF8 string to find text content
            try {
                var str = args[1].readUtf8String();
                if (str && str.length > 2) {
                    send('STR_A1 \"' + str.substring(0, 80).replace(/"/g, '\\\"') + '\"');
                }
            } catch(e) {}
        }

        // Also dump a2 content (GlobalContext)
        if (args[2]) {
            try {
                var p = args[2].readPointer();
                if (p) {
                    var str = p.readUtf8String();
                    if (str && str.length > 2) {
                        send('STR_A2 \"' + str.substring(0, 80).replace(/"/g, '\\\"') + '\"');
                    }
                }
            } catch(e) {}
        }
    }
});
send('R');
'''

session = frida.attach(PID)
script = session.create_script(js)
dump_idx = [0]

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)

        m = re.match(r'DUMP_A1 0x2d8 ([0-9a-fA-F]+)', line)
        if m:
            bin_path = os.path.join(dump_dir, f'msg_{dump_idx[0]:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m.group(1)))
            dump_idx[0] += 1

script.on('message', on_msg)
script.load()

print(f'M16 PID={PID}', flush=True)
print('指令:', flush=True)
print('1. 输入 q 开始监控，然后发一条带唯一标记的消息', flush=True)
print('2. 按 PageUp 翻页', flush=True)
print('3. 查看 dump 中是否有标记内容', flush=True)
print()

try:
    while True:
        cmd = input().strip()
        if cmd == 'q':
            break
except:
    pass

session.detach()
print(f'\nDumped {dump_idx[0]} message samples to {dump_dir}', flush=True)
