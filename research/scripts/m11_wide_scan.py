import frida, psutil, time, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PID = 17484
outfile = r'C:\Users\OK\Desktop\m11_widetrace.txt'
open(outfile, 'w').close()

dll_path = r'D:\Program Files\Tencent\Weixin\4.1.10.29\Weixin.dll'
with open(dll_path, 'rb') as f:
    dll_data = f.read()

# Search for PUSH RBP in key areas of the DLL
# Area 1: 0x01500000 - 0x01a00000 (5MB around old function area)
# Area 2: 0x00000000 - 0x05000000 (first 80MB, where .text usually is)
# But we can't hook ALL functions - too many.
#
# Strategy: Search for "has messages:" string callers too
# and look for functions that use BOTH "GetPagedMessages" and ",last:"

# Let me instead look at the area around the xref + connected functions
# The xref at 0x016feb6f is in some function. Let me look at what it calls.

# Actually, the simplest: hook the OLD offset area more broadly
# and see if anything fires during paging

# Read the actual .text section boundaries from the PE header
import struct

# Parse PE header to find .text section
def get_section_ranges(dll_data):
    # DOS header
    e_lfanew = struct.unpack_from('<I', dll_data, 0x3c)[0]
    # PE header
    if dll_data[e_lfanew:e_lfanew+4] != b'PE\0\0':
        return []

    # File header
    file_header = e_lfanew + 4
    # Size of optional header
    opt_header_size = struct.unpack_from('<H', dll_data, file_header + 16)[0]

    # Section headers start after optional header
    sections_start = file_header + 20 + opt_header_size

    sections = []
    for i in range(96):  # Max sections
        sec_start = sections_start + i * 40
        if sec_start + 40 > len(dll_data):
            break
        name = dll_data[sec_start:sec_start+8].rstrip(b'\0').decode('ascii', errors='replace')
        virt_size = struct.unpack_from('<I', dll_data, sec_start + 8)[0]
        virt_addr = struct.unpack_from('<I', dll_data, sec_start + 12)[0]
        raw_size = struct.unpack_from('<I', dll_data, sec_start + 16)[0]
        raw_addr = struct.unpack_from('<I', dll_data, sec_start + 20)[0]
        charact = struct.unpack_from('<I', dll_data, sec_start + 36)[0]

        # Code section
        is_code = charact & 0x20  # IMAGE_SCN_CNT_CODE
        is_exec = charact & 0x20000000  # IMAGE_SCN_MEM_EXECUTE

        sections.append({
            'name': name,
            'virt_addr': virt_addr,
            'virt_size': virt_size,
            'raw_addr': raw_addr,
            'raw_size': raw_size,
            'is_code': bool(is_code),
            'is_exec': bool(is_exec),
        })

    return sections

sections = get_section_ranges(dll_data)
print("DLL Sections:")
for s in sections:
    name_clean = s['name'].replace('�', '?')
    print(f"  {name_clean:>8} VA=0x{s['virt_addr']:08x} Size=0x{s['virt_size']:x} "
          f"Raw=0x{s['raw_addr']:08x} Code={s['is_code']} Exec={s['is_exec']}")

# Find .text section
text_section = None
for s in sections:
    if s['is_code'] or s['name'] in ['.text', 'PAGE', 'CODE']:
        text_section = s
        break

if text_section:
    text_start = text_section['virt_addr']
    text_end = text_section['virt_addr'] + text_section['virt_size']
    print(f"\n.text section: 0x{text_start:08x} - 0x{text_end:08x} "
          f"({(text_end-text_start)/1024/1024:.1f}MB)")

    # Scan for PUSH RBP in .text
    raw_start = text_section['raw_addr']
    raw_end = min(raw_start + text_section['raw_size'], len(dll_data))
    text_data = dll_data[raw_start:raw_end]

    funcs = []
    for i in range(len(text_data)):
        if text_data[i] == 0x55:
            # Check next byte for valid prologue continuation
            if i + 1 < len(text_data) and text_data[i+1] in [0x48, 0x53, 0x41, 0x56, 0x57]:
                func_rva = text_start + i
                funcs.append(func_rva)

    print(f"Functions in .text: {len(funcs)}")

    # Sample evenly: pick functions at regular intervals to reduce count
    # We want to test ~2000 functions max for performance
    max_hooks = 2000
    step = max(1, len(funcs) // max_hooks)
    sampled_funcs = funcs[::step]
    print(f"Sampled {len(sampled_funcs)} functions for hooking (step={step})")

    # Generate hook script
    hooks = []
    for f in sampled_funcs:
        hooks.append(f"0x{f:08x}")

    hooks_js = '\n'.join([f"try {{ Interceptor.attach(base.add({h}), {{ onEnter: function() {{ send('HIT {h}'); }} }}); }} catch(e) {{}}" for h in hooks])

    jscode = f'''
    'use strict';
    var base = Process.findModuleByName('Weixin.dll').base;
    {hooks_js}
    send('HOOKED {len(hooks)}');
    '''

    session = frida.attach(PID)
    script = session.create_script(jscode)

    hit_funcs = {}

    def on_msg(msg, d):
        if msg['type'] == 'send':
            payload = msg['payload']
            if payload.startswith('HIT '):
                func = payload.split()[1]
                hit_funcs[func] = hit_funcs.get(func, 0) + 1
                with open(outfile, 'a') as f:
                    f.write(f'{func} {hit_funcs[func]}\n')
            else:
                print(payload)

    script.on('message', on_msg)
    script.load()

    print(f'\nHooking {len(hooks)} functions across .text section...')
    print('Press PageUp 3-5 times')

    try:
        time.sleep(30)
    except:
        pass

    session.detach()

    if hit_funcs:
        print(f'\n=== Functions called during paging ({len(hit_funcs)} unique) ===')
        sorted_hits = sorted(hit_funcs.items(), key=lambda x: x[1], reverse=True)
        for func, count in sorted_hits[:30]:
            print(f'  0x{func}: {count}x')
    else:
        print('\nNo functions called in sampled set during paging')
        print('The paging function may not start with PUSH RBP,')
        print('or the .text section could be in a different area')
else:
    print("Could not find .text section")
