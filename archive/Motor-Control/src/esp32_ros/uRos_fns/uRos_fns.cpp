

#include "uRos_fns.h"
extern rcl_node_t node;
extern uRos_s testSetup;
extern bool ackermann_recv;

#ifdef TRANSPORT_WIFI
int uRos_init_wireless_node_ackermann(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, ackermann_msgs__msg__AckermannDrive *msg, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName){
    rcl_ret_t status;
    //192.168.1.126
    IPAddress local_IP(192, 168, 1, 126);
    //IPAddress local_IP(192, 168, 2, 58);

    String bssid = "";
    while(!WiFi.isConnected()) {
        delay(250);
        digitalWrite(BLUE_LED_PIN, LOW);
        delay(250);

        set_microros_wifi_transports(ssid, pass, local_IP, (uint16_t) port);
        // set_microros_wifi_transports(ssid, pass, ip, (uint16_t) port);
        bssid = WiFi.BSSIDstr();

        if(!WiFi.isConnected()){
            USER_SERIAL.println("WIFI CONNECTION FAILED, trying again");
        }
        digitalWrite(BLUE_LED_PIN, HIGH);

    }
    USER_SERIAL.println("WIFI CONNECTED");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);


    uRosStruct->allocator = rcl_get_default_allocator();




    // Create init_options
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_support_init(&uRosStruct->support, 0, NULL, &uRosStruct->allocator);
        USER_SERIAL.print("Support_init status: ");
        USER_SERIAL.println(status);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);
        delay(1000);

    }

    USER_SERIAL.println("SUPPORT_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);


    // Create node
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_node_init_default(&uRosStruct->node, "micro_ros_arduino_wifi_node_car", "", &uRosStruct->support);
        USER_SERIAL.print("node_init status: "); USER_SERIAL.println(status);
        delay(1000);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);


    }

    USER_SERIAL.println("NODE_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);

    //Create subscriber
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_subscription_init_best_effort(
                &uRosStruct->subscriber_1,
                &uRosStruct->node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(ackermann_msgs, msg, AckermannDrive), topicName);
        USER_SERIAL.print("subscriber_init status: "); USER_SERIAL.println(status);
        delay(1000);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);


    }


    USER_SERIAL.println("SUBSCRIBER_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);


    // Create executor
    //Create subscriber
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_executor_init(&uRosStruct->executor, &uRosStruct->support.context, 1, &uRosStruct->allocator);
        USER_SERIAL.print("executor_init status: "); USER_SERIAL.println(status);
        delay(1000);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);

    }

    USER_SERIAL.println("EXECUTOR_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);

    status = rclc_executor_add_subscription(&uRosStruct->executor, &uRosStruct->subscriber_1, msg, *subscription_callback, ON_NEW_DATA);
    USER_SERIAL.print("ex add sub init status: "); USER_SERIAL.println(status);
    if(status != RCL_RET_OK){return 0;}


    return status;
}
#endif

#ifdef TRANSPORT_SERIAL
int uRos_init_serial_node_ackermann(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, ackermann_msgs__msg__AckermannDrive *msg, char *nodeName, char *topicName){
    rcl_ret_t status;
    //192.168.1.126
    //IPAddress local_IP(192, 168, 1, 147);
    //IPAddress local_IP(192, 168, 2, 58);

    //Serial1.begin(115200, RX_PIN_1, TX_PIN_1);
    //pinMode(RX_PIN_1, INPUT_PULLUP);
    ROS_SERIAL.begin(115200, SERIAL_8N1, RX_PIN_1, TX_PIN_1);
    set_microros_serial_transports(ROS_SERIAL);



    uRosStruct->allocator = rcl_get_default_allocator();




    // Create init_options
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_support_init(&uRosStruct->support, 0, NULL, &uRosStruct->allocator);
        USER_SERIAL.print("Support_init status: ");
        USER_SERIAL.println(status);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);
        delay(1000);

    }

    USER_SERIAL.println("SUPPORT_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);


    // Create node
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_node_init_default(&uRosStruct->node, "micro_ros_arduino_wifi_node_car", "", &uRosStruct->support);
        USER_SERIAL.print("node_init status: "); USER_SERIAL.println(status);
        delay(1000);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);


    }

    USER_SERIAL.println("NODE_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);

    //Create subscriber
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_subscription_init_best_effort(
                &uRosStruct->subscriber_1,
                &uRosStruct->node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(ackermann_msgs, msg, AckermannDrive), topicName);
        USER_SERIAL.print("subscriber_init status: "); USER_SERIAL.println(status);
        delay(1000);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);


    }


    USER_SERIAL.println("SUBSCRIBER_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);


    // Create executor
    //Create subscriber
    status = 1;
    while(status) {
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        status = rclc_executor_init(&uRosStruct->executor, &uRosStruct->support.context, 1, &uRosStruct->allocator);
        USER_SERIAL.print("executor_init status: "); USER_SERIAL.println(status);
        delay(1000);
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);

    }

    USER_SERIAL.println("EXECUTOR_INIT SUCCESS");
    digitalWrite(GREEN_LED_PIN, LOW);
    delay(250);
    digitalWrite(GREEN_LED_PIN, HIGH);

    status = rclc_executor_add_subscription(&uRosStruct->executor, &uRosStruct->subscriber_1, msg, *subscription_callback, ON_NEW_DATA);
    USER_SERIAL.print("ex add sub init status: "); USER_SERIAL.println(status);
    if(status != RCL_RET_OK){return 0;}


    return status;
}
#endif

// #include "../hardware_fns/hardware_fns.h"
// extern Adafruit_MCP4725 dac;

void microROS_Task(void* parameter) {
    pinMode(32, INPUT);
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xFrequency = 10/ portTICK_PERIOD_MS; // 500 ms interval
  //dac.setVoltage(1, false);
    rcl_ret_t status;
    while (true) {
        //USER_SERIAL.println("braketask");
        status = rclc_executor_spin_some(&testSetup.executor, RCL_MS_TO_NS(5));
        vTaskDelayUntil(&xLastWakeTime, xFrequency); // Wait until next cycle

        if(digitalRead(32)){
            USER_SERIAL.println("DRIVER ERROR");
            digitalWrite(2, !digitalRead(2));
        }else{
            digitalWrite(2, LOW);
        }
    }



}



// void microROS_Task_joy(void* parameter) {
//     while (true) {
//         rclc_executor_spin_some(&testSetup.executor, RCL_MS_TO_NS(100));
//         vTaskDelay(100 / portTICK_PERIOD_MS); // Task delay
//     }
// }


