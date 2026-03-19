#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mqueue.h>
#include <fcntl.h>
#include <sys/stat.h>
#include "dbstruct.h"

int main(void) {
    // Open the queue as write only - DB app must be running first
    mqd_t mqd = mq_open("/db_queue", O_WRONLY);
    if (mqd == (mqd_t)-1) {
        perror("mq_open");
        return 1;
    }

    // Test 1 - send a sensor message
    DB_t msg1;
    strncpy(msg1.table, "sensors", sizeof(msg1.table));
    strncpy(msg1.id, "LIDAR", sizeof(msg1.id));
    strncpy(msg1.msg, "x=50.000000,y=100.00000,z=200.000", sizeof(msg1.msg));

    if (mq_send(mqd, (char*)&msg1, sizeof(DB_t), 0) == -1) {
        perror("mq_send");
    } else {
        printf("Sent sensor message\n");
    }

    // Test 2 - send a state message
    DB_t msg2;
    strncpy(msg2.table, "states", sizeof(msg2.table));
    strncpy(msg2.id, "GPS", sizeof(msg2.id));
    strncpy(msg2.msg, "LAT: 18.0 LONG: -57.0", sizeof(msg2.msg));

    if (mq_send(mqd, (char*)&msg2, sizeof(DB_t), 0) == -1) {
        perror("mq_send");
    } else {
        printf("Sent state message\n");
    }

    // Test 3 - send a log message
    DB_t msg3;
    strncpy(msg3.table, "logs", sizeof(msg3.table));
    strncpy(msg3.id, "SysControl", sizeof(msg3.id));
    strncpy(msg3.msg, "System startup complete", sizeof(msg3.msg));

    if (mq_send(mqd, (char*)&msg3, sizeof(DB_t), 0) == -1) {
        perror("mq_send");
    } else {
        printf("Sent log message\n");
    }

    // Test 4 - send an unknown table to test the unmatched case
    DB_t msg4;
    strncpy(msg4.table, "unknown", sizeof(msg4.table));
    strncpy(msg4.id, "test", sizeof(msg4.id));
    strncpy(msg4.msg, "This should not insert", sizeof(msg4.msg));

    if (mq_send(mqd, (char*)&msg4, sizeof(DB_t), 0) == -1) {
        perror("mq_send");
    } else {
        printf("Sent unknown table message\n");
    }

    //Test Shutdown
    DB_t msg5;
    strncpy(msg5.table, "logs", sizeof(msg5.table));
    strncpy(msg5.id, "Shutdown", sizeof(msg5.id));
    strncpy(msg5.msg, "System Shutdown", sizeof(msg5.msg));

    if (mq_send(mqd, (char*)&msg5, sizeof(DB_t), 0) == -1) {
        perror("mq_send");
    } else {
        printf("Sent shutdown log message\n");
    }

    mq_close(mqd);
    printf("Done\n");
    return 0;
}