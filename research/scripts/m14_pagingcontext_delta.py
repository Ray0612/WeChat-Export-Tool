import frida, psutil, time, os, re

PID = None
for p in sorted(psutil.process_iter(['pid','name']), key=lambda x: x.info['pid']):
    if p.info['name'] != 'Weixin.exe': continue
    try:
        sess = frida.attach(p.info['pid'])
        sc = sess.create_script("send(Process.findModuleByName('Weixin.dll')?'yes':'no');")
        r=[]
        def m(msg,d):
            if msg['type']=='send': r.append(msg['payload'])
        sc.on('message', m)
        sc.load()
        time.sleep(0.2)
        sess.detach()
        if r and r[0]=='yes':
            PID = p.info['pid']
            break
    except: pass

if not PID:
    print("No Weixin.exe with Weixin.dll found")
    exit(1)

outfile = r'C:\Users\OK\Desktop\m14_delta.txt'
dump_dir = r'C:\Users\OK\Desktop\m14_dumps'
os.makedirs(dump_dir, exist_ok=True)
open(outfile, 'w').close()

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
var caller1Addr = mod.base.add(0x01683b08);
var hitCount = 0;

Interceptor.attach(caller1Addr, {
    onEnter: function(args) {
        hitCount++;
        this.hitNum = hitCount;
        this.arg2 = args[2];  // PagingContext
        this.arg2Str = args[2] ? args[2].toString() : 'null';

        send('=== HIT #' + hitCount + ' ===');
        send('arg2=' + this.arg2Str);

        // Dump PagingContext BEFORE — 512 bytes
        if (args[2]) {
            try {
                var data = args[2].readByteArray(512);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 512; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('[BEFORE] ' + hex);
                }
            } catch(e) {
                send('[BEFORE_ERR] ' + e.toString().substring(0,40));
            }

            // Read key fields
            try {
                var wxidPtr = args[2].readPointer();
                if (wxidPtr) {
                    var str = wxidPtr.readUtf8String();
                    if (str) send('  wxid=' + str.substring(0,40));
                }
            } catch(e) {}

            try {
                var cursor = args[2].add(0x28).readU64();
                send('  cursor_before=' + cursor);
            } catch(e) {}

            try {
                var counter = args[2].add(0x30).readU32();
                send('  counter_before=' + counter);
            } catch(e) {}
        }
    },

    onLeave: function(retval) {
        send('[LEAVE #' + this.hitNum + '] retval=' + (retval ? retval.toString() : 'null'));

        // Dump PagingContext AFTER — same 512 bytes
        if (this.arg2) {
            try {
                var data = this.arg2.readByteArray(512);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 512; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('[AFTER] ' + hex);
                }
            } catch(e) {
                send('[AFTER_ERR] ' + e.toString().substring(0,40));
            }

            try {
                var cursor = this.arg2.add(0x28).readU64();
                send('  cursor_after=' + cursor);
            } catch(e) {}

            try {
                var counter = this.arg2.add(0x30).readU32();
                send('  counter_after=' + counter);
            } catch(e) {}
        }
        send('');
    }
});
'''

session = frida.attach(PID)
script = session.create_script(jscode)

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(outfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        # Save binary dumps
        m_before = re.match(r'\[BEFORE\]\s+([0-9a-fA-F]+)', line)
        m_after = re.match(r'\[AFTER\]\s+([0-9a-fA-F]+)', line)

        if m_before:
            bin_path = os.path.join(dump_dir, f'before_{dump_idx[0]:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m_before.group(1)))
        if m_after:
            bin_path = os.path.join(dump_dir, f'after_{dump_idx[0]:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m_after.group(1)))
            dump_idx[0] += 1

        # Compute and print diff inline
        if m_after:
            before_hex = last_before.get(dump_idx[0])
            if before_hex:
                compute_diff(dump_idx[0], before_hex, m_after.group(1))

        # Track before hex for this hit
        if m_before:
            # Figure out hit number from context
            pass

        print(line, flush=True)

    elif msg['type'] == 'error':
        print('ERR:', str(msg), flush=True)

dump_idx = [0]
last_before = {}

def compute_diff(hit, before_hex, after_hex):
    before = bytes.fromhex(before_hex[:2048])
    after = bytes.fromhex(after_hex[:2048])
    changes = []
    for i in range(0, len(before), 8):
        b = before[i:i+8]
        a = after[i:i+8]
        if b != a:
            b_val = int.from_bytes(b, 'little')
            a_val = int.from_bytes(a, 'little')
            tag = ''
            if b_val == 0 and a_val > 0x100000000:
                tag = ' [NEW_PTR]'
            elif a_val == 0 and b_val > 0x100000000:
                tag = ' [CLEARED]'
            elif b_val > 0x100000000 and a_val > 0x100000000 and b_val != a_val:
                tag = ' [PTR_CHANGED]'
            changes.append(f'  +0x{i:03x}: {b.hex()} -> {a.hex()}{tag}')

    if changes:
        with open(outfile, 'a', encoding='utf-8') as f:
            f.write(f'[DIFF #{hit}] {len(changes)} qwords changed:\n')
            for c in changes:
                f.write(c + '\n')

# intercept BEFORE hex and store
old_msg_fn = on_msg
script.on('message', on_msg)

# Patch: store before data
original_handler = script.on('message', lambda msg, data: None)

class DumpTracker:
    def __init__(self):
        self.current_hit = 0
        self.before_hex = {}

tracker = DumpTracker()

def enhanced_handler(msg, data):
    global tracker
    if msg['type'] == 'send':
        line = msg['payload']
        with open(outfile, 'a', encoding='utf-8') as f:
            pass  # already written above

        m_hit = re.match(r'=== HIT #(\d+) ===', line)
        if m_hit:
            tracker.current_hit = int(m_hit.group(1))

        m_before = re.match(r'\[BEFORE\]\s+([0-9a-fA-F]+)', line)
        if m_before and tracker.current_hit > 0:
            tracker.before_hex[tracker.current_hit] = m_before.group(1)

        m_after = re.match(r'\[AFTER\]\s+([0-9a-fA-F]+)', line)
        if m_after and tracker.current_hit in tracker.before_hex:
            before_hex = tracker.before_hex[tracker.current_hit]
            after_hex = m_after.group(1)
            before = bytes.fromhex(before_hex[:2048])
            after = bytes.fromhex(after_hex[:2048])
            changes = []
            for i in range(0, len(before), 8):
                b = before[i:i+8]
                a = after[i:i+8]
                if b != a:
                    b_val = int.from_bytes(b, 'little')
                    a_val = int.from_bytes(a, 'little')
                    tag = ''
                    if b_val == 0 and a_val > 0x100000000:
                        tag = '  [NEW_PTR]'
                    elif b_val > 0x100000000 and a_val == 0:
                        tag = '  [CLEARED]'
                    elif b_val > 0x100000000 and a_val > 0x100000000 and b_val != a_val:
                        tag = '  [PTR_CHANGED]'
                    changes.append(f'    +0x{i:03x}: {b.hex()} -> {a.hex()}{tag}')
            if changes:
                diff_line = f'[DIFF #{tracker.current_hit}] {len(changes)} changes:'
                print(diff_line, flush=True)
                with open(outfile, 'a', encoding='utf-8') as f:
                    f.write('\n' + diff_line + '\n')
                for c in changes:
                    print(c, flush=True)
                    with open(outfile, 'a', encoding='utf-8') as f:
                        f.write(c + '\n')

        # Save binary dumps
        m_before_bin = re.match(r'\[BEFORE\]\s+([0-9a-fA-F]+)', line)
        if m_before_bin:
            bin_path = os.path.join(dump_dir, f'before_{tracker.current_hit:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m_before_bin.group(1)))

        m_after_bin = re.match(r'\[AFTER\]\s+([0-9a-fA-F]+)', line)
        if m_after_bin:
            bin_path = os.path.join(dump_dir, f'after_{tracker.current_hit:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m_after_bin.group(1)))

        print(line, flush=True)

script.on('message', enhanced_handler)
script.load()

print(f'M14 PagingContext Delta (PID={PID})', flush=True)
print('PageUp 5 times (30s)', flush=True)

try:
    time.sleep(30)
except:
    pass
session.detach()
print('\nDone.', flush=True)
