from docx import Document
doc = Document(r"C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx")
t = doc.tables[10]
row = t.rows[3]
row.cells[0].text = "第三阶段"
row.cells[1].text = (
    "基础Reno拥塞控制：慢启动（cwnd初始10段，每ACK+min(newly_acked,SMSS)）、"
    "拥塞避免（cwnd>=ssthresh时每RTT约+1SMSS）；"
    "RTO超时（ssthresh=FlightSize/2，cwnd=1SMSS）；"
    "三次重复ACK快速重传（ssthresh减半，cwnd=ssthresh+3SMSS）；"
    "swnd=min(cwnd,rwnd)发送窗口约束。"
    "本地5项功能测试全部通过，4组对照实验（丢包率0%/10%、延迟50ms/300ms）完成，"
    "trace和图表可复现。"
)
row.cells[2].text = (
    "未实现完整NewReno（部分ACK退出快速恢复时cwnd调整未严格区分）和SACK；"
    "定时器粒度5ms偏粗；未做窗口缩放选项；"
    "在线rdt测试因平台180秒超时限制未完成评分（本地满分可复现）。"
)
row.cells[3].text = (
    "最终报告完善；可选做挑战任务（完整NewReno/CUBIC）；"
    "提高定时器精度以支持短RTT场景。"
)
doc.save(r"C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx")
print("Table 10 row 3 filled!")
