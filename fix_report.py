#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from docx import Document
doc = Document(r'C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx')

# === Fill Table 8: design-implementation-test summary ===
t8 = doc.tables[8]
data8 = [
    ['慢启动', 'cwnd < ssthresh时，每ACK增加min(newly_acked,SMSS)', 'tju_tcp.c: cong_on_ack() 332-341行', 'cwnd按ACK快速增长', '无丢包trace (client.event.trace)', '图1（红色点）'],
    ['拥塞避免', 'cwnd >= ssthresh时，每RTT约+1SMSS', 'tju_tcp.c: cong_on_ack() 338行', 'cwnd约每RTT增长一个SMSS', '无丢包trace', '图3（绿色线）'],
    ['RTO丢包', 'ssthresh=FlightSize/2，cwnd=1SMSS，重新慢启动', 'tju_tcp.c: cong_on_timeout() 345-350行', '降低ssthresh和cwnd并重新慢启动', '10%丢包trace', '图1（青色点）'],
    ['三次重复ACK', 'ssthresh=FlightSize/2，cwnd=ssthresh+3SMSS，立即重传', 'tju_tcp.c: cong_on_fast_rexmit() 354-361行', '快速重传并降低窗口', '10%丢包trace', '图1（蓝色点）'],
    ['rwnd约束', 'swnd=min(cwnd,peer_window)，peer_window来自报文', 'tju_tcp.c: flush_tx() 378行', '在途量受min(rwnd,cwnd)约束', '小rwnd实验trace', '图2（三窗口对比）'],
]
for i, row_data in enumerate(data8):
    row = t8.rows[i+1]
    for j, val in enumerate(row_data):
        row.cells[j].text = val

# === Fill Table 9: test environment ===
t9 = doc.tables[9]
data9 = [
    ['代码Git版本', '96ee3ba之后（第三阶段拥塞控制提交）', 'cd /vagrant/tju_tcp && make clean && make'],
    ['客户端/服务端环境', 'Vagrant双VM：client 172.17.0.2:2222，server 172.17.0.3:2200；Ubuntu容器', 'vagrant ssh client / vagrant ssh server'],
    ['时延/丢包/带宽/缓冲区', '带宽100Mbps；延迟50ms或300ms；丢包率0%或10%；RING_BYTES=7MB（小rwnd实验临时改为20000B）', 'tc qdisc ... (test_congestion.py自动设置)'],
    ['测试程序/脚本', 'test_congestion.py（自动设置网络条件并跑60秒传输）；gen_graph_win.py（绘图）；gen_graph_seq.py（序列号图）', 'cd /vagrant/tju_tcp/test && python3 test_congestion.py 100 300 50 10'],
    ['抓包、日志、trace、绘图工具', 'client.event.trace / server.event.trace（文本trace）；server.pcap（tcpdump）；gen_graph_win.py用matplotlib绘图', 'python3 gen_graph_win.py 10'],
]
for i, row_data in enumerate(data9):
    row = t9.rows[i+1]
    for j, val in enumerate(row_data):
        row.cells[j].text = val

# === Fix figure captions renumbering ===
# Fig1 (10% loss cwnd) stays as Fig1
# Fig3 (small rwnd) should become Fig2
# Fig2 (noloss 300ms) should become Fig3
# Fig5 (50ms) should become Fig4
# Fig4 (throughput) should become Fig5
caption_fixes = {
    '图3 小rwnd场景下cwnd': '图2 小rwnd场景下cwnd（红）、rwnd（绿）、swnd（蓝）三窗口对比，swnd被rwnd钳制',
    '图2 无丢包300ms延迟场景下cwnd从慢启动过渡到拥塞避免': '图3 无丢包300ms延迟场景下cwnd从慢启动过渡到拥塞避免',
    '图5 无丢包50ms延迟场景下cwnd曲线（慢启动阶段更陡峭）': '图4 无丢包50ms延迟场景下cwnd曲线（慢启动阶段更陡峭）',
    '图4 10%丢包场景下吞吐率随时间变化': '图5 10%丢包场景下吞吐率随时间变化',
}
for p in doc.paragraphs:
    for old, new in caption_fixes.items():
        if p.text.strip().startswith(old):
            for run in p.runs:
                run.text = ''
            if p.runs:
                p.runs[0].text = new
            else:
                p.add_run(new)

# === Fix text references to figures ===
text_fixes = {
    '图1为10%丢包场景下拥塞窗口随时间变化曲线，可见典型锯齿形状：慢启动（红色）、快速重传（蓝色）、拥塞避免（绿色）、超时（青色）循环振荡。图2为无丢包场景下cwnd曲线，慢启动后线性增长。图3为小rwnd场景下三窗口综合曲线，可见swnd（蓝）被rwnd（绿）钳制。':
    '图1为10%丢包场景下拥塞窗口随时间变化曲线，可见典型锯齿形状：慢启动（红色）、快速重传（蓝色）、拥塞避免（绿色）、超时（青色）循环振荡。图2为小rwnd场景下三窗口综合曲线，可见swnd（蓝）被rwnd（绿）钳制。',
    '图4为有丢包场景下吞吐率随时间变化曲线，可见初期慢启动时吞吐率峰值约150kbps，随后因丢包和cwnd降低而波动。图5为无丢包50ms延迟场景下cwnd曲线，慢启动阶段更陡峭（RTT短，ACK到达快，cwnd增长更快）。':
    '图5为有丢包场景下吞吐率随时间变化曲线，可见初期慢启动时吞吐率峰值约150kbps，随后因丢包和cwnd降低而波动。图4为无丢包50ms延迟场景下cwnd曲线，慢启动阶段更陡峭（RTT短，ACK到达快，cwnd增长更快）。',
}
for p in doc.paragraphs:
    for old, new in text_fixes.items():
        if p.text.strip() == old[:50]:
            for run in p.runs:
                run.text = ''
            if p.runs:
                p.runs[0].text = new
            break

doc.save(r'C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx')
print("Tables filled and figures renumbered!")
