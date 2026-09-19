#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import copy

doc = Document(r'C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx')

# Find anchor paragraphs by text content
def find_para(text_start):
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip().startswith(text_start):
            return i
    return None

def insert_image_after(anchor_idx, img_path, caption, width_inches=5.5):
    """Insert image and caption after anchor paragraph."""
    anchor_p = doc.paragraphs[anchor_idx]
    # Create image paragraph
    img_p = copy.deepcopy(anchor_p._p)
    anchor_p._p.addnext(img_p)
    # Refresh paragraphs list
    img_para = None
    for p in doc.paragraphs:
        if p._p is img_p:
            img_para = p
            break
    # Clear and add picture
    for run in img_para.runs:
        run.text = ''
    img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = img_para.add_run()
    run.add_picture(img_path, width=Inches(width_inches))
    
    # Caption paragraph after image
    cap_p = copy.deepcopy(anchor_p._p)
    img_p.addnext(cap_p)
    for p in doc.paragraphs:
        if p._p is cap_p:
            p.text = caption
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.size = None
            break

# 图1: after "图1为10%丢包场景" paragraph
idx = find_para('图1为10%丢包场景')
if idx:
    insert_image_after(idx,
        r'C:\netproject\tju_tcp\figure\wds10\Congestion_WindowSize_VS_Time_1_87.png',
        '图1 10%丢包场景下拥塞窗口随时间变化（红=慢启动，绿=拥塞避免，蓝=快速重传，青=超时）')
    print(f"Fig1 inserted after para {idx}")

# 图2: after "性能分析1" paragraph
idx = find_para('性能分析1')
if idx:
    insert_image_after(idx,
        r'C:\netproject\tju_tcp\figure\noloss\Congestion_WindowSize_VS_Time_1_181.png',
        '图2 无丢包300ms延迟场景下cwnd从慢启动过渡到拥塞避免')
    print(f"Fig2 inserted after para {idx}")

# 图3: after "图3为小rwnd" paragraph (same as fig1 anchor, need second insertion)
# Insert after fig1 caption instead - find "图3为小rwnd"
idx = find_para('图3为小rwnd')
if idx:
    insert_image_after(idx,
        r'C:\netproject\tju_tcp\figure\smallrwnd\AllWindowSize_VS_Time_0.044273_8.675225.png',
        '图3 小rwnd场景下cwnd（红）、rwnd（绿）、swnd（蓝）三窗口对比，swnd被rwnd钳制')
    print(f"Fig3 inserted after para {idx}")

# 图4: after "图4为有丢包" paragraph
idx = find_para('图4为有丢包场景')
if idx:
    insert_image_after(idx,
        r'C:\netproject\tju_tcp\figure\wds10\Throuput.png',
        '图4 10%丢包场景下吞吐率随时间变化')
    print(f"Fig4 inserted after para {idx}")

# 图5: after "性能分析2" paragraph
idx = find_para('性能分析2')
if idx:
    insert_image_after(idx,
        r'C:\netproject\tju_tcp\figure\lowlat\Congestion_WindowSize_VS_Time_1_181.png',
        '图5 无丢包50ms延迟场景下cwnd曲线（慢启动阶段更陡峭）')
    print(f"Fig5 inserted after para {idx}")

doc.save(r'C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx')
print("All images inserted!")
