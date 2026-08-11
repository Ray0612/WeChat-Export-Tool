# -*- coding: utf-8 -*-
"""HTML exporter - Telegram style bubbles，支持文件级图片导出"""
import datetime, html as h, os, base64

def export(msgs, path, my_name="我", title="聊天记录", img_dir=None):
    """导出 HTML。img_dir 指定后，图片保存到该目录并用相对路径引用"""
    msg_html = ""
    last_date = None
    img_idx = 0
    for m in msgs:
        ts = m.get('create_time',''); c = m.get('message_content','') or ''
        sr = m.get('sender_username',''); im = m.get('is_mine',0)
        lt = int(m.get('local_type',0))
        if lt == 47:
            text = '[表情]'
        elif lt == 3 and m.get('image_data'):
            img_idx += 1
            ext = m.get('image_ext', 'png')
            if img_dir:
                # 保存到文件并用相对路径引用
                safe_name = f'img_{img_idx}.{ext}'
                img_path = os.path.join(img_dir, safe_name)
                try:
                    with open(img_path, 'wb') as f:
                        f.write(base64.b64decode(m['image_data']))
                except: pass
                text = f'<img src="图片/{safe_name}" alt="图片" loading="lazy">'
            else:
                text = f'<img src="data:image/{ext};base64,{m["image_data"]}" alt="图片" loading="lazy">'
        elif lt == 3:
            text = '[图片]'
        elif lt in (1,244813135921) and c.strip():
            text = h.escape(c).replace('\n','<br>')
        else:
            continue
        mt = datetime.datetime.fromtimestamp(int(ts)) if ts.isdigit() else None
        if not mt: continue
        ds = mt.strftime('%Y-%m-%d'); tm = mt.strftime('%H:%M:%S')
        dn = my_name if im else sr; side = "right" if im else "left"
        if ds != last_date:
            if last_date is not None: msg_html += '\n'
            msg_html += '      <div class="date-sep"><span>'+ds+'</span></div>\n'
            last_date = ds
        msg_html += '      <div class="msg '+side+'">\n        <div class="sender">'+h.escape(dn)+'  <span class="time">'+tm+'</span></div>\n        <div class="bubble">'+text+'</div>\n      </div>\n'

    total = len(msgs)
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>'''+h.escape(title)+'''</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"PingFang SC","Microsoft YaHei",system-ui,-apple-system,sans-serif;background:#e8ecef;color:#1f2a37}
.page{max-width:860px;margin:0 auto;padding:12px 16px;min-height:100vh;display:flex;flex-direction:column}
.header{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:14px 20px;flex-shrink:0;margin-bottom:12px;position:sticky;top:12px;z-index:10}
.title{font-size:16px;font-weight:600;display:inline}
.meta{color:#6b7280;font-size:13px;display:inline;margin-left:12px}
.controls{display:flex;align-items:center;gap:8px;margin-top:8px;flex-wrap:wrap}
.controls input{border-radius:8px;border:1px solid #e5e7eb;padding:6px 10px;font-size:13px;font-family:inherit}
.controls input[type="search"]{width:220px}
.date-sep{text-align:center;margin:16px 0 12px}
.date-sep span{display:inline-block;background:rgba(0,0,0,.06);color:#6b7280;font-size:12px;padding:4px 14px;border-radius:12px}
.msg{display:flex;flex-direction:column;margin-bottom:10px;max-width:80%}
.msg.left{align-items:flex-start}
.msg.right{align-items:flex-end;margin-left:auto}
.msg .sender{font-size:12px;color:#6b7280;margin-bottom:3px;padding:0 4px}
.msg .sender .time{font-size:11px;opacity:.7}
.msg .bubble{padding:10px 14px;font-size:14px;line-height:1.6;word-break:break-word;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.msg.left .bubble{background:#fff;color:#000;border-radius:12px;border-bottom-left-radius:4px}
.msg.right .bubble{background:#6ab5ff;color:#fff;border-radius:12px;border-bottom-right-radius:4px}
.msg.right .sender{text-align:right}
.msg .bubble img{max-width:300px;max-height:300px;border-radius:4px;display:block}
.msg-list{flex:1;padding:4px 0}
.highlight{background:#fef08a;border-radius:2px;padding:0 1px}
.msg.hidden{display:none}
@media(max-width:600px){.page{padding:8px}.msg{max-width:90%}.controls input[type="search"]{width:160px}}
</style>
</head>
<body>
<div class="page">
<div class="header">
<div><h1 class="title">'''+h.escape(title)+'''</h1></div>
<div class="controls">
<input id="searchInput" type="search" placeholder="搜索消息..." oninput="filterMessages()" />
</div>
</div>
<div class="msg-list" id="msgList">
'''+msg_html+'''  </div>
</div>
<script>
function filterMessages(){var kw=document.getElementById('searchInput').value.trim().toLowerCase();var msgs=document.querySelectorAll('.msg');for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent.toLowerCase();if(!kw||t.indexOf(kw)>-1){msgs[i].classList.remove('hidden')}else{msgs[i].classList.add('hidden')}}
var dates=document.querySelectorAll('.date-sep');for(var i=0;i<dates.length;i++){var n=dates[i].nextElementSibling;var hv=false;while(n&&!n.classList.contains('date-sep')){if(n.classList.contains('msg')&&!n.classList.contains('hidden')){hv=true;break}n=n.nextElementSibling}
dates[i].style.display=hv?'':'none'}}
</script>
</body>
</html>'''
    with open(path,'w',encoding='utf-8') as f: f.write(html)
    return path
