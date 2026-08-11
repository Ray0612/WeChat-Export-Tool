import frida, psutil, time, sys

PID_WX = 17484
PID_WEB = 35700
outfile = r'C:\Users\OK\Desktop\m115_results.txt'

def log(msg):
    with open(outfile, 'a', encoding='utf-8') as f:
        f.write(str(msg) + '\n')
    print(msg, flush=True)

open(outfile, 'w').close()
log('M11.5 Process Ownership Check')
log('=' * 50)

# Baseline
log('\n[1] Baseline measuring...')
pids = set()
for p in psutil.process_iter(['pid','name']):
    n = p.info['name'] or ''
    if 'weixin' in n.lower() or 'wechatappex' in n.lower():
        pids.add(p.info['pid'])

before = {}
for pid in pids:
    try:
        p = psutil.Process(pid)
        before[pid] = {
            'cpu': p.cpu_percent(interval=0),
            'mem': p.memory_info().rss / 1024 / 1024,
            'name': p.name()
        }
    except: pass
time.sleep(3)

# Hook HeapAlloc
log('\n[2] Hooking HeapAlloc...')
sessions = []

for pid, tag in [(PID_WX, 'WX'), (PID_WEB, 'WEB')]:
    try:
        sess = frida.attach(pid)
        js = '''
        var count = 0;
        try {
            Interceptor.attach(Module.findExportByName('KERNELBASE.dll', 'HeapAlloc'), {
                onEnter: function() { count++; }
            });
        } catch(e) {}
        setInterval(function() {
            if (count > 0) send('CNT ' + count);
        }, 5000);
        '''
        scr = sess.create_script(js)
        scr.on('message', lambda msg, d: None)  # ignore messages
        scr.load()
        sessions.append((sess, tag, 0))
        log(f'  [{tag}] OK')
    except Exception as e:
        log(f'  [{tag}] FAIL: {str(e)[:60]}')

log('\n[3] NOW PRESS PAGEUP 20 TIMES (60s window)')
log('Waiting...')
time.sleep(60)

# Post-paging
log('\n[4] Post-paging measuring...')
after = {}
for pid in pids:
    try:
        p = psutil.Process(pid)
        after[pid] = {
            'cpu': p.cpu_percent(interval=0),
            'mem': p.memory_info().rss / 1024 / 1024,
        }
    except: pass

log(f'\n{\"PID\":>7}  {\"Name\":<22} {\"CPU%\":>8} {\"MEM(MB)\":>10} {"DELTA_CPU":>10} {"DELTA_MEM":>10}')
log('-' * 70)
for pid in sorted(pids):
    try:
        p = psutil.Process(pid)
        name = p.name()
        b = before.get(pid, {'cpu':0,'mem':0})
        a = after.get(pid, {'cpu':0,'mem':0})
        d_cpu = a['cpu'] - b['cpu']
        d_mem = a['mem'] - b['mem']
        flag = ' <<<' if d_cpu > 2 or d_mem > 20 else ''
        log(f'{pid:>7}  {name:<22} {a[\"cpu\"]:>7.1f}% {a[\"mem\"]:>8.1f}MB {d_cpu:>+9.1f} {d_mem:>+9.1f}{flag}')
    except: pass

log('\n[5] Done.')
for sess, tag, _ in sessions:
    try: sess.detach()
    except: pass
