#ifndef MCU_LOGIC_H
#define MCU_LOGIC_H

#include <stdint.h>
#include <netinet/in.h>
#include "command_pool.h"

/* -----------------------------------------------------------------------
 * MCULogic
 *
 * Implements the priority-based scheduling loop:
 *
 *   1. Block on pool_pop_best() to obtain the highest-priority valid
 *      command.
 *   2. Begin "executing" the command (forwarding the raw Ackermann bytes
 *      to the motor control team via UDP).
 *   3. A command that has been forwarded is considered done.
 *
 * Runs in its own POSIX thread with SCHED_FIFO priority on QNX.
 * ----------------------------------------------------------------------- */

typedef struct {
    CommandPool        *pool;           /* shared pool — NOT owned here     */
    int                 sock_fd;        /* UDP socket for outbound traffic   */
    struct sockaddr_in  mcu_addr;       /* motor-control team destination    */
    pthread_t           thread;
    volatile int        running;
} MCULogic;

/* Initialise (opens outbound UDP socket, does NOT start thread). */
int  mcu_init(MCULogic *mcu, CommandPool *pool,
              const char *mcu_host, uint16_t mcu_port);

/* Start the scheduling thread. */
int  mcu_start(MCULogic *mcu);

/* Signal shutdown and join. */
void mcu_stop(MCULogic *mcu);

/* Release all resources. */
void mcu_destroy(MCULogic *mcu);

#endif /* MCU_LOGIC_H */
