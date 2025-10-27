import os
from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)

# --- Locate the Firebase key file ---
base_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(base_dir, "../Database/autocar-ui-firebase-adminsdk-fbsvc-1771676b0b.json")

# --- Initialize Firebase ---
if not firebase_admin._apps:  # prevent re-initialization
    cred = credentials.Certificate(json_path)
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://autocar-ui-default-rtdb.firebaseio.com/",
        "projectId": "autocar-ui"
    })

# --- Reference base node ---
ref = db.reference("test_node")

# --- AUTO UPDATE: write Partha Das record when the server starts ---
def initialize_database():
    print("🔥 Writing Partha Das data to Firebase...")
    users_ref = ref.child("users")

    # Write only if not already present
    users_ref.child("ParthaDas").set({
        "full_name": "Partha Das",
        "date_of_birth": "October 10"
    })
    print("✅ Firebase test data written successfully (Partha Das added).")

initialize_database()  # run once at startup


# --- ROUTES ---

@app.route('/')
def home():
    users_ref = ref.child("users")
    users = users_ref.get()

    if not users:
        return "No users found in the database."

    # Create HTML output
    html = "<h2>👤 Firebase Users</h2><ul>"
    for key, data in users.items():
        name = data.get("full_name", key)
        dob = data.get("date_of_birth", "Unknown DOB")
        html += f"<li><strong>{name}</strong> — DOB: {dob}</li>"
    html += "</ul>"

    return html


@app.route('/users', methods=['GET'])
def get_users():
    users_ref = ref.child("users")
    users = users_ref.get()
    return jsonify(users if users else {})


@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.get_json()
    name = data.get("name")
    full_name = data.get("full_name")
    dob = data.get("date_of_birth")

    if not name:
        return jsonify({"error": "Name field is required"}), 400

    user_ref = ref.child("users").child(name)
    user_ref.set({
        "full_name": full_name or "Unknown",
        "date_of_birth": dob or "Unknown"
    })
    return jsonify({"message": f"User '{name}' added/updated successfully."}), 201


@app.route('/delete_user/<string:name>', methods=['DELETE'])
def delete_user(name):
    user_ref = ref.child("users").child(name)
    if user_ref.get():
        user_ref.delete()
        return jsonify({"message": f"User '{name}' deleted successfully."})
    else:
        return jsonify({"error": "User not found"}), 404


# --- Run the server ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
