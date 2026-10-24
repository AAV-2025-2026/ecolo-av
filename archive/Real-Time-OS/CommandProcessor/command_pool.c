#include "command_pool.h"

#include <string.h>
#include <errno.h>
#include <stdio.h>

/* -----------------------------------------------------------------------
 * Internal helpers
 * ----------------------------------------------------------------------- */

/* Returns 1 if entry a should be ranked higher than entry b.
 * Primary key: priority (higher wins).
 * Tie-break:   valid_until (longer remaining life wins). */
static inline int entry_beats(const PoolEntry *a, const PoolEntry *b)
{
    return a->priority > b->priority;
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

    if (pthread_mutex_init(&pool->lock, NULL) != 0)
    {
        perror("pool_init: pthread_mutex_init");
        return -1;
    }

    pthread_condattr_t cattr;
    pthread_condattr_init(&cattr);
    // Use CLOCK_MONOTONIC so timed waits are not affected by wall-clock
    pthread_condattr_setclock(&cattr, CLOCK_MONOTONIC);

    if (pthread_cond_init(&pool->not_empty, &cattr) != 0)
    {
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

    if (pool->count >= POOL_CAPACITY)
    {
        pthread_mutex_unlock(&pool->lock);
        fprintf(stderr, "pool_push: pool full, dropping command\n");
        return -1;
    }

    /* Find insertion point so array stays sorted best→worst. */
    size_t insert_at = pool->count;
    for (size_t i = 0; i < pool->count; ++i)
    {
        if (entry_beats(entry, &pool->entries[i]))
        {
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
 * Pop the highest-priority entry.
 * Blocks on the condition variable if the pool is empty.
 */
int pool_pop_best(CommandPool *pool, PoolEntry *out)
{
    if (!pool || !out)
        return -1;

    pthread_mutex_lock(&pool->lock);

    while (pool->count == 0)
    {
        pthread_cond_wait(&pool->not_empty, &pool->lock);
    }

    /* Best entry is always at index 0. */
    *out = pool->entries[0];

    /* Shift remaining entries up. */
    for (size_t i = 0; i < pool->count - 1; ++i)
        pool->entries[i] = pool->entries[i + 1];
    pool->count--;

    pthread_mutex_unlock(&pool->lock);
    return 0;
}
