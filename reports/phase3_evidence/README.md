# 第三阶段证据目录
- 源码构建：`make INIT_WDS=1/10/50`
- trace：client.event.trace、server.event.trace
- 抓包：server.pcap
- 测试日志：log.log
- 说明：每次测试先恢复 100Mbps/20ms，再设置目标带宽、时延、抖动和丢包率；测试结束后恢复网络。
