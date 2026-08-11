// 图片解密助手 — 从 wx_key.dll 获取 code → 推导 AES Key → 解密 + WXGF 剥壳
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const { execSync, execFileSync } = require('child_process');

const SCRIPT_DIR = __dirname;
const PROJECT_DIR = path.resolve(SCRIPT_DIR, '..');

// 资源路径: 优先本地打包资源，其次 WeFlow 安装目录
const NATIVE_CANDIDATES = [
    path.join(PROJECT_DIR, 'resources', 'native', 'weflow-image-native-win32-x64.node'),
    'C:/Users/OK/AppData/Local/Programs/WeFlow/resources/resources/wedecrypt/win32/x64/weflow-image-native-win32-x64.node',
];
const DLL_CANDIDATES = [
    path.join(PROJECT_DIR, 'dll', 'wx_key.dll'),
    path.join(PROJECT_DIR, 'APP', 'WeChatExport', 'dll', 'wx_key.dll'),
    'C:/Users/OK/AppData/Local/Programs/WeFlow/resources/resources/key/win32/x64/wx_key.dll',
];
const FFMPEG_CANDIDATES = [
    path.join(PROJECT_DIR, 'resources', 'bin', 'ffmpeg.exe'),
    'C:/Users/OK/AppData/Local/Programs/WeFlow/resources/app.asar.unpacked/node_modules/ffmpeg-static/ffmpeg.exe',
];

const filepath = process.argv[2];
if (!filepath || !fs.existsSync(filepath)) process.exit(1);

let native = null, koffi = null;
try {
    const np = NATIVE_CANDIDATES.find(p => fs.existsSync(p));
    if (np) native = require(np);
} catch(e) {}
try {
    koffi = require(path.join(SCRIPT_DIR, 'node_modules', 'koffi'));
} catch(e) {}

if (!native) process.exit(2);

try {
    // 1. 从 wx_key.dll 获取 code
    let code = 0, wxid = 'unknown';
    if (koffi) {
        const dllPath = DLL_CANDIDATES.find(p => fs.existsSync(p));
        if (dllPath) {
            try {
                const lib = koffi.load(dllPath);
                const fn = lib.func('bool GetImageKey(char* buf, int size)');
                const buf = Buffer.alloc(8192);
                if (fn(buf, buf.length)) {
                    const d = JSON.parse(buf.toString('utf-8').replace(/\0/g, '').trim());
                    if (d.accounts && d.accounts[0]) {
                        code = d.accounts[0].keys?.[0]?.code || 0;
                        wxid = d.accounts[0].wxid || 'unknown';
                    }
                }
            } catch(e) {}
        }
    }

    // 2. 从路径提取 wxid
    const wxidMatch = filepath.match(/(wxid_[a-z0-9]+)/i);
    if (wxidMatch) {
        const raw = wxidMatch[1];
        const parts = raw.split('_');
        wxid = parts.length >= 3 ? parts.slice(0, 2).join('_') : raw;
    }

    // 3. deriveImageKeys
    const md5 = crypto.createHash('md5').update(String(code) + wxid).digest('hex');
    const xorKey = code & 0xFF;
    const aesKey = md5.substring(0, 16);

    // 4. 解密
    const r = native.decryptDatNative(filepath, xorKey, aesKey);
    if (!r || !r.data) process.exit(3);

    let data = Buffer.isBuffer(r.data) ? r.data : Buffer.from(r.data);
    const isWxgf = r.isWxgf || r.is_wxgf || data.slice(0, 4).toString() === 'wxgf';

    // 5. WXGF 剥壳
    if (isWxgf) {
        let found = false;
        for (let i = 4; i < Math.min(data.length - 12, 4096); i++) {
            if (data[i] === 0xFF && data[i+1] === 0xD8 && data[i+2] === 0xFF) {
                data = data.slice(i); found = true; break;
            }
            if (data[i] === 0x89 && data[i+1] === 0x50 && data[i+2] === 0x4E) {
                data = data.slice(i); found = true; break;
            }
        }

        if (!found) {
            const ffmpeg = FFMPEG_CANDIDATES.find(p => fs.existsSync(p));
            if (ffmpeg) {
                const tmpRaw = path.join(require('os').tmpdir(), 'wx_decode_raw_' + Date.now() + '.hevc');
                const tmpOut = path.join(require('os').tmpdir(), 'wx_decode_out_' + Date.now() + '.jpg');
                try {
                    fs.writeFileSync(tmpRaw, data);
                    execFileSync(ffmpeg, ['-y', '-i', tmpRaw, '-update', '1', '-q:v', '2', tmpOut], {timeout: 30000, stdio: 'ignore'});
                    if (fs.existsSync(tmpOut) && fs.statSync(tmpOut).size > 1000) {
                        data = fs.readFileSync(tmpOut);
                    }
                } catch(e) {}
                try { fs.unlinkSync(tmpRaw); } catch(e) {}
                try { fs.unlinkSync(tmpOut); } catch(e) {}
            }
        }
    }

    // 6. 检测格式
    let ext = (r.ext || '').replace(/^\./, '');
    if (!ext) {
        if (data[0] === 0xFF && data[1] === 0xD8) ext = 'jpg';
        else if (data[0] === 0x89 && data[1] === 0x50) ext = 'png';
        else if (data[0] === 0x47 && data[1] === 0x49) ext = 'gif';
        else if (data[0] === 0x52 && data[1] === 0x49) ext = 'webp';
    }

    if (ext) {
        const buf = Buffer.isBuffer(data) ? data : Buffer.from(data);
        process.stdout.write(ext + '\n' + buf.toString('base64'));
        process.exit(0);
    }
} catch(e) {}

process.exit(4);
