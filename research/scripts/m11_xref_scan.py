import struct, os

dll_path = r'D:\Program Files\Tencent\Weixin\4.1.10.29\Weixin.dll'
string_rva = 0x084f4a2f  # RVA of "GetPagedMessages" string

print(f'Loading DLL: {dll_path} ({os.path.getsize(dll_path)/1024/1024:.1f}MB)')

with open(dll_path, 'rb') as f:
    data = f.read()

# Verify string
pos = data.find(b'GetPagedMessages')
if pos >= 0:
    print(f'String found at file offset 0x{pos:08x}')
else:
    print('String NOT found!')
    exit(1)

# Scan for RIP-relative LEA/MOV patterns referencing this string
# In x64 with DLL base 0x180000000:
#   instruction_va = 0x180000000 + file_offset (assuming file == RVA for simplicity)
#   string_va = 0x180000000 + string_rva
#   rip_offset = string_va - (instruction_va + 7)
#   rip_offset = string_rva - (file_offset + 7)

patterns = [
    (bytes([0x48, 0x8d, 0x0d]), 'lea rcx, [rip+'),
    (bytes([0x48, 0x8d, 0x15]), 'lea rdx, [rip+'),
    (bytes([0x48, 0x8d, 0x05]), 'lea rax, [rip+'),
    (bytes([0x4c, 0x8d, 0x05]), 'lea r8,  [rip+'),
    (bytes([0x4c, 0x8d, 0x0d]), 'lea r9,  [rip+'),
    (bytes([0x4c, 0x8d, 0x15]), 'lea r10, [rip+'),
    (bytes([0x4c, 0x8d, 0x1d]), 'lea r11, [rip+'),
    (bytes([0x48, 0x8b, 0x05]), 'mov rax, [rip+'),
    (bytes([0x48, 0x8b, 0x0d]), 'mov rcx, [rip+'),
    (bytes([0x48, 0x8b, 0x15]), 'mov rdx, [rip+'),
    (bytes([0x48, 0x8b, 0x1d]), 'mov rbx, [rip+'),
]

xrefs = []
for mask, desc in patterns:
    search_start = 0
    while True:
        off = data.find(mask, search_start)
        if off < 0:
            break
        if off + 7 <= len(data):
            rip_off = struct.unpack_from('<i', data, off + 3)[0]
            target_rva = string_rva
            calc_target = (off + 7) + rip_off
            if calc_target == string_rva or calc_target == string_rva - 0x180000000 or calc_target == pos:
                xrefs.append((off, desc, rip_off))
        search_start = off + 1

print(f'\nXrefs found: {len(xrefs)}')
for off, desc, rip_off in sorted(xrefs):
    print(f'  0x{off:08x}: {desc}{rip_off:+d}]')

# Group into functions
if xrefs:
    xrefs.sort()
    print('\n=== Function grouping (xrefs within 0x200 bytes) ===')
    groups = []
    current_group = [xrefs[0][0]]
    for i in range(1, len(xrefs)):
        if xrefs[i][0] - current_group[-1] < 0x200:
            current_group.append(xrefs[i][0])
        else:
            groups.append(current_group)
            current_group = [xrefs[i][0]]
    groups.append(current_group)

    # Find function start (nearest PUSH RBP before first xref in group)
    print(f'\n=== Candidate Functions ===')
    for g in groups:
        first_xref = g[0]
        # Search backwards for function prologue: 55 48 89 e5 (PUSH RBP; MOV RBP,RSP)
        # or 55 48 8b ec (PUSH RBP; MOV RBP,RSP)
        # or 48 89 5c 24 08 (MOV [RSP+8],RBX) - common modern prologue
        search_start = max(0, first_xref - 0x500)
        search_area = data[search_start:first_xref]

        # Try PUSH RBP (0x55) followed by MOV RBP,RSP
        func_start = -1
        for pi in range(len(search_area) - 1, -1, -1):
            if search_area[pi] == 0x55:
                # Check if this is a function start (preceded by alignment bytes or section start)
                check_addr = search_start + pi
                # Verify: previous bytes should be cc (int3) or 00 (padding) or start of section
                preceding = data[max(0, check_addr-4):check_addr]
                if all(b in [0x00, 0xcc, 0x90] for b in preceding) or check_addr < 16:
                    func_start = check_addr
                    break

        if func_start >= 0:
            print(f'  FUN_0x{func_start:08x} ({len(g)} xrefs)')
            for xoff, desc, _ in [x for x in xrefs if x[0] >= g[0] and x[0] <= g[-1]]:
                print(f'    xref at +0x{xoff - func_start:04x}: {desc}]')
        else:
            print(f'  NO_PROLOGUE_FOUND near 0x{first_xref:08x} ({len(g)} xrefs)')
            for xoff, desc, _ in [x for x in xrefs if x[0] >= g[0] and x[0] <= g[-1]]:
                print(f'    xref at 0x{xoff:08x}: {desc}]')

# Also find "has messages" string and its xrefs
hm_pos = data.find(b'has messages')
if hm_pos >= 0:
    print(f'\n"has messages" at file offset 0x{hm_pos:08x}')
    # Also check "last:" string
    last_pos = data.find(b', last:')
    if last_pos >= 0:
        print(f'", last:" at file offset 0x{last_pos:08x}')

print('\nDone.')
