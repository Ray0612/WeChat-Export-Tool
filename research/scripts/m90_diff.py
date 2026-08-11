"""
M90 — 差分实验
定位真实消息记录页
"""
import pymem, psutil, struct, time, os, json, hashlib
import pymem.memory
from datetime import datetime

OUTDIR = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m90'
os.makedirs(OUTDIR, exist_ok=True)

MSG = b'M90_ONLY_ONCE_A7D29F4B'

# Find Weixin.exe
pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'Weixin.exe':
        pid = proc.info['pid']
        break

pm = pymem.Pymem(pid)
print(f"Weixin.exe PID: {pid}")

# Step 1: Baseline
print(f"\nStep 1: Baseline before sending message")
print(f"Message: {MSG.decode()}")

# Save page 1 if available
for base_check in [0x15b000000000, 0x15b080000000, 0x15b0c0000000]:
    try:
        d = pm.read_bytes(base_check, 16)
        if d[:15] == b'SQLite format 3':
            page1 = pm.read_bytes(base_check, 4096)
            open(os.path.join(OUTDIR, 'page1_before.bin'), 'wb').write(page1)
            print(f"Page 1 found at 0x{base_check:x}")
            page1_addr = base_check
            break
    except:
        pass

# Search for the test string BEFORE sending
try:
    addrs_before = set(pm.pattern_scan_all(MSG, return_multiple=True))
    print(f"Test string occurrences BEFORE: {len(addrs_before)}")
except:
    addrs_before = set()
    print("Test string BEFORE: 0")

# Snapshot SQLite format 3 pages in heap
def find_sqlite_pages(pm, known=set()):
    pages = {}
    base = 0x15a000000000
    end = 0x15c000000000
    while base < end:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, base)
            if mbi.State == 0x1000 and mbi.RegionSize == 4096 and mbi.Protect == 0x04:
                try:
                    first = pm.read_bytes(base, 1)
                    # SQLite page type: 0x0D=leaf, 0x05=interior, 0x02=index, 0x0A=leaf index
                    if first in (b'\x0d', b'\x05', b'\x02', b'\x0a'):
                        pages[base] = first.hex()
                except:
                    pass
            base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            base += 0x10000
    return pages

print("Page types found BEFORE:")
pages_before = find_sqlite_pages(pm)
for addr, ptype in sorted(pages_before.items())[:20]:
    print(f"  0x{addr:x}: type 0x{ptype}")
print(f"  Total: {len(pages_before)} pages")

# Step 2: Wait for user to send the message
print(f"\nStep 2: Send this message NOW in WeChat:")
print(f"  {MSG.decode()}")
print(f"Waiting 30 seconds...")

time.sleep(30)

# Step 3: POST-snapshot
print(f"\nStep 3: Capturing POST state...")

try:
    addrs_after = set(pm.pattern_scan_all(MSG, return_multiple=True))
    print(f"Test string occurrences AFTER: {len(addrs_after)}")
except:
    addrs_after = set()

new_addrs = addrs_after - addrs_before
print(f"NEW occurrences: {len(new_addrs)}")

print("Page types found AFTER:")
pages_after = find_sqlite_pages(pm)
for addr, ptype in sorted(pages_after.items())[:20]:
    print(f"  0x{addr:x}: type 0x{ptype}")
print(f"  Total: {len(pages_after)} pages")

# New pages
new_pages = {a: p for a, p in pages_after.items() if a not in pages_before}
print(f"NEW pages: {len(new_pages)}")
for addr, ptype in sorted(new_pages.items()):
    print(f"  NEW 0x{addr:x}: type 0x{ptype}")

# Step 4: For each occurrence of the test string, analyze surrounding structure
print(f"\nStep 4: Analyzing string occurrences...")
for addr in sorted(new_addrs):
    print(f"\n--- Test string at 0x{addr:x} ---")

    # Read ±512 bytes
    data = pm.read_bytes(addr - 512, 1024)
    str_rel = 512  # offset of string in data

    # Find session tag and seq (from compact structure knowledge)
    # The compact structure: [prefix XX 02 05 09 01 01 04][content][04][2B seq][tag]
    # But we didn't find this prefix in v4.1.10.29, so the format might differ

    # Check if we're on a 4096-aligned page
    page_aligned = (addr // 4096) * 4096
    page_data = pm.read_bytes(page_aligned, 4096)

    # Check if this is a valid SQLite page
    page_type = page_data[0]
    if page_type in (0x0D, 0x05, 0x02, 0x0A, 0x00):
        print(f"  SQLite page type: 0x{page_type:02x}")
        print(f"  Page-aligned address: 0x{page_aligned:x}")

        # Dump page header
        print(f"  Page hex (first 64 bytes):")
        for i in range(0, 64, 16):
            h = ' '.join(f'{b:02x}' for b in page_data[i:i+16])
            a = ''.join(chr(b) if 32 <= b < 127 else '.' for b in page_data[i:i+16])
            print(f"    +{i:04x}: {h}  {a}")

        # Save page
        open(os.path.join(OUTDIR, f'page_0x{page_aligned:x}.bin'), 'wb').write(page_data)
        print(f"  Saved to page_0x{page_aligned:x}.bin")

    # Look for message content fields near the string
    # The Msg_ table has: local_id, server_id, local_type, sort_seq, real_sender_id, create_time, message_content
    # All INTEGER fields should be 4-8 byte values before/after the string

    now = int(datetime.now().timestamp())
    for off in range(0, 1024 - 4, 4):
        v = struct.unpack('<I', data[off:off+4])[0]
        rel = off - str_rel

        # Check for timestamp (around current time)
        if now - 10 < v < now + 10 and abs(rel) < 200:
            try:
                dt = datetime.fromtimestamp(v)
                print(f"  TIMESTAMP at rel {rel:+d}: {dt}")
            except:
                pass

        # Check for message type
        if v in {1, 3, 49, 51, 2000, 2001} and abs(rel) < 100 and off != str_rel:
            type_names = {1:'text', 3:'image', 49:'share', 51:'video', 2000:'transfer', 2001:'redpacket'}
            print(f"  TYPE at rel {rel:+d}: {v} ({type_names[v]})")

        # Check for svrid (large 64-bit values)
        if off % 8 == 0 and off + 8 <= 1024:
            v64 = struct.unpack('<Q', data[off:off+8])[0]
            if 1000000000000000000 < v64 < 20000000000000000000 and abs(rel) < 200:
                print(f"  SVRID at rel {rel:+d}: {v64}")

    # Full hex dump ±128 bytes from string
    print(f"\n  Hex dump ±128 bytes from string:")
    for i in range(-128, 128, 16):
        off = str_rel + i
        if off < 0 or off + 16 > 1024:
            continue
        chunk = data[off:off+16]
        h = ' '.join(f'{b:02x}' for b in chunk)
        a = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        marker = ' <<<' if i == 0 else ''
        print(f"    {i:+5d}: {h}  {a}{marker}")

# Save summary
summary = {
    'before_pages': len(pages_before),
    'after_pages': len(pages_after),
    'new_pages': {hex(a): p for a, p in new_pages.items()},
    'string_occurrences_before': len(addrs_before),
    'string_occurrences_after': len(addrs_after),
    'new_occurrences': len(new_addrs),
}
with open(os.path.join(OUTDIR, 'diff_summary.json'), 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\nDiff summary saved to {OUTDIR}/diff_summary.json")
print("Done")
