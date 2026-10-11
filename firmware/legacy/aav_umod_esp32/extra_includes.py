Import("env")

# The WebSockets library includes WiFi.h, which PlatformIO's library finder misses, so
# add the framework's WiFi folders by hand. Ask PlatformIO where the framework is: the
# folder's name depends on the machine (framework-arduinoespressif32, with or without
# "@3.20009.0").
framework = env.PioPlatform().get_package_dir("framework-arduinoespressif32")
env.Append(CPPPATH=[
    framework + "/libraries/WiFi/src",
    framework + "/libraries/WiFiClientSecure/src",
])
