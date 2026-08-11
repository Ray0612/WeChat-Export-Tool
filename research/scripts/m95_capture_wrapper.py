"""
M95 — 重启微信后捕获 0x2f8 包装对象 → 提取 sqlite3 handle
"""
import pymem, psutil, struct, time, os, sys
import pymem.memory

outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m95'
os.makedirs(outdir, exist_ok=True)

print("=" * 60)
print("M95 — 重启微信后捕获包装对象")
print("=" * 60)
print("\n1. 请完全退出微信")
print("2. 重新打开微信并登录")
print("3. 登录成功后告诉我")
print("\n监控将在你说"好了"后启动...")

input("按 Enter 继续...")

print("\n监控 WeChatAppEx 启动...")

found = False
for attempt in range(300):  # 5 minutes max
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        name = proc.info['name'] or ''
        exe = proc.info.get('exe', '') or ''
        if 'wechatappex' in name.lower() and 'xwechat' in exe.lower():
            pid = proc.info['pid']
            try:
                pm = pymem.Pymem(pid)

                # Find flue.dll
                flue_base = None
                for mod in pm.list_modules():
                    if 'flue.dll' in mod.name.lower():
                        flue_base = mod.lpBaseOfDll
                        break

                if not flue_base:
                    pm.close_process()
                    continue

                # Search heap for the wrapper pattern
                base = 0x100000
                while base < 0x7fffffffffff:
                    try:
                        mbi = pymem.memory.virtual_query(pm.process_handle, base)
                        if mbi.State == 0x1000 and mbi.RegionSize <= 65536 and mbi.Protect == 0x04:
                            try:
                                chunk = pm.read_bytes(base, min(mbi.RegionSize, 65536))
                                for off in range(8, len(chunk) - 0xb8, 8):
                                    # Check +0x28 = 2, +0x65 = 1, +0x6a = 0xff, +0x71 = 'm'
                                    if off + 0x72 > len(chunk):
                                        continue

                                    if not (chunk[off+0x28:off+0x2c] == b'\x02\x00\x00\x00'):
                                        continue
                                    if not (chunk[off+0x65] == 1):
                                        continue
                                    if not (chunk[off+0x6a] == 0xff):
                                        continue
                                    if not (chunk[off+0x71] == 0x6d):
                                        continue

                                    wrapper_addr = base + off

                                    # Verify +0xa8 = 0x7ffe0000c350
                                    try:
                                        a8_val = struct.unpack('<Q', pm.read_bytes(wrapper_addr + 0xa8, 8))[0]
                                        if a8_val != 0x7ffe0000c350:
                                            continue
                                    except:
                                        continue

                                    # Read handle at +0x58
                                    handle = struct.unpack('<Q', pm.read_bytes(wrapper_addr + 0x58, 8))[0]

                                    print(f"\n>>> WRAPPER FOUND at 0x{wrapper_addr:x}!")
                                    print(f"    PID: {pid}")
                                    print(f"    flue.dll: 0x{flue_base:x}")
                                    print(f"    Handle at +0x58: 0x{handle:x}")

                                    # Verify the handle has aDb[0].zDbName = "main"
                                    try:
                                        aDb = struct.unpack('<Q', pm.read_bytes(handle + 0x20, 8))[0]
                                        zName = struct.unpack('<Q', pm.read_bytes(aDb, 8))[0]
                                        name_bytes = pm.read_bytes(zName, 8)
                                        if b'main' in name_bytes:
                                            print(f"\n    >>> VERIFIED: sqlite3 handle = 0x{handle:x} <<<")
                                            print(f"    aDb[0].zDbName = 'main'")
                                            print(f"    aDb[0].pBt = 0x{struct.unpack('<Q', pm.read_bytes(aDb+8, 8))[0]:x}")

                                            with open(os.path.join(outdir, 'handle_addr.txt'), 'w') as f:
                                                f.write(f"PID: {pid}\nflue_base: 0x{flue_base:x}\nwrapper: 0x{wrapper_addr:x}\nhandle: 0x{handle:x}\n")

                                            found = True
                                            break
                                    except Exception as e:
                                        print(f"    Handle verification failed: {e}")
                            except:
                                pass
                        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
                    except:
                        base += 0x10000

                pm.close_process()
            except:
                pass

            if found:
                break
    if found:
        break

    if attempt % 10 == 0:
        print(f"  waiting... ({attempt*2}s)", end='\r')
    time.sleep(2)

if found:
    print(f"\n>>> HANDLE CAPTURED SUCCESSFULLY <<<")
else:
    print(f"\nWrapper not found after 5 minutes")
