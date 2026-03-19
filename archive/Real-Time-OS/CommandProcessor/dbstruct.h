//struct that includes message id and message, identifies table to enter into
typedef struct{
    //The type of message coming through (determines table to insert into)
    char table[100]; //sensors, logs, states (one for each table, exact naming conventions)
    //The id of the module the message is coming from (goes into table)
    char id[100]; //(BCM, safety, cmd, etc.)
    //The message to go into the table
    char msg[100]; //buffer of 100 characters for message
} DB_t; //allows this to be referred to as DB_t, e.g. DB_t msgq;