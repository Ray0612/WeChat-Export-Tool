# -*- coding: utf-8 -*-
"""PDF exporter - final version"""
import datetime, base64
from io import BytesIO

def export(msgs, path, my_name="我", title="聊天记录"):
    from fpdf import FPDF
    pdf=FPDF();pdf.add_page()
    pdf.add_font("YH","","C:/Windows/Fonts/msyh.ttc")
    pdf.add_font("YHB","","C:/Windows/Fonts/msyhbd.ttc")
    pw=pdf.w-2*pdf.l_margin;sb,rb=(106,181,255),(228,228,232)

    def rc(x,y,w,h,r,f):
        r=min(r,h/2,w/2);pdf.set_fill_color(*f);pdf.set_draw_color(*f)
        pdf.rect(x,y+r,w,h-2*r,'F');pdf.rect(x+r,y,w-2*r,h,'F');d=2*r
        for cx,cy in[(x,y),(x+w-d,y),(x,y+h-d),(x+w-d,y+h-d)]:pdf.ellipse(cx,cy,d,d,'F')

    pdf.set_font("YHB","",12);pdf.set_text_color(31,42,55)
    pdf.cell(pw,8,title+"  \xb7  "+str(len(msgs))+" msgs",align='C');pdf.ln(8)
    pdf.set_draw_color(200,205,212);pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin,pdf.get_y(),pdf.l_margin+pw,pdf.get_y());pdf.ln(4)

    labels={3:'[图片]',34:'[语音]',43:'[视频]',47:'[表情]',42:'[名片]',48:'[位置]',49:'[链接]',50:'[通话]',10000:'[通知]'}
    ld=None
    for m in msgs:
        ts=m.get('create_time','');c=m.get('message_content','')or''
        sr=m.get('sender_username','');im=m.get('is_mine',0)
        lt=int(m.get('local_type',0))
        mt=datetime.datetime.fromtimestamp(int(ts))if ts.isdigit()else None
        if not mt:continue
        ds=mt.strftime('%Y-%m-%d');tm=mt.strftime('%H:%M:%S')
        dn=my_name if im else sr

        # ── 日期 ──
        if ds!=ld:
            y=pdf.get_y();pdf.set_font("YH","",6)
            dw=pdf.get_string_width(ds)+4;rc((pdf.w-dw)/2,y,dw,5,2.5,(220,224,230))
            pdf.set_text_color(120,125,135);pdf.set_xy((pdf.w-dw)/2,y);pdf.cell(dw,5,ds,align='C')
            pdf.ln(4);ld=ds

        # ── 图片 ──
        if lt==3 and m.get('image_data'):
            try:
                pdf.set_font("YH","",7);pdf.set_text_color(120,125,135)
                if im:
                    nw=pdf.get_string_width(dn+"  "+tm)
                    pdf.set_x(pdf.l_margin+pw-nw-4);pdf.cell(nw+8,4,dn+"  "+tm,align='R')
                else:
                    pdf.set_x(pdf.l_margin+4);pdf.cell(pw,4,dn+"  "+tm)
                pdf.ln(5)
                img_bytes=base64.b64decode(m['image_data'])
                img_w=min(140,pw*0.5);img_io=BytesIO(img_bytes)
                img_x=pw-pdf.l_margin-img_w if im else pdf.l_margin
                if pdf.get_y()+img_w+10>pdf.h-25:pdf.add_page()
                pdf.image(img_io,x=img_x,w=img_w)
                pdf.ln(4)
            except:pass
            continue

        # ── 获取显示文字 ──
        if lt in(1,244813135921):
            text=c.strip()
        else:
            text=labels.get(lt,f'[类型{lt}]')
        if not text:continue

        lines=[l.strip() for l in text.split('\n')]
        lines=[l for l in lines if l]
        if not lines:continue

        # ── 用 multi_cell 精确计算气泡宽度和高度 ──
        pdf.set_font("YH","",11)
        px=3;mx=pw*0.6
        # 先按最大 text 宽度确定气泡宽
        max_line_w=max(pdf.get_string_width(l)for l in lines)if lines else 0
        bw=min(mx,max_line_w+px*2+4)

        # dry_run 获取精确换行结果
        text_for_render='\n'.join(lines)
        rendered=pdf.multi_cell(bw-px*2,6,text_for_render,dry_run=True,output='LINES')
        th=len(rendered)*6+2

        # ── 过长时不画气泡 ──
        lines_per_page=int((pdf.h-25-pdf.get_y())/(pdf.font_size*1.2))
        long_text=len(rendered)>lines_per_page

        # 发送者 + 时间
        pdf.set_font("YH","",7);pdf.set_text_color(120,125,135)
        if im:
            nw=pdf.get_string_width(dn+"  "+tm)
            pdf.set_x(pdf.l_margin+pw-nw-4);pdf.cell(nw+8,4,dn+"  "+tm,align='R')
        else:
            pdf.set_x(pdf.l_margin+4);pdf.cell(pw,4,dn+"  "+tm)
        pdf.ln(6)

        x0=pdf.l_margin if not im else pdf.l_margin+pw-bw
        y0=pdf.get_y()

        if long_text:
            pdf.set_font("YH","",11);pdf.set_text_color(0,0,0)
            pdf.multi_cell(pw-8,6,text_for_render)
            pdf.ln(2)
        else:
            if pdf.get_y()+th+8>pdf.h-25:pdf.add_page()
            y0=pdf.get_y()
            fc=sb if im else rb;tc=(255,255,255)if im else(0,0,0)
            rc(x0,y0,bw,th,4,fc)
            pdf.set_text_color(*tc)
            pdf.set_xy(x0+px,y0+1)
            pdf.multi_cell(bw-px*2,6,text_for_render)
            pdf.set_y(y0+th+4)
    pdf.output(path)
    return path
