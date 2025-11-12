import requests

from global_map_router.app.common.config_loader import GOOGLE_MAP_API_KEY
from global_map_router.app.common.constant import LogMessageCons, GoogleApiServiceCons

def get_coordinates(address: str, logger):
    """
    address -> latitude, longitude
    Using Google Geocoding API
    """
    url = GoogleApiServiceCons.API_GEOCODE_URL % (address, GOOGLE_MAP_API_KEY)
    resp = requests.get(url).json()

    if resp[GoogleApiServiceCons.RESP_STATUS] != GoogleApiServiceCons.RESP_STATUS_OK:
        logger.error(LogMessageCons.FAIL_RECIVED_GEOCODER, resp[GoogleApiServiceCons.RESP_STATUS])
        return None, None

    loc = resp[GoogleApiServiceCons.RESP_RESULTS][0][GoogleApiServiceCons.RESP_RESULTS_GEOMETRY][GoogleApiServiceCons.RESP_RESULTS_GEOMETRY_LOCATION]
    return loc[GoogleApiServiceCons.RESP_RESULTS_GEOMETRY_LOCATION_LAT], loc[GoogleApiServiceCons.RESP_RESULTS_GEOMETRY_LOCATION_LON]

def get_route(start, dest, logger):
    """
    Using Directions API get router polyline
    """
    s_lat, s_lon = start
    d_lat, d_lon = dest

    url = GoogleApiServiceCons.API_Directions_URL % (s_lat, s_lon, d_lat, d_lon, GOOGLE_MAP_API_KEY)

    resp = requests.get(url).json()

    if resp[GoogleApiServiceCons.RESP_STATUS] != GoogleApiServiceCons.RESP_STATUS_OK:
        logger.error(LogMessageCons.FAIL_RECIVED_DIRECTIONS, resp[GoogleApiServiceCons.RESP_STATUS])
        return None

    encoded = resp[GoogleApiServiceCons.RESP_ROUTES][0][GoogleApiServiceCons.RESP_ROUTES_OVERVIEW_POLILINE][GoogleApiServiceCons.RESP_ROUTES_OVERVIEW_POLILINE_POINTS]
    return decode_polyline(encoded)

def decode_polyline(poly):
    """
    Google polyline decode
    """
    points = []
    index = lat = lon = 0

    while index < len(poly):
        result = shift = 0
        while True:
            b = ord(poly[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lat_change = ~(result >> 1) if result & 1 else result >> 1
        lat += lat_change

        result = shift = 0
        while True:
            b = ord(poly[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lon_change = ~(result >> 1) if result & 1 else result >> 1
        lon += lon_change

        points.append((lat / 1e5, lon / 1e5))

    return points