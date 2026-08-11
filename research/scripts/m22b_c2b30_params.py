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

dump_dir = r'C:\Users\OK\Desktop\m22b_dumps'
os.makedirs(dump_dir, exist_ok=True)

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var funcAddr = mod.base.add(0x016c2b30);
var hit = 0;

send('c2b30 @ ' + funcAddr.toString());

Interceptor.attach(funcAddr, {
    onEnter: function(args) {
        hit++;
        if (hit > 8) return;
        this.h = hit;
        var txt = '';
        for (var i = 0; i < 4; i++) {
            try {
                var v = args[i];
                txt += ' a' + i + '=' + (v ? v.toString() : 'null');
            } catch(e) {}
        }
        send('HIT#' + hit + txt);

        // Dump each argument
        for (var ai = 0; ai < 4; ai++) {
            if (!args[ai]) continue;
            var sizes = [0x100, 0x200];
            if (ai === 0) sizes = [0x400];  // a0 - larger
            for (var si = 0; si < sizes.length; si++) {
                try {
                    var data = args[ai].readByteArray(sizes[si]);
                    if (data) {
                        var hex = '';
                        var bytes = new Uint8Array(data);
                        for (var j = 0; j < sizes[si]; j++) hex += ('0' + bytes[j].toString(16)).slice(-2);
                        send('D' + hit + '_a' + ai + '_' + sizes[si] + ' ' + hex);

                        // Search for strings
                        var str = '';
                        for (var j = 0; j < bytes.length && str.length < 40; j++) {
                            if (bytes[j] >= 0x20 && bytes[j] < 0x7f) {
                                str += String.fromCharCode(bytes[j]);
                            } else if (str.length > 3) {
                                send('S' + hit + '_a' + ai + ' \"' + str + '\"');
                                str = '';
                            } else {
                                str = '';
                            }
                        }
                    }
                } catch(e) {}
            }
        }
    }
});
'''

session = frida.attach(PID)
script = session.create_script(js)

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)

        m = __import__('re').match(r'D\d+_a(\d+)_(\d+) ([0-9a-fA-F]+)', line)
        if m:
            idx = __import__('re').search(r'HIT#(\d+)', line)
            # Save via separate method
            pass

script.on('message', on_msg)
script.load()

print(f'PID={PID} - PageUp a few times', flush=True)
try:
    time.sleep(45)
except:
    pass
session.detach()
print('Done.', flush=True)
