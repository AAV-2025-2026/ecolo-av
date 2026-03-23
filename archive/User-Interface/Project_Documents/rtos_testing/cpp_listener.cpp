#include <iostream>
#include <cstring>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

struct IMUPacket{ //container representing the structure in which the messages will be stored and sent over at every callback
  float ang_vel_x;
  float ang_vel_y;
  float ang_vel_z;
  float lin_acc_x;
  float lin_acc_y;
  float lin_acc_z;
};

int main(){

int sock = socket(AF_INET, SOCK_DGRAM, 0); // AF_INET = IPv4, SOCK_DGRAM = UDP behavior, 0 = default protocol for this socket type

struct sockaddr_in recc; //sockaddr_in is structure type of IPv4 socket address
                              //recc = instance of that structure
      
std::memset(&recc, 0, sizeof(recc)); //clear the entire structure to zero within the instance of the IPv4 structure
recc.sin_family = AF_INET; //defines the address as an IPv4 address
recc.sin_port = htons(5000); //set the destination port (send on and listen on)
recc.sin_addr.s_addr = INADDR_ANY; //set the destination IP address, right now set to local host, later change to IP address of the computer that will have the receiving UPD socket

if (bind(sock, (sockaddr*)&recc, sizeof(recc)) < 0){
    std::cerr << "Bind failed\n";
    close(sock);
    return 1;
}


while(true){

    IMUPacket pkt;

    ssize_t bytes_receied  = recvfrom(sock, &pkt, sizeof(pkt), 0, nullptr, nullptr);




std::cout << "Angular velocity: [" << pkt.ang_vel_x  << "," << pkt.ang_vel_y << "," << pkt.ang_vel_z << "]\n";

std::cout << "Linear Acceleration: [" << pkt.lin_acc_x  << "," << pkt.lin_acc_y << "," << pkt.lin_acc_z << "]\n";

};

close(sock);
return 0;
}