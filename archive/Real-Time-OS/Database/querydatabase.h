#ifndef QUERYDATABASE_H
#define QUERYDATABASE_H

#include "sqlite3.h"

void query_sensors(sqlite3 *db);
void query_states(sqlite3 *db);
void query_logs(sqlite3 *db);

#endif