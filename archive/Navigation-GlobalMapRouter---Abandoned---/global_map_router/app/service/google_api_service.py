import requests

from global_map_router.app.common.config_loader import GOOGLE_MAP_API_KEY

def get_coordinates(address: str, logger):
    """
    address -> latitude, longitude
    Using Google Geocoding API
    """
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={address}&key={GOOGLE_MAP_API_KEY}"
    )

    resp = requests.get(url).json()

    if resp["status"] != "OK":
        logger.error(f"❌ Geocoder failed: {resp['status']}")
        return None, None

    loc = resp["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]

def get_route(start, dest, logger):
    """
    Using Directions API get router polyline
    """
    s_lat, s_lon = start
    d_lat, d_lon = dest

    url = (
        "https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={s_lat},{s_lon}&destination={d_lat},{d_lon}&key={GOOGLE_MAP_API_KEY}"
    )

    resp = requests.get(url).json()

    if resp["status"] != "OK":
        logger.error(f"❌ Directions API failed: {resp['status']}")
        return None

    encoded = resp["routes"][0]["overview_polyline"]["points"]
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