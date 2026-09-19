#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix trace output format to match gen_graph_win.py expectations."""
import re

path = 'tju_tcp/src/tju_tcp.c'
with open(path, 'rb') as f:
    data = f.read()

nl = b'\r\n' if b'\r\n' in data else b'\n'
print(f"Line ending: {'CRLF' if nl == bytes([13,10]) else 'LF'}")

# 1. Replace trace_write function: TIME:ms -> us timestamp
old_tw = b'''static void trace_write(const char* fmt, ...) {
    char host[64] = {0};
    gethostname(host, sizeof(host) - 1);
    const char* name = (strcmp(host, "server") == 0) ? "server.event.trace" : "client.event.trace";
    FILE* f = fopen(name, "a");
    if(!f) return;
    struct timeval tv;
    gettimeofday(&tv, NULL);
    fprintf(f, "TIME:%llu ", (unsigned long long)tv.tv_sec * 1000ULL + tv.tv_usec / 1000ULL);
    va_list ap;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\\n', f);
    fclose(f);
}'''

new_tw = b'''static void trace_write(const char* fmt, ...) {
    char host[64] = {0};
    gethostname(host, sizeof(host) - 1);
    const char* name = (strcmp(host, "server") == 0) ? "server.event.trace" : "client.event.trace";
    FILE* f = fopen(name, "a");
    if(!f) return;
    struct timeval tv;
    gettimeofday(&tv, NULL);
    unsigned long long us = (unsigned long long)tv.tv_sec * 1000000ULL + (unsigned long long)tv.tv_usec;
    fprintf(f, "%llu ", us);
    va_list ap;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\\n', f);
    fclose(f);
}

/* flag string for trace */
static const char* trace_flags(uint8_t fl) {
    static __thread char buf[16];
    buf[0] = 0;
    if(fl & SYN_FLAG_MASK) strcat(buf, "SYN|");
    if(fl & ACK_FLAG_MASK) strcat(buf, "ACK|");
    if(fl & FIN_FLAG_MASK) strcat(buf, "FIN|");
    int l = (int)strlen(buf);
    if(l > 0 && buf[l-1] == '|') buf[l-1] = 0;
    if(buf[0] == 0) strcpy(buf, "NONE");
    return buf;
}'''

if old_tw in data:
    data = data.replace(old_tw, new_tw, 1)
    print("1. trace_write format fixed (us timestamp)")
else:
    print("1. SKIP: trace_write pattern not found")

# 2. cong_on_ack: CWND state=... -> CWND type:0|1 size:
old = b'    trace_write("CWND state=%s value=%u acked=%u", cc_state(cb), cb->cwnd, newly_acked);'
new = b'    int cwnd_type = (cb->cwnd < cb->ssthresh) ? 0 : 1;\n    trace_write("CWND type:%d size:%u", cwnd_type, cb->cwnd);'
if old in data:
    data = data.replace(old, new, 1)
    print("2. cong_on_ack trace fixed")
else:
    print("2. SKIP: cong_on_ack trace not found")

# 3. cong_on_timeout: TIMEOUT -> CWND type:3
old = b'    trace_write("TIMEOUT cwnd=%u ssthresh=%u", cb->cwnd, cb->ssthresh);'
new = b'    trace_write("CWND type:3 size:%u", cb->cwnd);'
if old in data:
    data = data.replace(old, new, 1)
    print("3. cong_on_timeout trace fixed")
else:
    print("3. SKIP: timeout trace not found")

# 4. cong_on_fast_rexmit: FAST_RETRANSMIT -> CWND type:2
old = b'    trace_write("FAST_RETRANSMIT cwnd=%u ssthresh=%u recover=%u", cb->cwnd, cb->ssthresh, cb->recover_point);'
new = b'    trace_write("CWND type:2 size:%u", cb->cwnd);'
if old in data:
    data = data.replace(old, new, 1)
    print("4. cong_on_fast_rexmit trace fixed")
else:
    print("4. SKIP: fast_rexmit trace not found")

# 5. Remove DUPACK trace
old = b'            trace_write("DUPACK ack:%u count:%d", acknum, cb->dup_ack_cnt);'
if old in data:
    data = data.replace(old, b'', 1)
    print("5. DUPACK trace removed")
else:
    print("5. SKIP: DUPACK trace not found")

# 6. Add SEND trace in emit_pkt (after free(buf))
old = b'    sendToLayer3(buf, DEFAULT_HEADER_LEN + dlen);' + nl + b'    free(buf);' + nl + b'    cb->last_advertised = adv;' + nl + b'}'
new = b'    sendToLayer3(buf, DEFAULT_HEADER_LEN + dlen);' + nl + b'    free(buf);' + nl + b'    cb->last_advertised = adv;' + nl + b'    trace_write("SEND seq:%u ack:%u flag:%s", seq, ack, trace_flags(flags));' + nl + b'}'
if old in data and b'trace_write("SEND' not in data:
    data = data.replace(old, new, 1)
    print("6. SEND trace added to emit_pkt")
else:
    print("6. SKIP: emit_pkt pattern not found or SEND already exists")

# 7. Add RECV trace in tju_handle_packet (after seq extraction, before lock)
old = b'    uint8_t flags = get_flags(pkt);' + nl + b'    uint32_t seq = get_seq(pkt);' + nl + nl + b'    pthread_mutex_lock(&cb->mtx);'
new = b'    uint8_t flags = get_flags(pkt);' + nl + b'    uint32_t seq = get_seq(pkt);' + nl + b'    uint32_t ackv = get_ack(pkt);' + nl + b'    trace_write("RECV seq:%u ack:%u flag:%s", seq, ackv, trace_flags(flags));' + nl + nl + b'    pthread_mutex_lock(&cb->mtx);'
if old in data and b'trace_write("RECV' not in data:
    data = data.replace(old, new, 1)
    print("7. RECV trace added to tju_handle_packet")
else:
    print("7. SKIP: handle_pkt pattern not found or RECV already exists")

# 8. Add RWND trace in handle_data_phase (after peer_window update)
old = b'    cb->peer_window = adv;' + nl + b'    uint64_t now = now_ms();'
new = b'    cb->peer_window = adv;' + nl + b'    trace_write("RWND size:%u", adv);' + nl + b'    uint64_t now = now_ms();'
if old in data and b'trace_write("RWND' not in data:
    data = data.replace(old, new, 1)
    print("8. RWND trace added to handle_data_phase")
else:
    print("8. SKIP: handle_data_phase pattern not found or RWND already exists")

# 9. Add RTTS trace in rtt_measure (after clamp_rto)
old = b'    clamp_rto(cb);' + nl + b'}'
new = b'    clamp_rto(cb);' + nl + b'    trace_write("RTTS SampleRTT:%u EstimatedRTT:%u DeviationRTT:%u TimeoutInterval:%u",' + nl + b'           r_ms, cb->srtt8/8, cb->rttvar8/8, cb->rto_ms);' + nl + b'}'
if old in data and b'trace_write("RTTS' not in data:
    data = data.replace(old, new, 1)
    print("9. RTTS trace added to rtt_measure")
else:
    print("9. SKIP: rtt_measure pattern not found or RTTS already exists")

# 10. Add DELV trace in tju_recv (after rx_read += n, before window update)
old = b'    cb->rx_read += n;' + nl + nl + b'    /* '
# Find the tju_recv specific occurrence
idx = data.find(b'    cb->rx_read += n;' + nl)
if idx >= 0 and b'trace_write("DELV' not in data:
    # Insert DELV trace after rx_read += n
    insert = b'    trace_write("DELV seq:%u size:%u", cb->rx_read - n, (unsigned)n);' + nl + nl
    data = data[:idx + len(b'    cb->rx_read += n;' + nl)] + insert + data[idx + len(b'    cb->rx_read += n;' + nl):]
    print("10. DELV trace added to tju_recv")
else:
    print("10. SKIP: tju_recv pattern not found or DELV already exists")

# 11. Add SWND trace in flush_tx (after win calculation)
old = b'#endif' + nl + b'        if(inflight_bytes >= win'
if old in data and b'trace_write("SWND' not in data:
    new = b'#endif' + nl + b'        trace_write("SWND size:%u", win);' + nl + b'        if(inflight_bytes >= win'
    data = data.replace(old, new, 1)
    print("11. SWND trace added to flush_tx")
else:
    print("11. SKIP: flush_tx pattern not found or SWND already exists")

with open(path, 'wb') as f:
    f.write(data)
print("\nAll trace format fixes applied!")
