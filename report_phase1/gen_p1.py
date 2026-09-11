# -*- coding: utf-8 -*-
"""V3模板综合填写脚本 - 第一阶段报告"""
from docx import Document
import shutil

SRC = r'C:\netproject\report_phase1\template_v3.docx'
DST = r'C:\netproject\report_phase1\计算机网络实践课程报告-第一阶段-V3.docx'
REPO = 'github.com/niuzeyu666/netproject'

shutil.copy(SRC, DST)
doc = Document(DST)

def rp(para, text):
    if not para.runs:
        para.add_run(text); return
    para.runs[0].text = text
    for r in para.runs[1:]:
        r._element.getparent().remove(r._element)

def fp(keyword):
    for p in doc.paragraphs:
        if keyword in p.text: return p
    return None

def sc(cell, text):
    for p in cell.paragraphs:
        for r in p.runs: r.text = ''
    if cell.paragraphs[0].runs:
        cell.paragraphs[0].runs[0].text = text
    else:
        cell.paragraphs[0].add_run(text)

# ===== 封面 =====
t0 = doc.tables[0]
cover = {'学号':'【请填写】','姓名':'【请填写】','学院':'电气自动化与信息工程学院',
         '专业':'电气工程及其自动化','年级':'2025级','任课教师':'【请填写】',
         '代码仓库/版本': f'{REPO}（第一阶段基线）'}
for row in t0.rows:
    k = row.cells[0].text.strip()
    if k in cover: sc(row.cells[1], cover[k])
for p in doc.paragraphs:
    if '提交日期：______' in p.text: rp(p, '提交日期：2026年09月11日'); break

# ===== 阶段索引 =====
t1 = doc.tables[1]
sc(t1.rows[1].cells[4], '已完成：环境搭建（Vagrant双虚拟机配置验证）、基线运行（编译通过+UDP通信验证）、框架代码架构分析（5个源文件+4个头文件+test测试目录）、协议总体设计（报文格式/状态机/窗口/并发/定时器）、第一阶段实验报告撰写')

# ===== 2.1 标准依据 =====
p = fp('RFC 9293、RFC 6298和RFC 5681为必做功能的主要依据')
if p: rp(p,
    '本项目必做功能的标准依据为 RFC 9293、RFC 6298 和 RFC 5681。TJU_TCP 是教学简化版本，逐项比较差异如下：\n'
    '（1）RFC 9293（TCP基本规范）：标准TCP头20字节+可变选项，含Checksum/Urgent Pointer/Options，6位控制位（URG/ACK/PSH/RST/SYN/FIN）。'
    '本项目用自定义20字节固定头，无Checksum/Urgent Pointer/Options，flags仅1字节（SYN=0x8/ACK=0x4/FIN=0x2），用hlen/plen代替Data Offset；'
    '单连接模型，不要求同时打开；不实现URG/PSH/RST；无窗口缩放选项。状态机（11状态）、三次握手、四次挥手、累计确认、滑动窗口均按RFC实现。\n'
    '（2）RFC 6298（RTT估计与RTO）：SRTT/RTTVAR平滑估计（α=1/8, β=1/4）、RTO初始1秒/最小1秒、指数退避、Karn算法均按RFC实现。'
    '差异：不使用时间戳选项（RFC 7323），RTT基于报文发送时间和ACK到达时间测量；定时器粒度G=100ms（独立线程实现）；RTO上限60秒。\n'
    '（3）RFC 5681（拥塞控制）：必做边界为慢启动+拥塞避免+RTO超时/三次重复ACK后的窗口减小。'
    '差异：完整快速恢复为挑战任务，必做中三次重复ACK后cwnd=ssthresh直接进入拥塞避免；SMSS固定为MAX_DLEN=1375字节，无MSS协商；不实现ABC（Appropriate Byte Counting）。')

t2 = doc.tables[2]
std = [
    ['RFC 9293','TCP基本规范、连接与可靠传输',
     '差异：自定义20字节头无Checksum/Options；flags仅SYN/ACK/FIN；单连接模型；不实现URG/PSH/RST；无窗口缩放。状态机/三次握手/四次挥手/累计确认/滑动窗口均按RFC实现',
     '第3节（报文格式）、第5节（连接管理/状态机）、第6节（可靠传输/流量控制）'],
    ['RFC 6298','RTT估计与RTO',
     '差异：无时间戳选项，RTT基于发送时间测量；定时器粒度G=100ms；RTO上限60秒。SRTT/RTTVAR公式/指数退避/Karn算法均按RFC实现',
     '第2节（RTT/RTO计算）、第5节（重传定时器）'],
    ['RFC 5681','基础Reno/完整Reno',
     '必做边界：慢启动+拥塞避免+RTO超时/三次重复ACK后的窗口减小。差异：完整快速恢复为挑战任务；SMSS固定1375字节无MSS协商；不实现ABC',
     '第3节（慢启动/拥塞避免）、第4节（丢包后窗口变化）'],
]
for i,row in enumerate(std):
    for j,v in enumerate(row): sc(t2.rows[i+1].cells[j], v)
for row in t2.rows:
    if '挑战任务' in row.cells[0].text:
        row._element.getparent().remove(row._element); break

# ===== 2.2 需求追踪矩阵 =====
p = fp('建立')
if p and '追踪关系' in p.text: p._element.getparent().remove(p._element)
t3 = doc.tables[3]
trace = [
    ['R1','连接建立与关闭','5','tju_tcp.c: tju_connect(), tju_accept(), tju_close(), tju_handle_packet()','第二阶段：三次握手/四次挥手抓包日志、状态转换trace'],
    ['R2','可靠数据传输','6','tju_tcp.c: tju_send(), tju_recv(), tju_handle_packet(); 发送/接收缓冲区、重传队列','第二阶段：数据完整性校验(md5)、丢包重传测试日志'],
    ['R3','流量控制','6','tju_tcp.c: 滑动窗口管理、advertised_window处理、零窗口探测','第二阶段：窗口约束测试、零窗口恢复测试'],
    ['R4','基础Reno','7','tju_tcp.c: cwnd/ssthresh管理、慢启动/拥塞避免状态机、丢包响应','第三阶段：cwnd变化trace、拥塞控制行为图表'],
    ['R5','性能评价与复现','8','测试脚本、数据采集与绘图脚本','第三阶段：吞吐率/重传率原始数据、性能对比图表'],
]
for i,row in enumerate(trace):
    for j,v in enumerate(row): sc(t3.rows[i+1].cells[j], v)

print('第二部分完成')
doc.save(DST)
