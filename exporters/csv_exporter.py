# -*- coding: utf-8 -*-
"""CSV exporter"""
import csv, datetime

def export(msgs, path, my_name="我", title=None, session_title=None):
    f = open(path,'w',newline='',encoding='utf-8-sig')
    w = csv.writer(f)
    w.writerow(['时间','发送者','消息内容','类型'])
    for m in msgs:
        ts=m.get('create_time','');c=m.get('message_content','')or''
        sr=m.get('sender_username','');im=m.get('is_mine',0)
        lt=int(m.get('local_type',0))
        if lt not in(1,244813135921)or not c.strip():continue
        t=datetime.datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')if ts.isdigit()else ts
        dn='我'if im else sr
        w.writerow([t,dn,c,'文字'if lt==1 else'ZSTD'])
    f.close()
    return path
