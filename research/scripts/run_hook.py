import frida, psutil, time, sys, os

logfile = r'C:\Users\OK\Desktop\hook_result.txt'

with open(logfile, 'w') as f:
    f.write('Starting hook...\n')

procs = [p for p in psutil.process_iter(['pid','name','create_time']) if p.info['name'] == 'Weixin.exe']
procs.sort(key=lambda x: x.info['create_time'])
pid = procs[0].info['pid']

with open(logfile, 'a') as f:
    f.write(f'Target PID: {pid}\n')

session = frida.attach(pid)

script = session.create_script('''
    var base = Module.findBaseAddress("Weixin.dll");
    var funcAddr = base.add(0x016ade70);
    var count = 0;
    send("Hook ready at " + funcAddr);
    Interceptor.attach(funcAddr, {
        onEnter: function() {
            count++;
            send("[HIT #" + count + "] GetPagedMessages called at " + new Date().toISOString());
        }
    });
''')

def on_msg(msg, data):
    if msg['type'] == 'send':
        with open(logfile, 'a') as f:
            f.write(msg['payload'] + '\n')
        print(msg['payload'])

script.on('message', on_msg)
script.load()

with open(logfile, 'a') as f:
    f.write('Hook running. 翻页试试...\n')
print('Hook running. 翻页试试...')

try:
    time.sleep(9999)
except:
    session.detach()
    with open(logfile, 'a') as f:
        f.write('Hook stopped.\n')
