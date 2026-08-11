// Frida hook for sqlite3_key_v2 - persistent monitoring
console.log("[*] Looking for flue.dll...");

function tryHook(pid) {
    var flueMod = Process.findModuleByName("flue.dll");
    if (!flueMod) {
        // Try alternate name
        Process.enumerateModules({
            onMatch: function(m) {
                if (m.name.toLowerCase().indexOf("flue") !== -1) {
                    flueMod = m;
                }
            },
            onComplete: function() {}
        });
    }

    if (flueMod) {
        var keyFunc = flueMod.base.add(0x2a9c805);
        console.log("[+] flue.dll found at: " + flueMod.base);
        console.log("[+] sqlite3_key_v2 at: " + keyFunc);

        Interceptor.attach(keyFunc, {
            onEnter: function(args) {
                var keyLen = args[3].toInt32();
                if (keyLen > 0 && keyLen <= 256) {
                    var keyData = Memory.readByteArray(args[2], keyLen);
                    var hex = "";
                    var arr = new Uint8Array(keyData);
                    for (var i = 0; i < arr.length; i++) {
                        hex += ("0" + arr[i].toString(16)).slice(-2);
                    }

                    var name = "";
                    try {
                        if (args[1] !== null) {
                            name = Memory.readUtf8String(args[1]);
                        }
                    } catch(e) {}

                    console.log("\n[KEY] sqlite3_key_v2 called!");
                    console.log("[KEY] name: " + name);
                    console.log("[KEY] key_len: " + keyLen);
                    console.log("[KEY] key_hex: " + hex);

                    // Save for later
                    if (!this.lastKey || this.lastKey !== hex) {
                        send({type: "key", payload: {hex: hex, len: keyLen, name: name}});
                        this.lastKey = hex;
                    }
                }
            }
        });
        return true;
    }
    return false;
}

// Try immediate hook
if (!tryHook()) {
    console.log("[-] flue.dll not found yet, waiting...");
    // Wait and retry
    var attempts = 0;
    var maxAttempts = 30;
    var timer = setInterval(function() {
        attempts++;
        if (tryHook()) {
            clearInterval(timer);
            console.log("[+] Hook established after " + attempts + " attempts");
        } else if (attempts >= maxAttempts) {
            clearInterval(timer);
            console.log("[-] flue.dll not found after " + maxAttempts + " attempts");
        }
    }, 1000);
}
