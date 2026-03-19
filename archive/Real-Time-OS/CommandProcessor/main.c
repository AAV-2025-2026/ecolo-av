#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>

#include "command_pool.h"
#include "command_interface.h"
#include "mcu_logic.h"

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

    /* --- Shared command pool. --- */
    CommandPool pool;
    if (pool_init(&pool) != 0) {
        fprintf(stderr, "main: failed to initialise command pool\n");
        return EXIT_FAILURE;
    }

    /* --- Command interface (inbound UDP). --- */
    CommandInterface iface;
    if (interface_init(&iface, INTERFACE_LISTEN_PORT, &pool) != 0) {
        fprintf(stderr, "main: failed to initialise command interface\n");
        pool_destroy(&pool);
        return EXIT_FAILURE;
    }

    /* --- MCU logic (outbound UDP + scheduling). --- */
    MCULogic mcu;
    if (mcu_init(&mcu, &pool, MCU_TARGET_HOST, MCU_TARGET_PORT) != 0) {
        fprintf(stderr, "main: failed to initialise MCU logic\n");
        interface_destroy(&iface);
        pool_destroy(&pool);
        return EXIT_FAILURE;
    }

    /* --- Start both threads. --- */
    if (interface_start(&iface) != 0) {
        fprintf(stderr, "main: failed to start command interface thread\n");
        goto cleanup;
    }

    if (mcu_start(&mcu) != 0) {
        fprintf(stderr, "main: failed to start MCU logic thread\n");
        interface_stop(&iface);
        goto cleanup;
    }

    printf("Command processor running.  "
           "Listening on :%u, forwarding to %s:%u\n",
           INTERFACE_LISTEN_PORT, MCU_TARGET_HOST, MCU_TARGET_PORT);

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

    printf("Command processor stopped.\n");
    return EXIT_SUCCESS;
}
