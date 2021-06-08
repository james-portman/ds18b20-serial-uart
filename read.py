import glob
import serial
import sys
import time
# import os
import traceback
import json

"""
https://www.maximintegrated.com/en/design/technical-documents/tutorials/2/214.html
"""

usb_ttys = glob.glob("/dev/ttyUSB*")
port = usb_ttys[0]

ser = serial.Serial()
ser.port = port
ser.baudrate = 115200
ser.bytesize = 8
ser.parity = 'N'
ser.stopbits = 1
ser.timeout = 0.1 # read timeout

# define OW_MATCH_ROM    0x55
#define OW_SKIP_ROM     0xcc
#define OW_SEARCH_ROM   0xf0

ser.open()
if not ser.is_open:
    print("Failed to open serial port")
    sys.exit(1)
print(ser)

def reset():
    """
    reply would be F0 if no device present (normal echo)
    or altered if a device is there

    A single slave device running at a minimum internal timing may respond with E0h, while one with maximum internal timing may return a value of 90h

    coming back as e0 in my testing

    00 might be a short
    f0 means no device
    """
    ser.baudrate = 9600
    ser.write(b'\xF0')
    print(ser.read())
    ser.baudrate = 115200


def send_byte(data):
    """
    send 0xFF to do a read
    """
    # print("sending byte "+hex(data))
    output = 0
    for i in range(8):
        bit = (data >> i) & 1
        # print("sending a bit")
        if bit == 1:
            ser.write(b'\xff')
        else:
            ser.write(b'\x00')
        outbit = ser.read()
        # print(outbit)
        if outbit == b'\xFF':
            output += (1 << i)
        # read_all()
        # TODO: save the reads as bits
        # time.sleep(0.001)
        # read values should be either FF for 1 or 00-FE for a 0
    print(hex(output))
    return output


def read_all():
    count = 0
    while True:
        data = ser.read()
        if data == b'':
            break
        print(data)
        count += 1
    print(count)



"""
Leftover Capture Data: ff00ff00ff00ff00  00 00 00 ff 00 ff 00 00
Leftover Capture Data: 0000000000ff00ff00ffffff0000ffff
Leftover Capture Data: ffff00ff00ffffff00000000ff000000
Leftover Capture Data: 0000000000ff0000ff00000000000000
Leftover Capture Data: 00ff00ff0000ffff
Leftover Capture Data: 000000ffffff00ff



Leftover Capture Data: ff00ff00ff00ff00000000ff00ff0000
"""

def do_a_temperature_read():
    reset()
    send_byte(0xCC)
    send_byte(0x44) # do a temperature read
    print("waiting for the read to finish")
    while True:
        if send_byte(0xFF) > 0:
            break
        time.sleep(0.5)

def get_scratchpad():
    reset()
    send_byte(0xCC)
    send_byte(0xbe) # read scratchpad (10 bytes?)
    temperature_lsb = send_byte(0xFF)
    temperature_msb = send_byte(0xFF)
    th_register = send_byte(0xFF)
    tl_register = send_byte(0xFF)
    configuration = send_byte(0xFF)
    reserved_ff = send_byte(0xFF)
    reserved_xx = send_byte(0xFF)
    reserved_10 = send_byte(0xFF)
    crc = send_byte(0xFF)
    send_byte(0xFF) # needed?
    temperature = (temperature_msb << 8) + temperature_lsb
    temperature = temperature * 0.0625
    print("temperature:", temperature)
    with open("temperature_log", "a") as output_file:
        output_file.write(f"{time.ctime()},{temperature}\n")

while True:
    do_a_temperature_read()
    get_scratchpad()
    time.sleep(60)
# getting number of replies for the byte value sent???
# e.g. FF - get 255 replies
# 0x10 - get 16 replies
