#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "sqlite3.h"

// Database file path
#define DB_FILE "system_data.db"

// Function prototypes
int init_database(sqlite3 **db);
int create_tables(sqlite3 *db);
int insert_sensor_data(sqlite3 *db, const char *sensor, const char *message);
int insert_state_data(sqlite3 *db, const char *state, const char *message);
int query_sensor_data(sqlite3 *db);
int query_state_data(sqlite3 *db);
void get_current_datetime(char *datetime_str, size_t size);

int main(void) {
    sqlite3 *db;
    int rc;

    // Initialize database
    rc = init_database(&db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to initialize database\n");
        return 1;
    }

    // Create tables
    rc = create_tables(db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to create tables\n");
        sqlite3_close(db);
        return 1;
    }

    printf("Database initialized successfully\n\n");

    // Example usage: Insert some test data
    printf("=== Inserting Test Data ===\n");
    insert_sensor_data(db, "Temperature_Sensor_1", "Temperature: 25.5C");
    insert_sensor_data(db, "Pressure_Sensor_2", "Pressure: 101.3 kPa");
    insert_state_data(db, "RUNNING", "System started successfully");
    insert_state_data(db, "IDLE", "Waiting for input");

    printf("\n=== Querying Sensor Data ===\n");
    query_sensor_data(db);

    printf("\n=== Querying State Data ===\n");
    query_state_data(db);

    // Close database
    sqlite3_close(db);
    return 0;
}

// Initialize database connection
int init_database(sqlite3 **db) {
    int rc = sqlite3_open(DB_FILE, db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(*db));
        return rc;
    }
    return SQLITE_OK;
}

// Create both tables
int create_tables(sqlite3 *db) {
    char *err_msg = NULL;
    int rc;

    // Create sensors table
    const char *sql_sensors =
        "CREATE TABLE IF NOT EXISTS sensors ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "date TEXT NOT NULL, "
        "time TEXT NOT NULL, "
        "sensor TEXT NOT NULL, "
        "message TEXT NOT NULL"
        ");";

    rc = sqlite3_exec(db, sql_sensors, NULL, NULL, &err_msg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error (sensors table): %s\n", err_msg);
        sqlite3_free(err_msg);
        return rc;
    }

    // Create states table
    const char *sql_states =
        "CREATE TABLE IF NOT EXISTS states ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "date TEXT NOT NULL, "
        "time TEXT NOT NULL, "
        "state TEXT NOT NULL, "
        "message TEXT NOT NULL"
        ");";

    rc = sqlite3_exec(db, sql_states, NULL, NULL, &err_msg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error (states table): %s\n", err_msg);
        sqlite3_free(err_msg);
        return rc;
    }

    printf("Tables created successfully\n");
    return SQLITE_OK;
}

// Get current date and time
void get_current_datetime(char *datetime_str, size_t size) {
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    strftime(datetime_str, size, "%Y-%m-%d %H:%M:%S", t);
}

// Insert sensor data
int insert_sensor_data(sqlite3 *db, const char *sensor, const char *message) {
    sqlite3_stmt *stmt;
    char date[11];  // YYYY-MM-DD
    char time_str[9];  // HH:MM:SS
    time_t now = time(NULL);
    struct tm *t = localtime(&now);

    // Format date and time separately
    strftime(date, sizeof(date), "%Y-%m-%d", t);
    strftime(time_str, sizeof(time_str), "%H:%M:%S", t);

    const char *sql = "INSERT INTO sensors (date, time, sensor, message) VALUES (?, ?, ?, ?)";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare statement: %s\n", sqlite3_errmsg(db));
        return rc;
    }

    sqlite3_bind_text(stmt, 1, date, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, time_str, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, sensor, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, message, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
        fprintf(stderr, "Failed to insert sensor data: %s\n", sqlite3_errmsg(db));
        sqlite3_finalize(stmt);
        return rc;
    }

    printf("Inserted sensor: %s %s %s %s\n", date, time_str, sensor, message);
    sqlite3_finalize(stmt);
    return SQLITE_OK;
}

// Insert state data
int insert_state_data(sqlite3 *db, const char *state, const char *message) {
    sqlite3_stmt *stmt;
    char date[11];  // YYYY-MM-DD
    char time_str[9];  // HH:MM:SS
    time_t now = time(NULL);
    struct tm *t = localtime(&now);

    // Format date and time separately
    strftime(date, sizeof(date), "%Y-%m-%d", t);
    strftime(time_str, sizeof(time_str), "%H:%M:%S", t);

    const char *sql = "INSERT INTO states (date, time, state, message) VALUES (?, ?, ?, ?)";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare statement: %s\n", sqlite3_errmsg(db));
        return rc;
    }

    sqlite3_bind_text(stmt, 1, date, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, time_str, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, state, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, message, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
        fprintf(stderr, "Failed to insert state data: %s\n", sqlite3_errmsg(db));
        sqlite3_finalize(stmt);
        return rc;
    }

    printf("Inserted state: %s %s %s %s\n", date, time_str, state, message);
    sqlite3_finalize(stmt);
    return SQLITE_OK;
}

// Query and display all sensor data
int query_sensor_data(sqlite3 *db) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT date, time, sensor, message FROM sensors ORDER BY date DESC, time DESC";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return rc;
    }

    printf("%-12s %-10s %-25s %s\n", "Date", "Time", "Sensor", "Message");
    printf("-------------------------------------------------------------------\n");

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *date = (const char*)sqlite3_column_text(stmt, 0);
        const char *time = (const char*)sqlite3_column_text(stmt, 1);
        const char *sensor = (const char*)sqlite3_column_text(stmt, 2);
        const char *message = (const char*)sqlite3_column_text(stmt, 3);

        printf("%-12s %-10s %-25s %s\n", date, time, sensor, message);
    }

    sqlite3_finalize(stmt);
    return SQLITE_OK;
}

// Query and display all state data
int query_state_data(sqlite3 *db) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT date, time, state, message FROM states ORDER BY date DESC, time DESC";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return rc;
    }

    printf("%-12s %-10s %-20s %s\n", "Date", "Time", "State", "Message");
    printf("-------------------------------------------------------------------\n");

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *date = (const char*)sqlite3_column_text(stmt, 0);
        const char *time = (const char*)sqlite3_column_text(stmt, 1);
        const char *state = (const char*)sqlite3_column_text(stmt, 2);
        const char *message = (const char*)sqlite3_column_text(stmt, 3);

        printf("%-12s %-10s %-20s %s\n", date, time, state, message);
    }

    sqlite3_finalize(stmt);
    return SQLITE_OK;
}
