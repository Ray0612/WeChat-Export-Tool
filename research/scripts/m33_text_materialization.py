"""
M33 — Find where garbled data becomes real text
Hook FUN_1816c2a20 downstream functions, search for readable content
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

outfile = r'C:\Users\OK\Desktop\wechat_v4_export\m33_text.jsonl'
os.makedirs(os.path.dirname(outfile), exist_ok=True)

# Downstream functions after FUN_1816c2a20 in the call chain
DOWNSTREAM = [
    (0x016c4100, "FUN_1816c4100"),
    (0x016c4230, "FUN_1816c4230"),
    (0x016c44d0, "FUN_1816c44d0"),
    (0x016c4630, "FUN_1816c4630"),
    (0x016c2b30, "FUN_1816c2b30"),
]

# Build hook JS
hooks_js = ""
for offset, name in DOWNSTREAM:
    hooks_js += f'''
try {{
    Interceptor.attach(mod.base.add({hex(offset)}), {{
        onEnter: function(args) {{
            for (var ai = 0; ai < 4; ai++) {{
                if (!args[ai]) continue;
                try {{
                    // Try reading as UTF8 string
                    var str = args[ai].readUtf8String();
                    if (str && str.length > 4 && str.length < 500) {{
                        // Check if it's real text (not binary garbage)
                        var printable = 0;
                        for (var ci = 0; ci < str.length && ci < 50; ci++) {{
                            var cc = str.charCodeAt(ci);
                            if ((cc >= 0x20 && cc < 0x7f) || cc >= 0x80) printable++;
                        }}
                        if (printable > str.length * 0.6 && str.length > 4) {{
                            send("TEXT {name} a" + ai + " " + JSON.stringify({{fn:"{name}",arg:ai,text:str.substring(0,200)}}));
                        }}
                    }}
                }} catch(e) {{}}

                // Also try reading as pointer to string
                try {{
                    var ptr = args[ai].readPointer();
                    if (ptr) {{
                        var str2 = ptr.readUtf8String();
                        if (str2 && str2.length > 4 && str2.length < 500) {{
                            var printable2 = 0;
                            for (var ci = 0; ci < str2.length && ci < 50; ci++) {{
                                var cc = str2.charCodeAt(ci);
                                if ((cc >= 0x20 && cc < 0x7f) || cc >= 0x80) printable2++;
                            }}
                            if (printable2 > str2.length * 0.6) {{
                                send("TEXT {name} *a" + ai + " " + JSON.stringify({{fn:"{name}",arg:ai,text:str2.substring(0,200)}}));
                            }}
                        }}
                    }}
                }} catch(e) {{}}
            }}
        }}
    }});
}} catch(e) {{}}
'''

js = '''
var mod = Process.findModuleByName("Weixin.dll");
''' + hooks_js + '''
send("R");
'''

session = frida.attach(PID)
script = session.create_script(js)
results = []

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        if line.startswith('TEXT '):
            parts = line.split(' ', 2)
            if len(parts) == 3:
                results.append(parts[2])
                print(f'  {parts[1]}: {parts[2][:80]}', flush=True)
        elif line != 'R':
            print(line, flush=True)

script.on('message', on_msg)
script.load()

print(f'M33 PID={PID} — PageUp (60s)', flush=True)
time.sleep(60)
session.detach()

# Group by function
from collections import Counter
fn_count = Counter()
for r in results:
    try:
        o = json.loads(r)
        fn_count[o['fn']] += 1
    except:
        pass

print(f'\n=== 结果 ===', flush=True)
print(f'文本出现次数: {len(results)}', flush=True)
print(f'按函数分布:', flush=True)
for fn, cnt in fn_count.most_common():
    print(f'  {fn}: {cnt} 次', flush=True)

with open(outfile, 'w', encoding='utf-8') as f:
    for r in results:
        f.write(r + '\n')
    # Add summary
    f.write(f'\n# 分布\n')
    for fn, cnt in fn_count.most_common():
        f.write(f'# {fn}: {cnt}\n')

print(f'输出: {outfile}', flush=True)
