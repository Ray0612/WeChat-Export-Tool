"""
M90 — contact.db / session.db 联系人映射分析
"""
import pymem, re, json, os, sys, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PID = 6312
pm = pymem.Pymem(PID)
outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m90'
os.makedirs(outdir, exist_ok=True)

# ================================================================
# Task 1: Find Contact/User table schemas in memory
# ================================================================
print("=" * 60)
print("M90 — Contact & Session DB Schema Analysis")
print("=" * 60)

print("\n--- Task 1: Searching for Contact/User/ID tables ---")

contact_patterns = [
    b'CREATE TABLE Contact', b'CREATE TABLE Friend', b'CREATE TABLE User',
    b'CREATE TABLE Member', b'CREATE TABLE ChatRoomMember',
    b'CREATE TABLE ChatRoom', b'CREATE TABLE ContactHeadImg',
    b'CREATE TABLE ABContact', b'CREATE TABLE HardLink',
    b'CREATE TABLE IDTable', b'CREATE TABLE Session',
    b'CREATE TABLE Conversation',
]

all_schemas = []

for pat in contact_patterns:
    try:
        addrs = pm.pattern_scan_all(pat, return_multiple=True)
        if addrs:
            name = pat.decode()
            print(f"  '{name}': {len(addrs)} matches!")
            for a in addrs[:5]:
                data = pm.read_bytes(a, 1024)
                null_pos = data.find(b'\x00')
                sql = data[:null_pos].decode('utf-8', errors='replace').strip()
                print(f"    -> {sql[:150]}...")
                all_schemas.append({'addr': a, 'sql': sql, 'source': name})
    except:
        pass

# Also search for contact-related patterns in WeChatAppEx
print("\n--- Also checking WeChatAppEx ---")
import psutil
appex_pid = None
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    name = proc.info['name'] or ''
    exe = proc.info.get('exe', '') or ''
    if 'wechatappex' in name.lower() and 'xwechat' in exe.lower():
        appex_pid = proc.info['pid']
        break

if appex_pid:
    try:
        pm2 = pymem.Pymem(appex_pid)
        for pat in [b'CREATE TABLE Contact', b'CREATE TABLE Friend']:
            addrs = pm2.pattern_scan_all(pat, return_multiple=True)
            if addrs:
                for a in addrs[:3]:
                    data = pm2.read_bytes(a, 512)
                    null_pos = data.find(b'\x00')
                    sql = data[:null_pos].decode('utf-8', errors='replace')
                    print(f"  WeChatAppEx: {sql[:150]}")
    except Exception as e:
        print(f"  WeChatAppEx error: {e}")

# ================================================================
# Task 2: Search for wxid/chatroom strings near INTEGER PRIMARY KEY
# ================================================================
print("\n--- Task 2: Searching for wxid/chatroom in schema ---")

# We know SessionTable has username = wxid/chatroom
# Look for INTEGER PRIMARY KEY AUTOINCREMENT tables that might link to it
for kw in [b'user_id', b'username_id', b'contact_id', b'sender_id',
           b'_id INTEGER PRIMARY', b'id INTEGER PRIMARY',
           b'friend_id', b'member_id']:
    try:
        addrs = pm.pattern_scan_all(kw, return_multiple=True)
        if addrs:
            print(f"  '{kw.decode()}': {len(addrs)} hits")
            # Show the CREATE TABLE containing this
            for a in addrs[:3]:
                # Search backwards for CREATE TABLE
                search_start = max(0, a - 256)
                ctx = pm.read_bytes(search_start, 512 + 256)
                create_pos = ctx.rfind(b'CREATE TABLE')
                if create_pos >= 0:
                    sql_bytes = ctx[create_pos:]
                    null_pos = sql_bytes.find(b'\x00')
                    sql = sql_bytes[:null_pos].decode('utf-8', errors='replace')
                    print(f"    TABLE: {sql[:200]}")
    except:
        pass

# ================================================================
# Task 3: Find real_sender_id → wxid mapping
# ================================================================
print("\n--- Task 3: Searching for real_sender_id → wxid mapping ---")

# Strategy: search for the Msg_<hash>_SENDERID index
# which is on real_sender_id
# Then look for a table that has "id INTEGER PRIMARY KEY" AND "wxid" or "username"

# Check session.db schema - look for the mapping table
# We already know SessionTable has username = wxid
# The question is: does any table have (id, wxid) pairs?

# Search for "id INTEGER PRIMARY KEY,username" or similar
for pat in [b'id INTEGER PRIMARY KEY,username',
            b'id INTEGER PRIMARY KEY AUTOINCREMENT,username',
            b'id INTEGER PRIMARY KEY AUTOINCREMENT,wxid',
            b'id INTEGER PRIMARY KEY,wxid']:
    try:
        addrs = pm.pattern_scan_all(pat, return_multiple=True)
        if addrs:
            print(f"  Found '{pat.decode()}': {len(addrs)}")
            for a in addrs[:3]:
                search_start = max(0, a - 256)
                ctx = pm.read_bytes(search_start, 768)
                create_pos = ctx.rfind(b'CREATE TABLE')
                if create_pos >= 0:
                    sql = ctx[create_pos:].split(b'\x00')[0].decode('utf-8', errors='replace')
                    print(f"    {sql[:300]}")
    except:
        pass

# Also look in contact.db tables
# Search for any table with both 'id' and 'wxid' or 'name' or 'nick'
for pat in [b'wxid', b'nickname', b'display_name', b'alias_name', b'remark']:
    try:
        addrs = pm.pattern_scan_all(pat, return_multiple=True)
        if addrs:
            # Show first CREATE TABLE containing this
            for a in addrs[:3]:
                search_start = max(0, a - 512)
                ctx = pm.read_bytes(search_start, 1024)
                create_pos = ctx.rfind(b'CREATE TABLE')
                if create_pos >= 0:
                    sql_bytes = ctx[create_pos:]
                    null_pos = sql_bytes.find(b'\x00')
                    sql = sql_bytes[:null_pos].decode('utf-8', errors='replace')
                    # Only show if this is a table definition with id field
                    if 'id INTEGER' in sql or 'ID INTEGER' in sql:
                        print(f"\n  '{pat.decode()}':")
                        print(f"    {sql[:300]}")
    except:
        pass

# ================================================================
# Task 4: Build sender mapping from known data
# ================================================================
print("\n--- Task 4: Building sender mapping ---")

# We have SessionTable.username = wxid/chatroom
# We have Msg_<md5> tables
# The mapping is MD5(username) → Msg_<md5>

# From our backup data (hit19), we have pairs:
# chatroom ID → wxid list (members)
# Let's build a mapping from those

hit19_path = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m85\m85_hit19_raw.bin'
hit19_data = open(hit19_path, 'rb').read()

chatrooms = set(re.findall(rb'[0-9]+@chatroom', hit19_data))
wxids = set(re.findall(rb'wxid_[a-zA-Z0-9_]{10,30}', hit19_data))

# Build sender mapping from chatrooms we can verify
sender_map = {}

# Add wxid entries (from our config)
config_path = r'C:\Users\OK\Desktop\wechat_v4_export_research\config.json'
if os.path.exists(config_path):
    import json as j
    cfg = j.load(open(config_path, 'r', encoding='utf-8'))
    nick_map = cfg.get('nickname_map', {})
    for wxid, nick in nick_map.items():
        sender_map[str(wxid)] = {
            'wxid': wxid,
            'nickname': nick,
            'source': 'config'
        }

# Save what we have so far
output = {
    'sender_mapping': sender_map,
    'known_chatrooms': [c.decode() for c in sorted(chatrooms)],
    'known_wxids': [w.decode() for w in sorted(wxids)],
    'mapping_method': 'MD5(username) → Msg_<hash>',
    'unresolved': 'real_sender_id (INTEGER FK) table still not found - likely in contact.db or session.db',
}

with open(os.path.join(outdir, 'sender_mapping.json'), 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"  Saved sender_mapping.json with {len(sender_map)} entries")

# Also check the actual database files on disk for reference
# (We can't read them encrypted, but we can check their sizes)
print("\n--- Database file sizes (for reference) ---")
db_dir = r"D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\db_storage"
for db_name in ['contact/contact.db', 'session/session.db', 'general/general.db',
                'message/message_0.db', 'hardlink/hardlink.db']:
    path = os.path.join(db_dir, db_name)
    if os.path.exists(path):
        sz = os.path.getsize(path)
        print(f"  {db_name}: {sz/1024:.0f}KB")

print("\nDone!")
