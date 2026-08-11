"""
M90 — 监听 Weixin.exe，等测试消息出现时抓取页面
你先发消息，监控自动检测
"""
import pymem, psutil, struct, time, os, json
from datetime import datetime

MSG = b'M90_ONLY_ONCE_A7D29F4B'
OUTDIR = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m90'
os.makedirs(OUTDIR, exist_ok=True)

print("=" * 60)
print("M90 — 监控等待测试消息")
print("=" * 60)
print(f"\n先在微信里发送这条消息（现在就可以发）：")
print(f"  {MSG.decode()}")
print(f"\n然后等 5 秒后监控会自动检测到...")
print()

time.sleep(5)

# Monitor all Weixin.exe processes
found = False
start = time.time()

while time.time() - start < 120 and not found:
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == 'Weixin.exe':
            pid = proc.info['pid']
            try:
                pm = pymem.Pymem(pid)
                addrs = pm.pattern_scan_all(MSG, return_multiple=True)
                if addrs:
                    print(f"\n>>> FOUND in PID {pid} at {datetime.now().strftime('%H:%M:%S')}")
                    print(f"    {len(addrs)} occurrence(s)")

                    for addr in addrs[:10]:
                        # Determine what page this is on
                        page_addr = (addr // 4096) * 4096
                        page_data = pm.read_bytes(page_addr, 4096)

                        # Check if this is a SQLite page
                        is_sqlite = page_data[:15] == b'SQLite format 3'
                        page_type = page_data[0]

                        print(f"\n--- Address: 0x{addr:x} ---")
                        print(f"    Page base: 0x{page_addr:x}")
                        print(f"    Page type: 0x{page_type:02x} {'(SQLite header)' if is_sqlite else ''}")
                        print(f"    Relative position in page: +0x{addr - page_addr:x}")

                        # Search for create_time, local_type, server_id nearby
                        now = int(datetime.now().timestamp())
                        data = pm.read_bytes(page_addr, 4096)
                        str_rel = addr - page_addr

                        for off in range(0, 4096 - 4, 4):
                            v = struct.unpack('<I', data[off:off+4])[0]
                            rel = off - str_rel

                            if now - 10 < v < now + 10 and abs(rel) < 500:
                                try:
                                    print(f"    TIMESTAMP at rel {rel:+d} (off +0x{off:x}): {datetime.fromtimestamp(v)}")
                                except:
                                    pass

                            if v in {1, 3, 49, 51} and abs(rel) < 200 and off != str_rel:
                                tn = {1:'text', 3:'image', 49:'share', 51:'video'}[v]
                                print(f"    local_type at rel {rel:+d} (off +0x{off:x}): {v} ({tn})")

                        # Save page
                        tag = 'sqlite' if is_sqlite else 'heap'
                        fname = f'page_{tag}_0x{page_addr:x}_{pid}.bin'
                        open(os.path.join(OUTDIR, fname), 'wb').write(page_data)
                        print(f"    Saved: {fname}")

                    found = True
                    pm.close_process()
                    break
                pm.close_process()
            except:
                pass

    if not found:
        print(f"  ... {int(time.time()-start)}s, scanning all Weixin.exe PIDs...", end='\r')
        time.sleep(2)

if found:
    print(f"\n>>> M90 CAPTURE COMPLETE <<<")
else:
    print(f"\nNot found after 120s. Did you send the message?")
