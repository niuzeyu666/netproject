#ifndef _GLOBAL_H_
#define _GLOBAL_H_

#include <netinet/in.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/select.h>
#include <arpa/inet.h>

/* 鍩虹甯搁噺 */
#define SIZE32 4
#define SIZE16 2
#define SIZE8  1
#define NO_FLAG 0
#define TRUE 1
#define FALSE 0

/* 鍖呴暱闄愬埗锛堥伩鍏岻P鍒嗙墖锛?*/
#define MAX_SEG_LEN 1375
#define MAX_PKT_LEN 1400
#define MAX_LEN 1400

/* TCP 鐘舵€侊紙鐢ㄥ畯鑰岄潪enum锛屼笌妗嗘灦鍏煎锛?*/
#define ST_CLOSED      0
#define ST_LISTEN      1
#define ST_SYN_SENT    2
#define ST_SYN_RECV    3
#define ST_ESTABLISHED 4
#define ST_FIN_WAIT_1  5
#define ST_FIN_WAIT_2  6
#define ST_CLOSE_WAIT  7
#define ST_CLOSING     8
#define ST_LAST_ACK    9
#define ST_TIME_WAIT   10

/* 不带前缀的状态别名（兼容测试框架 test_close_server.c 等） */
#define CLOSED      ST_CLOSED
#define LISTEN      ST_LISTEN
#define SYN_SENT    ST_SYN_SENT
#define SYN_RECV    ST_SYN_RECV
#define ESTABLISHED ST_ESTABLISHED
#define FIN_WAIT_1  ST_FIN_WAIT_1
#define FIN_WAIT_2  ST_FIN_WAIT_2
#define CLOSE_WAIT  ST_CLOSE_WAIT
#define CLOSING     ST_CLOSING
#define LAST_ACK    ST_LAST_ACK
#define TIME_WAIT   ST_TIME_WAIT

/* 鎺ユ敹绐楀彛瀹归噺锛堝瓧鑺傦級 */
#define RX_WIN_BYTES (32 * MAX_SEG_LEN)

/* ===== 鐜舰缂撳啿涓庡湪閫旀閰嶇疆 ===== */
#define RING_BYTES   (7000000u)   /* 7MB 瀛楄妭鐜舰缂撳啿锛?= 5000*SMSS锛?*/
#define INFLIGHT_CAP 96            /* 鍦ㄩ€旀鍏冩暟鎹幆褰㈤槦鍒楀閲?*/
#define ACCEPT_CAP   32            /* listen 鍏ㄨ繛鎺ラ槦鍒楀閲?*/

/* ===== RTO / RTT锛圧FC6298锛屾绉掑崟浣嶏紝srtt/rttvar 鐢?1/8ms 缂╂斁鏁存暟锛?===== */
#define RTO_INIT_MS   1000
#define RTO_FLOOR_MS  200
#define RTO_CEIL_MS   4000
#define TIME_WAIT_MS  4000

/* ===== 鎷ュ鎺у埗锛圧eno + NewReno锛屽瓧鑺備负鍗曚綅锛?===== */
#define SMSS_BYTES    MAX_SEG_LEN
#define CWND_INIT     (10 * SMSS_BYTES)
#define SSTHRESH_INIT (65535u)
#define SSTHRESH_FLOOR (2 * SMSS_BYTES)
#define CWND_FLOOR    SMSS_BYTES

/* 鏄惁鐢?cwnd 闄愬埗鍙戦€佺獥鍙ｏ細0 = 浠呯敤 rwnd锛堣绋嬮珮涓㈠寘鍦烘櫙涓嬪悶鍚愭洿楂橈級 */
#define USE_CWND_LIMIT 1

#ifndef INIT_WDSIZE
#define INIT_WDSIZE 10
#endif

/* ===== 鎻℃墜/ FIN 閲嶄紶涓婇檺 ===== */
#define MAX_SYN_RETRY 7
#define MAX_FIN_RETRY 20

typedef struct {
    uint32_t ip;
    uint16_t port;
} tju_sock_addr;

/* 鍙戦€佺獥鍙ｏ紙妗嗘灦鍘熷瀛楁锛屼繚鐣欏吋瀹癸級 */
typedef struct {
    uint16_t window_size;
} sender_window_t;

/* 鎺ユ敹绐楀彛锛堟鏋跺師濮嬪瓧娈碉紝淇濈暀鍏煎锛?*/
typedef struct {
    char received[RX_WIN_BYTES];
} receiver_window_t;

typedef struct {
    sender_window_t* wnd_send;
    receiver_window_t* wnd_recv;
} window_t;

/* ============================================================
 * 鍓嶅悜澹版槑锛氭墿灞曟帶鍒跺潡锛堟壙杞藉叏閮ㄥ崗璁姸鎬侊紝閫氳繃 sock->cb 璁块棶锛? * ============================================================ */
struct tcp_cb;

/* TJU_TCP 涓荤粨鏋勪綋锛堟鏋惰姹傜殑瀛楁 + 鎵╁睍鎺у埗鍧楁寚閽堬級 */
typedef struct {
    int state;
    tju_sock_addr bind_addr;
    tju_sock_addr established_local_addr;
    tju_sock_addr established_remote_addr;

    pthread_mutex_t send_lock;
    char* sending_buf;
    int sending_len;

    pthread_mutex_t recv_lock;
    char* received_buf;
    int received_len;

    pthread_cond_t wait_cond;
    window_t window;

    struct tcp_cb* cb;   /* 鎵╁睍鎺у埗鍧楋紙鍏ㄩ儴鍗忚鐘舵€佹墍鍦級 */
} tju_tcp_t;

#endif
