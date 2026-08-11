"""
M91 — 监控 Weixin.exe 内存，捕获翻页时加载的 SQLite 数据页
"""
import pymem, struct, datetime, os, time, json
import pymem.memory

PID = 6312
pm = pymem.Pymem(PID)
outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m91'
os.makedirs(outdir, exist_ok=True)

def find_leaf_pages(known=set()):
    """Scan heap for SQLite leaf table pages (type 0x0D)"""
    new_pages = {}
    base = 0x15a000000000
    end = 0x15c000000000

    while base < end:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, base)
            if mbi.State == 0x1000 and mbi.RegionSize <= 65536 and mbi.Protect == 0x04:
                try:
                    first = pm.read_bytes(base, 1)
                    if first == b'\x0d':
                        data = pm.read_bytes(base, 16)
                        cell_cnt = struct.unpack('>H', data[3:5])[0]
                        if 0 < cell_cnt < 1000:
                            if base not in known:
                                new_pages[base] = cell_cnt
                except:
                    pass
            base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            base += 0x10000
    return new_pages

# Step 1: Baseline
print("M91 — SQLite 页面捕获监控")
print("=" * 60)
print("\nStep 1: Baseline scan for existing leaf pages...")
known_pages = set()

# Do 3 quick scans to establish baseline
for i in range(3):
    pages = find_leaf_pages(known_pages)
    known_pages.update(pages.keys())
    print(f"  Scan {i+1}: {len(pages)} new, {len(known_pages)} total")
    time.sleep(0.5)

# Also check for page 1
try:
    page1_data = pm.read_bytes(0x15b08c852f0, 4)
    if page1_data[:4] == b'SQLi':
        known_pages.add(0x15b08c852f0)
        print(f"  Page 1 confirmed at 0x15b08c852f0")
except:
    pass

print(f"\nBaseline established: {len(known_pages)} pages")
print(f"\nNow scroll UP through chat history in WeChat to load more messages...")
print("Monitoring for 30 seconds...")

# Step 2: Monitor for new pages
all_pages = dict()
for addr in known_pages:
    all_pages[addr] = None  # placeholder

capture_round = 0
start = time.time()
while time.time() - start < 30:
    time.sleep(0.3)
    capture_round += 1

    new_pages = find_leaf_pages(set(all_pages.keys()))

    if new_pages:
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"\n[{ts}] Round {capture_round}: {len(new_pages)} NEW pages loaded!")

        for addr, cell_cnt in sorted(new_pages.items()):
            print(f"  Leaf page at 0x{addr:x}, cells={cell_cnt}")

            # Read and save the page
            page_data = pm.read_bytes(addr, 4096)
            path = os.path.join(outdir, f'leaf_0x{addr:x}.bin')
            open(path, 'wb').write(page_data)

            # Parse cell pointers to get first few messages
            cell_ptrs = []
            for i in range(min(cell_cnt, 10)):
                off = struct.unpack('>H', page_data[8+i*2:10+i*2])[0]
                cell_ptrs.append(off)

            print(f"    First cell pointers: {[hex(p) for p in cell_ptrs[:5]]}")

            # Try to read cell 0 to see the data
            if cell_ptrs:
                try:
                    cell_off = cell_ptrs[0]
                    # Leaf cell: payload_len(varint), rowid(varint), payload
                    pos = cell_off
                    payload_len = 0
                    shift = 0
                    while True:
                        byte = page_data[pos]
                        payload_len = (payload_len << 7) | (byte & 0x7f)
                        pos += 1
                        if not (byte & 0x80):
                            break

                    rowid = 0
                    shift = 0
                    while True:
                        byte = page_data[pos]
                        rowid = (rowid << 7) | (byte & 0x7f)
                        pos += 1
                        if not (byte & 0x80):
                            break

                    print(f"    RowID: {rowid}, Payload offset: {pos}, Payload length: {payload_len}")

                    # Read first 100 bytes of payload to see what's inside
                    payload = page_data[pos:pos+min(payload_len, 200)]
                    # Look for readable text
                    text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in payload[:100])
                    print(f"    Payload preview: {text}")

                except Exception as e:
                    print(f"    Parse error: {e}")

            all_pages[addr] = cell_cnt

        # Save after each capture
        output = {
            'capture_time': datetime.datetime.now().isoformat(),
            'total_pages': len(all_pages),
            'pages': [{'addr': hex(a), 'cells': c} for a, c in sorted(all_pages.items())]
        }
        with open(os.path.join(outdir, 'captured_pages.json'), 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    if capture_round % 20 == 0:
        print(f"  ... monitoring ({int(time.time()-start)}s, {len(all_pages)} total pages)")

print(f"\n{'='*60}")
print(f"Monitor ended. New pages captured: {len(all_pages) - len(known_pages)}")
print(f"Total pages in cache: {len(all_pages)}")
print(f"Pages saved to: {outdir}/")
