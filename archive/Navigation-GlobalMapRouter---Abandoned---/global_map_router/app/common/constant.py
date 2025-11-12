import os

class LogMessageCons:
    LOGGER_GLOBAL_MAP_ROUTER="global_map_router"
    LINE_BREAK="================"
    SUC_INIT_GNN_1="Starting Global Navigation Node"
    SUC_INIT_GNN_2="Waiting for /target_address..."
    SUC_RECEIVED_DESTINATION="Received destination: %s"
    SUC_RECEIVED_GPS="Current GPS: lat=%s, lon=%s"
    FAIL_GET_DESTINATION_COORDINATES="Failed to get destination coordinates"
    SUC_GET_DESTINATION_COORDINATES="Destination: lat=%s, lon=%s"
    FAIL_GET_ROUTE="Failed to get route"
    SUC_GET_ROUTE="Route received: %s points"
    PRT_ROUTE="   Point %s: lat=%s, lon=%s"

    FAIL_RECIVED_GEOCODER="Geocoder failed: %s"
    FAIL_RECIVED_DIRECTIONS="Directions API failed: %s"

class ApplicationCons:
    MAIN_MODUAL="__main__"
    NODE_TARGET_ADDRESS="/target_address"
    NODE_GLOBAL_MAP_ROUTER="global_map_router"

class GoogleApiServiceCons:
    API_GEOCODE_URL="https://maps.googleapis.com/maps/api/geocode/json?address=%s&key=%s"
    API_Directions_URL = "https://maps.googleapis.com/maps/api/directions/json?origin=%s,%s&destination=%s,%s&key=%s"
    RESP_STATUS="status"
    RESP_STATUS_OK="OK"
    RESP_RESULTS="results"
    RESP_RESULTS_GEOMETRY="geometry"
    RESP_RESULTS_GEOMETRY_LOCATION="location"
    RESP_RESULTS_GEOMETRY_LOCATION_LAT="lat"
    RESP_RESULTS_GEOMETRY_LOCATION_LON="lng"
    RESP_ROUTES="routes"
    RESP_ROUTES_OVERVIEW_POLILINE="overview_polyline"
    RESP_ROUTES_OVERVIEW_POLILINE_POINTS="points"
