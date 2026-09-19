path = 'tju_tcp/src/tju_tcp.c'
with open(path, 'rb') as f:
    data = f.read()

old = b'    int cwnd_type = (cb->cwnd < cb->ssthresh) ? 0 : 1;\n    trace_write("CWND type:%d size:%u", cwnd_type, cb->cwnd);'
new = b'    trace_write("CWND state=%s value=%u acked=%u", cc_state(cb), cb->cwnd, newly_acked);'

if old in data:
    data = data.replace(old, new, 1)
    with open(path, 'wb') as f:
        f.write(data)
    print('Fixed cong_on_ack (LF)')
else:
    old_crlf = old.replace(b'\n', b'\r\n')
    if old_crlf in data:
        data = data.replace(old_crlf, new.replace(b'\n', b'\r\n'), 1)
        with open(path, 'wb') as f:
            f.write(data)
        print('Fixed cong_on_ack (CRLF)')
    else:
        print('Pattern not found')
