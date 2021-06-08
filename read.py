import glob
import serial
import sys
import time
import traceback
import json

usb_ttys = glob.glob("/dev/ttyUSB*")
port = usb_ttys[0]

ser = serial.Serial()
ser.port = port
ser.baudrate = 115200
ser.bytesize = 8
ser.parity = 'N'
ser.stopbits = 1
ser.timeout = 0.1 # read timeout


ROM_BROADCAST = 0xcc # "skip rom" send to all devices

COMMAND_TEMPERATURE_READ = 0x44
COMMAND_READ_SCRATCHPAD = 0xbe

ser.open()
if not ser.is_open:
    print("Failed to open serial port")
    sys.exit(1)
print(ser)

def reset():
    ser.baudrate = 9600
    ser.write(b'\xF0')
    output = ser.read()
    if output == b'\xF0':
        raise Exception("No devices found")
    elif output == b'\x00':
        raise Exception("Shorted?")
    elif output == b'\xe0':
        # print("Single device")
        pass
    else:
        # print("Multiple devices?")
        pass
    ser.baudrate = 115200

def send_command(target, command):
    reset()
    send_byte(target)
    return send_byte(command)

def send_byte(data):
    """
    (send 0xFF to do a read)
    """
    output = 0
    for i in range(8):
        bit = (data >> i) & 1
        if bit == 1:
            ser.write(b'\xff')
        else:
            ser.write(b'\x00')
        outbit = ser.read()
        if outbit == b'\xFF':
            output += (1 << i)
        # read values should be either FF for 1 or 00-FE for a 0
    # print(hex(output))
    return output

def do_a_temperature_read():
    """
    Runs a temperature read, doesn't actually return or display anything
    """
    send_command(ROM_BROADCAST, COMMAND_TEMPERATURE_READ)
    print("running a temperature conversion (reading)")
    while True:
        if send_byte(0xFF) > 0:
            break
        time.sleep(0.5)

def get_scratchpad():
    output = {}
    send_command(ROM_BROADCAST, COMMAND_READ_SCRATCHPAD)
    output["temperature_lsb"] = send_byte(0xFF)
    output["temperature_msb"] = send_byte(0xFF)
    output["th_register"] = send_byte(0xFF)
    output["tl_register"] = send_byte(0xFF)
    output["configuration"] = send_byte(0xFF)
    output["reserved_ff"] = send_byte(0xFF)
    output["reserved_xx"] = send_byte(0xFF)
    output["reserved_10"] = send_byte(0xFF)
    output["crc"] = send_byte(0xFF)
    send_byte(0xFF) # needed? doc is vague about 9 or 10 scratch pad data points
    output["temperature"] = ((output["temperature_msb"] << 8) + output["temperature_lsb"]) * 0.0625
    return output


# temperature reading loop
while True:
    do_a_temperature_read()
    print(get_scratchpad()["temperature"])
    # time.sleep(60)
