#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sqlite3.h"
#include "querydatabase.h"

#define DB_FILE "database.db"


int main(void) {
    sqlite3 *db;

    int rc = sqlite3_open(DB_FILE, &db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(db));
        return 1;
    }

    printf("\n=== Sensor Table ===\n");
    query_sensors(db);

    printf("\n=== States Table ===\n");
    query_states(db);

    printf("\n=== System Logs Table ===\n");
    query_logs(db);

    sqlite3_close(db);
    return 0;
}

void query_sensors(sqlite3 *db) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT date, time, sensor, message FROM sensors ORDER BY date DESC, time DESC";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return;
    }

    printf("\n%-12s %-10s %-20s %s\n", "Date", "Time", "Sensor", "Message");
    printf("-------------------------------------------------------------------\n");

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *date    = (const char*)sqlite3_column_text(stmt, 0);
        const char *time    = (const char*)sqlite3_column_text(stmt, 1);
        const char *sensor  = (const char*)sqlite3_column_text(stmt, 2);
        const char *message = (const char*)sqlite3_column_text(stmt, 3);
        printf("%-12s %-10s %-20s %s\n", date, time, sensor, message);
    }
    printf("\n\n");
    sqlite3_finalize(stmt);
}

void query_states(sqlite3 *db) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT date, time, state, message FROM states ORDER BY date DESC, time DESC";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return;
    }

    printf("\n%-12s %-10s %-20s %s\n", "Date", "Time", "State", "Message");
    printf("-------------------------------------------------------------------\n");

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *date    = (const char*)sqlite3_column_text(stmt, 0);
        const char *time    = (const char*)sqlite3_column_text(stmt, 1);
        const char *state   = (const char*)sqlite3_column_text(stmt, 2);
        const char *message = (const char*)sqlite3_column_text(stmt, 3);
        printf("%-12s %-10s %-20s %s\n", date, time, state, message);
    }
    printf("\n\n");
    sqlite3_finalize(stmt);
}

void query_logs(sqlite3 *db) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT date, time, source, message FROM logs ORDER BY date DESC, time DESC";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return;
    }

    printf("\n%-12s %-10s %-20s %s\n", "Date", "Time", "Source", "Message");
    printf("-------------------------------------------------------------------\n");

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *date    = (const char*)sqlite3_column_text(stmt, 0);
        const char *time    = (const char*)sqlite3_column_text(stmt, 1);
        const char *source  = (const char*)sqlite3_column_text(stmt, 2);
        const char *message = (const char*)sqlite3_column_text(stmt, 3);
        printf("%-12s %-10s %-20s %s\n", date, time, source, message);
    }
    printf("\n\n");
    sqlite3_finalize(stmt);
}