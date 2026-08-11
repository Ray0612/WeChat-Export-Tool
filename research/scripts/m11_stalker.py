import frida, psutil, time, os

PID = 17484
outfile = r'C:\Users\OK\Desktop\m11_stalker.txt'
open(outfile, 'w').close()

jscode = '''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
var base = mod.base;
var size = mod.size;

send('base=' + base.toString() + ' size=' + size);

// Hook the function we found (the one xreffing GetPagedMessages)
var candidateAddr = base.add(0x016feab0);

// Instead, try to find the REAL function by hooking ALL calls during paging
// We'll use Stalker to trace execution for a brief period during paging
// But first, let's try hooking the "has messages" string xref area

// Actually, let's just hook functions near the known string references
// and see which one fires during paging

// Hook all callable exports for a short period? No, too many.

// Better approach: The function we want should be called during paging.
// Since the code at 0x016feab0 doesn't fire during paging,
// let's search for functions that DO fire during paging by:
// 1. First running without hook to establish baseline
// 2. Then looking for new function calls during paging

// For now, let's try to find the function by closely looking at
// instructions around the "GetPagedMessages" string reference to understand
// what function it's actually in

var strRefAddr = base.add(0x016feb6f);
send('String ref instruction at ' + strRefAddr.toString());

// Read surrounding bytes to understand the function structure
try {
    // Read 64 bytes context around the xref
    var ctxData = strRefAddr.sub(0x20).readByteArray(0x60);
    var bytes = new Uint8Array(ctxData);
    var hex = '';
    for (var i = 0; i < 0x60; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
    send('Context around xref: ' + hex);

    // Try to find the function prologue before the xref
    for (var off = 0x20; off < 0x200; off++) {
        var b = strRefAddr.sub(off).readU8();
        if (b === 0x55) {  // PUSH RBP
            send('PUSH RBP found at -' + off + ' bytes from xref');
            var funcStart = strRefAddr.sub(off);
            send('  Candidate function: ' + funcStart.toString());
            send('  DLL offset: 0x' + funcStart.sub(base).toInt32().toString(16));
            break;
        }
    }
} catch(e) {
    send('Error: ' + e.toString());
}

// Now try the approach from the OLD analysis:
// In old version, GetPagedMessages had arg pattern:
// arg0=constant, arg1=constant, arg2=changes, arg3=arg2+0x20
// Let's search for functions where the first argument matches known arg0 value
send('');
send('Note: Old GetPagedMessages was at DLL offset 0x016ade70');
send('New GetPagedMessages string at DLL offset 0x084f4a2f');
send('Found xref at DLL offset 0x016feb6f');
'''

session = frida.attach(PID)
script = session.create_script(jscode)

def on_msg(msg, d):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(outfile, 'a') as f:
            f.write(line + '\n')
        print(line)

script.on('message', on_msg)
script.load()
time.sleep(2)
session.detach()
print('Done')

# Read the context we captured
with open(outfile) as f:
    content = f.read()
print()
print('Analysis:')
for line in content.split('\n'):
    print(line)
