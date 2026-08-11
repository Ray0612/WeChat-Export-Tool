// Frida script: search for SQLCipher key in WeChatAppEx memory
// The 64-byte key is stored in the sqlite3 handle structure
// Search for high-entropy 64-byte blocks near known markers

console.log("[*] Scanning WeChatAppEx memory for SQLCipher key...");

// The key is 64 bytes: first 32 = encryption, second 32 = HMAC
// In flue.dll, the cipher context stores this key
// We can search for it by pattern

// Method 1: Look for the cipher configuration objects
// flue.dll stores the cipher key in CipherCtx or similar structures
var flueMod = Process.findModuleByName("flue.dll");
if (!flueMod) {
    console.log("[-] flue.dll not found");
    Process.enumerateModules({onMatch: function(m) {
        if (m.name.indexOf("flue") !== -1) {
            console.log("  found: " + m.name + " @ " + m.base);
            flueMod = m;
        }
    }, onComplete: function() {}});
}

if (flueMod) {
    console.log("[+] flue.dll at " + flueMod.base);

    // Method 1: Search for "sqlite3_key_v2" string reference in flue.dll
    // and read the key from the call site

    // Method 2: Hook sqlite3_exec and read key from db handle
    var sqlite3_exec = Module.findExportByName(null, "sqlite3_exec");
    if (!sqlite3_exec) {
        // Try finding it in flue.dll exports
        var exports = Module.enumerateExports("flue.dll");
        for (var i = 0; i < exports.length; i++) {
            if (exports[i].name.indexOf("sqlite3_exec") !== -1 ||
                exports[i].name.indexOf("sqlite3_prepare") !== -1) {
                sqlite3_exec = exports[i].address;
                console.log("[+] Found export: " + exports[i].name + " @ " + exports[i].address);
                break;
            }
        }
    }

    if (sqlite3_exec) {
        console.log("[+] Hooking sqlite3_exec at " + sqlite3_exec);
        Interceptor.attach(sqlite3_exec, {
            onEnter: function(args) {
                // args[0] = sqlite3* db
                var dbPtr = args[0];
                // In SQLCipher, the key is stored in the db handle at specific offsets
                // For SQLCipher 4 with flue.dll, the key offset varies
                // Try to read the cipher context from the db handle
                console.log("\n[+] sqlite3_exec called, db = " + dbPtr);
                console.log("[+] SQL: " + Memory.readUtf8String(args[1]));

                // Read potential key locations from the db handle
                // The key is typically stored in the pCipher or aCipher fields
                // Try reading various offsets
                for (var offset = 0x200; offset < 0x400; offset += 8) {
                    try {
                        var ptr = Memory.readPointer(dbPtr.add(offset));
                        if (ptr.isNull()) continue;
                        // Check if this looks like a cipher context
                        // Try to read 32 bytes from it
                        var data = Memory.readByteArray(ptr, 32);
                        var arr = new Uint8Array(data);
                        // Check entropy
                        var distinct = {};
                        for (var j = 0; j < arr.length; j++) {
                            distinct[arr[j]] = true;
                        }
                        if (Object.keys(distinct).length >= 20) {
                            console.log("    possible key at db+" + offset.toString(16) + " -> " + ptr + " (entropy=" + Object.keys(distinct).length + ")");
                            var hex = "";
                            for (var j = 0; j < arr.length; j++) {
                                hex += ("0" + arr[j].toString(16)).slice(-2);
                            }
                            console.log("      data: " + hex);
                        }
                    } catch(e) {}
                }
            }
        });
    } else {
        console.log("[-] sqlite3_exec not found, trying alternative approach...");

        // Method 3: Memory.scan for the key
        console.log("[*] Scanning memory for 64-byte high-entropy blocks...");
        // This would be too slow for the full address space
        // Instead, focus on the flue.dll data sections
        var ranges = Process.enumerateRanges('r--');
        console.log("[*] Found " + ranges.length + " readable ranges");
    }
} else {
    console.log("[-] flue.dll not found in any module");
}
