#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include <mqueue.h>
#include <fcntl.h>

#include "command_pool.h"
#include "command_interface.h"
#include "mcu_logic.h"
#include "dbstruct.h"

/* -----------------------------------------------------------------------
 * Configuration — adjust these to match your deployment environment.
 * ----------------------------------------------------------------------- */
#define INTERFACE_LISTEN_PORT   5000u       /* inbound from nav team        */
#define MCU_TARGET_HOST         "192.168.56.1" /* motor control team UDP host  */
#define MCU_TARGET_PORT         5001u       /* motor control team UDP port  */

/* -----------------------------------------------------------------------
 * Graceful shutdown
 * ----------------------------------------------------------------------- */
static volatile int g_running = 1;

static void signal_handler(int sig)
{
    (void)sig;
    g_running = 0;
}

/* -----------------------------------------------------------------------
 * main
 * ----------------------------------------------------------------------- */
int main(void)
{
    /* --- Wire up signal handling. --- */
    signal(SIGINT,  signal_handler);
    signal(SIGTERM, signal_handler);

    /* --- Open message queue for logging startup. --- */
    mqd_t mqd = mq_open("/db_queue", O_WRONLY | O_NONBLOCK);
    if (mqd == (mqd_t)-1) {
        perror("main: mq_open");
        // Continue anyway
    }

    /* --- Shared command pool. --- */
    CommandPool pool;
    if (pool_init(&pool) != 0) {
        fprintf(stderr, "main: failed to initialise command pool\n");
        return EXIT_FAILURE;
    } else {
        DB_t msg;
        strncpy(msg.table, "logs", sizeof(msg.table));
        strncpy(msg.id, "cmd", sizeof(msg.id));
        strncpy(msg.msg, "Command pool initialized", sizeof(msg.msg));
        if (mqd != (mqd_t)-1) mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);
    }

    /* --- Command interface (inbound UDP). --- */
    CommandInterface iface;
    if (interface_init(&iface, INTERFACE_LISTEN_PORT, &pool) != 0) {
        fprintf(stderr, "main: failed to initialise command interface\n");
        pool_destroy(&pool);
        return EXIT_FAILURE;
    } else {
        DB_t msg;
        strncpy(msg.table, "logs", sizeof(msg.table));
        strncpy(msg.id, "cmd", sizeof(msg.id));
        strncpy(msg.msg, "Command interface initialized", sizeof(msg.msg));
        if (mqd != (mqd_t)-1) mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);
    }

    /* --- MCU logic (outbound UDP + scheduling). --- */
    MCULogic mcu;
    if (mcu_init(&mcu, &pool, MCU_TARGET_HOST, MCU_TARGET_PORT) != 0) {
        fprintf(stderr, "main: failed to initialise MCU logic\n");
        interface_destroy(&iface);
        pool_destroy(&pool);
        return EXIT_FAILURE;
    } else {
        DB_t msg;
        strncpy(msg.table, "logs", sizeof(msg.table));
        strncpy(msg.id, "cmd", sizeof(msg.id));
        strncpy(msg.msg, "MCU logic initialized", sizeof(msg.msg));
        if (mqd != (mqd_t)-1) mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);
    }

    /* --- Start both threads. --- */
    if (interface_start(&iface) != 0) {
        fprintf(stderr, "main: failed to start command interface thread\n");
        goto cleanup;
    } else {
        DB_t msg;
        strncpy(msg.table, "logs", sizeof(msg.table));
        strncpy(msg.id, "cmd", sizeof(msg.id));
        strncpy(msg.msg, "Command interface thread started", sizeof(msg.msg));
        if (mqd != (mqd_t)-1) mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);
    }

    if (mcu_start(&mcu) != 0) {
        fprintf(stderr, "main: failed to start MCU logic thread\n");
        interface_stop(&iface);
        goto cleanup;
    } else {
        DB_t msg;
        strncpy(msg.table, "logs", sizeof(msg.table));
        strncpy(msg.id, "cmd", sizeof(msg.id));
        strncpy(msg.msg, "MCU logic thread started", sizeof(msg.msg));
        if (mqd != (mqd_t)-1) mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);
    }

    printf("Command processor running.  "
           "Listening on :%u, forwarding to %s:%u\n",
           INTERFACE_LISTEN_PORT, MCU_TARGET_HOST, MCU_TARGET_PORT);

    {
        DB_t msg;
        strncpy(msg.table, "logs", sizeof(msg.table));
        strncpy(msg.id, "cmd", sizeof(msg.id));
        strncpy(msg.msg, "Command processor running", sizeof(msg.msg));
        if (mqd != (mqd_t)-1) mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);
    }

    /* --- Main thread idles until a signal is received. --- */
    while (g_running)
        sleep(1);

    printf("\nShutdown requested — stopping threads...\n");

    interface_stop(&iface);
    mcu_stop(&mcu);

cleanup:
    mcu_destroy(&mcu);
    interface_destroy(&iface);
    pool_destroy(&pool);
    mq_close(mqd);

    printf("Command processor stopped.\n");
    return EXIT_SUCCESS;
}
