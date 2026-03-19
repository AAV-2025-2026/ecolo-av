#include "mcu_logic.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <time.h>

/* -----------------------------------------------------------------------
 * Internal helpers
 * ----------------------------------------------------------------------- */

/* Returns 1 if timespec a is strictly after timespec b. */
static inline int ts_after(const struct timespec *a, const struct timespec *b)
{
    if (a->tv_sec != b->tv_sec)
        return a->tv_sec > b->tv_sec;
    return a->tv_nsec > b->tv_nsec;
}

/*
 * Forward the raw Ackermann bytes to the motor control team.
 * Returns 0 on success, -1 on error.
 */
static int forward_command(MCULogic *mcu, const PoolEntry *cmd)
{
    ssize_t sent = sendto(mcu->sock_fd,
                          cmd->ackermann_bytes,
                          ACKERMANN_PAYLOAD_SIZE,
                          0,
                          (const struct sockaddr *)&mcu->mcu_addr,
                          sizeof(mcu->mcu_addr));

    // Log send time for database entry
    struct timespec send_time;
    clock_gettime(CLOCK_MONOTONIC, &send_time);

    if (sent < 0)
    {
        perror("mcu: forward_command: sendto");
        return -1;
    }

    if ((size_t)sent != ACKERMANN_PAYLOAD_SIZE)
    {
        fprintf(stderr, "mcu: forward_command: partial send (%zd / %u bytes)\n",
                sent, (unsigned)ACKERMANN_PAYLOAD_SIZE);
        return -1;
    }

    // CMD SENT SUCCESSFULLY ADD INFO TO DATABASE cmd->ackermann_bytes, cmd->priority, cmd->valid_until, send_time
    return 0;
}

/* -----------------------------------------------------------------------
 * Scheduling thread
 * ----------------------------------------------------------------------- */

static void *mcu_thread(void *arg)
{
    MCULogic *mcu = (MCULogic *)arg;

    while (mcu->running)
    {
        /* --- 1. Block until the highest-priority valid command is available.
         *        pool_pop_best handles expiry and ordering internally.    --- */
        PoolEntry current;
        if (pool_pop_best(mcu->pool, &current) != 0)
        {
            fprintf(stderr, "mcu_thread: pool_pop_best error\n");
            continue;
        }

        /* --- 2. Guard against expiry in the gap between pop and send.
         *        Normally negligible, but correct to check on an RTOS
         *        where this thread could be preempted by a higher-priority
         *        system task between the two calls.                       --- */
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        if (!ts_after(&current.valid_until, &now))
        {
            continue;
        }

        /* --- 3. Forward the raw Ackermann payload to motor control. --- */
        forward_command(mcu, &current);
    }

    return NULL;
}

/* -----------------------------------------------------------------------
 * Public API
 * ----------------------------------------------------------------------- */

int mcu_init(MCULogic *mcu, CommandPool *pool,
             const char *mcu_host, uint16_t mcu_port)
{
    if (!mcu || !pool || !mcu_host)
        return -1;

    memset(mcu, 0, sizeof(*mcu));
    mcu->pool = pool;
    mcu->running = 0;
    mcu->sock_fd = -1;

    /* Open outbound UDP socket (connectionless). */
    mcu->sock_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (mcu->sock_fd < 0)
    {
        perror("mcu_init: socket");
        return -1;
    }

    /* Pre-fill the destination address for sendto. */
    memset(&mcu->mcu_addr, 0, sizeof(mcu->mcu_addr));
    mcu->mcu_addr.sin_family = AF_INET;
    mcu->mcu_addr.sin_port = htons(mcu_port);

    if (inet_pton(AF_INET, mcu_host, &mcu->mcu_addr.sin_addr) != 1)
    {
        fprintf(stderr, "mcu_init: invalid host address '%s'\n", mcu_host);
        close(mcu->sock_fd);
        mcu->sock_fd = -1;
        return -1;
    }

    return 0;
}

int mcu_start(MCULogic *mcu)
{
    if (!mcu || mcu->sock_fd < 0)
        return -1;

    mcu->running = 1;

    pthread_attr_t attr;
    pthread_attr_init(&attr);

    /* MCU logic thread runs at a higher real-time priority than the
     * interface thread so scheduling decisions are never delayed by
     * incoming packet processing. */
#ifdef __QNXNTO__
    struct sched_param sp;
    pthread_attr_setschedpolicy(&attr, SCHED_FIFO);
    sp.sched_priority = 30; /* higher than interface (20) */
    pthread_attr_setschedparam(&attr, &sp);
    pthread_attr_setinheritsched(&attr, PTHREAD_EXPLICIT_SCHED);
#endif

    int rc = pthread_create(&mcu->thread, &attr, mcu_thread, mcu);
    pthread_attr_destroy(&attr);

    if (rc != 0)
    {
        fprintf(stderr, "mcu_start: pthread_create failed: %s\n", strerror(rc));
        mcu->running = 0;
        return -1;
    }

    return 0;
}

void mcu_stop(MCULogic *mcu)
{
    if (!mcu)
        return;

    mcu->running = 0;

    /* Wake the MCU thread if it is blocked in pool_pop_best. */
    pthread_cond_signal(&mcu->pool->not_empty);

    pthread_join(mcu->thread, NULL);
}

void mcu_destroy(MCULogic *mcu)
{
    if (!mcu)
        return;

    if (mcu->sock_fd >= 0)
    {
        close(mcu->sock_fd);
        mcu->sock_fd = -1;
    }
}
