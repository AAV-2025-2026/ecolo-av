#ifndef DATABASE_H
#define DATABASE_H

#include "sqlite3.h"
#include <mqueue.h>
//Function prototypes
//----------------------------------------
// Initialization
int init_database(sqlite3 **db);
int create_tables(sqlite3 *db);
mqd_t open_mqueue(); //For opening message queue on DB start
void drain_queue(mqd_t mqd);

//Insertion into db
int receive_and_store(sqlite3 *db, mqd_t mqd); //For receiving from mqueue and storing in db
int insert_sensor_data(sqlite3 *db, const char *sensor, const char *message);
int insert_state_data(sqlite3 *db, const char *state, const char *message);
int insert_syslogs_data(sqlite3 *db, const char *source, const char *message);

//Read from DB
int query_sensor_data(sqlite3 *db);
int query_state_data(sqlite3 *db);
int query_syslogs_data(sqlite3 *db);

#endif