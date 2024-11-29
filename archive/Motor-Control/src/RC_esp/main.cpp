//
// Created by Charlie Wadds on 2024-11-22.
//
#include <Arduino.h>
#include <micro_ros_platformio.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <std_msgs/msg/int32.h>
#include <ackermann_msgs/msg/ackermann_drive.h>

// Pin definitions for RC inputs
#define CH1 4  // Right joystick horizontal (steering)
#define CH3 5  // Left joystick vertical (throttle/brake)

// Pin definition for status LED
#define LED_PIN 2  // Adjusted for ESP32 onboard LED (default GPIO 2)

// ROS variables
rcl_publisher_t throttle_brake_publisher;
rcl_publisher_t steering_publisher;
std_msgs__msg__Int32 throttle_brake_msg;
std_msgs__msg__Int32 steering_msg;
ackermann_msgs__msg__AckermannDrive ackermann_msg;
rclc_support_t support;
rcl_allocator_t allocator;
rcl_node_t node;

// Macro for error handling
#define RCCHECK(fn) { rcl_ret_t temp_rc = fn; if ((temp_rc != RCL_RET_OK)) { error_loop(); } }
#define RCSOFTCHECK(fn) { rcl_ret_t temp_rc = fn; if ((temp_rc != RCL_RET_OK)) {} }

// Function to handle ROS errors
void error_loop() {
    while (1) {
        digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blink LED to indicate an error
        delay(100);
        Serial.println("ROS Error");
    }
}

// Function to read a channel and map its value to a given range
int readChannel(int channelInput, int minLimit, int maxLimit, int defaultValue) {
    int ch = pulseIn(channelInput, HIGH, 30000); // Read PWM signal
    if (ch < 100) return defaultValue; // Default value if signal is invalid
    return map(ch, 1000, 2000, minLimit, maxLimit);
}

void setup() {
    // Initialize serial communication and Wi-Fi transport
    Serial.begin(115200);
    IPAddress local_IP(192, 168, 1, 126);
    set_microros_wifi_transports("AAVwifi", "aav@2023", local_IP, (uint16_t) 8888);


    // Initialize LED
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);

    // Initialize RC input pins
    pinMode(CH1, INPUT); // Right joystick horizontal
    pinMode(CH3, INPUT); // Left joystick vertical

    allocator = rcl_get_default_allocator();

    // Create ROS node and publishers
    RCCHECK(rclc_support_init(&support, 0, NULL, &allocator));
    RCCHECK(rclc_node_init_default(&node, "micro_ros_esp32_rc_node", "", &support));

//    // Create publisher for throttle and brake
//    RCCHECK(rclc_publisher_init_best_effort(
//            &throttle_brake_publisher,
//            &node,
//            ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
//            "/throttle_brake"));

    // Create publisher for steering
    RCCHECK(rclc_publisher_init_best_effort(
            &steering_publisher,
            &node,
            ROSIDL_GET_MSG_TYPE_SUPPORT(ackermann_msgs, msg, AckermannDrive),
            "/driveData"));

    // Initialize message data
//    throttle_brake_msg.data = 0;
//    steering_msg.data = 0;

    delay(2000);
}

void loop() {
    // Read joystick inputs
    int leftVertical = readChannel(CH3, -255, 255, 0); // Left joystick vertical
    int rightHorizontal = readChannel(CH1, -255, 255, 0); // Right joystick horizontal

    // Map left joystick vertical to throttle and brake
    if (leftVertical > 0) { // Positive: throttle
        ackermann_msg.acceleration = (float) leftVertical * 10;
    } else { // Negative or zero: brake
        ackermann_msg.acceleration = (float) leftVertical * 10; // Brake as a negative value
    }

    // Map right joystick horizontal to steering
    ackermann_msg.steering_angle = (float) rightHorizontal *10;

    // Publish throttle/brake and steering values
    //RCSOFTCHECK(rcl_publish(&throttle_brake_publisher, &throttle_brake_msg, NULL));
    //RCSOFTCHECK(rcl_publish(&steering_publisher, &steering_msg, NULL));
    RCSOFTCHECK(rcl_publish(&steering_publisher, &ackermann_msg, NULL));

    // Debug output
    Serial.print("Throttle/Brake: ");
    Serial.println(throttle_brake_msg.data);
    Serial.print("Steering: ");
    Serial.println(steering_msg.data);

    delay(50); // Small delay for stability
}
