/*
 * DatabaseApp.c
 *
 *  Created on: Nov 21, 2025
 *      Author: Nick
 */
#include "sqlite3.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>
#include <stdbool.h>
#include <stdatomic.h>

/* QNX-specific headers for IPC, won't work on Windows */
#include <sys/neutrino.h>
#include <sys/iomsg.h>

/* Message structures for IPC */
typedef struct {
    struct _pulse pulse;  /* QNX message header */
    char source[64];
    char message[256];
} SensorMessage;

typedef struct {
    struct _pulse pulse;  /* QNX message header */
    char state[64];
    char message[256];
} StateMessage;

/* Message types */
#define MSG_SENSOR_DATA    (_PULSE_CODE_MINAVAIL + 1)
#define MSG_STATE_DATA     (_PULSE_CODE_MINAVAIL + 2)
#define MSG_SHUTDOWN       (_PULSE_CODE_MINAVAIL + 3)

/* Database structure */
typedef struct {
    sqlite3* db;
} Database;

/* Database Logger Server structure */
typedef struct {
    Database db;
    int chid;  /* Channel ID for IPC */
    atomic_bool running;
} DatabaseLoggerServer;

/* Database Logger Client structure */
typedef struct {
    int coid;  /* Connection ID */
} DatabaseLoggerClient;

/* Forward declarations */
void get_current_date(char* buffer, size_t size);
void get_current_time(char* buffer, size_t size);

/* Get current date in YYYY-MM-DD format */
void get_current_date(char* buffer, size_t size) {
    time_t now = time(NULL);
    struct tm* local = localtime(&now);
    strftime(buffer, size, "%Y-%m-%d", local);
}

/* Get current time in HH:MM:SS.mmm format */
void get_current_time(char* buffer, size_t size) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);

    struct tm* local = localtime(&ts.tv_sec);
    char time_str[64];
    strftime(time_str, sizeof(time_str), "%H:%M:%S", local);

    int ms = ts.tv_nsec / 1000000;
    snprintf(buffer, size, "%s.%03d", time_str, ms);
}

/* Database functions */
bool database_init(Database* db, const char* db_name) {
    int rc = sqlite3_open(db_name, &db->db);
    if (rc) {
        fprintf(stderr, "Can't open database: %s\n", sqlite3_errmsg(db->db));
        db->db = NULL;
        return false;
    }
    printf("Database opened successfully\n");
    return true;
}

void database_close(Database* db) {
    if (db->db) {
        sqlite3_close(db->db);
        db->db = NULL;
    }
}

bool database_create_tables(Database* db) {
    if (!db->db) return false;

    char* err_msg = NULL;

    const char* sql_sensors =
        "CREATE TABLE IF NOT EXISTS sensors ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "Date TEXT NOT NULL, "
        "Timestamp TEXT NOT NULL, "
        "Source TEXT NOT NULL, "
        "Message TEXT);";

    int rc = sqlite3_exec(db->db, sql_sensors, NULL, 0, &err_msg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error (sensors): %s\n", err_msg);
        sqlite3_free(err_msg);
        return false;
    }

    const char* sql_vehicle_state =
        "CREATE TABLE IF NOT EXISTS vehicle_state ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "Date TEXT NOT NULL, "
        "Timestamp TEXT NOT NULL, "
        "State TEXT NOT NULL, "
        "Message TEXT);";

    rc = sqlite3_exec(db->db, sql_vehicle_state, NULL, 0, &err_msg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error (vehicle_state): %s\n", err_msg);
        sqlite3_free(err_msg);
        return false;
    }

    printf("Tables created successfully\n");
    return true;
}

bool database_insert_sensor(Database* db, const char* source, const char* message) {
    if (!db->db) return false;

    char date[32];
    char timestamp[32];
    get_current_date(date, sizeof(date));
    get_current_time(timestamp, sizeof(timestamp));

    sqlite3_stmt* stmt;
    const char* sql = "INSERT INTO sensors (Date, Timestamp, Source, Message) VALUES (?, ?, ?, ?);";

    int rc = sqlite3_prepare_v2(db->db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare statement: %s\n", sqlite3_errmsg(db->db));
        return false;
    }

    sqlite3_bind_text(stmt, 1, date, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, timestamp, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, source, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, message, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE) {
        fprintf(stderr, "Failed to insert sensor data: %s\n", sqlite3_errmsg(db->db));
        return false;
    }

    printf("[%s] Sensor: %s - %s\n", timestamp, source, message);
    return true;
}

bool database_insert_vehicle_state(Database* db, const char* state, const char* message) {
    if (!db->db) return false;

    char date[32];
    char timestamp[32];
    get_current_date(date, sizeof(date));
    get_current_time(timestamp, sizeof(timestamp));

    sqlite3_stmt* stmt;
    const char* sql = "INSERT INTO vehicle_state (Date, Timestamp, State, Message) VALUES (?, ?, ?, ?);";

    int rc = sqlite3_prepare_v2(db->db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare statement: %s\n", sqlite3_errmsg(db->db));
        return false;
    }

    sqlite3_bind_text(stmt, 1, date, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, timestamp, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, state, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, message, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE) {
        fprintf(stderr, "Failed to insert vehicle state: %s\n", sqlite3_errmsg(db->db));
        return false;
    }

    printf("[%s] State: %s - %s\n", timestamp, state, message);
    return true;
}

//Transaction for database
bool database_begin_transaction(Database* db) {
    if (!db->db) return false;
    char* err_msg = NULL;
    int rc = sqlite3_exec(db->db, "BEGIN TRANSACTION;", NULL, 0, &err_msg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Begin transaction error: %s\n", err_msg);
        sqlite3_free(err_msg);
        return false;
    }
    return true;
}

//Commits the transaction to the database
bool database_commit_transaction(Database* db) {
    if (!db->db) return false;
    char* err_msg = NULL;
    int rc = sqlite3_exec(db->db, "COMMIT;", NULL, 0, &err_msg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Commit transaction error: %s\n", err_msg);
        sqlite3_free(err_msg);
        return false;
    }
    return true;
}

/* Database Logger Server functions */
bool server_init(DatabaseLoggerServer* server, const char* db_name) {
    if (!database_init(&server->db, db_name)) {
        return false;
    }
    server->chid = -1;
    atomic_init(&server->running, false);
    return true;
}

void server_cleanup(DatabaseLoggerServer* server) {
    atomic_store(&server->running, false);
    if (server->chid != -1) {
        ChannelDestroy(server->chid);
        server->chid = -1;
    }
    database_close(&server->db);
}

bool server_start(DatabaseLoggerServer* server) {
    if (!database_create_tables(&server->db)) {
        fprintf(stderr, "Failed to create database tables\n");
        return false;
    }

    /* Create a channel for receiving messages */
    server->chid = ChannelCreate(0);
    if (server->chid == -1) {
        fprintf(stderr, "Failed to create channel: %s\n", strerror(errno));
        return false;
    }

    printf("Database Logger Server started. Channel ID: %d\n", server->chid);
    printf("Other processes can connect using chid: %d\n", server->chid);

    atomic_store(&server->running, true);
    return true;
}

void server_run(DatabaseLoggerServer* server) {
    struct _pulse pulse;
    SensorMessage sensor_msg;
    StateMessage state_msg;

    while (atomic_load(&server->running)) {
        /* Receive messages (blocking call) */
        int rcvid = MsgReceive(server->chid, &pulse, sizeof(pulse), NULL);

        if (rcvid == -1) {
            if (errno == EINTR) continue;
            fprintf(stderr, "MsgReceive error: %s\n", strerror(errno));
            break;
        }

        if (rcvid == 0) {
            /* Pulse received */
            switch (pulse.code) {
                case MSG_SENSOR_DATA:
                    /* Read the full sensor message */
                    if (MsgRead(rcvid, &sensor_msg, sizeof(sensor_msg), 0) != -1) {
                        database_insert_sensor(&server->db, sensor_msg.source, sensor_msg.message);
                    }
                    break;

                case MSG_STATE_DATA:
                    /* Read the full state message */
                    if (MsgRead(rcvid, &state_msg, sizeof(state_msg), 0) != -1) {
                        database_insert_vehicle_state(&server->db, state_msg.state, state_msg.message);
                    }
                    break;

                case MSG_SHUTDOWN:
                    printf("Shutdown signal received\n");
                    atomic_store(&server->running, false);
                    break;
            }
        } else {
            /* Regular message (not pulse) */
            MsgReply(rcvid, EOK, NULL, 0);
        }
    }
}

//Returns a pointer to the channel id
int server_get_channel_id(DatabaseLoggerServer* server) {
    return server->chid;
}

/* Database Logger Client functions */
void client_init(DatabaseLoggerClient* client) {
    client->coid = -1;
}

//detach client from id
void client_cleanup(DatabaseLoggerClient* client) {
    if (client->coid != -1) {
        ConnectDetach(client->coid);
        client->coid = -1;
    }
}

//Connect client to server
bool client_connect(DatabaseLoggerClient* client, pid_t server_pid, int chid) {
    client->coid = ConnectAttach(0, server_pid, chid, _NTO_SIDE_CHANNEL, 0);
    if (client->coid == -1) {
        fprintf(stderr, "Failed to connect: %s\n", strerror(errno));
        return false;
    }
    printf("Connected to database logger server\n");
    return true;
}

bool client_send_sensor_data(DatabaseLoggerClient* client, const char* source, const char* message) {
    if (client->coid == -1) return false;

    SensorMessage msg;
    memset(&msg, 0, sizeof(msg));
    msg.pulse.type = _PULSE_TYPE;
    msg.pulse.code = MSG_SENSOR_DATA;

    strncpy(msg.source, source, sizeof(msg.source) - 1);
    strncpy(msg.message, message, sizeof(msg.message) - 1);

    if (MsgSend(client->coid, &msg, sizeof(msg), NULL, 0) == -1) {
        fprintf(stderr, "MsgSend error: %s\n", strerror(errno));
        return false;
    }

    return true;
}

bool client_send_state_data(DatabaseLoggerClient* client, const char* state, const char* message) {
    if (client->coid == -1) return false;

    StateMessage msg;
    memset(&msg, 0, sizeof(msg));
    msg.pulse.type = _PULSE_TYPE;
    msg.pulse.code = MSG_STATE_DATA;

    strncpy(msg.state, state, sizeof(msg.state) - 1);
    strncpy(msg.message, message, sizeof(msg.message) - 1);

    if (MsgSend(client->coid, &msg, sizeof(msg), NULL, 0) == -1) {
        fprintf(stderr, "MsgSend error: %s\n", strerror(errno));
        return false;
    }

    return true;
}

/* Main function */
int main(int argc, char* argv[]) {
    if (argc > 1 && strcmp(argv[1], "server") == 0) {
        /* Run as server */
        DatabaseLoggerServer server;

        if (!server_init(&server, "vehicle_data.db")) {
            return 1;
        }

        if (!server_start(&server)) {
            server_cleanup(&server);
            return 1;
        }

        printf("Server PID: %d\n", getpid());
        printf("Channel ID: %d\n", server_get_channel_id(&server));
        printf("Press Ctrl+C to stop...\n");

        server_run(&server);
        server_cleanup(&server);

    } else if (argc > 1 && strcmp(argv[1], "client") == 0) {
        /* Run as client (simulation) */
        if (argc < 4) {
            printf("Usage: %s client <server_pid> <channel_id>\n", argv[0]);
            return 1;
        }

        pid_t server_pid = atoi(argv[2]);
        int chid = atoi(argv[3]);

        DatabaseLoggerClient client;
        client_init(&client);

        if (!client_connect(&client, server_pid, chid)) {
            return 1;
        }

        /* Simulate sending data */
        printf("Sending test data...\n");

        client_send_sensor_data(&client, "Temperature", "25.5°C");
        client_send_sensor_data(&client, "Speed", "60 mph");
        client_send_state_data(&client, "Moving", "Highway driving");

        /* High frequency simulation */
        for (int i = 0; i < 10; i++) {
            client_send_sensor_data(&client, "GPS", "Lat: 45.42, Lon: -75.69");
            usleep(100000);  /* Sleep for 100ms */
        }

        printf("Test data sent successfully\n");
        client_cleanup(&client);

    } else {
        printf("Usage:\n");
        printf("  Server: %s server\n", argv[0]);
        printf("  Client: %s client <server_pid> <channel_id>\n", argv[0]);
    }

    return 0;
}

