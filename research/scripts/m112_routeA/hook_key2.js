// Hook sqlite3_key_v2 - enumerate modules first
console.log("[*] Enumerating modules...");
Process.enumerateModules({
    onMatch: function(module) {
        // Print all DLLs with "flue", "sqlite", or "cipher" in name
        var name = module.name.toLowerCase();
        if (name.indexOf("flue") !== -1 || name.indexOf("sqlite") !== -1 || name.indexOf("cipher") !== -1) {
            console.log("    " + module.name + " -> " + module.base);
        }
    },
    onComplete: function() {
        console.log("[*] Enumerate complete");
    }
});

// Try to find sqlite3_key_v2 by export
console.log("[*] Searching for sqlite3_key_v2...");
var keyFunc = Module.findExportByName(null, "sqlite3_key_v2");
if (keyFunc) {
    console.log("[*] sqlite3_key_v2 found globally at: " + keyFunc);
} else {
    console.log("[-] sqlite3_key_v2 not found as global export");

    // Try in flue.dll
    var flueMod = Process.findModuleByName("flue.dll");
    if (flueMod) {
        var offset = ptr(0x2a9c805);
        var addr = flueMod.base.add(offset);
        console.log("[*] Attempting to hook flue.dll+0x2a9c805");

        Interceptor.attach(addr, {
            onEnter: function(args) {
                console.log("\n[+] sqlite3_key_v2 CALLED!");
                console.log("    db: " + args[0]);
                console.log("    key_len: " + args[3].toInt32());
                if (args[2] !== null) {
                    var keyLen = args[3].toInt32();
                    var keyData = Memory.readByteArray(args[2], Math.min(keyLen, 64));
                    var hex = "";
                    var arr = new Uint8Array(keyData);
                    for (var i = 0; i < arr.length; i++) {
                        hex += ("0" + arr[i].toString(16)).slice(-2);
                    }
                    console.log("    key_hex: " + hex);
                }
            }
        });
    } else {
        console.log("[-] flue.dll module not found");
    }
}
