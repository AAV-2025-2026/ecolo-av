"""
The HUD's web server: the HTTP routes and Socket.IO events of the Flutter app.

No ROS imports. hud_server gives it a backend (the ROS side) and calls send() to push
an event to every app window. The tests use Flask's and Flask-SocketIO's test clients.

HTTP
  GET  /             the newest copy of every event, as JSON: a health check
  POST /receive      the route the app locked, [{'lat': .., 'lon': ..}, ...]: Nav2 drives it
  POST /cancel       stop following the route (the app has no button for it yet)
  GET  /stream-info  where MediaMTX serves the video (the app's camera page)
Socket.IO
  each new client gets stream_info, then the newest copy of every event (events.py)

The backend has follow(waypoints) and cancel(). Each returns None when done, or the
reason it couldn't.
"""

import logging
import threading

from aav_hud import events
from aav_hud.route import parse_route, to_waypoints
from flask import Flask, jsonify, request
from flask_socketio import emit, SocketIO


class HudWeb:
    """The Flask app and its Socket.IO server, for one backend."""

    def __init__(self, backend, stream_info, tolerance=1.0, min_spacing=5.0):
        self.backend = backend
        self.stream_info = stream_info
        self.tolerance = tolerance
        self.min_spacing = min_spacing
        self.app = Flask('aav_hud')
        # Any origin, as in 2025-26. The host parameter decides who can connect at all.
        self.socketio = SocketIO(self.app, cors_allowed_origins='*', async_mode='threading')
        self._latest = {}
        self._lock = threading.Lock()
        self._routes()

    def send(self, event, payload):
        """Push an event to every client, and keep it for clients that join later."""
        with self._lock:
            self._latest[event] = payload
        self.socketio.emit(event, payload)

    def latest(self):
        """Return the newest copy of every event sent so far."""
        with self._lock:
            return dict(self._latest)

    def run(self, host, port):
        """Serve until the process ends. Blocks: run it in a thread."""
        # Werkzeug logs every request, and Socket.IO polling makes many.
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        # allow_unsafe_werkzeug: Flask-SocketIO 5.3+ refuses Werkzeug when stdin isn't a
        # terminal (systemd, launch), and the back end then silently never listens.
        self.socketio.run(self.app, host=host, port=port, debug=False, use_reloader=False,
                          allow_unsafe_werkzeug=True)

    def _routes(self):
        app, socketio = self.app, self.socketio

        @app.route('/')
        def health():
            return jsonify(self.latest())

        @app.route('/stream-info')
        def stream_info():
            return jsonify(self.stream_info)

        @app.route('/receive', methods=['POST'])
        def receive():
            data = request.get_json(silent=True)
            try:
                waypoints = to_waypoints(parse_route(data), self.tolerance, self.min_spacing)
            except ValueError as e:
                return jsonify({'status': 'error', 'message': f'bad route: {e}'}), 400
            problem = self.backend.follow(waypoints)
            if problem:
                return jsonify({'status': 'error', 'message': problem}), 503
            return jsonify({'status': 'success', 'received': data,
                            'waypoints': len(waypoints)})

        @app.route('/cancel', methods=['POST'])
        def cancel():
            problem = self.backend.cancel()
            if problem:
                return jsonify({'status': 'error', 'message': problem}), 409
            return jsonify({'status': 'success'})

        @socketio.on('connect')
        def on_connect(auth=None):
            emit(events.STREAM_INFO, self.stream_info)
            for event, payload in self.latest().items():
                emit(event, payload)
