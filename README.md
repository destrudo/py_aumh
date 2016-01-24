# py_aumh
Python libraries for talking to  `Arduino_UART_MessageHandler` flashed devices.  This was originally bundled with Arduino_UART_MessageHandler, but it's just not reasonable to bundle it at this point.

# Current State
I don't consider it production worthy, but it works.  It needs more testing.

### Firmware
Firmware _is_ required for the end devices that this talks to.  You can get it at https://github.com/destrudo/Arduino_UART_MessageHandler

### Software Notes
1. UARTMessageHandler
  - Possible Changes:
    * Too many to count, mostly cleanup and proper status handling.  Right now I check *everything* or cast *everything* when I don't really need to.
  - State:
    * Relatively stable for UART_MH, UART_Digital and UART_Neopixel.  Everything else is empty.

2. MQTTHandler
  - Possible Changes:
    * Add *some* sort of abstraction so that I don't need to 'if' over a bunch of different types in the future
  - Going to Change:
    * Better thread cleanup
  - State:
    * Extremely dirty but it does work.