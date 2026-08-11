// Hook sqlite3_key_v2 in WeChatAppEx
// flue.dll + 0x2a9c805 = sqlite3_key_v2

// Find flue.dll base address
var flueBase = null;
Process.enumerateModules({
    onMatch: function(module) {
        if (module.name.toLowerCase() === "flue.dll") {
            flueBase = module.base;
            console.log("[*] flue.dll base: " + module.base);
        }
    },
    onComplete: function() {}
});

if (flueBase) {
    var sqlite3_key_v2 = flueBase.add(0x2a9c805);
    console.log("[*] sqlite3_key_v2 at: " + sqlite3_key_v2);

    Interceptor.attach(sqlite3_key_v2, {
        onEnter: function(args) {
            // sqlite3_key_v2(db, name, key, key_len)
            // x64: RCX=db, RDX=name, R8=key, R9=key_len
            console.log("\n[+] sqlite3_key_v2 CALLED!");
            console.log("    db: " + args[0]);

            // Read key name (RDX)
            if (args[1] !== null) {
                try {
                    var name = Memory.readUtf8String(args[1]);
                    console.log("    name: " + name);
                } catch(e) {
                    console.log("    name: (unreadable)");
                }
            }

            // Read key data (R8) - 32 bytes for SQLCipher v4
            if (args[2] !== null) {
                try {
                    var keyLen = args[3].toInt32();
                    console.log("    key_len: " + keyLen);
                    var keyData = Memory.readByteArray(args[2], Math.min(keyLen, 64));
                    var keyHex = "";
                    var uint8 = new Uint8Array(keyData);
                    for (var i = 0; i < uint8.length; i++) {
                        keyHex += ("0" + uint8[i].toString(16)).slice(-2);
                    }
                    console.log("    key_hex: " + keyHex);

                    // Save to a global for later retrieval
                    if (typeof globalThis !== 'undefined') {
                        globalThis.lastKey = keyHex;
                        globalThis.lastKeyLen = keyLen;
                    }
                } catch(e) {
                    console.log("    key: (error reading) - " + e);
                }
            }
        },
        onLeave: function(retval) {
            console.log("    retval: " + retval);
        }
    });
} else {
    console.log("[-] flue.dll not found");
}
