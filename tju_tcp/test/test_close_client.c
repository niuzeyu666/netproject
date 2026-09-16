#include "tju_tcp.h"
#include <string.h>
#include <signal.h>

void fflushbeforeexit(int signo){
    exit(0);
}

void sleep_no_wake(int sec){  
    do{        
        sec =sleep(sec);
    }while(sec > 0);             
}

int main(int argc, char **argv) {
    signal(SIGHUP, fflushbeforeexit);
    signal(SIGINT, fflushbeforeexit);
    signal(SIGQUIT, fflushbeforeexit);

    // 寮€鍚豢鐪熺幆澧?
    startSimulation();

    tju_tcp_t* my_socket = tju_socket();
    
    tju_sock_addr target_addr;
    target_addr.ip = inet_network("172.17.0.6");
    target_addr.port = 1234;

    tju_connect(my_socket, target_addr);
    
    sleep_no_wake(1);
    printf("[鏂紑杩炴帴娴嬭瘯-瀹㈡埛绔痌 璋冪敤 tju_close\n");
    tju_close(my_socket);

    printf("[鏂紑杩炴帴娴嬭瘯-瀹㈡埛绔痌 绛夊緟10s纭繚杩炴帴瀹屽叏鏂紑\n");
    sleep_no_wake(10);

    return EXIT_SUCCESS;
}
