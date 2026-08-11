'use strict';

var base = Module.findBaseAddress('Weixin.dll');
if (!base) {
    console.log('[-] Weixin.dll not found!');
} else {
    var funcAddr = base.add(0x016ade70);
    console.log('[*] Weixin.dll base: ' + base);
    console.log('[*] Target: ' + funcAddr);

    var hitCount = 0;
    Interceptor.attach(funcAddr, {
        onEnter: function(args) {
            hitCount++;
            var now = new Date();
            console.log('[GetPagedMessages] HIT #' + hitCount + ' @ ' + now.toISOString());
        }
    });
    console.log('[*] Hook installed! 翻页试试...');
}
