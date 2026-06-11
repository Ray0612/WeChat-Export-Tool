// 正确的 key 提取: 关微信 → 开微信 → 启动时 Hook 捕获 SetDBKey
// 微信 4.x 的 SetDBKey 只在进程启动时调用, 登录/退出登录不会触发
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');

const SELF = __dirname;
const LOCAL_APP_DATA = process.env.LOCALAPPDATA || '';
const PROGRAM_FILES = process.env['ProgramFiles'] || 'C:\\Program Files';
const PROGRAM_FILES_X86 = process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)';
const DLL_CANDIDATES = [
    path.join(SELF, '..', 'dll', 'wx_key.dll'),
    path.join(SELF, '..', '..', '..', 'research', 'tools', 'wx_key', 'build', 'Release', 'wx_key.dll'),
    path.join(LOCAL_APP_DATA, 'Programs', 'WeFlow', 'resources', 'resources', 'key', 'win32', 'x64', 'wx_key.dll'),
    path.join(PROGRAM_FILES, 'Tencent', 'WeFlow', 'resources', 'resources', 'key', 'win32', 'x64', 'wx_key.dll'),
    path.join(PROGRAM_FILES_X86, 'Tencent', 'WeFlow', 'resources', 'resources', 'key', 'win32', 'x64', 'wx_key.dll'),
];
const OUT = path.join(process.env.USERPROFILE || SELF, 'Desktop', 'wx_export');
const STATUS_FILE = path.join(OUT, 'key_status.txt');
fs.mkdirSync(OUT, { recursive: true });
function setStatus(s) { try { fs.writeFileSync(STATUS_FILE, s); } catch(e) {} }

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function decode(arr) {
    const idx = arr.indexOf(0);
    return Buffer.from(arr.slice(0, idx >= 0 ? idx : arr.length)).toString('utf-8').trim();
}

async function findWeChatPid() {
    const names = ['Weixin.exe', 'WeChat.exe', 'WeChatAppEx.exe'];
    const tasklistPaths = ['tasklist', 'C:\\Windows\\System32\\tasklist.exe'];
    for (const tl of tasklistPaths) {
        for (const name of names) {
            try {
                const out = execFileSync(tl, ['/FI', `IMAGENAME eq ${name}`, '/FO', 'CSV', '/NH'], { encoding: 'utf8', timeout: 5000 });
                for (const line of out.split('\n')) {
                    if (line.toLowerCase().includes(name.replace('.exe','').toLowerCase())) {
                        const pid = parseInt(line.split('","')[1]?.replace(/"/g, ''));
                        if (!isNaN(pid)) return pid;
                    }
                }
            } catch(e) {}
        }
    }
    try {
        const out = execFileSync('wmic', ['process', 'where', 'name like "%Wei%"', 'get', 'ProcessId,name'], { encoding: 'utf8', timeout: 5000 });
        for (const line of out.split('\n')) {
            if (line.includes('Weixin') || line.includes('WeChat')) {
                const parts = line.trim().split(/\s+/);
                const pid = parseInt(parts[parts.length - 1]);
                if (!isNaN(pid)) return pid;
            }
        }
    } catch(e) {}
    return null;
}

// 等待微信退出 (最多等 20s)
async function waitWeChatExit() {
    for (let i = 0; i < 40; i++) {
        if (!(await findWeChatPid())) return true;
        await sleep(500);
    }
    return false;
}

// 等待微信启动 (最多等 60s)
async function waitWeChatStart() {
    for (let i = 0; i < 120; i++) {
        const pid = await findWeChatPid();
        if (pid) return pid;
        await sleep(500);
    }
    return null;
}

// 加载 wx_key.dll
function loadWxKey() {
    const dllPath = DLL_CANDIDATES.find(f => fs.existsSync(f));
    if (!dllPath) { console.error('[KEY] 找不到 wx_key.dll'); setStatus('dll_not_found'); return null; }
    setStatus('dll_found');
    const koffi = require('koffi');
    const lib = koffi.load(dllPath);
    setStatus('dll_loaded');
    return {
        initHook: lib.func('bool InitializeHook(uint32 targetPid)'),
        pollKey: lib.func('bool PollKeyData(_Out_ char* buf, int size)'),
        getStatus: lib.func('bool GetStatusMessage(_Out_ char* buf, int size, _Out_ int* level)'),
        cleanup: lib.func('bool CleanupHook()'),
        getError: lib.func('const char* GetLastErrorMsg()'),
    };
}

async function main() {
    setStatus('started');

    // ── 加载 DLL ──
    const api = loadWxKey();
    if (!api) process.exit(1);

    // ── 阶段 1: 确保微信已关闭 ──
    let existing = await findWeChatPid();
    if (existing) {
        console.log('[KEY] 微信还在运行, 等待关闭...');
        setStatus('waiting_close');
        const ok = await waitWeChatExit();
        if (!ok) {
            console.log('[KEY] 等待微信关闭超时, 请手动关闭');
            setStatus('timeout_close');
            process.exit(1);
        }
        console.log('[KEY] 微信已关闭');
    }

    // ── 阶段 2: 等微信启动 ──
    console.log('[KEY] 请打开微信并登录');
    setStatus('waiting_start');
    const pid = await waitWeChatStart();
    if (!pid) {
        console.log('[KEY] 等待微信启动超时');
        setStatus('timeout_start');
        process.exit(1);
    }
    console.log(`[KEY] 检测到微信 PID: ${pid}`);

    // ── 阶段 3: 立即 Hook (微信刚启动, SetDBKey 还没被调用) ──
    setStatus('injecting');
    if (!api.initHook(pid)) {
        const err = api.getError();
        const msg = err ? decode(err) : '未知错误';
        console.log(`[KEY] Hook 注入失败: ${msg}`);
        setStatus('hook_failed:' + msg.substring(0, 60));
        process.exit(1);
    }
    console.log('[KEY] Hook 注入成功, 等待 SetDBKey 调用...');
    setStatus('hook_ok');

    // ── 读 DLL 状态消息 ──
    for (let i = 0; i < 30; i++) {
        const s = Buffer.alloc(512);
        const l = [0];
        while (api.getStatus(s, s.length, l)) {
            const m = decode(s);
            if (m) console.log(`  [${l[0]}] ${m}`);
        }
        await sleep(200);
    }

    // ── 阶段 4: 轮询 key (200ms, 120s) ──
    console.log('[KEY] 等待微信登录过程中捕获密钥...');
    setStatus('polling');
    const buf = Buffer.alloc(128);
    const start = Date.now();
    while (Date.now() - start < 120000) {
        if (api.pollKey(buf, buf.length)) {
            const key = buf.toString('ascii').substring(0, 64);
            if (/^[0-9a-f]{64}$/i.test(key)) {
                fs.writeFileSync(path.join(OUT, 'key.txt'), key);
                console.log(`\n[KEY] ✅ 成功: ${key.substring(0, 16)}...`);
                setStatus('captured');
                api.cleanup();
                process.exit(0);
            }
        }
        // 读日志
        const s = Buffer.alloc(512);
        const l = [0];
        while (api.getStatus(s, s.length, l)) {
            const m = decode(s);
            if (m) console.log(`  [${l[0]}] ${m}`);
        }
        await sleep(200);
    }

    console.log('\n[KEY] 获取超时');
    setStatus('timeout_poll');
    api.cleanup();
    process.exit(1);
}

main().catch(e => {
    console.error('[KEY] 错误:', e.message);
    setStatus('error:' + e.message.substring(0, 80));
    process.exit(1);
});
