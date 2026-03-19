#ifndef COMMAND_POOL_H
#define COMMAND_POOL_H

#include <stdint.h>
#include <time.h>
#include <pthread.h>

/* -----------------------------------------------------------------------
 * Wire format of an inbound UDP packet from the navigation team.
 *
 *   [ ackermann_payload (ACKERMANN_PAYLOAD_SIZE bytes) ]
 *   [ freshness_ms : uint32_t (4 bytes, big-endian)    ]
 *   [ priority     : uint8_t  (1 byte)                 ]
 *
 * The ackermann_payload is treated as an opaque blob — we never
 * deserialise it.  Only the trailing metadata fields are inspected
 * by this component.
 * ----------------------------------------------------------------------- */
#define ACKERMANN_PAYLOAD_SIZE  16u          /* adjust to match nav team  */
#define INBOUND_PACKET_SIZE     (ACKERMANN_PAYLOAD_SIZE + 4u + 1u)

/* Maximum number of commands that may sit in the pool simultaneously. */
#define POOL_CAPACITY           64u

/* -----------------------------------------------------------------------
 * PoolEntry — the unit that lives inside the pool.
 * ----------------------------------------------------------------------- */
typedef struct {
    uint8_t  ackermann_bytes[ACKERMANN_PAYLOAD_SIZE]; /* opaque blob       */
    uint8_t  priority;                                /* higher = more urgent */
    struct timespec valid_until;                      /* recv_time + freshness */
} PoolEntry;

/* -----------------------------------------------------------------------
 * CommandPool — thread-safe, priority-ordered pool.
 *
 * Internally a max-heap ordered by (priority DESC, valid_until DESC).
 * All public functions are safe to call from multiple threads.
 * ----------------------------------------------------------------------- */
typedef struct {
    PoolEntry        entries[POOL_CAPACITY];
    size_t           count;
    pthread_mutex_t  lock;
    pthread_cond_t   not_empty;  /* signalled whenever an entry is pushed  */
} CommandPool;

/* Initialise / destroy -------------------------------------------------- */
int  pool_init(CommandPool *pool);
void pool_destroy(CommandPool *pool);

/* Push a new entry.  Returns 0 on success, -1 if pool is full. */
int  pool_push(CommandPool *pool, const PoolEntry *entry);

/*
 * Pop the highest-priority entry whose valid_until is still in the future.
 *
 * Blocks until at least one valid entry is available (or the calling
 * thread is cancelled).  Expired entries are silently discarded while
 * searching.
 *
 * Returns 0 and fills *out on success.
 */
int  pool_pop_best(CommandPool *pool, PoolEntry *out);

#endif /* COMMAND_POOL_H */
