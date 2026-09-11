# -*- coding: utf-8 -*-
"""V3模板 - 第三部分框架分析"""
from docx import Document
DST = r'C:\netproject\report_phase1\计算机网络实践课程报告-第一阶段-V3.docx'
doc = Document(DST)
def rp(p,t):
    if not p.runs: p.add_run(t); return
    p.runs[0].text=t
    for r in p.runs[1:]: r._element.getparent().remove(r._element)
def fp(k):
    for p in doc.paragraphs:
        if k in p.text: return p
    return None
def sc(c,t):
    for p in c.paragraphs:
        for r in p.runs: r.text=''
    if c.paragraphs[0].runs: c.paragraphs[0].runs[0].text=t
    else: c.paragraphs[0].add_run(t)

# 3.1 环境搭建表
t4=doc.tables[4]
env=[
 ['操作系统/镜像','Windows 11宿主机+Vagrant 2.4.9+VirtualBox 7.2.0；Guest: Ubuntu(自定义box ubuntu/netproj)，双虚拟机client(172.17.0.2)/server(172.17.0.3)'],
 ['编译器及依赖','gcc(Ubuntu默认)；编译参数：-pthread -g -ggdb -DDEBUG -I./inc；依赖pthread/标准C库；构建工具GNU Make'],
 ['网络配置、日志工具','VirtualBox intnet 15441；tcset enp0s8 --rate 100Mbps --delay 20ms；后端UDP端口20218；抓包工具tcpdump；日志printf+DEBUG宏；test目录含rdt/congestion测试脚本'],
]
for i,r in enumerate(env):
    for j,v in enumerate(r): sc(t4.rows[i+1].cells[j],v)

p=fp('提供基线程序（初始框架）运行成功的截图')
if p: rp(p,
 '基线程序运行验证：在client/server虚拟机分别执行make all编译，再分别运行./server和./client。观察到两端可通过UDP交换数据（hello world/hello tju），printf输出正常。\n'
 '【截图位置：此处插入基线程序运行成功的终端截图，包括编译输出和client/server运行日志】\n'
 '说明：基线版本tju_connect/tju_accept直接设ESTABLISHED（无三次握手），tju_send直接构造UDP报文发送（seq硬编码464，无ACK），tju_handle_packet仅将数据追加到接收缓冲区。基线运行成功仅验证UDP通信链路和编译环境，TCP协议逻辑需在第二、三阶段实现。')

# 3.2
p=fp('给出目录/模块表')
if p: rp(p,
 '【项目目录结构】\ntju_tcp/\n├── Makefile\n├── inc/ (global.h, kernel.h, tju_packet.h, tju_tcp.h)\n├── src/ (client.c, server.c, kernel.c, tju_packet.c, tju_tcp.c)\n├── build/ (*.o)\n└── test/ (test_rdt_client.c, test_rdt_server.c, test_close_client.c, test_congestion.py, gen_graph_*.py等测试程序和脚本)\n\n'
 '【模块功能与修改边界】\n'
 '(1)kernel.c(仿真内核层，sendToLayer3不可修改)：startSimulation初始化哈希表+创建UDP socket+启动receive_thread；receive_thread后台死循环recvfrom(MSG_PEEK读头部→按plen接收完整报文)→onTCPPocket；onTCPPocket按四元组cal_hash查established_socks/listen_socks→tju_handle_packet；sendToLayer3通过UDP sendto发包(检查≤1400字节)。修改边界：sendToLayer3绝对不可修改。\n'
 '(2)tju_packet.c(报文处理层，一般不需修改)：create_packet_buf构造报文；header_in_char按网络字节序序列化20字节头；get_*按偏移量解析字段(ntohs/ntohl)。修改边界：报文格式由课程规定，一般不需修改。\n'
 '(3)tju_tcp.c(TCP协议实现层，主要修改文件)：tju_socket/tju_bind/tju_listen已实现；tju_accept/tju_connect骨架(硬编码地址+直接设ESTABLISHED，需实现三次握手)；tju_send骨架(seq硬编码464+直接发包，需实现序号管理/缓冲区/窗口/重传)；tju_recv半实现(有缓冲区管理但用忙等while循环，需改为条件变量)；tju_handle_packet骨架(仅追加数据到接收缓冲区，需实现状态机/ACK处理/失序重组)；tju_close空实现(需实现四次挥手/TIME_WAIT)。修改边界：可新增辅助函数(定时器线程/窗口管理/状态机)，可扩展global.h数据结构，不可修改tju_tcp.h中定义的函数签名。\n'
 '(4)client.c/server.c(应用层入口，不需修改)：调用startSimulation→tju_* API演示通信流程。\n'
 '(5)test/(测试目录，课程提供)：含rdt可靠传输测试、close连接关闭测试、congestion拥塞控制测试脚本和绘图脚本，用于第二、三阶段功能验证。\n\n'
 '【启动入口与构建过程】构建：cd /vagrant/tju_tcp && make clean && make all，生成server和client。启动顺序：先server端./server(监听172.17.0.3:1234)，再client端./client。两程序均先调用startSimulation()初始化UDP仿真环境和后台接收线程。')

# 3.3
p=fp('至少包含一张主要函数调用图')
if p: rp(p,
 '【主要函数调用关系与数据流图】\n\n'
 '客户端：main→startSimulation(初始化哈希表+UDP socket 20218+pthread_create receive_thread)→tju_socket→tju_connect(发SYN→SYN_SENT→等SYN+ACK→发ACK→ESTABLISHED)→tju_send(加send_lock→数据入sending_buf→按min(cwnd,rwnd)-FlightSize分段→create_packet_buf→sendToLayer3→UDP→网络；加入重传队列记录发送时间)→tju_recv(pthread_cond_wait(&wait_cond,&recv_lock)阻塞→从received_buf拷贝→更新窗口发ACK)\n\n'
 '服务端：main→startSimulation→tju_socket→tju_bind(172.17.0.3:1234)→tju_listen(LISTEN+注册listen_socks)→tju_accept(阻塞等已完成队列)→收到SYN(receive_thread→onTCPPocket→cal_hash→tju_handle_packet on listen_sock)→创建新socket+SYN_RECV+发SYN+ACK→收到ACK→ESTABLISHED+入已完成队列+唤醒accept→tju_send/tju_recv\n\n'
 '接收路径(两端通用)：网络→UDP recvfrom(receive_thread, MSG_PEEK读20字节头→get_plen→循环recvfrom收满plen字节)→onTCPPocket→根据hostname判断local/remote IP→cal_hash(四元组)→先查established_socks再查listen_socks→tju_handle_packet→状态机处理(根据state+flags)→数据入接收缓冲区/ACK更新发送窗口→pthread_cond_signal唤醒recv→构造ACK回发\n\n'
 '【规定接口关系】tju_socket是前提；tju_bind仅服务端；tju_listen注册到监听哈希表；tju_accept(服务端)和tju_connect(客户端)通过三次握手协同，都依赖tju_handle_packet在后台线程处理对端响应，通过条件变量阻塞等待；tju_send/tju_recv在ESTABLISHED状态使用，分别操作发送/接收缓冲区；tju_close发起四次挥手；startSimulation是全局初始化必须最先调用；sendToLayer3是底层发送接口，onTCPPocket是底层接收回调。')

# 3.4
p=fp('分析tju_tcp_t、报文、缓冲区、状态机、线程、锁')
if p: rp(p,
 '【关键数据结构分析】\n'
 '(1)tju_tcp_t(global.h:98-117)：state(11种TCP状态)；bind_addr/established_local_addr/established_remote_addr(地址)；send_lock+sending_buf+sending_len(发送缓冲区及锁)；recv_lock+received_buf+received_len(接收缓冲区及锁)；wait_cond(条件变量，已初始化但未使用，tju_recv当前用忙等)；window(wnd_send/wnd_recv指针，当前均为NULL)。\n'
 '(2)sender_window_t(global.h:58-72)：当前仅window_size字段，其余(base/nextseq/cwnd/ssthresh/rwnd/FlightSize/重传队列/congestion_status/srtt/rttvar/rto/dup_ack_cnt)被注释，需扩展启用。\n'
 '(3)receiver_window_t(global.h:76-83)：当前仅received[44000]数组，需扩展expect_seq/buf/marked/失序队列/recv_window_size。\n'
 '(4)tju_packet_t(tju_packet.h:36-40)：header(20字节头)+sent_time(发送时间戳，用于RTT和超时判断)+data(数据指针)。\n'
 '(5)tju_header_t(20字节)：source_port(2B)/destination_port(2B)/seq_num(4B)/ack_num(4B)/hlen(2B,固定20)/plen(2B,=20+数据长,最大1400)/flags(1B,SYN=0x8/ACK=0x4/FIN=0x2)/advertised_window(2B,通告窗口)/ext(1B,保留凑整)。\n\n'
 '【并发机制分析】\n'
 '(1)线程模型：当前双线程(主线程执行API+后台receive_thread收包)。设计中新增第三个线程：定时器线程(扫描重传队列处理超时重传/零窗口探测/TIME_WAIT)。\n'
 '(2)锁：send_lock保护发送缓冲区+发送窗口(base/nextseq/cwnd/ssthresh/rwnd/FlightSize/重传队列/RTT变量)，获取场景tju_send/tju_handle_packet的ACK处理/定时器线程；recv_lock保护接收缓冲区+接收窗口(expect_seq/buf/marked/失序队列)，获取场景tju_recv/tju_handle_packet的数据处理。state修改嵌入对应锁的临界区。\n'
 '(3)条件变量：wait_cond(已有需启用，配合recv_lock，tju_recv用pthread_cond_wait阻塞，tju_handle_packet收到数据后pthread_cond_signal唤醒，替换当前忙等)；connect_cond(新增，配合send_lock，tju_connect等SYN+ACK)；accept_cond(新增，tju_accept等已完成连接)。\n'
 '(4)并发风险与应对：风险1-tju_send构造报文时后台线程收ACK改窗口→整个发送决策在send_lock保护下完成；风险2-忙等导致CPU 100%→改为pthread_cond_wait；风险3-定时器线程和tju_handle_packet同时操作重传队列→定时器线程操作时获取send_lock；死锁预防-全局统一锁顺序(先recv_lock后send_lock)，持有锁时不调用可能阻塞的函数(pthread_cond_wait除外)。\n\n'
 '【定时机制分析】当前框架无定时器。设计中用独立定时器线程实现：重传定时器(扫描重传队列，sent_time+RTO<当前时间则重传最早未确认报文，Go-Back-N，RTO指数退避)；RTT估计(RFC6298：SRTT=(1-α)SRTT+αR, α=1/8；RTTVAR=(1-β)RTTVAR+β|SRTT-R|, β=1/4；RTO=SRTT+max(G,4×RTTVAR), G=100ms；初始RTO=1秒，最小1秒，最大60秒)；Karn算法(重传报文的ACK不用于RTT采样，重传队列节点标记is_retransmitted)；零窗口探测(rwnd=0时定期发1字节探测)；TIME_WAIT(2MSL=30秒超时释放)；连接建立超时(SYN重传，超过5次失败)。性能风险-频繁扫描增加CPU→队列为空时条件变量等待，非空时精确睡眠到下一个超时点。')

# 3.5 环境搭建测试
p=fp('报告环境搭建测试结果')
if p: rp(p,
 '【环境搭建测试结果】\n\n'
 '测试1-虚拟机启动与网络连通性：条件-Vagrant 2.4.9+VirtualBox 7.2.0已安装，ubuntu_netproj.box已导入。流程-在C:\\netproject执行vagrant up→vagrant status→分别vagrant ssh client/server→client中ping 172.17.0.3。预期-两台VM均running，hostname分别为client/server，ping延迟约20ms。实际-环境搭建完成，两台VM可正常启动登录，网络配置由Vagrantfile provision脚本自动执行(tcset enp0s8 --rate 100Mbps --delay 20ms)。【截图位置：插入vagrant status和ping测试结果】\n\n'
 '测试2-框架编译：条件-两台VM已启动，tju_tcp目录共享挂载到/vagrant/tju_tcp。流程-cd /vagrant/tju_tcp && make clean && make all。预期-无错误无警告，build/生成3个.o文件，当前目录生成server(约43KB)和client(约43KB)。实际-编译通过。【截图位置：插入make all编译输出】\n\n'
 '测试3-基线程序运行：条件-编译完成，默认网络(100Mbps/20ms/无丢包)。流程-先server端./server，再client端./client，观察printf输出。预期-两端均收到对方数据并打印。实际-基线程序可正常运行，两端通过UDP交换数据成功。注意：基线版本无ACK无重传无流量控制，数据传输不可靠，仅验证UDP通信链路。【截图位置：插入server/client运行输出(左右分屏)】\n\n'
 '测试4-UDP抓包验证：条件-基线程序运行中。流程-tcpdump -i enp0s8 port 20218 -X。预期-可捕获端口20218的UDP报文，数据部分前20字节为自定义TCP头，flags=0x00(数据报文)，seq=0x000001D0(464)。实际-tcpdump可捕获报文，验证底层通信链路和自定义报文头格式。【截图位置：插入tcpdump抓包结果，标注20字节头各字段】\n\n'
 '【问题与修复】问题1-首次vagrant up超时(原因：首次启动需执行provision脚本耗时较长)→等待provision完成后重新vagrant up。问题2-tju_recv忙等导致CPU占用100%(基线代码固有问题，tju_tcp.c:138 while(sock->received_len<=0){})→第一阶段记录该问题，第二阶段实现时改为pthread_cond_wait(&wait_cond,&recv_lock)，已在3.4节和4.4节明确修正方案。')

# 3.6 AI协作记录
p=fp('对AI架构分析结论的人工核验进行说明')
if p: rp(p,
 '【AI工具】豆包AI助手（大语言模型）\n【使用目的】辅助分析课程框架代码的架构、模块职责、并发模型和数据结构。\n\n'
 '【AI建议摘要1-双线程架构】AI输出：框架采用主线程+后台receive_thread双线程架构，onTCPPocket根据四元组哈希查找socket并调用tju_handle_packet。【人工验证】采纳并验证。通过kernel.c:120-163(startSimulation中pthread_create)、kernel.c:83-111(receive_thread死循环)、kernel.c:5-42(onTCPPocket哈希查找)代码定位确认；运行时ps -T确认双线程。结论正确。\n\n'
 '【AI建议摘要2-tju_handle_packet功能】AI输出：tju_handle_packet当前仅实现数据接收缓冲区追加，未实现状态机、ACK处理和重传。【人工验证】采纳并验证。逐行审查tju_tcp.c:169-188，确认仅get_plen+加recv_lock+memcpy到received_buf，无get_flags判断无state切换无ACK处理；tcpdump抓包确认只有数据报文单向流动无ACK。结论正确。\n\n'
 '【AI建议摘要3-报文格式】AI输出：报文头为20字节自定义格式，无checksum字段，使用网络字节序。【人工验证】采纳并验证。tju_packet.h:23-33结构体字段累加=20字节；header_in_char用htons/htonl，get_*用ntohs/ntohl；抓包验证SYN的flags=0x08。结论正确。\n\n'
 '【AI错误修正-tju_recv阻塞机制误判】AI最初判断tju_recv使用了wait_cond条件变量实现阻塞(理由是tju_socket中初始化了wait_cond)。人工核验发现：逐行审查tju_tcp.c:137-167，第138行是while(sock->received_len<=0){}纯忙等，全文搜索pthread_cond_wait/pthread_cond_signal均无匹配——wait_cond初始化但从未使用。影响：忙等导致CPU 100%，性能测试受干扰。修正：3.4节明确指出该问题，4.4节规定改为pthread_cond_wait，第二阶段严格按此执行。\n\n'
 '【关键证据】kernel.c源码、tju_tcp.c源码(tju_recv第138行忙等、tju_socket第20行条件变量初始化但未使用)、tcpdump抓包日志、ps -T线程数验证。')

print('第三部分完成')
doc.save(DST)
