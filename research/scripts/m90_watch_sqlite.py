"""
M90 — 只监视 SQLite 页面上的测试字符串
发送消息后，翻聊天记录触发页面加载
"""
import pymem, psutil, struct, time, os
from datetime import datetime

MSG = b'M90_ONLY_ONCE_A7D29F4B'
OUTDIR = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m90'
os.makedirs(OUTDIR, exist_ok=True)

print("=" * 60)
print("M90 — SQLite 页面监控")
print("=" * 60)
print("\n先在微信发送消息：M90_ONLY_ONCE_A7D29F4B")
print("发送完后，打开那个聊天窗口，上下翻历史记录")
print("监控会自动检测 SQLite 页面上的消息...\n")

time.sleep(5)

start = time.time()
found = False

while time.time() - start < 120 and not found:
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] != 'Weixin.exe':
            continue
        pid = proc.info['pid']
        try:
            pm = pymem.Pymem(pid)
            import pymem.memory

            # Search all heap regions for "SQLite format 3"
            # When found, check if the test string is near it
            base = 0x15a000000000
            end = 0x15e000000000

            while base < end:
                try:
                    mbi = pymem.memory.virtual_query(pm.process_handle, base)
                    if mbi.State == 0x1000 and mbi.RegionSize <= 65536 and mbi.Protect == 0x04:
                        try:
                            d = pm.read_bytes(base, 16)
                        except:
                            base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
                            continue

                        # Check for SQLite page
                        if d[0] == 0x0d:  # Leaf table page
                            # Read full page
                            pg = pm.read_bytes(base, 4096)

                            # Check if test string is in or near this page
                            for off in range(0, 4096):
                                if pg[off:off+len(MSG)] == MSG:
                                    print(f"\n>>> FOUND on SQLite leaf page at 0x{base:x} PID {pid}!")
                                    print(f"    String at page offset +0x{off:x}")

                                    # Save page
                                    import hashlib
                                    fname = f'sqlite_leaf_0x{base:x}_{pid}.bin'
                                    open(os.path.join(OUTDIR, fname), 'wb').write(pg)
                                    print(f"    Saved: {fname}")

                                    # Parse cell structure
                                    cell_count = struct.unpack('>H', pg[3:5])[0]
                                    print(f"    Cells: {cell_count}")

                                    # Find the cell containing our string
                                    for cell_idx in range(cell_count):
                                        cell_off = struct.unpack('>H', pg[8+cell_idx*2:10+cell_idx*2])[0]
                                        if cell_off <= off < cell_off + 500:
                                            print(f"    Cell {cell_idx} at offset 0x{cell_off:x} contains the string")
                                            # Parse cell: payload_len(varint), rowid(varint), payload
                                            pos = cell_off
                                            # payload_len
                                            pl = 0
                                            while True:
                                                b = pg[pos]
                                                pl = (pl << 7) | (b & 0x7f)
                                                pos += 1
                                                if not (b & 0x80):
                                                    break
                                            # rowid
                                            rid = 0
                                            while True:
                                                b = pg[pos]
                                                rid = (rid << 7) | (b & 0x7f)
                                                pos += 1
                                                if not (b & 0x80):
                                                    break
                                            print(f"    Payload len: {pl}, RowID: {rid}")
                                            print(f"    Payload starts at +0x{pos:x}")

                                            # Dump payload
                                            payload = pg[pos:pos+min(pl, 300)]
                                            text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in payload[:200])
                                            print(f"    Payload text: {text[:150]}")
                                            break

                                    found = True
                                    pm.close_process()
                                    break

                            if found:
                                break

                    base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
                except:
                    base += 0x10000

            pm.close_process()
        except:
            pass

    if not found:
        elapsed = int(time.time() - start)
        print(f"  Scanning... {elapsed}s", end='\r')
        time.sleep(2)

if found:
    print(f"\n>>> CAPTURE SUCCESSFUL <<<")
else:
    print(f"\nNot found in SQLite pages. Try scrolling more history.")
