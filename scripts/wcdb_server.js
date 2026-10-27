// WCDB HTTP 服务 — 自包含路径，不依赖外部配置
const http = require('http');
const path = require('path');
const koffi = require('koffi');
const fs = require('fs');
const fzstd = require('fzstd');

const SELF = __dirname;
// DLL 搜索路径: 源码开发时用 APP/WeChatExport/dll, 打包后用 ../dll
const DLL_CANDIDATES = [
    path.join(SELF, '..', 'APP', 'WeChatExport', 'dll'),
    path.join(SELF, '..', 'dll'),
];
let DLL = DLL_CANDIDATES.find(d => fs.existsSync(path.join(d, 'WCDB.dll'))) || DLL_CANDIDATES[0];

const key = process.argv[2];
const port = process.argv[3];
const DATA_DIR = process.argv[4] || '';     // 微信数据目录（可选）
// 如果没传数据目录，扫描常见位置
const COMMON_DIRS = DATA_DIR ? [DATA_DIR] : [
    path.join(process.env.USERPROFILE || 'C:', 'Documents', 'xwechat_files'),
    path.join(process.env.USERPROFILE || 'C:', 'Documents', 'WeChat Files'),
];

if (!key || key.length !== 64) { console.error('BAD_KEY'); process.exit(1); }

// ── 初始化 WCDB ──
let lib = null;
let legacy = false;   // 旧版 wcdb_api.dll：无 InitProtection，需要扁平化 DB 目录
try {
    koffi.load(path.join(DLL, 'WCDB.dll'));
    koffi.load(path.join(DLL, 'SDL2.dll'));
    const _lib = koffi.load(path.join(DLL, 'wcdb_api.dll'));
    let ip = null;
    try { ip = _lib.func('int32 InitProtection(const char* path)'); } catch(e) { legacy = true; }
    const wi = _lib.func('int32 wcdb_init()');
    if (ip) { try { ip(DLL); } catch(e) {} }
    const rc = wi();
    if (rc !== 0) { console.error('INIT_FAIL:' + rc); process.exit(1); }
    lib = _lib;
} catch(e) {
    console.error('DLL_LOAD_FAIL:' + e.message.substring(0, 80));
    process.exit(1);
}

// ── 找 session.db ──
function find(folder) {
    if (!folder) return null;
    try {
        for (const e of fs.readdirSync(folder)) {
            const full = path.join(folder, e);
            if (e === 'session.db' && !full.includes('-wal')) return full;
            if (fs.statSync(full).isDirectory()) {
                const r = find(full);
                if (r) return r;
            }
        }
    } catch(e) {}
    return null;
}

let sessionDb = null;
for (const dir of COMMON_DIRS) {
    sessionDb = find(dir);
    if (sessionDb) break;
}
if (!sessionDb) { console.error('DB_NOT_FOUND'); process.exit(1); }

// v1.2: 计算账号目录 (往上走到 wxid_* 目录)
let accountDir = '';
if (sessionDb) {
    let d = path.dirname(sessionDb);
    while (d && d !== path.dirname(d)) {
        if (path.basename(d).startsWith('wxid_')) {
            accountDir = d; break;
        }
        d = path.dirname(d);
    }
}

// ── 旧 DLL 兼容：把 session/message/contact 复制到一个纯 ASCII 的扁平目录 ──
// 旧版 wcdb_api.dll 只在 session.db 同目录找 message_*.db，且路径含中文会失败
function isAscii(s) { return /^[\x00-\x7F]*$/.test(s); }

function pickFlatDir() {
    const suffix = String(process.pid);
    const cands = [
        process.env.TEMP ? path.join(process.env.TEMP, 'wx_export_flat_' + suffix) : '',
        process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'wx_export_flat_' + suffix) : '',
        'C:\\wx_export_flat_' + suffix,
        'D:\\wx_export_flat_' + suffix,
    ].filter(Boolean);
    for (const c of cands) if (isAscii(c)) return c;
    throw new Error('找不到纯 ASCII 的暂存目录');
}

let FLAT_DIR = '';

function stageFlat(accDir) {
    const dbStorage = path.join(accDir, 'db_storage');
    if (!fs.existsSync(dbStorage)) throw new Error('db_storage 不存在: ' + dbStorage);
    const flat = pickFlatDir();
    FLAT_DIR = flat;
    fs.rmSync(flat, { recursive: true, force: true });
    fs.mkdirSync(flat, { recursive: true });

    const pairs = [
        [path.join(dbStorage, 'session', 'session.db'), path.join(flat, 'session.db')],
        [path.join(dbStorage, 'session', 'session.db-wal'), path.join(flat, 'session.db-wal')],
        [path.join(dbStorage, 'session', 'session.db-shm'), path.join(flat, 'session.db-shm')],
        [path.join(dbStorage, 'contact', 'contact.db'), path.join(flat, 'contact.db')],
    ];
    for (const [s, d] of pairs) if (fs.existsSync(s)) fs.copyFileSync(s, d);

    const msgDir = path.join(dbStorage, 'message');
    if (fs.existsSync(msgDir)) {
        for (const f of fs.readdirSync(msgDir)) {
            if (/^message_.*\.db$/i.test(f)) fs.copyFileSync(path.join(msgDir, f), path.join(flat, f));
        }
    }
    return path.join(flat, 'session.db');
}

let openDb = sessionDb;
if (legacy) {
    try {
        openDb = stageFlat(accountDir);
        console.error('STAGING_OK:' + openDb);
    } catch(e) {
        console.error('STAGING_FAIL:' + e.message);
        process.exit(1);
    }
}

// ── 绑定函数 ──
const oa = lib.func('int32 wcdb_open_account(const char* path, const char* key, _Out_ int64* h)');
const ca = lib.func('int32 wcdb_close_account(int64 h)');
const gs = lib.func('int32 wcdb_get_sessions(int64 h, _Out_ void** out)');
const gm = lib.func('int32 wcdb_get_messages(int64 h, const char* username, int32 limit, int32 offset, _Out_ void** out)');
const gc = lib.func('int32 wcdb_get_message_count(int64 h, const char* username, _Out_ int32* out)');
const dn = lib.func('int32 wcdb_get_display_names(int64 h, const char* json, _Out_ void** out)');
const fs2 = lib.func('void wcdb_free_string(void* p)');

function optFunc(sig) {
    try { return lib.func(sig); } catch(e) { return null; }
}
// v1.2: 媒体相关 API（旧 DLL 没有，缺失时降级到文件系统搜索）
const sm = optFunc('int32 wcdb_scan_media_stream(int64 h, const char* sessionIdsJson, int32 mediaType, int64 begin, int64 end, int32 limit, int32 offset, _Out_ void** outJson, _Out_ int32* outHasMore)');
const ri = optFunc('int32 wcdb_resolve_image_hardlink(int64 h, const char* md5, const char* accountDir, _Out_ void** outJson)');
const rib = optFunc('int32 wcdb_resolve_image_hardlink_batch(int64 h, const char* requestsJson, _Out_ void** outJson)');

const h = [BigInt(0)];
if (oa(openDb, key, h) !== 0) { console.error('OPEN_FAIL:' + openDb); process.exit(1); }

// ── HTTP 服务 ──
http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    const p = req.url.split('/').filter(Boolean);
    const a = p[0] || '';

    try {
        if (a === 'ping') { res.end('pong'); return; }

        if (a === 'sessions') {
            const out = [null]; gs(h[0], out);
            res.end(out[0] ? koffi.decode(out[0], 'char', -1) : '[]');
            if (out[0]) fs2(out[0]); return;
        }

        if (a === 'messages') {
            const out = [null]; gm(h[0], p[1], parseInt(p[2]||'200'), parseInt(p[3]||'0'), out);
            let raw = out[0] ? koffi.decode(out[0], 'char', -1) : '[]';
            if (out[0]) fs2(out[0]);
            // ZSTD 解压
            try {
                const msgs = JSON.parse(raw);
                for (const msg of msgs) {
                    for (const f of ['message_content', 'compress_content']) {
                        const v = msg[f];
                        if (!v || typeof v !== 'string') continue;
                        const buf = Buffer.from(v, 'hex');
                        if (buf.length >= 4 && buf.readUInt32LE(0) === 0xFD2FB528) {
                            try {
                                const dec = fzstd.decompress(buf);
                                let t = Buffer.from(dec).toString('utf-8').replace(/\0/g, '').trim();
                                const tm = t.match(/<title>(.*?)<\/title>/);
                                if (tm) t = tm[1];
                                if (t && t.length < 10000) { msg.message_content = t; break; }
                            } catch(e) {}
                        }
                    }
                }
                res.end(JSON.stringify(msgs));
            } catch(e) { res.end(raw); }
            return;
        }

        if (a === 'count') {
            const cnt = [0]; gc(h[0], p[1], cnt);
            res.end(String(cnt[0])); return;
        }

        if (a === 'displaynames') {
            let body = '';
            req.on('data', c => body += c);
            req.on('end', () => {
                const out = [null]; dn(h[0], body || '[]', out);
                res.end(out[0] ? koffi.decode(out[0], 'char', -1) : '{}');
                if (out[0]) fs2(out[0]);
            });
            return;
        }

        // v1.2: 媒体扫描
        if (a === 'scan_media') {
            if (!sm) { res.end(JSON.stringify({ messages: [], has_more: false })); return; }
            const outJson = [null]; const outHasMore = [0];
            sm(h[0], JSON.stringify([p[1]]), parseInt(p[2]||'1'), parseInt(p[3]||'0'), parseInt(p[4]||'4102444800'), parseInt(p[5]||'200'), parseInt(p[6]||'0'), outJson, outHasMore);
            const r = {messages: outJson[0] ? JSON.parse(koffi.decode(outJson[0], 'char', -1)) : [], has_more: outHasMore[0] !== 0};
            if (outJson[0]) fs2(outJson[0]);
            res.end(JSON.stringify(r)); return;
        }

        // v1.2: 图片路径解析
        if (a === 'resolve_image') {
            if (!ri) { res.end('{}'); return; }
            const out = [null];
            const rv = ri(h[0], p[1], accountDir, out);
            const raw = out[0] ? koffi.decode(out[0], 'char', -1) : '{}';
            if (out[0]) fs2(out[0]);
            res.end(raw); return;
        }

        // v1.2: 批量图片路径解析
        if (a === 'resolve_image_batch') {
            if (!rib) { res.end('[]'); return; }
            let body = '';
            req.on('data', c => body += c);
            req.on('end', () => {
                const out = [null]; rib(h[0], body || '[]', out);
                res.end(out[0] ? koffi.decode(out[0], 'char', -1) : '[]');
                if (out[0]) fs2(out[0]);
            }); return;
        }

        res.end('[]');
    } catch(e) { res.end(JSON.stringify({error: e.message})); }
}).listen(port, () => process.stdout.write('READY\n'));

// 清理临时扁平目录（仅当本进程创建过）
function cleanupFlat() {
    if (!FLAT_DIR) return;
    try { fs.rmSync(FLAT_DIR, { recursive: true, force: true }); } catch(e) {}
}

// 优雅退出: 父进程断开时自动退出
process.on('uncaughtException', (err) => {
    if (err.code === 'EPIPE' || err.message.includes('EPIPE')) return;
    console.error('UNCAUGHT:', err.message);
});
process.on('exit', cleanupFlat);
process.on('SIGTERM', () => { cleanupFlat(); process.exit(0); });
process.on('SIGINT', () => { cleanupFlat(); process.exit(0); });
process.stdout.on('error', () => process.exit(0));
process.stderr.on('error', () => {});
