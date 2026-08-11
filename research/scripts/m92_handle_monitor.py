"""
M92 — 持久监控：等待并捕获 sqlite3* handle
持续扫描 WeChatAppEx，一旦 handle 出现就捕获
"""
import pymem, psutil, struct, time, os, json
import pymem.memory

MONITOR_SECONDS = 600  # 10 minutes max
LOG_FILE = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m92\handle_log.txt'
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def find_flue(pid):
    """Find flue.dll base in a WeChatAppEx process"""
    try:
        pm = pymem.Pymem(pid)
        for mod in pm.list_modules():
            if 'flue.dll' in mod.name.lower():
                pm.close_process()
                return mod.lpBaseOfDll
        pm.close_process()
    except:
        pass
    return None

def check_handle(candidate, main_addr, pm, name=""):
    """Verify if a candidate is a valid sqlite3 handle"""
    try:
        # Check +0x00: should be small or null (nDb, flags)
        # Check +0x20: should point to main_addr (aDb[0].zDbName)
        aDb_ptr = struct.unpack('<Q', pm.read_bytes(candidate + 0x20, 8))[0]
        if aDb_ptr < 0x100000:
            return False
        zName = struct.unpack('<Q', pm.read_bytes(aDb_ptr, 8))[0]
        if zName == main_addr:
            # Found! Verify pBt
            pBt = struct.unpack('<Q', pm.read_bytes(aDb_ptr + 8, 8))[0]
            if pBt > 0x100000:
                log(f">>> HANDLE FOUND {name} at 0x{candidate:x}")
                log(f"    aDb at 0x{aDb_ptr:x}, zDbName='main', pBt=0x{pBt:x}")
                # Dump handle header
                data = pm.read_bytes(candidate, 128)
                for i in range(0, 128, 16):
                    h = ' '.join(f'{b:02x}' for b in data[i:i+16])
                    a = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
                    log(f"    +{i:03x}: {h}  {a}")

                # Try to get page count
                try:
                    bt_shared = struct.unpack('<Q', pm.read_bytes(pBt + 8, 8))[0]
                    pPager = struct.unpack('<Q', pm.read_bytes(bt_shared, 8))[0]
                    pgcount = struct.unpack('<I', pm.read_bytes(pPager + 0x38, 4))[0]
                    log(f"    pPager=0x{pPager:x}, page_count={pgcount}")
                except:
                    pass
                return True
    except:
        pass
    return False

log("=" * 60)
log("M92 — Handle Monitor Started")
log("=" * 60)

start_time = time.time()
found = False
checked_pids = set()

while time.time() - start_time < MONITOR_SECONDS and not found:
    # Step 1: Find all WeChatAppEx processes
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        name = proc.info['name'] or ''
        exe = proc.info.get('exe', '') or ''
        if 'wechatappex' in name.lower():
            pid = proc.info['pid']
            if pid in checked_pids:
                continue
            checked_pids.add(pid)

            flue_base = find_flue(pid)
            if not flue_base:
                continue

            log(f"Checking WeChatAppEx PID {pid}, flue=0x{flue_base:x}")

            try:
                pm = pymem.Pymem(pid)

                # The "main" string in flue.dll's .rdata
                # .rdata VA = 0xa8ed000. "main" was found at VA + offset
                # Search for it fresh in case addresses differ
                rdata_va = flue_base + 0xa8ed000
                rdata_size = 0x19c9eb8

                main_addr = None
                # Search for "main" string in .rdata
                for off in range(0, rdata_size, 4096):
                    try:
                        chunk = pm.read_bytes(rdata_va + off, min(4096, rdata_size - off))
                        pos = chunk.find(b'main\x00')
                        if pos >= 0:
                            main_addr = rdata_va + off + pos
                            log(f"  'main' at 0x{main_addr:x}")
                            break
                    except:
                        continue

                if not main_addr:
                    pm.close_process()
                    continue

                # Strategy A: Search .data section for pointers to "main"
                data_va = flue_base + 0xc2b7000
                data_size = 0x491df0
                log(f"  Scanning .data section for 'main' refs...")

                try:
                    data_chunk = pm.read_bytes(data_va, data_size)

                    # Search for QWORD = main_addr
                    main_packed = struct.pack('<Q', main_addr)
                    for off in range(0, data_size - 8, 8):
                        if data_chunk[off:off+8] == main_packed:
                            abs_addr = data_va + off
                            log(f"  'main' pointer in .data at 0x{abs_addr:x}")
                            # Trace back to find handle (aDb is at abs_addr)
                            aDb_addr = abs_addr
                            # Try different handle offsets (handle + 0x20 = aDb)
                            for delta in [0x20, 0x28, 0x18, 0x30]:
                                h_cand = aDb_addr - delta
                                if check_handle(h_cand, main_addr, pm, f".data+0x{delta:x}"):
                                    found = True
                                    break
                except Exception as e:
                    log(f"  .data scan error: {e}")

                # Strategy B: Search heap for the page count 24410 near "main"
                if not found:
                    log(f"  Scanning heap for handle...")
                    heap_base = 0x100000
                    while heap_base < 0x7fffffffffff and not found:
                        try:
                            mbi = pymem.memory.virtual_query(pm.process_handle, heap_base)
                            if mbi.State == 0x1000 and mbi.RegionSize <= 65536:
                                try:
                                    chunk = pm.read_bytes(heap_base, min(mbi.RegionSize, 65536))
                                    for off in range(0, len(chunk)-8, 8):
                                        if struct.unpack('<Q', chunk[off:off+8])[0] == main_addr:
                                            abs_addr = heap_base + off
                                            for delta in [0x20, 0x28, 0x18, 0x30]:
                                                h_cand = abs_addr - delta
                                                if check_handle(h_cand, main_addr, pm, f"heap+0x{delta:x}"):
                                                    found = True
                                                    break
                                except:
                                    pass
                            heap_base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
                        except:
                            heap_base += 0x10000

                pm.close_process()

            except Exception as e:
                log(f"  PID {pid} error: {e}")

    if not found:
        time.sleep(3)

if found:
    log(f"\n>>> HANDLE CAPTURED SUCCESSFULLY <<<")
else:
    log(f"\nNo handle found after {MONITOR_SECONDS}s monitoring")
    log(f"Checked PIDs: {list(checked_pids)}")

log("Done")
