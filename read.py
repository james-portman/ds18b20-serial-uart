import glob
import sys
import time
import serial

usb_ttys = glob.glob("/dev/ttyUSB*")
port = usb_ttys[0]

ser = serial.Serial()
ser.port = port
ser.baudrate = 115200
ser.bytesize = 8
ser.parity = 'N'
ser.stopbits = 1
ser.timeout = 0.1 # read timeout

# ROM commands - where to send data
SEARCH_ROM = 0xf0 # get rom code from all devices, may need running multiple times
READ_ROM = 0x33 # reads the 64-bit rom code if a single device is connected
MATCH_ROM = 0x55 # use this then a 64-bit rom code to specify a single device
SKIP_ROM_BROADCAST = 0xcc # "skip rom" send to all devices
ALARM_SEARCH = 0xec # only devices with an alarm flag set will reply

# function commands
TEMPERATURE_READ = 0x44
READ_SCRATCHPAD = 0xbe
WRITE_SCRATCHPAD = 0x4e # follow with 3 bytes to write, first to Th register, second to Tl register, third goes to config register
COPY_SCRATCHPAD = 0x48 # copies scratchpad Th, Tl and config to EEPROM (will be loaded at boot time in future)
RECALL_EEPROM = 0xb8 # loads Th, Tl, config registers from EEPROM
READ_POWER_SUPPLY = 0xb4 # parasite devices will reply 0, properly powered will reply 1

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
    send_command(SKIP_ROM_BROADCAST, TEMPERATURE_READ)
    # print("running a temperature conversion (reading)")
    while True:
        if send_byte(0xFF) > 0:
            break
        time.sleep(0.5)

def get_scratchpad():
    output = {}
    send_command(SKIP_ROM_BROADCAST, READ_SCRATCHPAD)
    output["temperature_lsb"] = send_byte(0xFF)
    output["temperature_msb"] = send_byte(0xFF)
    output["th_register"] = send_byte(0xFF)
    output["tl_register"] = send_byte(0xFF)
    output["configuration"] = send_byte(0xFF)
    output["reserved_ff"] = send_byte(0xFF)
    output["reserved_xx"] = send_byte(0xFF)
    output["reserved_10"] = send_byte(0xFF)
    output["crc"] = send_byte(0xFF)
    return output

def get_temperature():
    do_a_temperature_read()
    send_command(SKIP_ROM_BROADCAST, READ_SCRATCHPAD)
    temperature = send_byte(0xFF) # temperature lsb
    temperature += send_byte(0xFF) << 8 # temperature msb
    # you can apparently stop short reading and do a reset to ignore the rest of the scratch pad
    # (next command will do a reset so just stop)
    temperature *= 0.0625
    return temperature


def get_single_rom_code():
    print("ROM code:")
    reset()
    send_byte(READ_ROM)
    for _ in range(8):
        print(hex(send_byte(0xff)), end=" ")
    print()


def get_power_supply():
    send_command(SKIP_ROM_BROADCAST, READ_POWER_SUPPLY)
    if send_byte(0xff) == 0xff:
        print("All devices connected to proper power")
    else:
        print("Some devices connected as parasitic")


get_power_supply()

get_single_rom_code()

while True:
    print(get_temperature())
    # time.sleep(60)
