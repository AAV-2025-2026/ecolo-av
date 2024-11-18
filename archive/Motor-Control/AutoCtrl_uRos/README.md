# Autonomous Control Embedded Systems



# Communication Protocol Between Microcontrollers

## Overview
This will be used for the esp32, which will handle microRos communication and higher level processing to communicate with other microcontollers such as an arduino nano or motor controllers etc. 

## The Protocol
Each message starts and ends with '%%'
after the first %% there is an 'opcode' which are outlined below

### opcodes:
-  IMU data return(%%IMU)
    - Used to send IMU data back to the machine that hosts ros.