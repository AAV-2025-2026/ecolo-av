




#define TURN_SIGNAL_INTERVAL 700 //turn signal interval in ms
#define LEFT_TURN_PIN 1
#define RIGHT_TURN_PIN 2




//nRF52840 timer register definitions

#define TIMER0_BASE 0x40008000 
#define TIMER1_BASE 0x40009000 
#define TIMER2_BASE 0x4000A000
#define TIMER3_BASE 0x4001A000 
#define TIMER4_BASE 0x4001B000 


#define TIMER0_START 0x40008000//start timer
#define TIMER1_START 0x40009000//start timer
#define TIMER2_START 0x4000A000//start timer
#define TIMER3_START 0x4001A000//start timer
#define TIMER4_START 0x4001B000//start timer

#define NRF_TIMER_START 0x00000001



#define TIMER0_STOP (0x40008000 + 0x004)//stop timer
#define TIMER1_STOP (0x40009000 + 0x004)//stop timer
#define TIMER2_STOP (0x4000A000 + 0x004)//stop timer
#define TIMER3_STOP (0x4001A000 + 0x004)//stop timer
#define TIMER4_STOP (0x4001B000 + 0x004)//stop timer

#define NRF_TIMER_STOP 0x00000000



#define TIMER0_COUNT (0x40008000 + 0x008)//increment timer (Counter Mode only)
#define TIMER1_COUNT (0x40009000 + 0x008)//increment timer (Counter Mode only)
#define TIMER2_COUNT (0x4000A000 + 0x008)//increment timer (Counter Mode only)
#define TIMER3_COUNT (0x4001A000 + 0x008)//increment timer (Counter Mode only)
#define TIMER4_COUNT (0x4001B000 + 0x008)//increment timer (Counter Mode only)


#define TIMER0_CLEAR (0x40008000 + 0x00C)//clear time
#define TIMER1_CLEAR (0x40009000 + 0x00C)//clear time
#define TIMER2_CLEAR (0x4000A000 + 0x00C)//clear time
#define TIMER3_CLEAR (0x4001A000 + 0x00C)//clear time
#define TIMER4_CLEAR (0x4001B000 + 0x00C)//clear time

#define NRF_CLEAR_TIMER 0x00000001


#define TIMER0_SHUTDOWN (0x40008000 + 0x010)//depricated
#define TIMER1_SHUTDOWN (0x40009000 + 0x010)//depricated
#define TIMER2_SHUTDOWN (0x4000A000 + 0x010)//depricated
#define TIMER3_SHUTDOWN (0x4001A000 + 0x010)//depricated
#define TIMER4_SHUTDOWN (0x4001B000 + 0x010)//depricated




#define TIMER0_CCR0_CAP (0x40008000 + 0x040)//Capture timer value to CC[0] register
#define TIMER1_CCR0_CAP (0x40009000 + 0x040)//Capture timer value to CC[0] register
#define TIMER4_CCR0_CAP (0x4001B000 + 0x040)//Capture timer value to CC[0] register
#define TIMER2_CCR0_CAP (0x4000A000 + 0x040)//Capture timer value to CC[0] register
#define TIMER3_CCR0_CAP (0x4001A000 + 0x040)//Capture timer value to CC[0] register


#define TIMER0_CCR1_CAP (0x40008000 + 0x044)//Capture timer value to CC[1] register
#define TIMER1_CCR1_CAP (0x40009000 + 0x044)//Capture timer value to CC[1] register
#define TIMER4_CCR1_CAP (0x4001B000 + 0x044)//Capture timer value to CC[1] register
#define TIMER2_CCR1_CAP (0x4000A000 + 0x044)//Capture timer value to CC[1] register
#define TIMER3_CCR1_CAP (0x4001A000 + 0x044)//Capture timer value to CC[1] register

#define TIMER0_CCR2_CAP (0x40008000 + 0x048)//Capture timer value to CC[2] register
#define TIMER1_CCR2_CAP (0x40009000 + 0x048)//Capture timer value to CC[2] register
#define TIMER4_CCR2_CAP (0x4001B000 + 0x048)//Capture timer value to CC[2] register
#define TIMER2_CCR2_CAP (0x4000A000 + 0x048)//Capture timer value to CC[2] register
#define TIMER3_CCR2_CAP (0x4001A000 + 0x048)//Capture timer value to CC[2] register

#define TIMER0_CCR3_CAP (0x40008000 + 0x04C)//Capture timer value to CC[3] register
#define TIMER1_CCR3_CAP (0x40009000 + 0x04C)//Capture timer value to CC[3] register
#define TIMER4_CCR3_CAP (0x4001B000 + 0x04C)//Capture timer value to CC[3] register
#define TIMER2_CCR3_CAP (0x4000A000 + 0x04C)//Capture timer value to CC[3] register
#define TIMER3_CCR3_CAP (0x4001A000 + 0x04C)//Capture timer value to CC[3] register


#define TIMER0_CCR4_CAP (0x40008000 + 0x050)//Capture timer value to CC[4] register
#define TIMER1_CCR4_CAP (0x40009000 + 0x050)//Capture timer value to CC[4] register
#define TIMER4_CCR4_CAP (0x4001B000 + 0x050)//Capture timer value to CC[4] register
#define TIMER2_CCR4_CAP (0x4000A000 + 0x050)//Capture timer value to CC[4] register
#define TIMER3_CCR4_CAP (0x4001A000 + 0x050)//Capture timer value to CC[4] register


#define TIMER0_CCR5_CAP (0x40008000 + 0x054)//Capture timer value to CC[5] register
#define TIMER1_CCR5_CAP (0x40009000 + 0x054)//Capture timer value to CC[5] register
#define TIMER4_CCR5_CAP (0x4001B000 + 0x054)//Capture timer value to CC[5] register
#define TIMER2_CCR5_CAP (0x4000A000 + 0x054)//Capture timer value to CC[5] register
#define TIMER3_CCR5_CAP (0x4001A000 + 0x054)//Capture timer value to CC[5] register






#define TIMER0_CCR0_CMP (0x40008000 + 0x140)//Compare event on CC[0] match
#define TIMER1_CCR0_CMP (0x40009000 + 0x140)//Compare event on CC[0] match
#define TIMER4_CCR0_CMP (0x4001B000 + 0x140)//Compare event on CC[0] match
#define TIMER2_CCR0_CMP (0x4000A000 + 0x140)//Compare event on CC[0] match
#define TIMER3_CCR0_CMP (0x4001A000 + 0x140)//Compare event on CC[0] match


#define TIMER0_CCR1_CMP (0x40008000 + 0x144)//Compare event on CC[1] match
#define TIMER1_CCR1_CMP (0x40009000 + 0x144)//Compare event on CC[1] match
#define TIMER4_CCR1_CMP (0x4001B000 + 0x144)//Compare event on CC[1] match
#define TIMER2_CCR1_CMP (0x4000A000 + 0x144)//Compare event on CC[1] match
#define TIMER3_CCR1_CMP (0x4001A000 + 0x144)//Compare event on CC[1] match

#define TIMER0_CCR2_CMP (0x40008000 + 0x148)//Compare event on CC[2] match
#define TIMER1_CCR2_CMP (0x40009000 + 0x148)//Compare event on CC[2] match
#define TIMER4_CCR2_CMP (0x4001B000 + 0x148)//Compare event on CC[2] match
#define TIMER2_CCR2_CMP (0x4000A000 + 0x148)//Compare event on CC[2] match
#define TIMER3_CCR2_CMP (0x4001A000 + 0x148)//Compare event on CC[2] match

#define TIMER0_CCR3_CMP (0x40008000 + 0x14C)//Compare event on CC[3] match
#define TIMER1_CCR3_CMP (0x40009000 + 0x14C)//Compare event on CC[3] match
#define TIMER4_CCR3_CMP (0x4001B000 + 0x14C)//Compare event on CC[3] match
#define TIMER2_CCR3_CMP (0x4000A000 + 0x14C)//Compare event on CC[3] match
#define TIMER3_CCR3_CMP (0x4001A000 + 0x14C)//Compare event on CC[3] match


#define TIMER0_CCR4_CMP (0x40008000 + 0x150)//Compare event on CC[4] match
#define TIMER1_CCR4_CMP (0x40009000 + 0x150)//Compare event on CC[4] match
#define TIMER4_CCR4_CMP (0x4001B000 + 0x150)//Compare event on CC[4] match
#define TIMER2_CCR4_CMP (0x4000A000 + 0x150)//Compare event on CC[4] match
#define TIMER3_CCR4_CMP (0x4001A000 + 0x150)//Compare event on CC[4] match


#define TIMER0_CCR5_CMP (0x40008000 + 0x154)//Compare event on CC[5] match
#define TIMER1_CCR5_CMP (0x40009000 + 0x154)//Compare event on CC[5] match
#define TIMER4_CCR5_CMP (0x4001B000 + 0x154)//Compare event on CC[5] match
#define TIMER2_CCR5_CMP (0x4000A000 + 0x154)//Compare event on CC[5] match
#define TIMER3_CCR5_CMP (0x4001A000 + 0x154)//Compare event on CC[5] match



#define TIMER0_SHORTS (0x40008000 + 0x200)//Shortcut between local event and task
#define TIMER1_SHORTS (0x40009000 + 0x200)//Shortcut between local event and task
#define TIMER4_SHORTS (0x4001B000 + 0x200)//Shortcut between local event and task
#define TIMER2_SHORTS (0x4000A000 + 0x200)//Shortcut between local event and task
#define TIMER3_SHORTS (0x4001A000 + 0x200)//Shortcut between local event and task

#define TIMER0_INTENSET (0x40008000 + 0x304)//Enable interrupt
#define TIMER1_INTENSET (0x40009000 + 0x304)//Enable interrupt
#define TIMER4_INTENSET (0x4001B000 + 0x304)//Enable interrupt
#define TIMER2_INTENSET (0x4000A000 + 0x304)//Enable interrupt
#define TIMER3_INTENSET (0x4001A000 + 0x304)//Enable interrupt

#define NRF_CCRINT5_SET = 0x80000
#define NRF_CCRINT4_SET = 0x40000
#define NRF_CCRINT3_SET = 0x20000
#define NRF_CCRINT2_SET = 0x10000
#define NRF_CCRINT1_SET = 0x8000
#define NRF_CCRINT0_SET = 0x4000


#define TIMER0_INTENCLR (0x40008000 + 0x308)//Clear interrupt
#define TIMER1_INTENCLR (0x40009000 + 0x308)//Clear interrupt
#define TIMER4_INTENCLR (0x4001B000 + 0x308)//Clear interrupt
#define TIMER2_INTENCLR (0x4000A000 + 0x308)//Clear interrupt
#define TIMER3_INTENCLR (0x4001A000 + 0x308)//Clear interrupt

#define NRF_CCRINT5_CLR = 0x80000
#define NRF_CCRINT4_CLR = 0x40000
#define NRF_CCRINT3_CLR = 0x20000
#define NRF_CCRINT2_CLR = 0x10000
#define NRF_CCRINT1_CLR = 0x8000
#define NRF_CCRINT0_CLR = 0x4000

#define TIMER0_MODE (0x40008000 + 0x504)//TIMER MODE SELECTION
#define TIMER1_MODE (0x40009000 + 0x504)//TIMER MODE SELECTION
#define TIMER4_MODE (0x4001B000 + 0x504)//TIMER MODE SELECTION
#define TIMER2_MODE (0x4000A000 + 0x504)//TIMER MODE SELECTION
#define TIMER3_MODE (0x4001A000 + 0x504)//TIMER MODE SELECTION

#define NRF_TIMER_MODE 0x0
#define NRF_COUNTER_MODE 0x1
#define NRF_LP_COUNTER_MODE 0x2


#define TIMER0_BITMODE (0x40008000 + 0x508)//number of bits for timer to use
#define TIMER1_BITMODE (0x40009000 + 0x508)//number of bits for timer to use
#define TIMER4_BITMODE (0x4001B000 + 0x508)//number of bits for timer to use
#define TIMER2_BITMODE (0x4000A000 + 0x508)//number of bits for timer to use
#define TIMER3_BITMODE (0x4001A000 + 0x508)//number of bits for timer to use

#define NRF_TIMER_BITMODE_16 0x0
#define NRF_TIMER_BITMODE_8 0x1
#define NRF_TIMER_BITMODE_24 0x2
#define NRF_TIMER_BITMODE_32 0x3


#define TIMER0_PRESCALER (0x40008000 + 0x510)//timer prescaler
#define TIMER1_PRESCALER (0x40009000 + 0x510)//timer prescaler
#define TIMER4_PRESCALER (0x4001B000 + 0x510)//timer prescaler
#define TIMER2_PRESCALER (0x4000A000 + 0x510)//timer prescaler
#define TIMER3_PRESCALER (0x4001A000 + 0x510)//timer prescaler



#define TIMER0_CCR0 (0x40008000 + 0x540)//CCR register 
#define TIMER1_CCR0 (0x40009000 + 0x540)//CCR register 
#define TIMER4_CCR0 (0x4001B000 + 0x540)//CCR register 
#define TIMER2_CCR0 (0x4000A000 + 0x540)//CCR register 
#define TIMER3_CCR0 (0x4001A000 + 0x540)//CCR register 

#define TIMER0_CCR1 (0x40008000 + 0x544)//CCR register 
#define TIMER1_CCR1 (0x40009000 + 0x544)//CCR register 
#define TIMER4_CCR1 (0x4001B000 + 0x544)//CCR register 
#define TIMER2_CCR1 (0x4000A000 + 0x544)//CCR register 
#define TIMER3_CCR1 (0x4001A000 + 0x544)//CCR register 

#define TIMER0_CCR2 (0x40008000 + 0x548)//CCR register 
#define TIMER1_CCR2 (0x40009000 + 0x548)//CCR register 
#define TIMER4_CCR2 (0x4001B000 + 0x548)//CCR register 
#define TIMER2_CCR2 (0x4000A000 + 0x548)//CCR register 
#define TIMER3_CCR2 (0x4001A000 + 0x548)//CCR register 

#define TIMER0_CCR3 (0x40008000 + 0x54C)//CCR register 
#define TIMER1_CCR3 (0x40009000 + 0x54C)//CCR register 
#define TIMER4_CCR3 (0x4001B000 + 0x54C)//CCR register 
#define TIMER2_CCR3 (0x4000A000 + 0x54C)//CCR register 
#define TIMER3_CCR3 (0x4001A000 + 0x54C)//CCR register 

#define TIMER0_CCR4 (0x40008000 + 0x550)//CCR register 
#define TIMER1_CCR4 (0x40009000 + 0x550)//CCR register 
#define TIMER4_CCR4 (0x4001B000 + 0x550)//CCR register 
#define TIMER2_CCR4 (0x4000A000 + 0x550)//CCR register 
#define TIMER3_CCR4 (0x4001A000 + 0x550)//CCR register 

#define TIMER0_CCR5 (0x40008000 + 0x554)//CCR register 
#define TIMER1_CCR5 (0x40009000 + 0x554)//CCR register 
#define TIMER4_CCR5 (0x4001B000 + 0x554)//CCR register 
#define TIMER2_CCR5 (0x4000A000 + 0x554)//CCR register 
#define TIMER3_CCR5 (0x4001A000 + 0x554)//CCR register







