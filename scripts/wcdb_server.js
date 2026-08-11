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
try {
    koffi.load(path.join(DLL, 'WCDB.dll'));
    koffi.load(path.join(DLL, 'SDL2.dll'));
    const _lib = koffi.load(path.join(DLL, 'wcdb_api.dll'));
    const ip = _lib.func('int32 InitProtection(const char* path)');
    const wi = _lib.func('int32 wcdb_init()');
    ip(DLL);
    if (wi() !== 0) { console.error('INIT_FAIL'); process.exit(1); }
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

// ── 绑定函数 ──
const oa = lib.func('int32 wcdb_open_account(const char* path, const char* key, _Out_ int64* h)');
const ca = lib.func('int32 wcdb_close_account(int64 h)');
const gs = lib.func('int32 wcdb_get_sessions(int64 h, _Out_ void** out)');
const gm = lib.func('int32 wcdb_get_messages(int64 h, const char* username, int32 limit, int32 offset, _Out_ void** out)');
const gc = lib.func('int32 wcdb_get_message_count(int64 h, const char* username, _Out_ int32* out)');
const dn = lib.func('int32 wcdb_get_display_names(int64 h, const char* json, _Out_ void** out)');
const fs2 = lib.func('void wcdb_free_string(void* p)');

// v1.2: 媒体相关 API
const sm = lib.func('int32 wcdb_scan_media_stream(int64 h, const char* sessionIdsJson, int32 mediaType, int64 begin, int64 end, int32 limit, int32 offset, _Out_ void** outJson, _Out_ int32* outHasMore)');
const ri = lib.func('int32 wcdb_resolve_image_hardlink(int64 h, const char* md5, const char* accountDir, _Out_ void** outJson)');
const rib = lib.func('int32 wcdb_resolve_image_hardlink_batch(int64 h, const char* requestsJson, _Out_ void** outJson)');

const h = [BigInt(0)];
if (oa(sessionDb, key, h) !== 0) { console.error('OPEN_FAIL'); process.exit(1); }

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
            const outJson = [null]; const outHasMore = [0];
            sm(h[0], JSON.stringify([p[1]]), parseInt(p[2]||'1'), parseInt(p[3]||'0'), parseInt(p[4]||'4102444800'), parseInt(p[5]||'200'), parseInt(p[6]||'0'), outJson, outHasMore);
            const r = {messages: outJson[0] ? JSON.parse(koffi.decode(outJson[0], 'char', -1)) : [], has_more: outHasMore[0] !== 0};
            if (outJson[0]) fs2(outJson[0]);
            res.end(JSON.stringify(r)); return;
        }

        // v1.2: 图片路径解析
        if (a === 'resolve_image') {
            const out = [null];
            const rv = ri(h[0], p[1], accountDir, out);
            const raw = out[0] ? koffi.decode(out[0], 'char', -1) : '{}';
            if (out[0]) fs2(out[0]);
            res.end(raw); return;
        }

        // v1.2: 批量图片路径解析
        if (a === 'resolve_image_batch') {
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

// 优雅退出: 父进程断开时自动退出
process.on('uncaughtException', (err) => {
    if (err.code === 'EPIPE' || err.message.includes('EPIPE')) return;
    console.error('UNCAUGHT:', err.message);
});
process.stdout.on('error', () => process.exit(0));
process.stderr.on('error', () => {});
