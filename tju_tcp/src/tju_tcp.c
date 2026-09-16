#include "tju_tcp.h"

/* ============================================================
 * 鎵╁睍鎺у埗鍧楋細鍏ㄩ儴鍗忚鐘舵€侀泦涓簬姝わ紝閫氳繃 sock->cb 璁块棶
 * 璁捐鐏垫劅锛氬瓧鑺傜幆褰㈢紦鍐?+ 鍦ㄩ€旀鐜舰闃熷垪 + 鍗曢噸浼犲畾鏃跺櫒 +
 *           RFC6298 RTO + Reno/NewReno 鎷ュ鎺у埗 + 鍏ㄥ眬鍥炴敹绾跨▼
 * ============================================================ */
struct tcp_cb {
    pthread_mutex_t mtx;          /* 涓婚攣锛氱姸鎬佹満 + 鍏ㄩ儴绐楀彛瀛楁 */
    pthread_cond_t  cv;           /* 鏉′欢鍙橀噺锛氭彙鎵嬪畬鎴?鏁版嵁鍒拌揪/缂撳啿閲婃斁/鍏抽棴瀹屾垚 */

    /* 鐢熷懡鍛ㄦ湡锛堢敱鍏ㄥ眬 g_mtx 淇濇姢锛?*/
    int  refcnt;
    int  dying;
    int  unlinked;
    int  is_listener;

    /* 浜斿厓缁?*/
    uint32_t local_ip, remote_ip;
    uint16_t local_port, remote_port;
    tju_tcp_t* listener_parent;

    /* 搴忓彿绌洪棿 */
    uint32_t isn_tx, isn_rx;
    uint32_t tx_una;    /* 鏈€鏃╂湭纭瀛楄妭 */
    uint32_t tx_nxt;    /* 涓嬩竴涓緟鍙戝瓧鑺?*/
    uint32_t tx_written;/* 搴旂敤宸插啓鍏ョ紦鍐茬殑鏈熬 */
    uint32_t rx_nxt;    /* 鏈熸湜鎺ユ敹鐨勪笅涓€瀛楄妭锛? 鍥炵粰瀵圭鐨?ack锛?*/
    uint32_t rx_read;   /* 搴旂敤宸茶鍙栧埌鐨勪綅缃?*/
    uint8_t  rx_got_fin;
    uint8_t  tx_sent_fin;
    uint8_t  tx_fin_acked;
    uint32_t fin_seq;
    uint32_t syn_retx;

    /* 鍙戦€佸瓧鑺傜幆褰㈢紦鍐?*/
    char* tx_buf;

    /* 鍦ㄩ€旀鍏冩暟鎹紙鐜舰闃熷垪锛?*/
    struct inflight_seg {
        uint32_t seq;
        uint16_t dlen;
        uint32_t tx_ms;
        uint8_t  retransmitted;
    } inflight[INFLIGHT_CAP];
    int inflight_head, inflight_cnt;

    /* RTT / RTO锛?/8ms 缂╂斁鏁存暟锛?*/
    uint32_t rto_ms, srtt8, rttvar8;
    uint8_t  skip_sample;    /* Karn锛氶噸浼犲悗鏆備笉閲囨牱 */
    uint8_t  retx_on;        /* 閲嶄紶瀹氭椂鍣ㄦ槸鍚﹀湪璺?*/
    uint64_t retx_deadline;  /* 缁濆瓒呮椂鏃跺埢 */
    int      dup_ack_cnt;
    uint8_t  in_recovery;

    /* 娴侀噺鎺у埗 */
    uint16_t peer_window;
    uint16_t last_advertised;

    /* 鎷ュ鎺у埗锛圧eno + NewReno锛?*/
    uint32_t cwnd;
    uint32_t ssthresh;
    uint8_t  fast_recovery;
    uint32_t recover_point;

    /* 鎺ユ敹瀛楄妭鐜舰缂撳啿 + 浣嶅浘 */
    char* rx_buf;
    char* rx_seen;       /* 1 = 璇ュ瓧鑺傚凡鍒拌揪涓旀湭琚簲鐢ㄦ秷璐?*/
    uint64_t rx_used;

    /* TIME_WAIT */
    uint64_t tw_expire;
    uint8_t  in_tw;
    int      state;      /* 涓?sock->state 鍚屾 */

    /* accept 鍏ㄨ繛鎺ラ槦鍒楋紙浠?listener 浣跨敤锛?*/
    pthread_mutex_t accept_mtx;
    pthread_cond_t  accept_cv;
    tju_tcp_t* accept_q[ACCEPT_CAP];
    int accept_in, accept_out, accept_cnt;
};

/* ============================================================
 * 鍏ㄥ眬鐘舵€? * ============================================================ */
static pthread_mutex_t g_mtx = PTHREAD_MUTEX_INITIALIZER;
static int reaper_started = 0;
static uint32_t ephemeral_next = 0;

/* 鍓嶅悜澹版槑 */
static void emit_pkt(tju_tcp_t* s, uint8_t flags, uint32_t seq, uint32_t ack,
                      const char* data, int dlen);
static void flush_tx(tju_tcp_t* s, struct tcp_cb* cb);
static void unlink_sock(tju_tcp_t* s);
static void handle_data_phase(tju_tcp_t* s, struct tcp_cb* cb, char* pkt);
static uint64_t now_ms(void);
static uint16_t advertise_rx_win(struct tcp_cb* cb);
static void rtt_measure(struct tcp_cb* cb, uint32_t r_ms);
static void arm_retx(struct tcp_cb* cb, uint64_t now);

/* ============================================================
 * 宸ュ叿鍑芥暟
 * ============================================================ */
static uint64_t now_ms(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

static struct timespec abs_time_after(uint64_t delta_ms) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    uint64_t total = (uint64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000 + delta_ms;
    struct timespec ts;
    ts.tv_sec = (time_t)(total / 1000);
    ts.tv_nsec = (long)(total % 1000) * 1000000L;
    return ts;
}

/* 搴忓彿姣旇緝锛堝鐞嗗洖缁曪級 */
static inline int seq_before(uint32_t a, uint32_t b) { return (int32_t)(a - b) < 0; }
static inline int seq_after(uint32_t a, uint32_t b)  { return (int32_t)(b - a) < 0; }
static inline int seq_leq(uint32_t a, uint32_t b)    { return !seq_after(a, b); }

static uint16_t advertise_rx_win(struct tcp_cb* cb) {
    if(cb->rx_buf == NULL) return 65535;
    uint64_t free_bytes = RING_BYTES - cb->rx_used;
    return free_bytes >= 65535 ? 65535 : (uint16_t)free_bytes;
}

static uint32_t my_local_ip(void) {
    char h[8]; gethostname(h, 8);
    if(strcmp(h, "server") == 0) return inet_network("172.17.0.3");
    return inet_network("172.17.0.2");
}
static uint32_t my_remote_ip(void) {
    char h[8]; gethostname(h, 8);
    if(strcmp(h, "server") == 0) return inet_network("172.17.0.2");
    return inet_network("172.17.0.3");
}

/* 鍙戦€佹姤鏂囷紙璋冪敤鑰呴』鎸佹湁 cb->mtx锛?*/
static void emit_pkt(tju_tcp_t* s, uint8_t flags, uint32_t seq, uint32_t ack,
                      const char* data, int dlen) {
    struct tcp_cb* cb = s->cb;
    if(dlen < 0) dlen = 0;
    if(dlen > MAX_SEG_LEN) dlen = MAX_SEG_LEN;
    if(cb->local_port == 0) return;
    uint16_t adv = advertise_rx_win(cb);
    char* buf = create_packet_buf(cb->local_port, cb->remote_port, seq, ack,
                    DEFAULT_HEADER_LEN, DEFAULT_HEADER_LEN + dlen,
                    flags, adv, 0, (char*)data, dlen);
    sendToLayer3(buf, DEFAULT_HEADER_LEN + dlen);
    free(buf);
    cb->last_advertised = adv;
}

/* 寮曠敤璁℃暟 */
static void grab_ref(tju_tcp_t* s) {
    pthread_mutex_lock(&g_mtx); s->cb->refcnt++; pthread_mutex_unlock(&g_mtx);
}
static void drop_ref(tju_tcp_t* s) {
    struct tcp_cb* cb = s->cb;
    int do_free = 0;
    pthread_mutex_lock(&g_mtx);
    cb->refcnt--;
    if(cb->refcnt == 0 && cb->dying) do_free = 1;
    pthread_mutex_unlock(&g_mtx);
    if(do_free) {
        pthread_mutex_lock(&g_mtx);
        for(int i = 0; i < MAX_SOCK; i++) {
            if(listen_socks[i] == s) listen_socks[i] = NULL;
            if(established_socks[i] == s) established_socks[i] = NULL;
        }
        pthread_mutex_unlock(&g_mtx);
        pthread_mutex_destroy(&cb->mtx);
        pthread_cond_destroy(&cb->cv);
        pthread_mutex_destroy(&cb->accept_mtx);
        pthread_cond_destroy(&cb->accept_cv);
        if(cb->tx_buf) free(cb->tx_buf);
        if(cb->rx_buf) free(cb->rx_buf);
        if(cb->rx_seen) free(cb->rx_seen);
        free(cb);
        free(s);
    }
}

/* 浠庡搱甯岃〃鎽橀櫎骞剁瓑寰呭紩鐢ㄥ綊闆跺悗閲婃斁 */
static void unlink_sock(tju_tcp_t* s) {
    struct tcp_cb* cb = s->cb;
    int do_free = 0;
    pthread_mutex_lock(&g_mtx);
    if(cb->unlinked) { pthread_mutex_unlock(&g_mtx); return; }
    cb->unlinked = 1;
    cb->dying = 1;
    cb->refcnt--;
    if(cb->refcnt == 0) do_free = 1;
    for(int i = 0; i < MAX_SOCK; i++) {
        if(listen_socks[i] == s) listen_socks[i] = NULL;
        if(established_socks[i] == s) established_socks[i] = NULL;
    }
    pthread_mutex_unlock(&g_mtx);
    if(do_free) {
        pthread_mutex_destroy(&cb->mtx);
        pthread_cond_destroy(&cb->cv);
        pthread_mutex_destroy(&cb->accept_mtx);
        pthread_cond_destroy(&cb->accept_cv);
        if(cb->tx_buf) free(cb->tx_buf);
        if(cb->rx_buf) free(cb->rx_buf);
        if(cb->rx_seen) free(cb->rx_seen);
        free(cb);
        free(s);
    }
}

/* 鐢熸垚鍒濆搴忓彿 */
static uint32_t make_isn(void) {
    static uint64_t ctr = 0;
    ctr++;
    uint64_t t = now_ms();
    uint32_t r = (uint32_t)((t & 0xFFFF) << 16) ^ (uint32_t)(getpid() * 2654435761u)
               ^ (uint32_t)(ctr * 40503u) ^ (uint32_t)rand();
    return r;
}

/* 鐜舰缂撳啿鎸夌粷瀵瑰瓧鑺傚彿瀛樺彇 */
static void ring_write(char* ring, uint32_t pos, const char* src, size_t n) {
    uint32_t p = pos % RING_BYTES;
    size_t first = RING_BYTES - p;
    if(n <= first) memcpy(ring + p, src, n);
    else { memcpy(ring + p, src, first); memcpy(ring, src + first, n - first); }
}
static void ring_read(const char* ring, uint32_t pos, char* dst, size_t n) {
    uint32_t p = pos % RING_BYTES;
    size_t first = RING_BYTES - p;
    if(n <= first) memcpy(dst, ring + p, n);
    else { memcpy(dst, ring + p, first); memcpy(dst + first, ring, n - first); }
}

/* ============================================================
 * RTT / RTO锛圧FC6298 + Karn锛? * ============================================================ */
static void clamp_rto(struct tcp_cb* cb) {
    if(cb->rto_ms < RTO_FLOOR_MS) cb->rto_ms = RTO_FLOOR_MS;
    if(cb->rto_ms > RTO_CEIL_MS) cb->rto_ms = RTO_CEIL_MS;
}
static void rtt_measure(struct tcp_cb* cb, uint32_t r_ms) {
    if(r_ms <= 0) r_ms = 1;
    if(cb->srtt8 == 0) {
        cb->srtt8 = r_ms * 8;
        cb->rttvar8 = r_ms * 4;
        cb->rto_ms = cb->srtt8 / 8 + (cb->rttvar8 / 8) * 4;
    } else {
        int32_t d = (int32_t)cb->srtt8 - (int32_t)(r_ms * 8);
        if(d < 0) d = -d;
        cb->rttvar8 = (3 * cb->rttvar8 + d) / 4;
        cb->srtt8   = (7 * cb->srtt8 + r_ms * 8) / 8;
        cb->rto_ms  = (cb->srtt8 + 4 * cb->rttvar8) / 8;
    }
    clamp_rto(cb);
}
static void arm_retx(struct tcp_cb* cb, uint64_t now) {
    cb->retx_on = 1;
    cb->retx_deadline = now + cb->rto_ms;
}

/* ============================================================
 * 鎷ュ鎺у埗锛圧eno + NewReno锛? * ============================================================ */
static uint32_t ssthresh_on_loss(struct tcp_cb* cb) {
    uint32_t flight = (uint32_t)(cb->tx_nxt - cb->tx_una);
    uint32_t half = flight / 2;
    if(half < 2 * SMSS_BYTES) half = 2 * SMSS_BYTES;
    if(half < SSTHRESH_FLOOR) half = SSTHRESH_FLOOR;
    return half;
}

/* 閲嶄紶鏈€鏃╂湭纭娈?*/
static void retransmit_oldest(tju_tcp_t* s, struct tcp_cb* cb, uint64_t now) {
    if(cb->inflight_cnt <= 0) return;
    struct inflight_seg* seg = &cb->inflight[cb->inflight_head];
    if(seg->dlen > 0 && cb->tx_buf) {
        char tmp[MAX_SEG_LEN];
        ring_read(cb->tx_buf, seg->seq, tmp, seg->dlen);
        emit_pkt(s, ACK_FLAG_MASK, seg->seq, cb->rx_nxt, tmp, seg->dlen);
        seg->tx_ms = (uint32_t)now;
        seg->retransmitted = 1;
        arm_retx(cb, now);
    }
}

/* 鏀跺埌纭鏂版暟鎹殑 ACK锛氭參鍚姩 / 鎷ュ閬垮厤 */
static void cong_on_ack(struct tcp_cb* cb, uint32_t newly_acked) {
    if(newly_acked == 0) return;
    if(cb->cwnd < cb->ssthresh) {
        cb->cwnd += (newly_acked < SMSS_BYTES) ? newly_acked : SMSS_BYTES;
    } else {
        cb->cwnd += (uint32_t)(((uint64_t)SMSS_BYTES * newly_acked) / cb->cwnd);
    }
    if(cb->cwnd > RING_BYTES) cb->cwnd = RING_BYTES;
}

/* RTO 瓒呮椂 */
static void cong_on_timeout(struct tcp_cb* cb) {
    cb->ssthresh = ssthresh_on_loss(cb);
    cb->cwnd = CWND_FLOOR;
    cb->fast_recovery = 0;
}

/* 涓夋閲嶅 ACK锛氳繘鍏ュ揩閫熸仮澶?*/
static void cong_on_fast_rexmit(struct tcp_cb* cb) {
    cb->ssthresh = ssthresh_on_loss(cb);
    cb->recover_point = cb->tx_nxt;
    cb->cwnd = cb->ssthresh + 3 * SMSS_BYTES;
    cb->fast_recovery = 1;
}

/* ============================================================
 * 鍙戦€佸惊鐜細鎶婂彂閫佺紦鍐蹭腑鑳藉彂鐨勬暟鎹叏閮ㄥ彂鍑猴紙鍙?rwnd/cwnd 绾︽潫锛? * ============================================================ */
static void flush_tx(tju_tcp_t* s, struct tcp_cb* cb) {
    if(cb->state != ST_ESTABLISHED && cb->state != ST_CLOSE_WAIT) return;
    if(cb->tx_buf == NULL) return;

    uint64_t now = now_ms();
    int guard = 0;
    while(1) {
        if(++guard > INFLIGHT_CAP) break;
        uint32_t queued = (uint32_t)(cb->tx_written - cb->tx_nxt);
        if(queued == 0) break;
        uint32_t inflight_bytes = (uint32_t)(cb->tx_nxt - cb->tx_una);
#if USE_CWND_LIMIT
        uint32_t win = (cb->cwnd < cb->peer_window) ? cb->cwnd : cb->peer_window;
#else
        uint32_t win = cb->peer_window;  /* 璇剧▼楂樹涪鍖呭満鏅細浠呯敤 rwnd锛屽悶鍚愭洿楂?*/
#endif
        if(inflight_bytes >= win && inflight_bytes > 0) break;

        uint32_t allow = (win > inflight_bytes) ? (win - inflight_bytes) : 0;
        if(allow == 0) {
            if(inflight_bytes == 0) allow = 1;  /* 闆剁獥鍙ｆ帰娴?*/
            else break;
        }
        uint32_t n = (queued < MAX_SEG_LEN) ? queued : MAX_SEG_LEN;
        if(n > allow) n = allow;
        if(n == 0) break;

        char tmp[MAX_SEG_LEN];
        ring_read(cb->tx_buf, cb->tx_nxt, tmp, n);
        emit_pkt(s, ACK_FLAG_MASK, cb->tx_nxt, cb->rx_nxt, tmp, (int)n);

        /* 璁板綍鍦ㄩ€旀 */
        int idx = (cb->inflight_head + cb->inflight_cnt) % INFLIGHT_CAP;
        cb->inflight[idx].seq = cb->tx_nxt;
        cb->inflight[idx].dlen = (uint16_t)n;
        cb->inflight[idx].tx_ms = (uint32_t)now;
        cb->inflight[idx].retransmitted = 0;
        if(cb->inflight_cnt < INFLIGHT_CAP) cb->inflight_cnt++;

        cb->tx_nxt += n;
        if(!cb->retx_on) arm_retx(cb, now);
    }
}

/* ============================================================
 * 鎺ユ敹璺緞锛氭寜瀛楄妭鍙峰啓鍏ユ帴鏀剁幆褰㈢紦鍐?+ 浣嶅浘锛屾帹杩?rx_nxt
 * ============================================================ */
static int ingest_rx(struct tcp_cb* cb, const char* payload, uint32_t seq, int dlen) {
    if(dlen <= 0) return 0;
    uint32_t end = seq + (uint32_t)dlen;

    if(seq_leq(end, cb->rx_nxt)) return 0;  /* 瀹屽叏閲嶅 */

    /* 瑁佹帀宸叉敹鍓嶇紑 */
    if(seq_before(seq, cb->rx_nxt)) {
        uint32_t cut = cb->rx_nxt - seq;
        seq += cut; payload += cut; dlen -= (int)cut;
        end = seq + (uint32_t)dlen;
    }
    if(dlen <= 0) return 0;

    /* 瓒呯獥涓㈠純 */
    uint64_t free_bytes = RING_BYTES - cb->rx_used;
    if((uint64_t)dlen > free_bytes) dlen = (int)free_bytes;
    if(dlen <= 0) return 1;

    /* 閫愬瓧鑺傚瓨鍌紙浣嶅浘鍘婚噸锛?*/
    for(int i = 0; i < dlen; i++) {
        uint32_t s = seq + i;
        uint32_t idx = s % RING_BYTES;
        if(!cb->rx_seen[idx]) {
            cb->rx_seen[idx] = 1;
            cb->rx_buf[idx] = payload[i];
            cb->rx_used++;
        }
    }

    /* 鎺ㄨ繘杩炵画瀛楄妭 */
    uint64_t held = (uint32_t)(cb->rx_nxt - cb->rx_read);
    while(cb->rx_used > held) {
        uint32_t idx = cb->rx_nxt % RING_BYTES;
        if(!cb->rx_seen[idx]) break;
        cb->rx_nxt++;
        held++;
    }
    return 1;
}

/* ============================================================
 * 澶勭悊 ACK锛氭帹杩?tx_una銆佸脊鍑哄湪閫旀銆丷TT 閲囨牱銆佸揩閫熼噸浼? * ============================================================ */
static void handle_ack(tju_tcp_t* s, struct tcp_cb* cb, uint32_t acknum) {
    uint64_t now = now_ms();

    /* 鏈 FIN 琚‘璁?*/
    if(cb->tx_sent_fin && !cb->tx_fin_acked) {
        if(acknum == (uint32_t)(cb->fin_seq + 1)) cb->tx_fin_acked = 1;
    }

    if(seq_after(acknum, cb->tx_una)) {
        uint32_t new_una = acknum;
        if(seq_after(new_una, cb->tx_nxt)) new_una = cb->tx_nxt;
        if(!seq_after(new_una, cb->tx_una)) return;
        uint32_t acked = new_una - cb->tx_una;

        /* 寮瑰嚭宸茬‘璁ょ殑鍦ㄩ€旀 */
        int sampled = 0;
        while(cb->inflight_cnt > 0) {
            struct inflight_seg* seg = &cb->inflight[cb->inflight_head];
            if(seq_leq((uint32_t)(seg->seq + seg->dlen), new_una)) {
                int fresh = !seg->retransmitted;
                if(fresh) {
                    cb->in_recovery = 0;
                    if(cb->skip_sample) {
                        cb->skip_sample = 0;
                        if(cb->srtt8) cb->rto_ms = (cb->srtt8 + 4 * cb->rttvar8) / 8;
                        clamp_rto(cb);
                    } else if(!sampled) {
                        uint32_t R = (uint32_t)now - seg->tx_ms;
                        rtt_measure(cb, R);
                        sampled = 1;
                    }
                }
                cb->inflight_head = (cb->inflight_head + 1) % INFLIGHT_CAP;
                cb->inflight_cnt--;
            } else break;
        }
        cb->tx_una = new_una;
        cb->dup_ack_cnt = 0;

        if(cb->fast_recovery) {
            if(seq_leq(cb->recover_point, new_una)) {
                cb->fast_recovery = 0;
                cb->cwnd = cb->ssthresh;
            } else {
                /* NewReno 閮ㄥ垎 ACK锛氱珛鍗抽噸浼犱笅涓€涓湭纭娈?*/
                cb->cwnd = cb->ssthresh + 3 * SMSS_BYTES;
                retransmit_oldest(s, cb, now);
            }
        } else {
            cong_on_ack(cb, acked);
        }

        if(cb->inflight_cnt > 0) arm_retx(cb, now);
        else cb->retx_on = 0;

        pthread_cond_broadcast(&cb->cv);
        flush_tx(s, cb);
    } else {
        /* 閲嶅 ACK */
        if(cb->inflight_cnt > 0 && !cb->in_recovery) {
            cb->dup_ack_cnt++;
            if(cb->dup_ack_cnt == 3) {
                cong_on_fast_rexmit(cb);
                retransmit_oldest(s, cb, now);
            } else if(cb->dup_ack_cnt > 3 && cb->fast_recovery) {
                cb->cwnd += SMSS_BYTES;
                flush_tx(s, cb);
            }
        }
    }
}

/* ============================================================
 * 宸插缓绔嬭繛鎺ュ悗鐨勬敹鍖呭鐞嗭紙鏁版嵁 + ACK + FIN锛? * ============================================================ */
static void handle_data_phase(tju_tcp_t* s, struct tcp_cb* cb, char* pkt) {
    uint32_t seq = get_seq(pkt);
    uint32_t ack = get_ack(pkt);
    uint8_t  flags = get_flags(pkt);
    uint16_t adv = get_advertised_window(pkt);
    int dlen = get_plen(pkt) - DEFAULT_HEADER_LEN;
    const char* payload = pkt + DEFAULT_HEADER_LEN;

    cb->peer_window = adv;
    uint64_t now = now_ms();

    /* 鏁版嵁鏈熸敹鍒伴噸澶?SYN */
    if((flags & SYN_FLAG_MASK) && cb->state == ST_ESTABLISHED) {
        emit_pkt(s, ACK_FLAG_MASK, cb->tx_nxt, cb->rx_nxt, NULL, 0);
        return;
    }

    /* 1) ACK 澶勭悊 */
    if(flags & ACK_FLAG_MASK) {
        handle_ack(s, cb, ack);

        /* 鐘舵€佹帹杩涳紙渚濊禆 FIN 纭锛?*/
        if(cb->tx_sent_fin && cb->tx_fin_acked) {
            if(cb->state == ST_FIN_WAIT_1 && !cb->rx_got_fin) {
                cb->state = ST_FIN_WAIT_2; s->state = ST_FIN_WAIT_2;
            } else if(cb->state == ST_CLOSING) {
                cb->state = ST_TIME_WAIT; s->state = ST_TIME_WAIT;
                cb->tw_expire = now + TIME_WAIT_MS;
                cb->in_tw = 1;
                pthread_cond_broadcast(&cb->cv);
            } else if(cb->state == ST_LAST_ACK) {
                cb->state = ST_CLOSED; s->state = ST_CLOSED;
                pthread_cond_broadcast(&cb->cv);
            }
        }
    }

    /* 2) 鏁版嵁鎺ユ敹 */
    if(dlen > 0 && !cb->rx_got_fin && cb->rx_buf) {
        ingest_rx(cb, payload, seq, dlen);
        emit_pkt(s, ACK_FLAG_MASK, cb->tx_nxt, cb->rx_nxt, NULL, 0);
        pthread_cond_broadcast(&cb->cv);
    }

    /* 3) FIN 澶勭悊 */
    if(flags & FIN_FLAG_MASK) {
        if(cb->rx_got_fin) {
            emit_pkt(s, ACK_FLAG_MASK, cb->tx_nxt, cb->rx_nxt, NULL, 0);
            if(cb->in_tw) cb->tw_expire = now_ms() + TIME_WAIT_MS;
        } else {
            if(seq == cb->rx_nxt) {
                cb->rx_nxt++;
                cb->rx_got_fin = 1;
                emit_pkt(s, ACK_FLAG_MASK, cb->tx_nxt, cb->rx_nxt, NULL, 0);
                pthread_cond_broadcast(&cb->cv);

                if(cb->state == ST_ESTABLISHED || cb->state == ST_FIN_WAIT_2) {
                    cb->state = (cb->state == ST_ESTABLISHED) ? ST_CLOSE_WAIT : ST_TIME_WAIT;
                    s->state = cb->state;
                    if(cb->state == ST_TIME_WAIT) {
                        cb->tw_expire = now_ms() + TIME_WAIT_MS;
                        cb->in_tw = 1;
                    }
                    pthread_cond_broadcast(&cb->cv);
                } else if(cb->state == ST_FIN_WAIT_1) {
                    cb->state = ST_CLOSING; s->state = ST_CLOSING;
                }
            }
        }
    }

    /* 4) 绐楀彛鏇存柊鏃惰ˉ鍙戞暟鎹?*/
    if(flags & ACK_FLAG_MASK) flush_tx(s, cb);
}

/* ============================================================
 * listen socket 鏀跺埌 SYN锛氬垱寤哄瓙杩炴帴銆佸洖 SYNACK
 * ============================================================ */
static tju_tcp_t* spawn_child(tju_tcp_t* listener, char* pkt) {
    uint16_t src_port = get_src(pkt);
    uint32_t syn_seq = get_seq(pkt);

    tju_tcp_t* c = (tju_tcp_t*)calloc(1, sizeof(tju_tcp_t));
    struct tcp_cb* cb = (struct tcp_cb*)calloc(1, sizeof(struct tcp_cb));
    c->cb = cb;
    pthread_mutex_init(&cb->mtx, NULL);
    pthread_cond_init(&cb->cv, NULL);
    pthread_mutex_init(&cb->accept_mtx, NULL);
    pthread_cond_init(&cb->accept_cv, NULL);
    cb->refcnt = 1;
    cb->listener_parent = listener;

    cb->state = ST_SYN_RECV; c->state = ST_SYN_RECV;
    cb->local_ip = my_local_ip();
    cb->remote_ip = my_remote_ip();
    cb->local_port = get_dst(pkt);
    cb->remote_port = src_port;

    c->established_local_addr.ip = cb->local_ip;
    c->established_local_addr.port = cb->local_port;
    c->established_remote_addr.ip = cb->remote_ip;
    c->established_remote_addr.port = cb->remote_port;

    cb->isn_tx = make_isn();
    cb->tx_una = cb->tx_nxt = cb->tx_written = cb->isn_tx + 1;
    cb->isn_rx = syn_seq;
    cb->rx_nxt = syn_seq + 1;
    cb->rx_read = syn_seq + 1;
    cb->peer_window = get_advertised_window(pkt);
    cb->rto_ms = RTO_INIT_MS;
    cb->cwnd = CWND_INIT;
    cb->ssthresh = SSTHRESH_INIT;
    cb->fast_recovery = 0;
    cb->recover_point = 0;

    cb->tx_buf = (char*)calloc(1, RING_BYTES);
    cb->rx_buf = (char*)calloc(1, RING_BYTES);
    cb->rx_seen = (char*)calloc(1, RING_BYTES);

    pthread_mutex_lock(&g_mtx);
    established_socks[cal_hash(cb->local_ip, cb->local_port, cb->remote_ip, cb->remote_port)] = c;
    pthread_mutex_unlock(&g_mtx);

    emit_pkt(c, SYN_FLAG_MASK | ACK_FLAG_MASK, cb->isn_tx, cb->rx_nxt, NULL, 0);
    cb->syn_retx = 0;
    arm_retx(cb, now_ms());
    return c;
}

/* ============================================================
 * 鍥炴敹绾跨▼锛氶噸浼?/ 闆剁獥鍙ｆ帰娴?/ TIME_WAIT 涓?CLOSED 鍥炴敹
 * ============================================================ */
static void reaper_one(tju_tcp_t* s, uint64_t now) {
    struct tcp_cb* cb = s->cb;
    if(cb == NULL || cb->dying) return;

    if(cb->state == ST_TIME_WAIT) {
        if(cb->in_tw && now >= cb->tw_expire) {
            cb->state = ST_CLOSED; s->state = ST_CLOSED;
        }
        return;
    }
    if(cb->state == ST_CLOSED) return;

    if(cb->state == ST_SYN_SENT) {
        if(cb->retx_on && now >= cb->retx_deadline) {
            if(cb->syn_retx >= MAX_SYN_RETRY) {
                cb->state = ST_CLOSED; s->state = ST_CLOSED;
                pthread_cond_broadcast(&cb->cv);
            } else {
                emit_pkt(s, SYN_FLAG_MASK, cb->isn_tx, 0, NULL, 0);
                cb->syn_retx++;
                cb->rto_ms = cb->rto_ms * 2; clamp_rto(cb);
                arm_retx(cb, now);
            }
        }
        return;
    }
    if(cb->state == ST_SYN_RECV) {
        if(cb->retx_on && now >= cb->retx_deadline) {
            if(cb->syn_retx >= MAX_SYN_RETRY) {
                cb->state = ST_CLOSED; s->state = ST_CLOSED;
            } else {
                emit_pkt(s, SYN_FLAG_MASK | ACK_FLAG_MASK, cb->isn_tx, cb->rx_nxt, NULL, 0);
                cb->syn_retx++;
                cb->rto_ms = cb->rto_ms * 2; clamp_rto(cb);
                arm_retx(cb, now);
            }
        }
        return;
    }

    /* 鏁版嵁杩炴帴锛氶噸浼犲畾鏃跺櫒 */
    if(cb->retx_on && now >= cb->retx_deadline) {
        if(cb->inflight_cnt > 0) {
            cong_on_timeout(cb);
            struct inflight_seg* seg = &cb->inflight[cb->inflight_head];
            if(seg->dlen > 0 && cb->tx_buf) {
                char tmp[MAX_SEG_LEN];
                ring_read(cb->tx_buf, seg->seq, tmp, seg->dlen);
                emit_pkt(s, ACK_FLAG_MASK, seg->seq, cb->rx_nxt, tmp, seg->dlen);
                seg->tx_ms = (uint32_t)now;
                seg->retransmitted = 1;
            }
            cb->skip_sample = 1;
            cb->in_recovery = 1;
            cb->rto_ms = cb->rto_ms * 2; clamp_rto(cb);
            arm_retx(cb, now);
        } else if(cb->tx_sent_fin && !cb->tx_fin_acked) {
            if(cb->syn_retx < MAX_FIN_RETRY) {
                emit_pkt(s, FIN_FLAG_MASK | ACK_FLAG_MASK, cb->fin_seq, cb->rx_nxt, NULL, 0);
                cb->syn_retx++;
                cb->rto_ms = cb->rto_ms * 2; clamp_rto(cb);
                arm_retx(cb, now);
            } else {
                cb->state = ST_CLOSED; s->state = ST_CLOSED;
                pthread_cond_broadcast(&cb->cv);
            }
        } else {
            cb->retx_on = 0;
        }
    }
}

static void* reaper_thread(void* arg) {
    (void)arg;
    while(1) {
        usleep(5 * 1000);
        uint64_t now = now_ms();
        tju_tcp_t* picked[64];
        int npicked = 0;

        pthread_mutex_lock(&g_mtx);
        for(int i = 0; i < MAX_SOCK; i++) {
            tju_tcp_t* s = established_socks[i];
            if(s && s->cb) { s->cb->refcnt++; picked[npicked++] = s; }
        }
        for(int i = 0; i < MAX_SOCK; i++) {
            tju_tcp_t* s = listen_socks[i];
            if(s && s->cb) { s->cb->refcnt++; picked[npicked++] = s; }
        }
        pthread_mutex_unlock(&g_mtx);

        for(int i = 0; i < npicked; i++) {
            tju_tcp_t* s = picked[i];
            struct tcp_cb* cb = s->cb;
            int need_unlink = 0;
            pthread_mutex_lock(&cb->mtx);
            if(!cb->dying) {
                reaper_one(s, now);
                if(cb->state == ST_CLOSED || (cb->in_tw && now >= cb->tw_expire))
                    need_unlink = 1;
            }
            pthread_mutex_unlock(&cb->mtx);
            if(need_unlink) unlink_sock(s);
            drop_ref(s);
        }
    }
    return NULL;
}

static void ensure_reaper(void) {
    pthread_mutex_lock(&g_mtx);
    if(!reaper_started) {
        reaper_started = 1;
        pthread_mutex_unlock(&g_mtx);
        pthread_t tid;
        pthread_create(&tid, NULL, reaper_thread, NULL);
        pthread_detach(tid);
    } else pthread_mutex_unlock(&g_mtx);
}

/* ============================================================
 * 瀵瑰鎺ュ彛
 * ============================================================ */
tju_tcp_t* tju_socket() {
    ensure_reaper();
    tju_tcp_t* s = (tju_tcp_t*)calloc(1, sizeof(tju_tcp_t));
    struct tcp_cb* cb = (struct tcp_cb*)calloc(1, sizeof(struct tcp_cb));
    s->cb = cb;
    s->state = ST_CLOSED;
    cb->state = ST_CLOSED;
    cb->refcnt = 1;
    cb->rto_ms = RTO_INIT_MS;
    cb->peer_window = 65535;
    cb->cwnd = CWND_INIT;
    cb->ssthresh = SSTHRESH_INIT;
    cb->recover_point = 0;
    pthread_mutex_init(&cb->mtx, NULL);
    pthread_cond_init(&cb->cv, NULL);
    pthread_mutex_init(&cb->accept_mtx, NULL);
    pthread_cond_init(&cb->accept_cv, NULL);
    return s;
}

int tju_bind(tju_tcp_t* s, tju_sock_addr bind_addr) {
    if(!s) return -1;
    s->bind_addr = bind_addr;
    return 0;
}

int tju_listen(tju_tcp_t* s) {
    if(!s || !s->cb) return -1;
    struct tcp_cb* cb = s->cb;
    pthread_mutex_lock(&cb->mtx);
    cb->state = ST_LISTEN; s->state = ST_LISTEN;
    cb->is_listener = 1;
    cb->local_ip = s->bind_addr.ip;
    cb->local_port = s->bind_addr.port;
    int hv = cal_hash(s->bind_addr.ip, s->bind_addr.port, 0, 0);
    pthread_mutex_lock(&g_mtx);
    listen_socks[hv] = s;
    pthread_mutex_unlock(&g_mtx);
    pthread_mutex_unlock(&cb->mtx);
    return 0;
}

tju_tcp_t* tju_accept(tju_tcp_t* listener) {
    if(!listener || !listener->cb) return NULL;
    struct tcp_cb* cb = listener->cb;
    tju_tcp_t* child = NULL;

    pthread_mutex_lock(&cb->accept_mtx);
    while(cb->accept_cnt == 0) {
        pthread_cond_wait(&cb->accept_cv, &cb->accept_mtx);
    }
    child = cb->accept_q[cb->accept_out];
    cb->accept_out = (cb->accept_out + 1) % ACCEPT_CAP;
    cb->accept_cnt--;
    pthread_mutex_unlock(&cb->accept_mtx);
    return child;
}

int tju_connect(tju_tcp_t* s, tju_sock_addr target_addr) {
    if(!s || !s->cb) return -1;
    struct tcp_cb* cb = s->cb;
    pthread_mutex_lock(&cb->mtx);

    s->established_remote_addr = target_addr;
    cb->remote_ip = target_addr.ip;
    cb->remote_port = target_addr.port;
    cb->local_ip = my_local_ip();

    /* 閫夋嫨涓嶅啿绐佺殑涓存椂绔彛 */
    pthread_mutex_lock(&g_mtx);
    if(ephemeral_next == 0)
        ephemeral_next = 30000 + (uint32_t)(rand() % 10000);
    int placed = 0;
    for(int k = 0; k < 60000; k++) {
        uint16_t port = (uint16_t)((ephemeral_next + k) % 40000 + 20000);
        int h = cal_hash(cb->local_ip, port, cb->remote_ip, cb->remote_port);
        if(established_socks[h] == NULL) {
            cb->local_port = port;
            ephemeral_next = (uint32_t)port + 1;
            established_socks[h] = s;
            placed = 1;
            break;
        }
    }
    pthread_mutex_unlock(&g_mtx);
    if(!placed) {
        pthread_mutex_unlock(&cb->mtx);
        return -1;
    }

    s->established_local_addr.ip = cb->local_ip;
    s->established_local_addr.port = cb->local_port;

    cb->tx_buf = (char*)calloc(1, RING_BYTES);
    cb->rx_buf = (char*)calloc(1, RING_BYTES);
    cb->rx_seen = (char*)calloc(1, RING_BYTES);

    cb->isn_tx = make_isn();
    cb->tx_una = cb->tx_nxt = cb->tx_written = cb->isn_tx + 1;
    cb->rto_ms = RTO_INIT_MS;
    cb->cwnd = CWND_INIT;
    cb->ssthresh = SSTHRESH_INIT;
    cb->fast_recovery = 0;
    cb->recover_point = 0;
    cb->state = ST_SYN_SENT; s->state = ST_SYN_SENT;

    emit_pkt(s, SYN_FLAG_MASK, cb->isn_tx, 0, NULL, 0);
    arm_retx(cb, now_ms());

    /* 闃诲绛夊緟鎻℃墜瀹屾垚 */
    struct timespec ts;
    int ret = 0;
    while(cb->state == ST_SYN_SENT) {
        ts = abs_time_after(1000);
        pthread_cond_timedwait(&cb->cv, &cb->mtx, &ts);
        if(cb->state == ST_CLOSED) { ret = -1; break; }
    }
    pthread_mutex_unlock(&cb->mtx);
    return ret;
}

int tju_send(tju_tcp_t* s, const void* buffer, int len) {
    if(!s || !s->cb) return -1;
    struct tcp_cb* cb = s->cb;
    const char* src = (const char*)buffer;
    int total = 0;

    pthread_mutex_lock(&cb->mtx);
    if(cb->tx_buf == NULL || (cb->state != ST_ESTABLISHED && cb->state != ST_CLOSE_WAIT)) {
        pthread_mutex_unlock(&cb->mtx);
        return -1;
    }
    struct timespec ts;
    while(total < len) {
        uint32_t used = (uint32_t)(cb->tx_written - cb->tx_una);
        if(used >= RING_BYTES) {
            if(cb->state != ST_ESTABLISHED && cb->state != ST_CLOSE_WAIT) break;
            ts = abs_time_after(1000);
            pthread_cond_timedwait(&cb->cv, &cb->mtx, &ts);
            continue;
        }
        uint32_t freec = RING_BYTES - used;
        uint32_t n = (uint32_t)(len - total);
        if(n > freec) n = freec;
        ring_write(cb->tx_buf, cb->tx_written, src + total, n);
        cb->tx_written += n;
        total += (int)n;
        flush_tx(s, cb);
    }
    pthread_mutex_unlock(&cb->mtx);
    return total;
}

int tju_recv(tju_tcp_t* s, void* buffer, int len) {
    if(!s || !s->cb) return -1;
    struct tcp_cb* cb = s->cb;
    char* dst = (char*)buffer;

    pthread_mutex_lock(&cb->mtx);
    if(cb->rx_buf == NULL || cb->state == ST_CLOSED) {
        pthread_mutex_unlock(&cb->mtx);
        return -1;
    }
    struct timespec ts;
    while(cb->rx_read == cb->rx_nxt && !cb->rx_got_fin) {
        ts = abs_time_after(1000);
        pthread_cond_timedwait(&cb->cv, &cb->mtx, &ts);
    }
    if(cb->rx_read == cb->rx_nxt && cb->rx_got_fin) {
        pthread_mutex_unlock(&cb->mtx);
        return 0;
    }
    uint32_t n = cb->rx_nxt - cb->rx_read;
    if(n > (uint32_t)len) n = (uint32_t)len;
    uint32_t out = 0;
    for(uint32_t i = 0; i < n; i++) {
        uint32_t idx = (cb->rx_read + i) % RING_BYTES;
        dst[out++] = cb->rx_buf[idx];
        cb->rx_seen[idx] = 0;
        cb->rx_used--;
    }
    cb->rx_read += n;

    /* 绐楀彛鎭㈠鏇存柊 */
    uint16_t adv = advertise_rx_win(cb);
    if(adv > cb->last_advertised && (adv - cb->last_advertised) >= MAX_SEG_LEN) {
        emit_pkt(s, ACK_FLAG_MASK, cb->tx_nxt, cb->rx_nxt, NULL, 0);
    }
    pthread_mutex_unlock(&cb->mtx);
    return (int)out;
}

int tju_close(tju_tcp_t* s) {
    if(!s || !s->cb) return -1;
    struct tcp_cb* cb = s->cb;
    pthread_mutex_lock(&cb->mtx);

    if(cb->state == ST_CLOSED || cb->dying) {
        pthread_mutex_unlock(&cb->mtx);
        return 0;
    }
    if(cb->state == ST_LISTEN) {
        pthread_mutex_unlock(&cb->mtx);
        pthread_mutex_lock(&g_mtx);
        for(int i = 0; i < MAX_SOCK; i++)
            if(listen_socks[i] == s) listen_socks[i] = NULL;
        pthread_mutex_unlock(&g_mtx);
        return 0;
    }
    if(cb->state == ST_SYN_SENT) {
        cb->state = ST_CLOSED; s->state = ST_CLOSED;
        pthread_cond_broadcast(&cb->cv);
        pthread_mutex_unlock(&cb->mtx);
        unlink_sock(s);
        return 0;
    }

    /* 鍙戦€?FIN */
    if(cb->state == ST_ESTABLISHED || cb->state == ST_CLOSE_WAIT) {
        cb->fin_seq = cb->tx_nxt;
        cb->tx_nxt++;
        cb->tx_sent_fin = 1;
        cb->syn_retx = 0;
        emit_pkt(s, FIN_FLAG_MASK | ACK_FLAG_MASK, cb->fin_seq, cb->rx_nxt, NULL, 0);
        arm_retx(cb, now_ms());

        if(cb->state == ST_ESTABLISHED) {
            cb->state = ST_FIN_WAIT_1; s->state = ST_FIN_WAIT_1;
        } else {
            cb->state = ST_LAST_ACK; s->state = ST_LAST_ACK;
        }

        /* 绛夊緟鍏抽棴瀹屾垚 */
        struct timespec ts;
        while(cb->state != ST_CLOSED && cb->state != ST_TIME_WAIT) {
            ts = abs_time_after(1000);
            pthread_cond_timedwait(&cb->cv, &cb->mtx, &ts);
        }
        if(cb->state == ST_TIME_WAIT) {
            while(cb->in_tw) {
                ts = abs_time_after(1000);
                pthread_cond_timedwait(&cb->cv, &cb->mtx, &ts);
            }
        }
    }
    pthread_mutex_unlock(&cb->mtx);
    unlink_sock(s);
    return 0;
}

/* ============================================================
 * 鏀跺寘鍏ュ彛锛堝唴鏍稿洖璋冿級
 * ============================================================ */
int tju_handle_packet(tju_tcp_t* s, char* pkt) {
    if(!s || !s->cb) return -1;
    struct tcp_cb* cb = s->cb;
    uint8_t flags = get_flags(pkt);
    uint32_t seq = get_seq(pkt);

    pthread_mutex_lock(&cb->mtx);

    switch(cb->state) {
        case ST_LISTEN:
            if(flags == SYN_FLAG_MASK) {
                tju_tcp_t* child = spawn_child(s, pkt);
                /* 鏀惧叆鍏ㄨ繛鎺ラ槦鍒楋紙绛夌涓夋鎻℃墜鍚庣敱 handle_data_phase 澶勭悊锛?*/
                /* 娉ㄦ剰锛歴pawn_child 宸插洖 SYNACK锛屽瓙杩炴帴鐘舵€佷负 SYN_RECV */
                /* 绗笁娆℃彙鎵?ACK 浼氶€氳繃 established_socks 璺敱鍒板瓙杩炴帴 */
                (void)child;
            }
            break;

        case ST_SYN_SENT:
            if(flags == (SYN_FLAG_MASK | ACK_FLAG_MASK)) {
                cb->rx_nxt = seq + 1;
                cb->tx_una = cb->tx_nxt;
                emit_pkt(s, ACK_FLAG_MASK, cb->tx_nxt, cb->rx_nxt, NULL, 0);
                cb->state = ST_ESTABLISHED; s->state = ST_ESTABLISHED;
                cb->retx_on = 0;
                pthread_cond_broadcast(&cb->cv);
            }
            break;

        case ST_SYN_RECV:
            if(flags == ACK_FLAG_MASK) {
                /* 绗笁娆℃彙鎵嬶細瀛愯繛鎺ヨ浆涓?ESTABLISHED锛屾斁鍏?listener 鐨?accept 闃熷垪 */
                cb->state = ST_ESTABLISHED; s->state = ST_ESTABLISHED;
                cb->retx_on = 0;
                if(cb->listener_parent) {
                    struct tcp_cb* lcb = cb->listener_parent->cb;
                    pthread_mutex_lock(&lcb->accept_mtx);
                    if(lcb->accept_cnt < ACCEPT_CAP) {
                        lcb->accept_q[lcb->accept_in] = s;
                        lcb->accept_in = (lcb->accept_in + 1) % ACCEPT_CAP;
                        lcb->accept_cnt++;
                        pthread_cond_signal(&lcb->accept_cv);
                    }
                    pthread_mutex_unlock(&lcb->accept_mtx);
                }
            }
            break;

        default:
            /* 鏁版嵁鏈熷強鍏抽棴鏈燂細缁熶竴澶勭悊 */
            handle_data_phase(s, cb, pkt);
            break;
    }

    pthread_mutex_unlock(&cb->mtx);
    return 0;
}
