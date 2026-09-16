#include "tju_tcp.h"
#include <string.h>

int TEST_TYPE;  //0 娴嬭瘯鍏堝悗鏂紑
                //1 娴嬭瘯鍚屾椂鏂紑

int main(int argc, char **argv) { 
    startSimulation();

    tju_tcp_t* my_server = tju_socket();
    
    tju_sock_addr bind_addr;
    bind_addr.ip = inet_network("127.17.0.3");
    bind_addr.port = 1234;

    tju_bind(my_server, bind_addr);

    tju_listen(my_server);

    tju_tcp_t* new_conn = tju_accept(my_server);


    if (argc==2){
        TEST_TYPE = atoi(argv[1]);
        if (TEST_TYPE==0){
            printf("[鏈嶅姟绔痌 娴嬭瘯鍙屾柟鍏堝悗鏂紑杩炴帴鐨勬儏鍐礬n");
            while(new_conn->state != CLOSED){}
        }
        else if (TEST_TYPE==1){
            printf("[鏈嶅姟绔痌 娴嬭瘯鍙屾柟鍚屾椂鏂紑杩炴帴鐨勬儏鍐礬n");
            tju_close(new_conn);
        }
        else{
            printf("[鏈嶅姟绔痌 鏈煡娴嬭瘯绫诲瀷\n");
        }
    }
    

    printf("STATE TRANSFORM TO CLOSED\n");
    return EXIT_SUCCESS;
}
