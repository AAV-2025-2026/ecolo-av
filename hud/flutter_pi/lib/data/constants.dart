import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';

const kWindowConfig = WindowOptions(
    size: Size(800, 480),
    center: true,
    backgroundColor: Colors.transparent,
    skipTaskbar: false,
    titleBarStyle: TitleBarStyle.hidden,
);

const kAppTitle = 'ROS2 + Flask + Flutter Demo';

const kColorSchemeSeed = Colors.deepPurple;

const kOsrmBaseUrl = 'http://localhost:5001';

/// The HUD's back end (aav_hud's hud_server). Another one at build or run time:
/// --dart-define=HUD_BACKEND=http://127.0.0.1:5123
const kBackendUrl = String.fromEnvironment(
  'HUD_BACKEND',
  defaultValue: 'http://127.0.0.1:5000',
);

/// The credit the map tiles and the place database need: both are OpenStreetMap
/// data, under the ODbL.
const kOsmCredit = '© OpenStreetMap contributors';
