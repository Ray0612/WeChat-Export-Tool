"""
DB Export 主入口

用法:
    # 已知密钥直接导出
    python main.py --key_hex <64-char-hex>

    # 尝试自动推导密钥
    python main.py --auto

    # 只扫描 config 提取密钥材料
    python main.py --scan-config
"""
import os, sys, json, argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = r"D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\db_storage\message\message_0.db"
CONFIG_DIR = r"D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\config"

def scan_config():
    """扫描配置文件，寻找密钥材料"""
    from db_exporter.config_reader import search_uin, search_key_candidates, extract_uin_from_login

    print("=" * 60)
    print("扫描配置文件中的密钥材料")
    print("=" * 60)

    uins = search_uin(CONFIG_DIR)
    if uins:
        print(f"\n找到 {len(uins)} 个 UIN 候选:")
        for utype, val, path in uins[:10]:
            print(f"  [{utype}] {val} <- {os.path.basename(path)}")

    candidates = search_key_candidates(CONFIG_DIR)
    print(f"\n密钥派生材料:")
    for key, vals in candidates.items():
        if vals:
            print(f"  {key}: {', '.join(v[0] for v in vals[:5])}")

    # Try login_configv2
    login_path = os.path.join(CONFIG_DIR, 'login_configv2')
    if os.path.exists(login_path):
        data = open(login_path, 'rb').read()
        uins = extract_uin_from_login(data)
        if uins:
            print(f"\n从 login_configv2 解析出 UIN: {list(uins)[:10]}")

    print("\nDone")

def try_auto():
    """尝试自动推导密钥"""
    from db_exporter.unlock import try_keys, derive_from_wxid

    # 已知的 wxid
    wxid = 'wxid_caccoealsdbj12'

    print("=" * 60)
    print("尝试自动推导密钥")
    print("=" * 60)

    # 尝试从 wxid 推导
    result = derive_from_wxid(DB_PATH, wxid)
    if result.get('success'):
        print(f"\n!!! 密钥找到: {result}")
        return result

    # 从之前的 hex 候选尝试
    candidates = [
        "D286E19EE90CDAA02E09209CB8735D878A9A096E3550B12CFA36C1ADA369DF2B",
        "EC8AE087F807F78C271E37BDB073518F8095016D1D70B916FA27CABFBC26CE31",
    ]
    result = try_keys(DB_PATH, candidates)
    if result.get('success'):
        print(f"\n!!! 密钥找到: {result}")
        return result

    print("\n未找到密钥，需要进一步分析。")
    print(f"尝试 --key_hex <64-char-hex> 直接指定密钥。")
    return {'success': False}

def export_with_key(key_hex):
    """使用已知密钥导出所有消息"""
    from db_exporter.schema import MessageDB
    from db_exporter.export import export_txt, export_markdown

    print("=" * 60)
    print(f"使用密钥: {key_hex[:16]}...{key_hex[-16:]}")
    print("=" * 60)

    try:
        db = MessageDB(DB_PATH, key_hex=key_hex)
        print(f"连接成功! 发现 {db.table_count} 个表")

        tables = db.get_tables()
        print(f"\n表列表:")
        for name, ttype in tables:
            print(f"  {ttype}: {name}")

        print(f"\n按会话聚合消息...")
        sessions = db.get_sessions()
        print(f"共 {len(sessions)} 个会话")

        # 导出每个会话
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'experiments', 'exports')
        os.makedirs(out_dir, exist_ok=True)

        for session_name, msgs in sessions.items():
            if len(msgs) < 2:
                continue
            messages = [db.normalize_message(m) for m in msgs]
            export_txt(session_name, messages, out_dir)
            export_markdown(session_name, messages, out_dir)
            print(f"  导出: {session_name[:30]} ({len(msgs)} 条)")

        print(f"\n导出完成! 文件在: {out_dir}")

    except ValueError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='微信聊天记录数据库导出')
    parser.add_argument('--key_hex', help='64-char hex key')
    parser.add_argument('--auto', action='store_true', help='自动推导密钥')
    parser.add_argument('--scan-config', action='store_true', help='扫描配置文件')

    args = parser.parse_args()

    if args.key_hex:
        export_with_key(args.key_hex)
    elif args.auto:
        try_auto()
    elif args.scan_config:
        scan_config()
    else:
        parser.print_help()
