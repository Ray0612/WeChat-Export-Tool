"""
M89 — Schema 关系分析
任务 1-4 合并脚本
"""
import pymem, re, json, os, sys
from collections import defaultdict

PID = 6312
pm = pymem.Pymem(PID)

outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m89'
os.makedirs(outdir, exist_ok=True)

def save_path(name):
    return os.path.join(outdir, name)

# ================================================================
# Task 1 + 3: Extract ALL CREATE TABLE/INDEX statements
# ================================================================
print("Task 1+3: Extracting all schema statements from memory...")

all_schemas = {'tables': [], 'indexes': []}
seen_sql = set()

# Search for CREATE TABLE
for pat in [b'CREATE TABLE', b'CREATE INDEX']:
    is_table = b'TABLE' in pat
    try:
        addrs = pm.pattern_scan_all(pat, return_multiple=True)
        print(f"  '{pat.decode()}': {len(addrs)} occurrences")

        for addr in addrs[:500]:
            try:
                data = pm.read_bytes(addr, 1024)
                null_pos = data.find(b'\x00')
                sql = data[:null_pos].decode('utf-8', errors='replace')
                if sql in seen_sql:
                    continue
                seen_sql.add(sql)

                # Extract name
                if is_table:
                    m = re.search(r'CREATE TABLE\s+(?:\'main\'\.)?(?:"?)(\w+)(?:"?)\s*\(', sql)
                else:
                    m = re.search(r'CREATE(?: UNIQUE)? INDEX\s+(?:\'main\'\.)?(?:"?)(\w+)(?:"?)', sql)

                name = m.group(1) if m else 'unknown'
                entry = {'name': name, 'sql': sql, 'addr': addr}

                if is_table:
                    all_schemas['tables'].append(entry)
                else:
                    all_schemas['indexes'].append(entry)
            except:
                pass
    except:
        pass

print(f"  Unique tables: {len(all_schemas['tables'])}")
print(f"  Unique indexes: {len(all_schemas['indexes'])}")

# Save all SQL
with open(save_path('all_schema.sql'), 'w', encoding='utf-8') as f:
    for t in all_schemas['tables']:
        f.write(t['sql'] + '\n\n')
    for idx in all_schemas['indexes']:
        f.write(idx['sql'] + '\n\n')
print(f"  Saved to all_schema.sql")

# ================================================================
# Task 1: Table inventory
# ================================================================
print("\n\n--- Task 1: Table Inventory ---")

# Classify tables
classification = defaultdict(list)
for t in all_schemas['tables']:
    name = t['name'].lower()
    if name.startswith('msg_'):
        classification['Msg_'].append(t)
    elif any(k in name for k in ['session', 'conversation']):
        classification['Session'].append(t)
    elif any(k in name for k in ['contact', 'user', 'friend']):
        classification['Contact'].append(t)
    elif any(k in name for k in ['chatroom', 'member', 'group']):
        classification['ChatRoom'].append(t)
    elif any(k in name for k in ['delete']):
        classification['Delete'].append(t)
    elif any(k in name for k in ['timestamp', 'time']):
        classification['Time'].append(t)
    elif any(k in name for k in ['media', 'message_resource', 'message_fts']):
        classification['Media/FTS'].append(t)
    elif any(k in name for k in ['fts']):
        classification['FTS'].append(t)
    elif any(k in name for k in ['sync', 'backup', 'migrate']):
        classification['Sync'].append(t)
    else:
        classification['Other'].append(t)

# Save table inventory
lines = []
lines.append("=== Table Inventory ===\n")
lines.append(f"Total tables: {len(all_schemas['tables'])}\n")
lines.append(f"Total indexes: {len(all_schemas['indexes'])}\n\n")

for cat, tables in sorted(classification.items()):
    lines.append(f"\n--- {cat} ({len(tables)}) ---\n")
    for t in sorted(tables, key=lambda x: x['name']):
        lines.append(f"  {t['name']}\n")
        # Parse columns from SQL
        sql = t['sql']
        if sql.startswith('CREATE TABLE'):
            try:
                cols_start = sql.index('(') + 1
                depth = 1
                i = cols_start
                while depth > 0 and i < len(sql):
                    if sql[i] == '(':
                        depth += 1
                    elif sql[i] == ')':
                        depth -= 1
                    i += 1
                cols_def = sql[cols_start:i-1]
                # Check for REFERENCES
                for col in cols_def.split(','):
                    col = col.strip()
                    if col:
                        lines.append(f"    {col}\n")
            except:
                lines.append(f"    (parse error)\n")

with open(save_path('table_inventory.txt'), 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"  Saved to table_inventory.txt")

# ================================================================
# Task 2: Foreign key analysis
# ================================================================
print("\n\n--- Task 2: Foreign Key Analysis ---")

fk_lines = []
fk_lines.append("# Foreign Key Map\n\n")
fk_lines.append(f"Analyzed {len(all_schemas['tables'])} tables\n\n")

# Search for REFERENCES in SQL
for t in all_schemas['tables']:
    sql = t['sql']
    refs = re.findall(r'(REFERENCES\s+\w+\s*\([^)]+\))', sql, re.IGNORECASE)
    if refs:
        fk_lines.append(f"## {t['name']}\n")
        for ref in refs:
            fk_lines.append(f"- {ref}\n")
        fk_lines.append("\n")

# Specifically analyze real_sender_id
fk_lines.append("\n## real_sender_id Analysis\n\n")
fk_lines.append("Searching for 'real_sender_id' in all tables...\n\n")

real_sender_refs = []
for t in all_schemas['tables']:
    sql = t['sql']
    if 'real_sender_id' in sql or 'sender_id' in sql:
        fk_lines.append(f"### {t['name']}\n")
        fk_lines.append(f"```\n{sql}\n```\n\n")
        real_sender_refs.append(t)

# Also search for sender_id in indexes
fk_lines.append("### Indexes on sender fields\n\n")
for idx in all_schemas['indexes']:
    if 'sender' in idx['sql'].lower():
        fk_lines.append(f"- {idx['name']}: {idx['sql']}\n")

with open(save_path('foreign_key_map.md'), 'w', encoding='utf-8') as f:
    f.writelines(fk_lines)
print(f"  Saved to foreign_key_map.md")

# ================================================================
# Task 3: Msg_ table statistics
# ================================================================
print("\n\n--- Task 3: Msg_ Table Stats ---")

msg_tables = [t for t in all_schemas['tables'] if t['name'].startswith('Msg_')]
print(f"  Msg_ tables: {len(msg_tables)}")

# Group Msg_ tables by hash
msg_stats = []
for t in msg_tables:
    name = t['name']
    hash_val = name[4:]  # Remove "Msg_" prefix
    msg_stats.append({
        'table': name,
        'hash': hash_val,
        'columns': [],
        'indexes': [],
    })

# Add index info
for idx in all_schemas['indexes']:
    for stat in msg_stats:
        if stat['table'] in idx['sql']:
            stat['indexes'].append({
                'name': idx['name'],
                'sql': idx['sql']
            })
            break

msg_stats.sort(key=lambda x: x['table'])

# Save
with open(save_path('msg_table_stats.json'), 'w', encoding='utf-8') as f:
    json.dump(msg_stats, f, ensure_ascii=False, indent=2)
print(f"  Saved to msg_table_stats.json")

# ================================================================
# Task 4: Session hash mapping
# ================================================================
print("\n\n--- Task 4: Session Hash Mapping ---")

# The Msg_<hash> table names use a 32-char hex hash
# Try to find the mapping to session names

# Strategy 1: Check if hash matches attach directories
attach_dir = r"D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\msg\attach"
attach_hashes = set()
if os.path.exists(attach_dir):
    for d in os.listdir(attach_dir):
        if len(d) == 32 and all(c in '0123456789abcdef' for c in d.lower()):
            attach_hashes.add(d.lower())

# Strategy 2: Check if hash matches cache directories
cache_dir = r"D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\cache"
cache_hashes = set()
if os.path.exists(cache_dir):
    for year_month in os.listdir(cache_dir):
        msg_dir = os.path.join(cache_dir, year_month, 'Message')
        if os.path.exists(msg_dir):
            for d in os.listdir(msg_dir):
                if len(d) == 32 and all(c in '0123456789abcdef' for c in d.lower()):
                    cache_hashes.add(d.lower())

# Strategy 3: Check if hash appears in the backup session list
hit19_data_path = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m85\m85_hit19_raw.bin'
backup_wxids = set()
if os.path.exists(hit19_data_path):
    hit19_data = open(hit19_data_path, 'rb').read()
    for m in re.finditer(rb'wxid_[a-zA-Z0-9_]{10,30}', hit19_data):
        backup_wxids.add(m.group().decode())

session_lines = []
session_lines.append("# Session Hash Mapping\n\n")
session_lines.append(f"Total Msg_ tables: {len(msg_tables)}\n\n")

# Match hashes to directories
matched_attach = []
matched_cache = []
unmatched = []

for stat in msg_stats:
    h = stat['hash'].lower()
    if h in attach_hashes:
        matched_attach.append(h)
    if h in cache_hashes:
        matched_cache.append(h)
    if h not in attach_hashes and h not in cache_hashes:
        unmatched.append(h)

session_lines.append(f"Matched to attach directories: {len(matched_attach)}/{len(msg_tables)}\n")
session_lines.append(f"Matched to cache directories: {len(matched_cache)}/{len(msg_tables)}\n")
session_lines.append(f"Unmatched: {len(unmatched)}\n\n")

# Show a few examples
session_lines.append("## Sample Hash Mapping\n\n")
for stat in msg_tables[:10]:
    h = stat['name'][4:].lower()
    session_lines.append(f"- Table: {stat['name']}\n")
    session_lines.append(f"  Hash: {h}\n")
    if h in attach_hashes:
        session_lines.append(f"  Attach dir: ✅ FOUND ({attach_dir}/.../{h}/)\n")
    if h in cache_hashes:
        session_lines.append(f"  Cache dir: ✅ FOUND\n")

# Known mapping from backup data
session_lines.append("\n## wxid from backup cache\n\n")
session_lines.append(f"Backup wxids found: {len(backup_wxids)}\n")
for wxid in sorted(backup_wxids)[:20]:
    session_lines.append(f"  - {wxid}\n")

with open(save_path('session_hash_mapping.md'), 'w', encoding='utf-8') as f:
    f.writelines(session_lines)
print(f"  Saved to session_hash_mapping.md")

# ================================================================
# Also search for Session/Contact tables in other DB pages in memory
# ================================================================
print("\n\n--- Bonus: Searching for Session/Contact DB schemas in memory ---")

# Search for CREATE TABLE statements from session.db or contact.db
# These would have DIFFERENT page_count values in their page 1
for kw in ['CREATE TABLE Session', 'CREATE TABLE Contact', 'CREATE TABLE User',
            'CREATE TABLE ChatRoom', 'CREATE TABLE Member', 'CREATE TABLE Conversation',
            'CREATE TABLE Friend', 'CREATE TABLE Session', 'CREATE TABLE AddMsg',
            'CREATE TABLE BizChat', 'CREATE TABLE ChatRoomMember']:
    try:
        addrs = pm.pattern_scan_all(kw.encode(), return_multiple=True)
        if addrs:
            print(f"  '{kw}': {len(addrs)} matches!")
            for a in addrs[:3]:
                data = pm.read_bytes(a, 512)
                null_pos = data.find(b'\x00')
                sql = data[:null_pos].decode('utf-8', errors='replace')
                print(f"    0x{a:x}: {sql[:150]}")
    except:
        pass

print("\nDone!")
