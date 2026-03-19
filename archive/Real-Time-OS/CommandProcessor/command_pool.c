#include "command_pool.h"

#include <string.h>
#include <errno.h>
#include <stdio.h>

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

/* Returns 1 if entry a should be ranked higher than entry b.
 * Primary key: priority (higher wins).
 * Tie-break:   valid_until (longer remaining life wins). */
static inline int entry_beats(const PoolEntry *a, const PoolEntry *b)
{
    if (a->priority != b->priority)
        return a->priority > b->priority;
    return ts_after(&a->valid_until, &b->valid_until);
}

/* -----------------------------------------------------------------------
 * Public API
 * ----------------------------------------------------------------------- */

int pool_init(CommandPool *pool)
{
    if (!pool)
        return -1;

    memset(pool->entries, 0, sizeof(pool->entries));
    pool->count = 0;

    if (pthread_mutex_init(&pool->lock, NULL) != 0) {
        perror("pool_init: pthread_mutex_init");
        return -1;
    }

    pthread_condattr_t cattr;
    pthread_condattr_init(&cattr);
    /* Use CLOCK_MONOTONIC so timed waits are not affected by wall-clock
     * adjustments — important on an RTOS. */
    pthread_condattr_setclock(&cattr, CLOCK_MONOTONIC);

    if (pthread_cond_init(&pool->not_empty, &cattr) != 0) {
        perror("pool_init: pthread_cond_init");
        pthread_mutex_destroy(&pool->lock);
        pthread_condattr_destroy(&cattr);
        return -1;
    }
    pthread_condattr_destroy(&cattr);

    return 0;
}

void pool_destroy(CommandPool *pool)
{
    if (!pool)
        return;
    pthread_cond_destroy(&pool->not_empty);
    pthread_mutex_destroy(&pool->lock);
}

/* Push — O(n) insertion that keeps the array sorted (descending by rank)
 * so that the best entry is always at index 0.  For POOL_CAPACITY = 64
 * this is perfectly adequate; switch to a proper heap if capacity grows. */
int pool_push(CommandPool *pool, const PoolEntry *entry)
{
    if (!pool || !entry)
        return -1;

    pthread_mutex_lock(&pool->lock);

    if (pool->count >= POOL_CAPACITY) {
        pthread_mutex_unlock(&pool->lock);
        fprintf(stderr, "pool_push: pool full, dropping command\n");
        return -1;
    }

    /* Find insertion point so array stays sorted best→worst. */
    size_t insert_at = pool->count;
    for (size_t i = 0; i < pool->count; ++i) {
        if (entry_beats(entry, &pool->entries[i])) {
            insert_at = i;
            break;
        }
    }

    /* Shift entries down to make room. */
    for (size_t i = pool->count; i > insert_at; --i)
        pool->entries[i] = pool->entries[i - 1];

    pool->entries[insert_at] = *entry;
    pool->count++;

    pthread_cond_signal(&pool->not_empty);
    pthread_mutex_unlock(&pool->lock);

    return 0;
}

/*
 * Pop the best still-valid entry.
 *
 * Expired entries are discarded on the fly.  If the pool is empty (or
 * everything is expired) we wait on the condition variable, then retry.
 */
int pool_pop_best(CommandPool *pool, PoolEntry *out)
{
    if (!pool || !out)
        return -1;

    pthread_mutex_lock(&pool->lock);

    for (;;) {
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);

        /* Scan from the front (highest priority) and find first valid entry. */
        int found = -1;
        for (size_t i = 0; i < pool->count; ++i) {
            if (ts_after(&pool->entries[i].valid_until, &now)) {
                found = (int)i;
                break;
            }
        }

        if (found >= 0) {
            *out = pool->entries[found];

            /* Remove the entry by shifting the rest up. */
            for (size_t i = (size_t)found; i < pool->count - 1; ++i)
                pool->entries[i] = pool->entries[i + 1];
            pool->count--;

            pthread_mutex_unlock(&pool->lock);
            return 0;
        }

        /* Purge entries that have already expired to keep the pool tidy. */
        pool->count = 0;

        /* Nothing valid — wait for a new push. */
        pthread_cond_wait(&pool->not_empty, &pool->lock);
    }
}
