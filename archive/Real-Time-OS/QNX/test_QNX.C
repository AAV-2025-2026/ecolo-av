#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#define PORT 9000

#pragma pack(push, 1)
typedef struct {
    uint32_t seq;
    float ax, ay, az;
    float gx, gy, gz;
} ImuUdpPacket;
#pragma pack(pop)

int main(void)
{
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) { perror("socket"); return 1; }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PORT);
    addr.sin_addr.s_addr = INADDR_ANY;

    if (bind(sock, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return 1;
    }

    printf("Listening UDP on port %d...\n", PORT);

    while (1) {
        ImuUdpPacket pkt;
        ssize_t n = recv(sock, &pkt, sizeof(pkt), 0);
        if (n != (ssize_t)sizeof(pkt)) {
            printf("Got %ld bytes (expected %ld)\n", (long)n, (long)sizeof(pkt));
            continue;
        }

        printf("SEQ %u | ACC [%.3f %.3f %.3f] | GYRO [%.3f %.3f %.3f]\n",
               pkt.seq,
               pkt.ax, pkt.ay, pkt.az,
               pkt.gx, pkt.gy, pkt.gz);
        fflush(stdout);
    }

    close(sock);
    return 0;
}
