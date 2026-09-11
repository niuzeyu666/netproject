# -*- coding: utf-8 -*-
"""V3模板 - 第四部分协议设计 + 附录"""
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

# 4.1
p=fp('给出总体架构图，说明连接管理、可靠传输')
if p: rp(p,
 '【设计目标】在应用层基于UDP实现教学简化版TCP(TJU_TCP)：(1)连接管理-三次握手/四次挥手/11状态FSM；(2)可靠传输-序号/累计确认/超时重传/快速重传/失序重组/重复抑制；(3)流量控制-滑动窗口/advertised_window通告/零窗口探测；(4)基础Reno拥塞控制-慢启动/拥塞避免/RTO超时和三次重复ACK后的窗口减小；(5)可测试可复现。\n'
 '【实现范围】必做：连接管理/可靠传输/流量控制/基础Reno/功能与性能测试。不做(教学简化)：完整快速恢复/NewReno/SACK/RACK/CUBIC(挑战任务，未选做)；URG/PSH/RST标志；IP分片；TCP选项字段(MSS协商/窗口缩放/时间戳/SACK)；多连接并发调度；TCP校验和(依赖UDP校验和)。\n'
 '【总体架构】应用层(client.c/server.c)调用tju_*API→TJU_TCP协议层(tju_tcp.c)包含连接管理(状态机FSM)/可靠传输(序号/ACK/重传队列)/流量控制(滑动窗口/rwnd通告)/拥塞控制(基础Reno/cwnd/ssthresh)→核心数据结构(tju_tcp_t/sender_window_t/receiver_window_t/重传队列/失序队列)→定时器模块(独立线程：RTO重传/RTT估计RFC6298/指数退避/Karn/零窗口探测/TIME_WAIT)→报文处理层(tju_packet.c：20字节头构造解析/网络字节序/最大1400字节)→仿真内核层(kernel.c：startSimulation/receive_thread后台UDP收包/onTCPPocket哈希分发/sendToLayer3 UDP发包)→虚拟网络(Vagrant+VirtualBox intnet 15441：client 172.17.0.2 ←100Mbps/20ms→ server 172.17.0.3)。\n'
 '【模块关系】连接管理是前提(只有ESTABLISHED才能传数据)；可靠传输用base/nextseq管理发送序号+重传队列，用expect_seq+失序队列管理接收，通过ACK推进窗口；流量控制用advertised_window通告rwnd，发送量受min(cwnd,rwnd)约束，零窗口时暂停+探测；拥塞控制维护cwnd/ssthresh，慢启动指数增长，拥塞避免线性增长，丢包后ssthresh=max(FlightSize/2,2×SMSS)；定时器支撑重传和连接关闭；底层UDP对协议层透明。')

# 4.2
p=fp('说明课程自定义20字节报文头、各字段用途')
if p: rp(p,
 '【自定义20字节报文头】字段布局(字节偏移)：Source Port(0-1)/Destination Port(2-3)/Sequence Number(4-7)/Acknowledgment Number(8-11)/Header Length(12-13,固定20)/Packet Length(14-15,=20+数据长,最大1400,接收方靠此字段知道收多少)/Flags(16,SYN=0x8/ACK=0x4/FIN=0x2,可组合SYN+ACK=0xC/FIN+ACK=0x6)/Advertised Window(17-18,接收方通告剩余接收能力,用于流量控制)/Ext(19,保留凑整无意义)。\n'
 '【序号与确认号】seq_num：数据报文=第一个数据字节序号；SYN报文=ISN，SYN占一个序号；FIN报文FIN也占一个序号。ack_num：期望收到的下一个字节序号=累计确认，仅ACK标志有效时有效。例：客户端ISN=1000，发SYN(seq=1000)，服务端回SYN+ACK(seq=2000,ack=1001)，客户端回ACK(seq=1001,ack=2001)。连接建立后发100字节数据(seq=1001,序号1001~1100)，服务端回ACK(ack=1101)。\n'
 '【校验和覆盖范围】本框架无TCP层checksum字段，数据完整性依赖：(1)UDP层校验和(覆盖伪首部+UDP头+数据)；(2)应用层序号机制检测丢包乱序+重传恢复。若UDP校验和关闭则比特错误可能不被检测——已知简化局限。\n'
 '【序号空间】32位无符号整数，空间2^32=4,294,967,296字节。ISN基于系统时间生成(避免框架硬编码464的问题)。教学场景数据量小，不处理序号回绕。SYN和FIN各占一个序号。\n'
 '【网络字节序】所有多字节字段网络传输用大端序。发送时header_in_char用htons/htonl转换；接收时get_*用ntohs/ntohl转换。单字节字段(flags/ext)不需转换。例：端口5678=0x162E，主机小端存2E 16，网络大端发16 2E。\n'
 '【关键数据结构】(1)扩展sender_window_t：base(窗口左边界,最早未确认序号)/nextseq(下一个待发送序号)/cwnd(拥塞窗口,字节)/ssthresh(慢启动阈值)/rwnd(对端通告窗口)/FlightSize(在途量=nextseq-base)/congestion_status(SLOW_START/CONGESTION_AVOIDANCE/FAST_RECOVERY)/重传队列(链表:packet/sent_time/retransmit_count/is_retransmitted/next)/srtt/rttvar/rto(RTT估计变量)/dup_ack_cnt(重复ACK计数)。功能：管理发送方所有状态-哪些已确认/哪些在途/还能发多少/拥塞阶段/哪些需重传/RTT估计值。(2)扩展receiver_window_t：expect_seq(期望接收序号)/buf[44000](接收缓冲区)/marked[](标记数组,标记哪些字节已收到,用于失序重组)/out_of_order_queue(失序报文队列,按序号排序链表)/recv_window_size(当前接收窗口大小,用于advertised_window通告)。功能：管理接收方所有状态-期望什么序号/哪些已收到待交付/哪些失序等缺失报文/接收窗口还剩多少。(3)重传队列节点retransmit_node_t：packet(已发送报文)/sent_time(发送时间,用于RTT和超时)/retransmit_count(重传次数,用于指数退避和最大次数判断)/is_retransmitted(是否被重传过,Karn算法用)/next(链表指针)。功能：跟踪所有已发送未确认报文，按序号排序；收ACK时删除所有序号<ack_num的节点(累计确认)，用最早被确认节点的发送时间采样RTT；定时器扫描检查超时。')

# 4.3
p=fp('说明连接状态、发送/接收缓冲区、滑动窗口、rwnd')
if p: rp(p,
 '【TCP连接状态机FSM】客户端：CLOSED→(tju_connect发SYN)→SYN_SENT→(收SYN+ACK发ACK)→ESTABLISHED→(tju_close发FIN)→FIN_WAIT_1→(收ACK)→FIN_WAIT_2→(收FIN发ACK)→TIME_WAIT→(等2MSL=30秒)→CLOSED。同时关闭：FIN_WAIT_1→(收FIN)→CLOSING→(收ACK)→TIME_WAIT。服务端：CLOSED→(bind+listen)→LISTEN→(收SYN发SYN+ACK)→SYN_RECV→(收ACK)→ESTABLISHED(入已完成队列唤醒accept)→(收FIN发ACK)→CLOSE_WAIT→(tju_close发FIN)→LAST_ACK→(收ACK)→CLOSED。实现要点：tju_handle_packet中根据当前state和收到报文flags组合执行状态转换，每个状态对SYN/ACK/FIN/数据报文都有明确处理分支，不符合当前状态的报文丢弃。\n'
 '【发送缓冲区与发送窗口】sending_buf存储tju_send传入但尚未发送的数据。发送窗口示意：|←已确认→|←在途FlightSize→|←可发送→|←缓冲区→|，0/base/nextseq/窗口右边界(base+min(cwnd,rwnd))/sending_buf末尾。FlightSize=nextseq-base，可发送量=min(cwnd,rwnd)-FlightSize。重传队列：所有已发送未确认报文按序号排列，收ACK时删除所有序号<ack_num的节点(累计确认)，用最早被确认节点发送时间采样RTT；定时器扫描超时则重传最早未确认报文(Go-Back-N)。\n'
 '【接收缓冲区与接收窗口】expect_seq期望接收的下一个字节序号。收到报文时：seq==expect_seq→按序到达，拷贝到buf，expect_seq+=data_len，尝试向前推进(合并失序队列中连续报文)；seq>expect_seq→失序到达，存入失序队列(按序号排序)，marked数组标记；seq<expect_seq→重复数据，丢弃但重新发ACK(ack=expect_seq)帮助发送方快速恢复。每次收到数据后发ACK，ack_num=expect_seq(累计确认)，advertised_window=剩余接收缓冲区大小。接收窗口示意：|←已交付应用→|←已接收待读→|←可接收窗口→|，0/expect_seq/buf数据末尾/buf末尾，advertised_window=buf末尾-buf数据末尾。\n'
 '【rwnd/cwnd/FlightSize协同】发送方实际允许在途量上限=min(cwnd,rwnd)。cwnd由拥塞控制动态调整(反映网络承载能力)，rwnd由接收方在ACK的advertised_window通告(反映接收方处理能力)，取较小值确保既不拥塞网络也不淹没接收方。发送决策(伪代码，调用者持有send_lock)：wnd=min(cwnd,rwnd); while FlightSize<wnd and sending_buf非空: seg_len=min(wnd-FlightSize, sending_buf数据量, MAX_DLEN); 构造报文(seq=nextseq, flags=ACK, adv_window=本端接收窗口); sendToLayer3; 加入重传队列记录发送时间; nextseq+=seg_len; FlightSize+=seg_len; 从sending_buf移除。ACK到达时：更新rwnd=对端advertised_window; 推进base=ack_num, FlightSize=nextseq-base; 拥塞控制更新cwnd(慢启动cwnd+=SMSS每ACK, 拥塞避免cwnd+=SMSS×SMSS/cwnd约每RTT增1); 若有新可发送空间且sending_buf有数据则继续发送(try_send)。丢包检测时：RTO超时→ssthresh=max(FlightSize/2,2×SMSS), cwnd=1×SMSS, 进入慢启动, 重传最早未确认报文；三次重复ACK→ssthresh=max(FlightSize/2,2×SMSS), cwnd=ssthresh(不实现完整快速恢复时直接进入拥塞避免), 重传被认为丢失的报文。零窗口处理：rwnd==0→停止发数据，启动零窗口探测定时器(定期发1字节探测)，收到rwnd>0的ACK后恢复发送；即使rwnd=0，ACK报文和控制报文(SYN/FIN)仍可发送。')

# 4.4
p=fp('说明线程/锁/条件变量、重传计时、资源释放')
if p: rp(p,
 '【并发控制设计】(1)线程模型-三线程：主线程(执行tju_*API)、接收线程receive_thread(后台UDP收包→onTCPPocket→tju_handle_packet)、定时器线程(新增，后台扫描重传队列处理超时重传/零窗口探测/TIME_WAIT超时释放)。三线程共享tju_tcp_t，用锁保护。(2)锁-send_lock(pthread_mutex_t)保护发送相关状态：sending_buf/sending_len、sender_window_t(base/nextseq/cwnd/ssthresh/rwnd/FlightSize/重传队列/拥塞状态/srtt/rttvar/rto/dup_ack_cnt)。获取场景：tju_send(写sending_buf+发送决策)、tju_handle_packet的ACK处理(更新窗口+重传队列+RTT估计)、定时器线程的超时重传(检查重传队列+执行重传+RTO退避)。recv_lock保护接收相关状态：received_buf/received_len、receiver_window_t(expect_seq/buf/marked/失序队列/接收窗口大小)。获取场景：tju_recv(读received_buf)、tju_handle_packet的数据处理(写接收缓冲区+更新expect_seq+失序重组)。state修改嵌入send_lock或recv_lock保护的临界区，不单独设state_lock。(3)条件变量-wait_cond(已有需启用，配合recv_lock)：tju_recv用pthread_cond_wait(&wait_cond,&recv_lock)阻塞等待数据，tju_handle_packet收到数据后pthread_cond_signal唤醒，替换当前框架的忙等while循环。connect_cond(新增，配合send_lock)：tju_connect发SYN后pthread_cond_wait等待SYN+ACK，tju_handle_packet收到SYN+ACK后pthread_cond_signal唤醒。accept_cond(新增，配合监听socket锁)：tju_accept pthread_cond_wait等待已完成连接，tju_handle_packet完成三次握手后将新连接加入已完成队列pthread_cond_signal唤醒。注意pthread_cond_wait原子释放锁并阻塞，被唤醒后重新获取锁，必须与互斥锁配合。(4)死锁预防-锁顺序规则：如需同时持有send_lock和recv_lock，全局统一先recv_lock后send_lock；避免在持有锁时调用可能阻塞的函数(pthread_cond_wait除外，它原子释放锁)；定时器线程操作重传队列时只获取send_lock不获取recv_lock。\n'
 '【定时器设计】(1)重传定时器RTO-独立定时器线程循环：若重传队列为空则pthread_cond_wait等待(有新报文加入时signal)；若队列非空则计算到最近节点超时的时间差睡眠到该时间点；有节点超时则重传该报文(Go-Back-N重传最早未确认报文)，重传次数+1，RTO指数退避(×2)；同时检查零窗口状态和TIME_WAIT超时。(2)RTO计算(RFC6298)-初始RTO=1秒。首次RTT测量R：SRTT=R, RTTVAR=R/2, RTO=SRTT+max(G,4×RTTVAR), G=100ms时钟粒度。后续测量R：RTTVAR=(1-β)RTTVAR+β|SRTT-R|(β=1/4), SRTT=(1-α)SRTT+αR(α=1/8), RTO=SRTT+max(G,4×RTTVAR)。边界：RTO最小1秒，最大60秒。重传时RTO=RTO×2(指数退避)，直到收到新的ACK确认(非重传报文的ACK)后恢复正常RTO计算。(3)Karn算法-被重传过的报文的ACK不用于RTT采样(无法确定ACK是对原始发送还是重传的确认)。重传队列节点标记is_retransmitted，收ACK时检查该标记。(4)零窗口探测定时器-rwnd=0时启动，每隔RTO时间发1字节探测报文(携带1字节数据，序号为当前nextseq)，收到rwnd>0的ACK后停止探测恢复正常发送，可与重传定时器共用同一线程。(5)TIME_WAIT定时器(2MSL)-主动关闭方进入TIME_WAIT后等待2MSL(本设计取30秒，MSL=15秒)，超时后将state置CLOSED并释放tju_tcp_t资源，在定时器线程中维护time_wait节点。(6)连接建立超时-tju_connect发SYN后若RTO内未收到SYN+ACK则重传SYN(RTO指数退避)，超过最大重传次数(如5次)后超时失败，利用重传队列机制将SYN报文也加入重传队列管理。\n'
 '【资源释放】连接完全关闭后(CLOSED状态)释放：sending_buf/received_buf(free)、sender_window_t/receiver_window_t(含重传队列/失序队列的每个节点和报文)、pthread_mutex_destroy(send_lock/recv_lock)、pthread_cond_destroy(wait_cond/connect_cond/accept_cond)、从established_socks哈希表移除、free(tju_tcp_t)。避免内存泄漏：重传队列中被ACK确认的节点必须free_packet+free；失序队列中被交付的报文必须释放。避免重复释放：tju_close和定时器线程都可能触发资源释放，通过state状态确保只释放一次。\n'
 '【异常处理路径】(1)丢包-数据报文丢失→接收方不发ACK→发送方RTO超时重传最早未确认报文；ACK丢失→发送方超时重传数据→接收方收到重复数据后重新发ACK→发送方收到后推进窗口；SYN丢失→connect重传SYN(指数退避)超过最大次数失败；FIN丢失→close重传FIN或对端超时后自行关闭。(2)重复报文-重复数据报文(seq<expect_seq)→丢弃数据但重新发ACK(ack=expect_seq)；重复SYN→服务端重新发SYN+ACK(幂等)；重复FIN→重新发ACK状态不变；重复ACK→发送方计数dup_ack_cnt达到3次触发快速重传。(3)失序报文-收到seq>expect_seq的报文→存入失序队列(按序号排序)发ACK(ack=expect_seq)marked数组标记；缺失报文到达后(seq==expect_seq)将其和失序队列中连续的报文一起交付expect_seq向前推进。(4)校验错误-本框架无TCP层checksum依赖UDP层校验和，若UDP层检测到校验错误报文被UDP层丢弃等同于丢包通过超时重传恢复；若UDP校验和未启用且发生比特错误可能导致数据损坏——已知简化局限。(5)零窗口-接收方缓冲区满时advertised_window=0→发送方收到rwnd=0的ACK后停止发数据→启动零窗口探测(定期发1字节)→接收方应用读取数据后缓冲区有空间→下一个ACK中advertised_window>0→发送方恢复发送。(6)半关闭连接-一方发FIN后进入FIN_WAIT_1→收ACK进入FIN_WAIT_2→本方不再发数据但仍可收数据→对端发完数据后close发FIN→本方收到FIN发ACK进入TIME_WAIT。实现要点：FIN_WAIT_2状态下tju_handle_packet仍需正常处理数据报文和ACK直到收到FIN。(7)同时关闭-双方同时发FIN→各自进入FIN_WAIT_1→收到对方FIN进入CLOSING→收到ACK进入TIME_WAIT。本设计在状态机中保留CLOSING状态处理确保健壮性。')

# 4.5 分阶段计划表
t5=doc.tables[5]
phase=[
 ['第一阶段',
  '1.环境搭建与基线运行验证(Vagrant双虚拟机/编译/UDP通信)；2.框架代码架构分析(kernel/tju_packet/tju_tcp 5源文件+4头文件+test测试目录)；3.协议总体设计(报文格式/状态机FSM/缓冲区/滑动窗口/并发控制/定时器/异常处理)；4.扩展数据结构设计(sender_window_t/receiver_window_t/重传队列/失序队列)；5.初始化Git仓库，提交基线代码和设计文档；6.完成第一阶段实验报告',
  '默认网络：100Mbps带宽，20ms延迟，无丢包；Vagrant双虚拟机正常运行(client=172.17.0.2,server=172.17.0.3)；框架代码可编译(make all)；基线程序可运行；测试工具：tcpdump抓包、printf日志',
  '1.能够编译并运行基线程序，client和server可通过UDP通信；2.完成框架架构分析，所有模块职责/接口/数据流/并发机制清晰；3.完成协议总体设计，报文格式/状态机/窗口协同/并发定时器设计明确；4.AI分析结论经人工核验，至少记录一项AI错误修正；5.Git仓库初始化，基线代码提交',
  '风险1-对框架并发模型理解偏差→应对：代码定位+运行验证+AI核验三重确认(见3.6节)；风险2-数据结构设计不足导致后续扩展困难→应对：充分考虑RFC要求和三阶段功能需求预留扩展字段；风险3-定时器实现复杂度高→应对：第一阶段仅设计，第二阶段实现连接管理时先实现SYN重传定时器逐步扩展'],
 ['第二阶段',
  '1.连接管理：三次握手(tju_connect/tju_accept/tju_handle_packet状态机)；2.连接关闭：四次挥手(tju_close状态机/TIME_WAIT)；3.可靠传输：序号管理/累计确认/发送接收缓冲区/滑动窗口；4.重传机制：超时重传/重传队列/RTT-RTO估计(RFC6298)/Karn算法；5.流量控制：advertised_window通告/rwnd约束/零窗口探测；6.失序重组和重复数据抑制；7.条件变量替换忙等',
  '第一阶段设计完成；网络条件：默认20ms/100Mbps，可配置丢包率(1%/5%/10%)测试重传；测试工具：tcpdump抓包、printf日志、自定义测试程序、md5校验、test目录提供的rdt测试程序',
  '1.三次握手成功：client connect后state=ESTABLISHED，server accept返回已连接socket；2.四次挥手成功：双方close后状态正确转换资源释放；3.可靠传输：大数据量传输无丢失无乱序无重复(md5校验)；4.丢包恢复：1%/5%丢包率下仍能正确传输重传次数合理；5.流量控制：接收方慢速读取时发送方不超过rwnd零窗口后可恢复；6.RTT/RTO：SRTT随网络延迟变化RTO在重传时指数退避',
  '风险1-状态机转换遗漏导致连接卡死→应对：严格按RFC9293 FSM实现每个状态每个报文类型都有处理分支；风险2-并发竞态导致缓冲区数据损坏→应对：所有共享数据访问都在锁保护下使用条件变量代替忙等；风险3-重传队列管理复杂(RTT采样/Karn/指数退避)→应对：先实现简单超时重传再逐步添加RTT估计和Karn算法；风险4-失序重组逻辑易错→应对：使用marked数组+失序队列充分测试乱序场景'],
 ['第三阶段',
  '1.基础Reno拥塞控制：慢启动/拥塞避免；2.丢包后窗口减小：RTO超时和三次重复ACK场景；3.快速重传(三次重复ACK触发不含完整快速恢复)；4.综合功能测试：连接+可靠传输+流量控制+拥塞控制端到端测试；5.性能实验：丢包率/时延等变量对照实验吞吐率/重传率指标；6.完成完整报告补齐所有章节和附录',
  '第二阶段功能全部实现并通过测试；网络条件：可配置丢包率(0.1%/1%/5%)/时延(20ms/50ms/100ms)/带宽(10Mbps/100Mbps)；性能测试工具：自定义数据采集脚本/matplotlib或gnuplot绘图/tcpdump trace分析/test目录提供的congestion测试脚本',
  '1.慢启动：cwnd从1×SMSS开始指数增长达到ssthresh后进入拥塞避免；2.拥塞避免：cwnd约每RTT增长1×SMSS；3.RTO丢包：ssthresh=max(FlightSize/2,2×SMSS)cwnd=1×SMSS重新慢启动；4.三次重复ACK：快速重传ssthresh减半cwnd=ssthresh(不做完整快速恢复)；5.性能实验：不同丢包率下吞吐率变化曲线可解释重传率与丢包率正相关；6.完整报告通过自查清单所有图表可追溯Git版本明确',
  '风险1-拥塞控制与流量控制交互复杂(min(cwnd,rwnd))→应对：明确FlightSize计算和发送决策逻辑单独测试cwnd约束和rwnd约束场景；风险2-性能实验数据波动大→应对：每个配置重复多次(如5次)取平均值报告标准差；风险3-cwnd增长计算精度问题(整数截断)→应对：使用字节为单位的cwnd拥塞避免阶段使用cwnd+=SMSS×SMSS/cwnd公式；风险4-trace数据量大分析困难→应对：编写自动化trace分析脚本提取cwnd/rwnd/FlightSize随时间变化曲线'],
]
for i,r in enumerate(phase):
    for j,v in enumerate(r): sc(t5.rows[i+1].cells[j],v)

# 4.6 AI协作记录
p=fp('对AI工具与使用目的、AI建议摘要、人工处理与验证、关键证据等进行说明')
if p: rp(p,
 '【AI工具】豆包AI助手（大语言模型）\n【使用目的】辅助进行协议总体设计，包括报文格式设计、状态机FSM设计、滑动窗口协同机制设计、并发控制(锁/条件变量/定时器线程)设计、异常处理路径设计。\n\n'
 '【AI建议摘要-发送窗口与接收窗口协同设计】AI输出：发送方使用base/nextseq管理发送窗口，接收方使用expect_seq管理接收前沿；发送方实际可发送量=min(cwnd,rwnd)-FlightSize；收到ACK时推进base、更新cwnd、继续发送；接收方收到失序报文时存入失序队列等缺失报文到达后合并交付。\n'
 '【人工处理与验证】采纳并补充。AI设计的窗口协同机制基本合理，与RFC793/5681的滑动窗口原理一致。在此基础上补充了：(1)FlightSize的明确定义(FlightSize=nextseq-base)和更新时机(发送时增加ACK时减少)；(2)零窗口处理的完整流程(rwnd=0时停止发送/启动零窗口探测/收到rwnd>0后恢复)；(3)失序重组的具体数据结构(marked数组+失序队列链表+expect_seq推进逻辑)；(4)重复ACK的处理(dup_ack_cnt计数达到3次触发快速重传)；(5)发送决策和ACK处理的伪代码(见4.3节)明确了锁的使用位置(send_lock保护整个发送决策过程)。经RFC5681第3节(慢启动)第4节(拥塞避免)和RFC9293第3.3节(序列号)对照验证设计符合标准要求。\n\n'
 '【关键证据】RFC9293(第3.3节序列号第3.4节窗口)、RFC5681(第3-4节拥塞控制)、global.h(sender_window_t/receiver_window_t结构定义)、tju_tcp.c(tju_send/tju_recv/tju_handle_packet骨架代码)、4.3节设计的发送窗口/接收窗口示意图和伪代码。')

print('第四部分完成')
doc.save(DST)
