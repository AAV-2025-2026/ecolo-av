#ifndef COMMAND_INTERFACE_H
#define COMMAND_INTERFACE_H

#include <stdint.h>
#include "command_pool.h"

#include "dbstruct.h"
#include <mqueue.h>
#include <fcntl.h>

/* -----------------------------------------------------------------------
 * CommandInterface
 *
 * Owns a UDP socket that listens for inbound Ackermann packets from the
 * navigation team.  For each valid packet it:
 *   1. Records the receive timestamp.
 *   2. Parses the trailing freshness_ms and priority fields.
 *   3. Computes  valid_until = recv_time + freshness_ms.
 *   4. Pushes a PoolEntry (opaque ackermann bytes + metadata) into the
 *      shared CommandPool.
 *
 * The interface runs in its own POSIX thread.
 * ----------------------------------------------------------------------- */

typedef struct {
    int             sock_fd;        /* UDP socket file descriptor           */
    uint16_t        listen_port;    /* port we bind to                      */
    CommandPool    *pool;           /* shared pool — NOT owned by interface */
    pthread_t       thread;
    volatile int    running;        /* set to 0 to request shutdown         */
} CommandInterface;

/* Initialise the interface (opens socket, does NOT start the thread). */
int  interface_init(CommandInterface *iface, uint16_t listen_port,
                    CommandPool *pool);

/* Start the receive thread. */
int  interface_start(CommandInterface *iface);

/* Signal the thread to stop and join it. */
void interface_stop(CommandInterface *iface);

/* Release all resources. */
void interface_destroy(CommandInterface *iface);

//Message queue struct
extern mqd_t mqd;

#endif /* COMMAND_INTERFACE_H */
