"""
M52 — Hook GetMessageListBySvrIds, capture SvrId sources
"""
import frida, psutil, time, json, os

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

session = frida.attach(PID)

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var f3b30 = mod.base.add(0x016f3b30);
var hit = 0;

// Track handle->path mapping for NtCreateFile
var handleMap = {};

Interceptor.attach(f3b30, {
    onEnter: function(args) {
        hit++;
        if (hit > 50) return;
        send("=== #" + hit + " ===");
        for (var i = 0; i < 4; i++) {
            try {
                var v = args[i];
                if (!v) { send("  a" + i + "=null"); continue; }
                send("  a" + i + "=" + v.toString());

                // Read as pointer and try string
                try {
                    var p2 = v.readPointer();
                    if (p2) {
                        var s2 = p2.readUtf8String();
                        if (s2 && s2.length > 2) {
                            send("    *a" + i + " = \"" + s2.substring(0, 80) + "\"");
                        }
                    }
                } catch(e) {}

                // Read as u64 (could be count/size)
                try {
                    var u = v.readU64();
                    if (u > 0 && u < 1000000) {
                        send("    u64=" + u);
                    }
                } catch(e) {}

                // Read as u32
                try {
                    var u32 = v.readU32();
                    if (u32 > 0 && u32 < 1000000 && u32 !== u) {
                        send("    u32=" + u32);
                    }
                } catch(e) {}
            } catch(e) {}
        }
    }
});

// Also track SvrId strings being passed
// Search for "SvrId" in memory references
send("Ready");
'''

script = session.create_script(js)
script.on('message', lambda msg,d: print(msg['payload'], flush=True) if msg['type']=='send' else None)
script.load()

print(f"PID={PID} - 等待 GetMessageListBySvrIds 被调用...", flush=True)
print("翻页 / 搜索 / 切换会话", flush=True)

# Also start pymem scanning periodically for large containers
import pymem, struct
pm = pymem.Pymem()
pm.open_process_from_id(PID)

try:
    for i in range(30):
        time.sleep(2)
except:
    pass

session.detach()
print("Done.", flush=True)
