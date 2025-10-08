from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
def home():
    return "Flask Server for UI" 


if __name__ == '__main__':
    # host='0.0.0.0' allows access from other devices on the same network
    app.run(host='0.0.0.0', port=5000, debug=True)
