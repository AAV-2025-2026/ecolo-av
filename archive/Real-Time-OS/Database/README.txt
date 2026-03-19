Author: Nick Fuda, Carleton University

**Important**
The database must be one of the first apps running on the machine so that mq_open
does not fail in other apps. Make sure it is first opened if other apps send a
startup message. It is small and should start quickly.

The database app does not currently have a way to close. The message queue remains
open indefinitely and the app ultimately shuts down with the system. There is
some code that exists in the main function that can never be reached due to
having to break the while loop, which will most likely be done through a specific
message from one of the senders.
--------------------------------------------------------------------------------

# To use:
## Compilation
On Linux or Windows:
1. Be sure you have QCC installed
2. Run qnxsdp-env.bat as admin in terminal
3. Navigate to the directory of the files (e.g. "cd C:\Users\Me\Desktop\Db")
3. Enter the following to compile with qcc

    **For the Database App itself**
    qcc sqlite3.c database.c -o DBapp

    **For the Queue Test**
    qcc queuetest.c -o QTest

On QNX:
    QNX should only receive the compiled applications. Therefore compile on
    windows or linux, then transfer to QNX.

## Running:
1. Navigate to the directory of the files
2. type "chmod +x filename" for both the DBapp and QTest
3.  ./DBapp  --> Runs the DBapplication
    ./QTest  --> Runs the Queue Test

    To run both: First run the DB app in the background (./DBapp &)
    then run the queue test (./QTest)


    Once compiled, the database app should;
    - Create a database (or use an existing one if the file exists)
    - Open a message queue (if it isn't open already)
    - Run a while loop that waits to receive from the message queue
    - Insert messages from the queue into tables




## Adding Senders;

Add the following includes

#include "dbstruct.h"

#include <mqueue.h>

#include <fcntl.h>

Add this snippet to main

mqd_t mqd = mq_open("/db_queue", O_WRONLY);
if (mqd == (mqd_t)-1) {
perror("mq_open");
return 1;
}

To send a message, create a DB_t struct and use mq_send:

DB_t msg;
strncpy(msg.table, "sensors", sizeof(msg.table));  // "sensors", "states", or "logs"
strncpy(msg.id, "your_sensor_name", sizeof(msg.id));
strncpy(msg.msg, "your message here", sizeof(msg.msg));

Then use

mq_send(mqd, (char*)&msg, sizeof(DB_t), 0);


4. Close the queue on shutdown
mq_close(mqd);


The current build is running on QNX with working queues. Message senders need to
have a few lines of code added, the format of which will be added below.

--------------------------------------------------------------------------------
## Notes on dbstruct.h

The table parameter in DB_t refers to the table to insert the data into. It must
be one of the following:
    - "sensors" --> for inserting into the sensors table
    - "states" --> for inserting into the states table
    - "logs" --> for inserting into the logs table

As new tables are added, this may need to be updated. This will include adding
a new table via create_tables(), a new insert function for the table, and adding
to the receive_and_store() function to process and insert the message data.

--------------------------------------------------------------------------------

# Notes on the database.c files

It will NOT compile on Windows through gnu or gcc. It contains a POSIX library
called mqueue.h, which is only available on qnx and linux. It should compile and
run normally on Linux with a gcc command.

The message queue requires some implementation in other modules that interact
with it. For example, the BCM will need a function to send to the message queue
(mq_send()). It will also need privileges assigned, which would be write
privileges so that it may interact by adding a message.

QNX has a default limit of 10 messages in a message queue. This can be changed
but I do not believe we will have the time to do this.

--------------------------------------------------------------------------------

Tested on Oracle Virtualbox VM with scp to send the files.
To send:
1. Find the ip of your vm (run ifconfig, look for inet followed by IP address)
2. In windows, open cmd, navigate to your folder, and type:
    scp -o MACs=hmac-sha2-256 <filename> root@<ip>

    e.g. scp -o MACs=hmac-sha2-256 QTest root@127.0.0.1: