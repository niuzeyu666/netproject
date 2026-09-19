#!/bin/bash
# Run a congestion test and generate figures
cd /vagrant/tju_tcp/test
pkill -9 -f rdt_server 2>/dev/null
pkill -9 -f rdt_client 2>/dev/null
sleep 1

PARAMS="$1"
OUTDIR="$2"

rm -f client.event.trace server.event.trace client.log server.log
python3 test_congestion.py $PARAMS > /tmp/cong_${OUTDIR}.log 2>&1

mkdir -p /vagrant/tju_tcp/figure/${OUTDIR}
python3 gen_graph_win.py 10 2>&1 | tee /tmp/graph_${OUTDIR}.log
python3 gen_graph_seq.py 2>&1

cp /vagrant/tju_tcp/figure/wds10/*.png /vagrant/tju_tcp/figure/${OUTDIR}/ 2>/dev/null
cp /vagrant/tju_tcp/test/SeqNum_VS_Time.png /vagrant/tju_tcp/figure/${OUTDIR}/ 2>/dev/null
cp /vagrant/tju_tcp/test/client.event.trace /vagrant/tju_tcp/figure/${OUTDIR}/ 2>/dev/null
cp /vagrant/tju_tcp/test/server.event.trace /vagrant/tju_tcp/figure/${OUTDIR}/ 2>/dev/null

echo "DONE: ${OUTDIR}"
