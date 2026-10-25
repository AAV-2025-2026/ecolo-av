"""
What this .py file is: Code that utilizes "Cloud Firestore" for the AAV project.

Google has a platform called "Firebase". 
Firebase offers a lot of services, one of which includes "Cloud Firestore", a NoSQL database service.
"""

# code by Alexandre Laframboise (message me on the project's Discord if any questions)
# The following link contains information on how to get started with Firestore for Python: "https://firebase.google.com/docs/firestore/quickstart"

import os
import firebase_admin
from firebase_admin import firestore, credentials



# For database access credentials, two options available:
# * Option 1: we store .json file (the credentials) in an env variable. in Windows's CMD, type:  "set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\private_key.json"
# * Option 2: hardcode the path in, leading to the .json file itself.

# use command "echo %GOOGLE_APPLICATION_CREDENTIALS%" to print value of env variable, if correctly set (it should output the path)
print(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))  # prints path to credentials (private key), see if it's detected...

# IMPORTANT -- There is room for improvement for database security. To make it more secure
cred = credentials.Certificate(r"C:\Users\alex_\OneDrive\Carleton 2025 Q4\SYSC 4907 - Capstone\UI\python_code\firestore_private_key\autocar-ui-firebase-adminsdk-fbsvc-9e85130845.json")
firebase_admin.initialize_app(cred, {"projectId": "autocar-ui"})
db = firestore.client()              #  firebase_admin.firestore.client() must not have parameters, despite showing it needs one ... unless you use google.cloud.firestore.Client()


# Note about Firestore:
# Data is stored in Documents, which are further stored in Collections.
# Docs and Collections are added implicity (as in no need to declare... It's automatic)

# example1: 
doc_ref = db.collection("users").document("alovelace")
doc_ref.set({"first": "Ada", "last": "Lovelace", "born": 1815})


# example2: key/value pair example
doc_ref = db.collection("users").document("aturing")
doc_ref.set({"first": "Alan", "middle": "Mathison", "last": "Turing", "born": 1912})



# read data:
users_ref = db.collection("users")
docs = users_ref.stream()

for doc in docs:
    print(f"{doc.id} => {doc.to_dict()}")