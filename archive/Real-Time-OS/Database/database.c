#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <mqueue.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#include "sqlite3.h"
#include "dbstruct.h"

// Database file path
#define DB_FILE "database.db"

//Function prototypes
//----------------------------------------
// Initialization
int init_database(sqlite3 **db);
int create_tables(sqlite3 *db);
mqd_t open_mqueue(); //For opening message queue on DB start

//Insertion into db
void receive_and_store(sqlite3 *db, mqd_t mqd); //For receiving from mqueue and storing in db
int insert_sensor_data(sqlite3 *db, const char *sensor, const char *message);
int insert_state_data(sqlite3 *db, const char *state, const char *message);
int insert_syslogs_data(sqlite3 *db, const char *source, const char *message);

//Read from DB
int query_sensor_data(sqlite3 *db);
int query_state_data(sqlite3 *db);
int query_syslogs_data(sqlite3 *db);

//-----------------------------------------


//redefine msg queue attributes
struct mq_attr attr = {
    .mq_flags = 0,
    .mq_maxmsg = 10, //max of 10 messages in queue
    .mq_msgsize = sizeof(DB_t) //resizes to our message size
};

//---------------------------------------------------------------------------
//Main --> Initializes DB and opens Mqueue, then runs until stop flag
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

    //Open queue
    mqd_t mqd = open_mqueue();

    printf("Database initialized successfully\n\n");

    printf("\n=== Querying Sensor Table ===\n");
    query_sensor_data(db);

    printf("\n=== Querying State Table ===\n");
    query_state_data(db);

    printf("\n=== Querying System Logs Table===\n");
    query_syslogs_data(db);

    printf("\n=== Database app running ===\n");

    //Keep db app running (for now)
    while (1) {
        receive_and_store(db, mqd);
        // placeholder for closing app.
        // if(msgqueue id isclose){break;}
    }
    // Close database
    sqlite3_close(db);
    mq_close(mqd);
    return 0;
}
//---------------------------------------------------------------------------


//Function implementations

// Initialize database connection
int init_database(sqlite3 **db) {
    int rc = sqlite3_open(DB_FILE, db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(*db));
        return rc;
    }
    return SQLITE_OK;
}

// Create tables
int create_tables(sqlite3 *db) {
    char *err_msg = NULL;
    int rc;

    // Create sensors table (note, sensor field is name of sensor, if possible)
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

    // Create states table (for logging positional state e.g. 18 deg LAT -57 deg LONG)
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

    //Create system log table for messages from Safety Sys and Sys Control, BCM
    const char *sql_systemlogs =
        "CREATE TABLE IF NOT EXISTS logs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "date TEXT NOT NULL, "
        "time TEXT NOT NULL, "
        "source TEXT NOT NULL, "
        "message TEXT NOT NULL"
        ");";

        rc = sqlite3_exec(db, sql_systemlogs, NULL, NULL, &err_msg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error (sensors table): %s\n", err_msg);
        sqlite3_free(err_msg);
        return rc;
    }

    printf("Tables created successfully\n");
    return SQLITE_OK;
}

//Opens message queue
mqd_t open_mqueue() {
    mqd_t mqd = mq_open("/db_queue", O_CREAT | O_EXCL | O_RDONLY, 0644, &attr);
    if (mqd == (mqd_t)-1) {
        if (errno == EEXIST) {
            mqd = mq_open("/db_queue", O_RDONLY, 0644, NULL);
            if (mqd == (mqd_t)-1) {
                perror("mq_open");
                exit(EXIT_FAILURE);
            }
        } else {             // <-- now correctly paired with if (errno == EEXIST)
            perror("mq_open");
            exit(EXIT_FAILURE);
        }
    }
    return mqd;
}

//Receive from message queue and store into db
void receive_and_store(sqlite3 *db, mqd_t mqd){
    DB_t received; //the struct from the mqueue

    ssize_t bytes = mq_receive(mqd, (char*)&received, sizeof(DB_t), NULL);
    //If error, print to console and return 
    if(bytes == -1) {
        perror("mq_receive");
        return;
    }

    //If message, we route to correct table (prototype with if, replace with switch)
    if(strcmp(received.table, "sensors")==0){
        //Insert into sensors table
        insert_sensor_data(db, received.id, received.msg);
    } else if(strcmp(received.table, "states") ==0){
        //Insert into states table
        insert_state_data(db, received.id, received.msg);
    } else if(strcmp(received.table, "logs")==0){
        //Insert into syslogs table
        insert_syslogs_data(db, received.id, received.msg);
    } else {
        //Unknown Table
        fprintf(stderr, "Unknown table: %s\n", received.table);
}
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
//Insert into system logs table
int insert_syslogs_data(sqlite3 *db, const char *source, const char *message) {
    sqlite3_stmt *stmt;
    char date[11];  // YYYY-MM-DD
    char time_str[9];  // HH:MM:SS
    time_t now = time(NULL);
    struct tm *t = localtime(&now);

    // Format date and time separately
    strftime(date, sizeof(date), "%Y-%m-%d", t);
    strftime(time_str, sizeof(time_str), "%H:%M:%S", t);

    const char *sql = "INSERT INTO logs (date, time, source, message) VALUES (?, ?, ?, ?)";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare statement: %s\n", sqlite3_errmsg(db));
        return rc;
    }

    sqlite3_bind_text(stmt, 1, date, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, time_str, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, source, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, message, -1, SQLITE_TRANSIENT);

    rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
        fprintf(stderr, "Failed to insert log data: %s\n", sqlite3_errmsg(db));
        sqlite3_finalize(stmt);
        return rc;
    }

    printf("Inserted log: %s %s %s %s\n", date, time_str, source, message);
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

    printf("\n");
    printf("%-12s %-10s %-20s %s\n", "Date", "Time", "Sensor", "Message");
    printf("-------------------------------------------------------------------\n");

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *date = (const char*)sqlite3_column_text(stmt, 0);
        const char *time = (const char*)sqlite3_column_text(stmt, 1);
        const char *sensor = (const char*)sqlite3_column_text(stmt, 2);
        const char *message = (const char*)sqlite3_column_text(stmt, 3);

        printf("%-12s %-10s %-20s %s\n", date, time, sensor, message);
    }

    sqlite3_finalize(stmt);
    return SQLITE_OK;
}

// Query and display all state data
int query_state_data(sqlite3 *db) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT date, time, state, message FROM states ORDER BY date ASC, time ASC";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return rc;
    }

    printf("\n");
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

//Query and display all syslogs data
int query_syslogs_data(sqlite3 *db) {
    sqlite3_stmt *stmt;
    const char *sql = "SELECT date, time, source, message FROM logs ORDER BY date ASC, time ASC";

    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Failed to prepare query: %s\n", sqlite3_errmsg(db));
        return rc;
    }

    printf("\n");
    printf("%-12s %-10s %-20s %s\n", "Date", "Time", "Source", "Message");
    printf("-------------------------------------------------------------------\n");

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        const char *date = (const char*)sqlite3_column_text(stmt, 0);
        const char *time = (const char*)sqlite3_column_text(stmt, 1);
        const char *source = (const char*)sqlite3_column_text(stmt, 2);
        const char *message = (const char*)sqlite3_column_text(stmt, 3);

        printf("%-12s %-10s %-20s %s\n", date, time, source, message);
    }

    sqlite3_finalize(stmt);
    return SQLITE_OK;
}