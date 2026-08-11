import pymem, psutil, struct, time

target_pid = None
for p in sorted(psutil.process_iter(['pid','name']), key=lambda x: x.info['pid']):
    if p.info['name'] != 'Weixin.exe': continue
    try:
        pm = pymem.Pymem()
        pm.open_process_from_id(p.info['pid'])
        try:
            mod = pymem.process.module_from_name(pm.process_handle, 'Weixin.dll')
            if mod:
                target_pid = p.info['pid']
                break
        except:
            pass
        pm.close_process_handle()
    except:
        pass

pm = pymem.Pymem()
pm.open_process_from_id(target_pid)

# Known addresses
aaa_content = 0x1df1c15a24c
bbb_content = 0x1df1c15a21c
ccc_content = 0x1df56f478e0
aaa_table_entry = 0x1df24a26620  # where AAA content ptr is stored
bbb_table_entry = 0x1df24a26640  # where BBB content ptr is stored
table_base = 0x1df24a26600

targets = {
    'AAA_content': aaa_content,
    'BBB_content': bbb_content,
    'CCC_content': ccc_content,
    'AAA_table_entry': aaa_table_entry,
    'BBB_table_entry': bbb_table_entry,
    'Table_base': table_base,
}

# Scan heap for reverse pointers
print('Reverse pointer scan (this takes a minute)...', flush=True)

results = {}
for name, target in targets.items():
    results[name] = []
    base = 0x1df00000000
    scanned_mb = 0
    while base < 0x1df80000000:
        try:
            import pymem.memory
            mbi = pymem.memory.virtual_query(pm.process_handle, base)
            if mbi.State == 0x1000:
                size = min(mbi.RegionSize, 2*1024*1024)
                data = pm.read_bytes(base, size)
                for off in range(0, len(data) - 8, 8):
                    val = struct.unpack_from('<Q', data, off)[0]
                    if val == target:
                        ptr_loc = base + off
                        results[name].append(ptr_loc)
                scanned_mb += len(data)
            base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            base += 0x10000

    r = results[name]
    print(f'{name} (0x{target:x}): {len(r)} refs', flush=True)
    for addr in r[:5]:
        print(f'  <- 0x{addr:x}', flush=True)
        # Read context around this pointer
        try:
            ctx = pm.read_bytes(addr - 8, 0x28)
            # Check for nearby wxid
            wxid_pos = -1
            for ci in range(len(ctx)):
                if ctx[ci:ci+5] == b'wxid_' or ctx[ci:ci+10] == b'filehelper':
                    end = ci
                    while end < len(ctx) and ctx[end] >= 0x20 and ctx[end] < 0x7f:
                        end += 1
                    wxid = ctx[ci:end].decode('ascii', errors='replace')
                    print(f'     wxid nearby: {wxid}', flush=True)
                    break
        except:
            pass

print('\nDone.', flush=True)
