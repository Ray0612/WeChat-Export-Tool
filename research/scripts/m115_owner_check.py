import frida, psutil, time, os

PID_WEIXIN = 17484
PID_WEB = 35700
outfile = r'C:\Users\OK\Desktop\m115_results.txt'
open(outfile, 'w').close()

def monitor_cpu_mem(duration, label):
    """Monitor CPU and memory across all WeChat processes."""
    pids = set()
    for p in psutil.process_iter(['pid', 'name']):
        n = (p.info['name'] or '').lower()
        if 'weixin' in n or 'wechatappex' in n:
            pids.add(p.info['pid'])

    # Sample before
    before = {}
    for pid in pids:
        try:
            p = psutil.Process(pid)
            before[pid] = {
                'cpu': p.cpu_percent(interval=0.1),
                'mem': p.memory_info().rss / 1024 / 1024,
                'name': p.name()
            }
        except:
            pass

    with open(outfile, 'a') as f:
        f.write(f'\n=== {label} ===\n')

    time.sleep(duration)

    # Sample after
    for pid in pids:
        try:
            p = psutil.Process(pid)
            cpu = p.cpu_percent(interval=0.1)
            mem = p.memory_info().rss / 1024 / 1024
            b = before.get(pid, {'cpu': 0, 'mem': 0})
            d_cpu = cpu - b['cpu']
            d_mem = mem - b['mem']
            name = p.name()
            line = f'  {pid:>6} {name:<20} CPU:{cpu:>6.1f}%({d_cpu:>+5.1f}) Mem:{mem:>7.1f}({d_mem:>+6.1f})MB'
            with open(outfile, 'a') as f:
                f.write(line + '\n')
            if abs(d_cpu) > 0.5 or abs(d_mem) > 3:
                print(line)
        except:
            pass

print('M11.5 Process Ownership Verification')
print('=' * 50)

# Step 1: Baseline
print('\n[1] Baseline (5s)...')
monitor_cpu_mem(5, 'BASELINE')

# Step 2: Hook HeapAlloc in Weixin.exe
print('\n[2] Hooking HeapAlloc...')
heap_info = {'wx': 0, 'web': 0}

for pid, label in [(PID_WEIXIN, 'WX'), (PID_WEB, 'WEB')]:
    try:
        session = frida.attach(pid)
        js = '''
        var count = 0;
        try {
            var mod = Process.findModuleByName('KERNELBASE.dll');
            var addr = mod.findExportByName('HeapAlloc');
            if (addr) {
                Interceptor.attach(addr, {
                    onEnter: function(args) {
                        count++;
                    }
                });
                send('HOOK_OK');
            } else {
                send('HOOK_FAIL no export');
            }
        } catch(e) {
            send('HOOK_FAIL ' + e.toString().substring(0,80));
        }
        // Report count every 5s
        setInterval(function() {
            if (count > 0) send('HEAP_CNT ' + count);
        }, 5000);
        '''
        script = session.create_script(js)
        def make_handler(lbl):
            def handler(msg, d):
                if msg['type'] == 'send':
                    payload = msg['payload']
                    if payload.startswith('HEAP_CNT'):
                        heap_info[lbl] = int(payload.split()[1])
                    elif payload.startswith('HOOK'):
                        print(f'  [{lbl}] {payload}')
            return handler
        script.on('message', make_handler(label))
        script.load()
        sessions.append((session, label))
    except Exception as e:
        print(f'  [{label}] Error: {str(e)[:60]}')

sessions = []
# Re-attach properly
for pid, label in [(PID_WEIXIN, 'WX'), (PID_WEB, 'WEB')]:
    try:
        session = frida.attach(pid)
        js_code = f'''
        var count = 0;
        try {{
            var mod = Process.findModuleByName('KERNELBASE.dll');
            var addr = mod.findExportByName('HeapAlloc');
            if (addr) {{
                Interceptor.attach(addr, function() {{
                    count++;
                }});
                send('HOOK_OK_{label}');
            }}
        }} catch(e) {{
            send('HOOK_FAIL_{label} ' + e.toString().substring(0,60));
        }}
        setInterval(function() {{ if (count > 0) send('HEAP_{label} ' + count); }}, 5000);
        '''
        script = session.create_script(js_code)
        script.on('message', lambda msg, d, lbl=label:
            print(f'  [{lbl}] {msg["payload"]}') if msg['type'] == 'send' else None)
        script.load()
        sessions.append((session, label))
        print(f'  [{label}] HeapAlloc hooked')
    except Exception as e:
        print(f'  [{label}] Attach failed: {str(e)[:60]}')

# Step 3: Wait for paging
print('\n[3] Press PageUp 20 times now (60s window)...')
time.sleep(60)

# Step 4: Post-paging measurement
print('\n[4] Post-paging (5s)...')
monitor_cpu_mem(5, 'POST_PAGING')

# Cleanup
for s, lbl in sessions:
    try: s.detach()
    except: pass

print('\nDone. Results in m115_results.txt')
