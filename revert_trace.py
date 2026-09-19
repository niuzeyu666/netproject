#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Revert all changes made by fix_trace.py."""

path = 'tju_tcp/src/tju_tcp.c'
with open(path, 'rb') as f:
    data = f.read()

nl = b'\r\n' if b'\r\n' in data else b'\n'
count = 0

# 1. Revert trace_write: us -> ms, remove trace_flags function
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

if new_tw in data:
    data = data.replace(new_tw, old_tw, 1)
    count += 1
    print("1. Reverted trace_write")
else:
    print("1. SKIP")

# 2. Revert cong_on_ack
old = b'    int cwnd_type = (cb->cwnd < cb->ssthresh) ? 0 : 1;' + nl + b'    trace_write("CWND type:%d size:%u", cwnd_type, cb->cwnd);'
new = b'    trace_write("CWND state=%s value=%u acked=%u", cc_state(cb), cb->cwnd, newly_acked);'
if old in data:
    data = data.replace(old, new, 1)
    count += 1
    print("2. Reverted cong_on_ack")
else:
    print("2. SKIP")

# 3. Revert timeout
old = b'    trace_write("CWND type:3 size:%u", cb->cwnd);'
new = b'    trace_write("TIMEOUT cwnd=%u ssthresh=%u", cb->cwnd, cb->ssthresh);'
if old in data:
    data = data.replace(old, new, 1)
    count += 1
    print("3. Reverted timeout")
else:
    print("3. SKIP")

# 4. Revert fast_rexmit
old = b'    trace_write("CWND type:2 size:%u", cb->cwnd);'
new = b'    trace_write("FAST_RETRANSMIT cwnd=%u ssthresh=%u recover=%u", cb->cwnd, cb->ssthresh, cb->recover_point);'
if old in data:
    data = data.replace(old, new, 1)
    count += 1
    print("4. Reverted fast_rexmit")
else:
    print("4. SKIP")

# 5. Restore DUPACK trace (was removed)
# Find the line that was right after dup_ack_cnt++
old = b'            cb->dup_ack_cnt++;' + nl + b'            if(cb->dup_ack_cnt == 3) {'
new = b'            cb->dup_ack_cnt++;' + nl + b'            trace_write("DUPACK ack:%u count:%d", acknum, cb->dup_ack_cnt);' + nl + b'            if(cb->dup_ack_cnt == 3) {'
if old in data:
    data = data.replace(old, new, 1)
    count += 1
    print("5. Restored DUPACK trace")
else:
    print("5. SKIP")

# 6. Remove SEND trace from emit_pkt
old = b'    cb->last_advertised = adv;' + nl + b'    trace_write("SEND seq:%u ack:%u flag:%s", seq, ack, trace_flags(flags));' + nl + b'}'
new = b'    cb->last_advertised = adv;' + nl + b'}'
if old in data:
    data = data.replace(old, new, 1)
    count += 1
    print("6. Removed SEND trace")
else:
    print("6. SKIP")

# 7. Remove RECV trace from tju_handle_packet
old = b'    uint32_t ackv = get_ack(pkt);' + nl + b'    trace_write("RECV seq:%u ack:%u flag:%s", seq, ackv, trace_flags(flags));' + nl
if old in data:
    data = data.replace(old, b'', 1)
    count += 1
    print("7. Removed RECV trace")
else:
    print("7. SKIP")

# 8. Remove RWND trace from handle_data_phase
old = b'    cb->peer_window = adv;' + nl + b'    trace_write("RWND size:%u", adv);' + nl
if old in data:
    data = data.replace(old, b'    cb->peer_window = adv;' + nl, 1)
    count += 1
    print("8. Removed RWND trace")
else:
    print("8. SKIP")

# 9. Remove RTTS trace from rtt_measure
old = b'    clamp_rto(cb);' + nl + b'    trace_write("RTTS SampleRTT:%u EstimatedRTT:%u DeviationRTT:%u TimeoutInterval:%u",' + nl + b'           r_ms, cb->srtt8/8, cb->rttvar8/8, cb->rto_ms);' + nl + b'}'
new = b'    clamp_rto(cb);' + nl + b'}'
if old in data:
    data = data.replace(old, new, 1)
    count += 1
    print("9. Removed RTTS trace")
else:
    print("9. SKIP")

# 10. Remove DELV trace from tju_recv
old = b'    trace_write("DELV seq:%u size:%u", cb->rx_read - n, (unsigned)n);' + nl + nl
if old in data:
    data = data.replace(old, b'', 1)
    count += 1
    print("10. Removed DELV trace")
else:
    print("10. SKIP")

# 11. Remove SWND trace from flush_tx
old = b'        trace_write("SWND size:%u", win);' + nl
if old in data:
    data = data.replace(old, b'', 1)
    count += 1
    print("11. Removed SWND trace")
else:
    print("11. SKIP")

with open(path, 'wb') as f:
    f.write(data)
print(f"\nReverted {count}/11 changes. Back to user's original phase-3 state.")
