#include "command_interface.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <mqueue.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#include "dbstruct.h"

/* -----------------------------------------------------------------------
 * Wire-format helpers
 *
 * Inbound packet layout (big-endian):
 *
 *   Offset  Size  Field
 *   ------  ----  -----
 *   0       16    ackermann_payload  (opaque)
 *   16       4    freshness_ms       (uint32_t, milliseconds)
 *   20       1    priority           (uint8_t)
 *
 * Total: INBOUND_PACKET_SIZE (21) bytes.
 * ----------------------------------------------------------------------- */

#define FRESHNESS_OFFSET ACKERMANN_PAYLOAD_SIZE
#define PRIORITY_OFFSET (ACKERMANN_PAYLOAD_SIZE + 4u)

static inline uint32_t read_u32_be(const uint8_t* p) {
    return ((uint32_t)p[0] << 24) |
           ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) |
           (uint32_t)p[3];
}

/* Add milliseconds to a timespec. */
static void ts_add_ms(struct timespec* ts, uint32_t ms) {
    ts->tv_nsec += (long)ms * 1000000L;
    if (ts->tv_nsec >= 1000000000L) {
        ts->tv_sec += ts->tv_nsec / 1000000000L;
        ts->tv_nsec = ts->tv_nsec % 1000000000L;
    }
}

/* -----------------------------------------------------------------------
 * Receive thread
 * ----------------------------------------------------------------------- */

static void* interface_thread(void* arg) {
    CommandInterface* iface = (CommandInterface*)arg;
    uint8_t buf[INBOUND_PACKET_SIZE];

    // Open message queue to write
    mqd_t mqd = mq_open("/db_queue", O_WRONLY);
    if (mqd == (mqd_t)-1) {
        perror("mq_open");
        return 1;
    }

    while (iface->running) {
        ssize_t n = recv(iface->sock_fd, buf, sizeof(buf), 0);

        if (n < 0) {
            if (errno == EINTR)
                continue; /* interrupted — retry              */
            if (!iface->running)
                break; /* shutdown path                    */
            perror("interface_thread: recv");
            continue;
        }

        if ((size_t)n != INBOUND_PACKET_SIZE) {
            fprintf(stderr,
                    "interface_thread: unexpected packet size %zd (expected %u), dropping\n",
                    n, (unsigned)INBOUND_PACKET_SIZE);
            continue;
        }

        /* --- Timestamp the arrival as early as possible. --- */
        struct timespec recv_time;
        clock_gettime(CLOCK_MONOTONIC, &recv_time);

        /* --- Parse trailing metadata. --- */
        uint32_t freshness_ms = read_u32_be(buf + FRESHNESS_OFFSET);
        uint8_t priority = buf[PRIORITY_OFFSET];

        /* --- Compute valid_until = recv_time + freshness_ms. --- */
        struct timespec valid_until = recv_time;
        ts_add_ms(&valid_until, freshness_ms);

        // ADD DATABASE ENTRY HERE THAT WILL STORE CMD, PRIORITY, AND RECEIVE TIME
        DB_t msg;
        strncpy(msg.table, "logs", sizeof(msg.table));  // "sensors", "states", or "logs"
        strncpy(msg.id, "cmd", sizeof(msg.id));
        strncpy(msg.msg, "Command Received: ", sizeof(msg.msg));  // add details

        mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);

        /* --- Build the pool entry (ackermann bytes stay opaque). --- */
        PoolEntry entry;
        memcpy(entry.ackermann_bytes, buf, ACKERMANN_PAYLOAD_SIZE);
        entry.priority = priority;
        entry.valid_until = valid_until;

        if (pool_push(iface->pool, &entry) != 0) {
            fprintf(stderr, "interface_thread: pool_push failed, command dropped\n");
        }
    }

    return NULL;
}

/* -----------------------------------------------------------------------
 * Public API
 * ----------------------------------------------------------------------- */

int interface_init(CommandInterface* iface, uint16_t listen_port,
                   CommandPool* pool) {
    if (!iface || !pool)
        return -1;

    memset(iface, 0, sizeof(*iface));
    iface->listen_port = listen_port;
    iface->pool = pool;
    iface->running = 0;
    iface->sock_fd = -1;

    /* Open UDP socket. */
    iface->sock_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (iface->sock_fd < 0) {
        perror("interface_init: socket");
        return -1;
    }

    /* Bind to the listen port on all interfaces. */
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(listen_port);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(iface->sock_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("interface_init: bind");
        close(iface->sock_fd);
        iface->sock_fd = -1;
        return -1;
    }

    return 0;
}

int interface_start(CommandInterface* iface) {
    if (!iface || iface->sock_fd < 0)
        return -1;

    iface->running = 1;

    pthread_attr_t attr;
    pthread_attr_init(&attr);

    /* On QNX use SCHED_FIFO; the interface thread runs at a moderate
     * real-time priority so it never blocks the MCU logic thread. */
#ifdef __QNXNTO__
    struct sched_param sp;
    pthread_attr_setschedpolicy(&attr, SCHED_FIFO);
    sp.sched_priority = 20; /* tune as required */
    pthread_attr_setschedparam(&attr, &sp);
    pthread_attr_setinheritsched(&attr, PTHREAD_EXPLICIT_SCHED);
#endif

    int rc = pthread_create(&iface->thread, &attr, interface_thread, iface);
    pthread_attr_destroy(&attr);

    if (rc != 0) {
        fprintf(stderr, "interface_start: pthread_create failed: %s\n",
                strerror(rc));
        iface->running = 0;
        return -1;
    }

    return 0;
}

void interface_stop(CommandInterface* iface) {
    if (!iface)
        return;

    iface->running = 0;

    /* Unblock the recv() call so the thread can exit cleanly. */
    if (iface->sock_fd >= 0)
        shutdown(iface->sock_fd, SHUT_RDWR);

    pthread_join(iface->thread, NULL);
}

void interface_destroy(CommandInterface* iface) {
    if (!iface)
        return;

    if (iface->sock_fd >= 0) {
        close(iface->sock_fd);
        iface->sock_fd = -1;
    }
}
