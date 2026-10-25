

"""
This python module will help either "store" or "fetch" data from a local database (using SQLite).
Code by: Alexandre Laframboise
Link to "Python SQLite Tutorial": sqlitetutorial.net/sqlite-python/creating-database
View .db files with this software: "DB Browser for SQLite"

How this .py file works:
* 'execute' this script at least once to set the database (create .db file, create the tables).
* then 'use' this script as a module in ros2 .py files to modify existing tables.


Local DB will help record or fetch the following:

timestamp, current_location(name, latitude, longitude), destination(name, latitude, longitude))


(may add more)
Note: Perhaps eventually create code that periodically synchronizes SQLite with Firebase (SQlite --> Firebase)


"""

import os
import sqlite3

from datetime import datetime

#class LocalDB

path_to_home_pi = "/home/pi"
path_to_local_db = "/home/pi/local_databases"

path_to_travel_data_db = "/home/pi/local_databases/travel_data.db"



# if local_databases fikder does not exist, create it 
def _create_local_db_folder():
    print("Checking if '/home/pi/local_databases' folder exists")
    # create "pi" folder if not exist
    if os.path.exists(path_to_home_pi):
        pass
    else:
        os.mkdir(path_to_home_pi, mode=0o755)


        
    if os.path.exists(path_to_local_db):
        print("SUCCESS: '/home/pi/local_databases' exits, all good.")
        pass # Folder exists, do nothing
    else:
        os.mkdir(path_to_local_db, mode=0o755)
        print("Warning: Folder 'local_databases' did not exist, so we created one for you.")



def _create_local_db_travel_data():

    # using "with" and "as" python syntax closes DB connection automatically
    # No need to  close manually in code
    try:
        with sqlite3.connect(path_to_travel_data_db) as conn:
            # connected to DB. Do whatever you want with "conn"

            cursor = conn.cursor()

            # creates schema for db (table with no data)
            sql_statement_create_table = """
                CREATE TABLE IF NOT EXISTS "routes" (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL DEFAULT (datetime('now')),

                        current_location_name TEXT NOT NULL,
                        current_lat REAL NOT NULL,
                        current_lon REAL NOT NULL,

                        destination_name TEXT NOT NULL,
                        dest_lat REAL NOT NULL,
                        dest_lon REAL NOT NULL
                
                );
                """


            cursor.execute(sql_statement_create_table)
            
            conn.commit()


    except sqlite3.OperationalError as e:
        print("Failed to open the local database", e)


class CarLocalDB():
    """
    Manages the local database of the car
    """

    def __init__(self):
        pass



    def store_current_location(self, name:str, lat:float, lon:float):
        # update only timestamp, name/lat/lon of current location
        pass
    def fetch_current_location(self):
        pass

    def store_destination(self, name:str, lat:float, lon:float):
        # update only timestamp, name/lat/lon of destination
        pass
    def fetch_destination(self):
        pass




    def _store_location_test(self, 
                               cur_name:str, cur_lat:float, cur_lon:float,
                               dest_name:str, dest_lat:float, dest_lon:float):
        """
        Do not use this function by itself (private function)
        """

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # insert to table:
        sql_statement = """
            INSERT INTO routes
            (timestamp, current_location_name, current_lat, current_lon, destination_name, dest_lat, dest_lon)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params = (now, cur_name, cur_lat, cur_lon, dest_name, dest_lat, dest_lon)

        self.access_existing_db(path_to_travel_data_db, sql_statement, params)



        pass

    
    def test_add_mock_data(self):
        """
            Execute this function to add mock data in 
            /home/pi/travel_data.db
        """
        self._store_location_test("Test Location", 0.123, 0.456, "Test Destination", 1337, 50)
        pass





    def access_existing_db(self, db_path:str, sql_statement:str, params:tuple):
        """
            Add/Remove data from a some_database.db and in table_name

            Parameters
            ------------
            db_path : str
                Path to db file (example: "/home/pi/my_database.db")
            sql_statement : str
                The SQL code for what to do with the table.
        """
        try:
            with sqlite3.connect(db_path) as conn:
                # connected to DB. Do whatever you want with "conn"

                cursor = conn.cursor()
                cursor.execute(sql_statement, params)
                
                conn.commit()

        except sqlite3.OperationalError as e:
            print("Failed to open the local database", e)


def main():

    # creates folder for all local db's at /home/pi/local_db
    _create_local_db_folder()


    # creates the empty database "travel_data.db" complete with schema
    _create_local_db_travel_data()

    # Adds "test" data in "travel_data.db"
    maincar = CarLocalDB()
    maincar.test_add_mock_data()

    








if __name__ == "__main__":
    main()