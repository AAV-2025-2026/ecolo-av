# For DB, choose either "Firebase Realtime Database" (FRD) or MongoDB
# The w3schools.com website helps a lot on relearning Python
# The w3schools.com website also helps teach how MongoDB can be implemented in Python (if needed)
# I hate Python already...If I ever have spare time, recode all this in Java or C++...

"""
Script: This Python code handles the database for the autonomous car.
Purpose: To update in real time as efficient as it can
Goal: To run a while loop that keeps updating the DB with project info
"""


import sys;
print(sys.path) # where Python looks for modules

import firebase_admin;
from firebase_admin import credentials
from firebase_admin import db

cred = credentials.Certificate("autocar-ui-firebase-adminsdk-fbsvc-1771676b0b.json")  # loads private key (in the same folder as this .py file). Grants admin access.
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://autocar-ui-default-rtdb.firebaseio.com/",
    "projectId": "autocar-ui"
})


ref = db.reference("test_node")       # not required to have root node, but helps with organization.

ref.set("Hello from Python!");


ref_users = ref.child("users")


ref_users.set({
    "Alex" : {
        "date_of_birth" : "August 20",
        "full_name" : "Alex Laf"
    }
})



print("Python editor version -- "+sys.version);

#x = str(3)    # x will be '3'
y = int(3)    # y will be 3
z = float(3)  # z will be 3.0
x = 5;
y = 6;
z = 7;


