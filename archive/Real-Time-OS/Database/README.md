Author: Nick Fuda, Carleton University


To use:
Compilation
On Linux or Windows:
1. Be sure you have QCC installed
2. Run qnxsdp-env.bat as admin in terminal
3. Enter the following to compile with qcc
    qcc sqlite3.c database.c -o DBapp

On QNX:
1. Compile with qcc, same command as above

Running:
    Once compiled, run the process on QNX. It should;
        - Create a database (or use an existing one)
        - Open a message queue (if it isn't open already)
        - Run a while loop that waits to receive from the message queue
        - Insert messages from the queue into tables


********************************************************************************
The current build is ready for testing on QNX, though other programs will need
to use the dbstruct.h to have the correct format.


--------------------------------------------------------------------------------
Notes on dbstruct.h

The table parameter in DB_t refers to the table to insert the data into. It must
be one of the following:
    - "sensors" --> for inserting into the sensors table
    - "states" --> for inserting into the states table
    - "logs" --> for inserting into the logs table

As new tables are added, this may need to be updated. This will include adding
a new table via create_tables(), a new insert function for the table, and adding
to the receive_and_store() function to process and insert the message data.
--------------------------------------------------------------------------------

Notes on the database.c files

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

Testing on QNX is difficult via a VM or trying QEmu at this time. I am relying
on group members with a RPi to test for me. 