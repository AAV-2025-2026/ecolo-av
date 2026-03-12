Author: Nick Fuda, Carleton University


To use:

1. Open Database folder directory in terminal
2. Build using the command 'gcc -o dbapp database.c sqlite3.c'
3. Run in terminal by typing 'dbapp.exe'

Note that if you are testing, and the database is not valuable, you can simply 
delete the database file (database.db) to start fresh. If the database has 
been used in field testing, make sure to back up the database.

You can insert a database file as long as it uses the same name, and read it
by using the command "query_sensors" or "query_states" in the database app.

******************************************************************************
This current build works on windows, but will need to be adjusted for QNX.

The main adjustment is the collection of date and time from the operating system.
The rest of the code (sqlite and functions) should perform as intended.