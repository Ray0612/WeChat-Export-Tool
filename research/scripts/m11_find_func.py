import frida, psutil, time, struct

PID = 16460

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
var base = mod.base;
var size = mod.size;
var strOffset = 0x084f4a2f;  // "GetPagedMessages" string offset in DLL
var strAddr = base.add(strOffset);

send('Weixin.dll base=' + base.toString() + ' size=' + size);
send('String "GetPagedMessages" @ runtime=' + strAddr.toString());

// The string is in .rdata (read-only). Let's verify
try {
    var str = strAddr.readCString();
    send('String content: "' + str + '"');
} catch(e) {
    send('Cannot read string: ' + e.toString());
}

// Now scan executable sections for RIP-relative references to this string
// In x64, references to a global address use RIP-relative LEA:
//   lea rcx, [rip + offset]  ->  48 8d 0d XX XX XX XX
//   lea rdx, [rip + offset]  ->  48 8d 15 XX XX XX XX
//   lea r8,  [rip + offset]  ->  4c 8d 05 XX XX XX XX
//   lea r9,  [rip + offset]  ->  4c 8d 0d XX XX XX XX
// etc.
// The offset = target_addr - (instruction_addr + 7)

var refPatterns = [
    {mask: [0x48, 0x8d, 0x0d], desc: 'lea rcx'},   // lea rcx, [rip+xx]
    {mask: [0x48, 0x8d, 0x15], desc: 'lea rdx'},   // lea rdx, [rip+xx]
    {mask: [0x48, 0x8d, 0x05], desc: 'lea rax'},   // lea rax, [rip+xx]
    {mask: [0x4c, 0x8d, 0x05], desc: 'lea r8'},    // lea r8, [rip+xx]
    {mask: [0x4c, 0x8d, 0x0d], desc: 'lea r9'},    // lea r9, [rip+xx]
    {mask: [0x4c, 0x8d, 0x15], desc: 'lea r10'},   // lea r10, [rip+xx]
    {mask: [0x4c, 0x8d, 0x1d], desc: 'lea r11'},   // lea r11, [rip+xx]
    {mask: [0x48, 0x8b, 0x05], desc: 'mov rax'},   // mov rax, [rip+xx]
    {mask: [0x48, 0x8b, 0x0d], desc: 'mov rcx'},   // mov rcx, [rip+xx]
    {mask: [0x48, 0x8b, 0x15], desc: 'mov rdx'},   // mov rdx, [rip+xx]
];

send('');
send('Scanning executable memory for xrefs...');

var ranges = Process.enumerateRanges('--x');
var totalCount = 0;
var xrefs = [];

for (var ri = 0; ri < ranges.length; ri++) {
    var r = ranges[ri];
    // Only scan within Weixin.dll
    if (r.base < base || r.base >= base.add(size)) continue;

    var rSize = parseInt(r.size);
    if (rSize > 5000000) rSize = 5000000;

    try {
        var data = r.base.readByteArray(rSize);
        if (!data) continue;
        var bytes = new Uint8Array(data);

        for (var pi = 0; pi < refPatterns.length; pi++) {
            var mask = refPatterns[pi].mask;
            for (var j = 0; j < bytes.length - 7; j++) {
                // Check pattern match
                var match = true;
                for (var k = 0; k < 3; k++) {
                    if (bytes[j+k] !== mask[k]) { match = false; break; }
                }
                if (!match) continue;

                // Read the 4-byte signed offset
                var off = (bytes[j+3]) | (bytes[j+4] << 8) | (bytes[j+5] << 16) | (bytes[j+6] << 24);
                if (off > 0x7fffffff) off -= 0x100000000;  // sign extend

                // Calculate target = instruction_addr + 7 + offset
                var instrAddr = r.base.add(j);
                var targetAddr = instrAddr.add(7 + off);

                // Check if it points to our string
                if (targetAddr.toString() === strAddr.toString()) {
                    var dllOffset = instrAddr.sub(base).toInt32();
                    var refType = refPatterns[pi].desc;
                    xrefs.push({offset: dllOffset, type: refType});
                    send('XREF: ' + refType + ' at DLL 0x' + dllOffset.toString(16));
                    totalCount++;
                }
            }
        }
    } catch(e) {
        // Range read error, skip
    }
}

send('');
send('Total xrefs to "GetPagedMessages" string: ' + totalCount);
if (xrefs.length > 0) {
    // Group by proximity (functions)
    xrefs.sort(function(a,b) { return a.offset - b.offset; });

    send('');
    send('Grouped by function (xrefs within 0x100 of each other):');
    var groupStart = xrefs[0].offset;
    var groupTypes = [xrefs[0].type];
    for (var i = 1; i < xrefs.length; i++) {
        if (xrefs[i].offset - groupStart < 0x100) {
            groupTypes.push(xrefs[i].type);
        } else {
            send('  Function near 0x' + groupStart.toString(16) + ': ' + groupTypes.join(', '));
            groupStart = xrefs[i].offset;
            groupTypes = [xrefs[i].type];
        }
    }
    send('  Function near 0x' + groupStart.toString(16) + ': ' + groupTypes.join(', '));

    // Deduce function entry (find nearest PUSH RBP before first xref)
    send('');
    send('Searching for function entry points (PUSH RBP = 55)...');
    var firstXref = xrefs[0].offset;
    // Search backwards from first xref for function prologue
    for (var i = 0; i < xrefs.length; i++) {
        var searchStart = xrefs[i].offset - 0x200;
        if (searchStart < 0) searchStart = 0;
        for (var ri = 0; ri < ranges.length; ri++) {
            var r = ranges[ri];
            if (r.base < base || r.base >= base.add(size)) continue;
            // This search approach won't work well without reading the DLL file itself
        }
    }
}
'''

session = frida.attach(PID)
script = session.create_script(jscode)

def on_msg(msg, data):
    if msg['type'] == 'send':
        print(msg['payload'])
    elif msg['type'] == 'error':
        print('ERR:', str(msg))

script.on('message', on_msg)
import threading
timer = threading.Timer(120, lambda: session.detach())
timer.start()
script.load()
time.sleep(115)
timer.cancel()
try: session.detach()
except: pass
