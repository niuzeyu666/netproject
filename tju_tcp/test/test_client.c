#include "tju_tcp.h"
#include <string.h>


int main(int argc, char **argv) {
    // 寮€鍚豢鐪熺幆澧?
    startSimulation();

    tju_tcp_t* my_socket = tju_socket();
    
    tju_sock_addr target_addr;
    target_addr.ip = inet_network("172.17.0.6");
    target_addr.port = 1234;

    tju_connect(my_socket, target_addr);

    sleep(5);

    return EXIT_SUCCESS;
}
