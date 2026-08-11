import frida, psutil, time, os, struct

# Step 1: Find current PID with Weixin.dll
PID = None
for p in sorted(psutil.process_iter(['pid','name','create_time']), key=lambda x: x.info['create_time']):
    if p.info['name'] != 'Weixin.exe': continue
    pid = p.info['pid']
    try:
        session = frida.attach(pid)
        script = session.create_script("send(Process.findModuleByName('Weixin.dll') ? 'yes' : 'no');")
        r = []
        def m(msg,d):
            if msg['type']=='send': r.append(msg['payload'])
        script.on('message', m)
        script.load()
        time.sleep(0.2)
        session.detach()
        if r and r[0] == 'yes':
            PID = pid
            print(f'Target PID: {PID} (has Weixin.dll)')
            break
    except:
        pass

if not PID:
    print('No Weixin.exe with Weixin.dll found')
    exit(1)

outfile = r'C:\Users\OK\Desktop\m12_bline.txt'
open(outfile, 'w').close()

# Step 2: Hook GetPagedMessages function by its old behavior pattern
# We know GetPagedMessages should read PagingContext+0x28 and +0x30
# Let's search for functions that use these offsets in their code

# Read the DLL to find code patterns referencing +0x28 and +0x30
dll_path = r'D:\Program Files\Tencent\Weixin\4.1.10.29\Weixin.dll'
with open(dll_path, 'rb') as f:
    dll_data = f.read()

# In x64, offsets like 0x28 and 0x30 appear as:
# [rbp+0x28] -> 48 63 45 28 or 48 8b 45 28 or 48 89 45 28 etc
# [rbp+0x30] -> 48 63 45 30 or 48 8b 45 30 etc
# Also common: lea rcx, [rbp+0x28] or mov rax, [rbx+0x28] etc

# Search for instructions that operate on +0x28 and +0x30 offsets
# Common patterns:
# 48 8b 45 28 = mov rax, [rbp+0x28]  (read)
# 48 89 45 28 = mov [rbp+0x28], rax  (write)
# 48 8b 4d 28 = mov rcx, [rbp+0x28]  (read to rcx)
# 48 8b 55 30 = mov rdx, [rbp+0x30]  (read to rdx)
# 48 8b 43 28 = mov rax, [rbx+0x28]  (read using rbx)
# Also with other base registers

# Search in .text section
text_raw_off = 0x400  # from section info earlier
text_va = 0x1000
text_size = 0x689df4c
text_data = dll_data[text_raw_off:text_raw_off + min(text_size, len(dll_data)-text_raw_off)]

# Patterns that suggest accessing +0x28 and +0x30
# We want code that accesses BOTH offsets within a small range (likely same function)
patterns_28 = [
    bytes([0x8b, 0x45, 0x28]),  # mov eax, [rbp+0x28]
    bytes([0x8b, 0x4d, 0x28]),  # mov ecx, [rbp+0x28]
    bytes([0x8b, 0x55, 0x28]),  # mov edx, [rbp+0x28]
    bytes([0x89, 0x45, 0x28]),  # mov [rbp+0x28], eax
    bytes([0x8b, 0x43, 0x28]),  # mov eax, [rbx+0x28]
    bytes([0x8b, 0x4b, 0x28]),  # mov ecx, [rbx+0x28]
    bytes([0x89, 0x43, 0x28]),  # mov [rbx+0x28], eax
    bytes([0x8b, 0x40, 0x28]),  # mov eax, [rax+0x28]
]

patterns_30 = [
    bytes([0x8b, 0x45, 0x30]),
    bytes([0x8b, 0x4d, 0x30]),
    bytes([0x8b, 0x55, 0x30]),
    bytes([0x89, 0x45, 0x30]),
    bytes([0x8b, 0x43, 0x30]),
    bytes([0x8b, 0x4b, 0x30]),
    bytes([0x89, 0x43, 0x30]),
    bytes([0x8b, 0x40, 0x30]),
]

# Find all locations with +0x28 and +0x30 patterns
locs_28 = []
locs_30 = []

for pat in patterns_28:
    pos = -1
    while True:
        pos = text_data.find(pat, pos+1)
        if pos < 0: break
        locs_28.append(text_va + pos)

for pat in patterns_30:
    pos = -1
    while True:
        pos = text_data.find(pat, pos+1)
        if pos < 0: break
        locs_30.append(text_va + pos)

print(f'Locations referencing +0x28: {len(locs_28)}')
print(f'Locations referencing +0x30: {len(locs_30)}')

# Find functions that use BOTH offsets within 0x100 bytes (same function body)
locs_28_set = set(locs_28)
locs_30_set = set(locs_30)

both = []
for loc in locs_28:
    # Check if there's a +0x30 reference within 0x100 bytes
    nearby_30 = [x for x in locs_30 if abs(x - loc) < 0x100]
    if nearby_30:
        both.append((loc, min(nearby_30)))

print(f'\nLocations with BOTH +0x28 and +0x30 references within 0x100 bytes: {len(both)}')

# Group into functions (find PUSH RBP before each pair)
functions_found = []
for loc_28, loc_30 in both[:50]:  # Check top 50
    search_start = max(0, loc_28 - 0x500)
    search_end = loc_28
    # Search backwards for function prologue in the file data
    for off in range(search_end, search_start, -1):
        file_off = off - text_va + text_raw_off
        if file_off < 0 or file_off + 4 >= len(dll_data): continue
        if dll_data[file_off] == 0x55:  # PUSH RBP
            if dll_data[file_off+1] in [0x48, 0x53, 0x41, 0x56, 0x57]:
                func_rva = off
                if func_rva not in functions_found:
                    functions_found.append(func_rva)
                break

print(f'\nCandidate functions (use both +0x28 and +0x30): {len(functions_found)}')
for f in functions_found[:20]:
    # Count how many 0x28 and 0x30 references within 0x1000 of this function
    cnt_28 = sum(1 for x in locs_28 if abs(x - f) < 0x1000)
    cnt_30 = sum(1 for x in locs_30 if abs(x - f) < 0x1000)
    print(f'  FUN_0x{f:08x} (+0x28 refs={cnt_28}, +0x30 refs={cnt_30})')

# Save to file
with open(outfile, 'w', encoding='utf-8') as f:
    f.write('B-Line: PagingContext Consumer Analysis (DLL 4.1.10.29)\n')
    f.write(f'Total +0x28 refs: {len(locs_28)}, +0x30 refs: {len(locs_30)}\n')
    f.write(f'Functions with both offsets: {len(functions_found)}\n\n')
    for func in functions_found[:30]:
        cnt_28 = sum(1 for x in locs_28 if abs(x - func) < 0x1000)
        cnt_30 = sum(1 for x in locs_30 if abs(x - func) < 0x1000)
        f.write(f'FUN_0x{func:08x} +0x28={cnt_28} +0x30={cnt_30}\n')

print(f'\nResults saved to {outfile}')
