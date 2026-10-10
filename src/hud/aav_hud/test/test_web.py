"""Tests for web.py: the HTTP routes and Socket.IO events, with a fake ROS side."""

from aav_hud import events
import pytest

# Not pytest.importorskip: ROS's launch_testing pytest plugin turns a module-level skip
# into a skip of every test in the folder.
try:
    from aav_hud.web import HudWeb
except ImportError:
    HudWeb = None

pytestmark = pytest.mark.skipif(HudWeb is None, reason='needs Flask and Flask-SocketIO')

ROUTE = [{'lat': 45.3860, 'lon': -75.6960}, {'lat': 45.3870, 'lon': -75.6960}]
STREAM = {'name': 'cam1'}


class FakeBackend:

    def __init__(self, problem=None, picture=None):
        self.problem = problem
        self.picture = picture
        self.routes = []
        self.cancels = 0

    def follow(self, waypoints):
        self.routes.append(waypoints)
        return self.problem

    def cancel(self):
        self.cancels += 1
        return self.problem

    def camera_png(self):
        if isinstance(self.picture, Exception):
            raise self.picture
        return self.picture


def make_web(problem=None, picture=None):
    return HudWeb(FakeBackend(problem, picture), STREAM, tolerance=1.0, min_spacing=5.0,
                  camera_fps=50.0)


def test_a_locked_route_goes_to_the_backend():
    web = make_web()
    reply = web.app.test_client().post('/receive', json=ROUTE)
    assert reply.status_code == 200
    body = reply.get_json()
    assert body['status'] == 'success'
    assert body['received'] == ROUTE
    assert body['waypoints'] == 1
    [waypoints] = web.backend.routes
    assert (waypoints[0].lat, waypoints[0].lon) == (45.3870, -75.6960)


@pytest.mark.parametrize('bad', [{'json': {'nope': 1}}, {'json': []},
                                 {'data': 'not json', 'content_type': 'text/plain'}])
def test_a_bad_route_is_refused(bad):
    web = make_web()
    reply = web.app.test_client().post('/receive', **bad)
    assert reply.status_code == 400
    assert reply.get_json()['message'].startswith('bad route')
    assert web.backend.routes == []


def test_without_nav2_the_app_gets_503():
    web = make_web('Nav2 is not running')
    reply = web.app.test_client().post('/receive', json=ROUTE)
    assert reply.status_code == 503
    assert reply.get_json() == {'status': 'error', 'message': 'Nav2 is not running'}


def test_cancel():
    assert make_web().app.test_client().post('/cancel').status_code == 200
    web = make_web('no route is being followed')
    reply = web.app.test_client().post('/cancel')
    assert reply.status_code == 409
    assert web.backend.cancels == 1


def test_health_check_shows_the_newest_events():
    web = make_web()
    web.send(events.SPEED, {'mock_speed': 1.0})
    web.send(events.SPEED, {'mock_speed': 2.0})
    assert web.app.test_client().get('/').get_json() == {
        'mock_speed_update': {'mock_speed': 2.0}}


def test_stream_info_route():
    assert make_web().app.test_client().get('/stream-info').get_json() == STREAM


def test_a_new_client_gets_stream_info_then_the_newest_events():
    web = make_web()
    web.send(events.SPEED, {'mock_speed': 2.0})
    web.send(events.STOP_SIGN, {'mock_sign_detected': True, 'message': 'STOP'})
    received = web.socketio.test_client(web.app).get_received()
    assert received == [
        {'name': 'stream_info', 'args': [STREAM], 'namespace': '/'},
        {'name': 'mock_speed_update', 'args': [{'mock_speed': 2.0}], 'namespace': '/'},
        {'name': 'mock_stop_sign_alert',
         'args': [{'mock_sign_detected': True, 'message': 'STOP'}], 'namespace': '/'},
    ]


def test_send_reaches_every_client():
    web = make_web()
    clients = [web.socketio.test_client(web.app) for _ in range(2)]
    for c in clients:
        c.get_received()
    web.send(events.POSITION, {'mock_latitude': 45.0, 'mock_longitude': -75.0})
    for c in clients:
        assert c.get_received() == [{
            'name': 'mock_gps_update',
            'args': [{'mock_latitude': 45.0, 'mock_longitude': -75.0}],
            'namespace': '/'}]


def test_the_newest_camera_picture():
    web = make_web(picture=b'\x89PNG...')
    reply = web.app.test_client().get('/camera/latest.png')
    assert reply.status_code == 200
    assert reply.mimetype == 'image/png'
    assert reply.data == b'\x89PNG...'
    assert reply.headers['Cache-Control'] == 'no-store'


def test_no_camera_picture_yet():
    reply = make_web().app.test_client().get('/camera/latest.png')
    assert reply.status_code == 503
    assert reply.headers['Retry-After'] == '1'


def test_a_camera_encoding_it_cannot_show():
    web = make_web(picture=ValueError("camera encoding 'yuv422' is not one of rgb8, ..."))
    reply = web.app.test_client().get('/camera/latest.png')
    assert reply.status_code == 415
    assert b'yuv422' in reply.data


def test_the_camera_stream_sends_each_new_picture():
    web = make_web(picture=b'one')
    pictures = web.pictures()
    assert next(pictures) == (b'--picture\r\nContent-Type: image/png\r\n'
                              b'Content-Length: 3\r\n\r\none\r\n')
    web.backend.picture = b'two'
    assert next(pictures).endswith(b'\r\n\r\ntwo\r\n')
    reply = web.app.test_client().get('/camera/stream', buffered=False)
    assert reply.content_type == 'multipart/x-mixed-replace; boundary=picture'
    reply.close()
