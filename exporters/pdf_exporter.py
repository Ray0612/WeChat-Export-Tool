# -*- coding: utf-8 -*-
"""PDF exporter - final version"""
import datetime

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

    ld=None
    for m in msgs:
        ts=m.get('create_time','');c=m.get('message_content','')or''
        sr=m.get('sender_username','');im=m.get('is_mine',0)
        lt=int(m.get('local_type',0))
        if lt not in(1,244813135921)or not c.strip():continue
        mt=datetime.datetime.fromtimestamp(int(ts))if ts.isdigit()else None
        if not mt:continue
        ds=mt.strftime('%Y-%m-%d');tm=mt.strftime('%H:%M:%S')
        dn=my_name if im else sr;lines=c.split('\n')

        if ds!=ld:
            y=pdf.get_y();pdf.set_font("YH","",6)
            dw=pdf.get_string_width(ds)+4;rc((pdf.w-dw)/2,y,dw,5,2.5,(220,224,230))
            pdf.set_text_color(120,125,135);pdf.set_xy((pdf.w-dw)/2,y);pdf.cell(dw,5,ds,align='C')
            pdf.ln(4);ld=ds

        pdf.set_font("YH","",11)
        mlw=max(pdf.get_string_width(l)for l in lines)if lines else 0
        px=3;mx=pw*0.6;bw=min(mx,mlw+px*2+4);lh=6;wr=[]
        for line in lines:
            w=pdf.get_string_width(line)
            if w>bw-px*2:
                cpl=max(int((bw-px*2)/(w/max(len(line),1))),1)
                for i in range(0,len(line),cpl):wr.append(line[i:i+cpl])
            else:wr.append(line)
        th=len(wr)*lh+2
        if pdf.get_y()+th+8>pdf.h-25:pdf.add_page()

        pdf.set_font("YH","",7);pdf.set_text_color(120,125,135)
        if im:
            nw=pdf.get_string_width(dn+"  "+tm)
            pdf.set_x(pdf.l_margin+pw-nw-4);pdf.cell(nw+8,4,dn+"  "+tm,align='R')
        else:
            pdf.set_x(pdf.l_margin+4);pdf.cell(pw,4,dn+"  "+tm)
        pdf.ln(6)
        y0,x0=pdf.get_y(),pdf.l_margin if not im else pdf.l_margin+pw-bw
        if im:rc(x0,y0,bw,th,4,sb);pdf.set_text_color(255,255,255)
        else:rc(x0,y0,bw,th,4,rb);pdf.set_text_color(0,0,0)
        for i,l in enumerate(wr):
            pdf.set_xy(x0+px,y0+1+i*lh);pdf.cell(bw-px*2,lh,l)
        pdf.set_y(y0+th+4)
    pdf.output(path)
    return path
