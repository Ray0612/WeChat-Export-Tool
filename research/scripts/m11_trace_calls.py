import frida, psutil, time, os, struct

PID = 17484
outfile = r'C:\Users\OK\Desktop\m11_traced.txt'
open(outfile, 'w').close()

# Hook every function entry (PUSH RBP = 0x55) in a range around the xref
# We'll search the DLL first to find all PUSH RBP locations
dll_path = r'D:\Program Files\Tencent\Weixin\4.1.10.29\Weixin.dll'
with open(dll_path, 'rb') as f:
    dll_data = f.read()

# Find all function prologues in the range around xref
xref_area = 0x016f0000
search_size = 0x20000  # 128KB around xref

# Also search around old function offset
old_func_area = 0x016ade70
old_search_size = 0x2000

all_funcs = set()
for area, sz in [(xref_area, search_size), (old_func_area, old_search_size)]:
    start = area
    for i in range(start, start + sz):
        if dll_data[i] == 0x55 and i + 4 < len(dll_data):
            # Verify it's a function prologue (55 48 89 e5 or 55 48 8b ec or 55 53 48 83 ec...)
            next_bytes = dll_data[i+1:i+4]
            if next_bytes[0] in [0x48, 0x53, 0x41, 0x56, 0x57]:
                all_funcs.add(i)

all_funcs = sorted(all_funcs)
print(f"Found {len(all_funcs)} candidate functions in search range")

# Generate Frida hook script that hooks all these functions
hook_code = ""
for f in all_funcs:
    hook_code += f"""
    try {{
        Interceptor.attach(base.add(0x{f:08x}), {{
            onEnter: function() {{ send('CALL 0x{f:08x}'); }}
        }});
    }} catch(e) {{}}
"""

jscode = f'''
'use strict';

var base = Process.findModuleByName('Weixin.dll').base;
send('base=' + base.toString());

{hook_code}

send('HOOKS_INSTALLED count={len(all_funcs)}');
'''

session = frida.attach(PID)
script = session.create_script(jscode)

counts = {}

def on_msg(msg, d):
    if msg['type'] == 'send':
        payload = msg['payload']
        if payload.startswith('CALL '):
            func = int(payload.split()[1], 16)
            counts[func] = counts.get(func, 0) + 1
            with open(outfile, 'a') as f:
                f.write(f'{func:08x} {counts[func]}\n')
        else:
            print(payload)

script.on('message', on_msg)
script.load()

print(f'Tracking {len(all_funcs)} functions...')
print('Press PageUp in WeChat, then press Ctrl+C')
print('(will auto-stop after 60s)')

try:
    time.sleep(60)
except:
    pass
session.detach()

# Report results
if counts:
    print(f'\n=== Functions called during paging ({len(counts)} unique) ===')
    sorted_funcs = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    for func, count in sorted_funcs[:20]:
        print(f'  0x{func:08x}: {count} calls')
else:
    print('\nNo functions were called in the search range during paging')
PYEOF