#!/usr/bin/env python
import glob
import sys
import time
import serial


class Ds18b20():

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


    def __init__(self, port=None):
        self.ser = None
        if port is not None:
            self.port = port
        else:
            self.port = None
        self.connect()

    def connect(self):
        if self.port is None:
            usb_ttys = glob.glob("/dev/ttyUSB*")
            self.port = usb_ttys[0]

        self.ser = serial.Serial()
        self.ser.port = self.port
        self.ser.baudrate = 115200
        self.ser.bytesize = 8
        self.ser.parity = 'N'
        self.ser.stopbits = 1
        self.ser.timeout = 0.1 # read timeout

        self.ser.open()
        if not self.ser.is_open:
            print("Failed to open serial port")
            sys.exit(1)
        # print(self.ser)

    def close(self):
        self.ser.close()

    def reset(self):
        """
        Required before every command
        """
        self.ser.baudrate = 9600
        self.ser.write(b'\xF0')
        output = self.ser.read()
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
        self.ser.baudrate = 115200

    def send_byte(self, data):
        """
        (send 0xFF to do a read)
        """
        output = 0
        for i in range(8):
            bit = (data >> i) & 1
            if bit == 1:
                self.ser.write(b'\xff')
            else:
                self.ser.write(b'\x00')
            outbit = self.ser.read()
            if outbit == b'\xFF':
                output += (1 << i)
            # read values should be either FF for 1 or 00-FE for a 0
        # print(hex(output))
        return output

    def send_command(self, target, command):
        self.reset()
        self.send_byte(target)
        return self.send_byte(command)

    def do_a_temperature_read(self):
        """
        Runs a temperature read, doesn't actually return or display anything
        """
        self.send_command(Ds18b20.SKIP_ROM_BROADCAST, Ds18b20.TEMPERATURE_READ)
        # print("running a temperature conversion (reading)")
        while True:
            if self.send_byte(0xFF) > 0:
                break
            time.sleep(0.5)

    def get_scratchpad(self):
        output = {}
        self.send_command(Ds18b20.SKIP_ROM_BROADCAST, Ds18b20.READ_SCRATCHPAD)
        scratchpad = []
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))
        scratchpad.append(self.send_byte(0xFF))

        output["temperature_lsb"] = scratchpad[0]
        output["temperature_msb"] = scratchpad[1]
        output["th_register"] = scratchpad[2]
        output["tl_register"] = scratchpad[3]
        output["configuration"] = scratchpad[4]
        output["reserved_ff"] = scratchpad[5]
        output["reserved_xx"] = scratchpad[6]
        output["reserved_10"] = scratchpad[7]
        output["crc"] = scratchpad[8]

        # get resolution - 9-12 bits
        r0 = (output["configuration"] >> 5) & 1
        r1 = (output["configuration"] >> 6) & 1
        r = r0 + (r1 << 1)
        output["resolution"] = 9 + r

        return output

    def write_scratchpad(self, th, tl, config):
        self.send_command(Ds18b20.SKIP_ROM_BROADCAST, Ds18b20.WRITE_SCRATCHPAD)
        self.send_byte(th)
        self.send_byte(tl)
        self.send_byte(config)

    def get_temperature(self):
        self.do_a_temperature_read()
        self.send_command(Ds18b20.SKIP_ROM_BROADCAST, Ds18b20.READ_SCRATCHPAD)
        temperature = self.send_byte(0xFF) # temperature lsb
        temperature += self.send_byte(0xFF) << 8 # temperature msb
        # you can apparently stop short reading and do a reset to ignore the rest of the scratch pad
        # (next command will do a reset so just stop)
        # TODO: deal with negative/signed numbers
        # TODO: OR the data down to the number of accuracy bits being used
        temperature *= 0.0625
        # print(time.time(), end=",")
        # print(temperature)
        return temperature

    def get_single_rom_code(self):
        rom_code = []
        rom_code_bytes = b''
        self.reset()
        self.send_byte(Ds18b20.READ_ROM)
        for _ in range(8):
            abyte = self.send_byte(0xff)
            # print(hex(abyte))
            rom_code_bytes = bytes([abyte]) + rom_code_bytes
            rom_code = [abyte] + rom_code

        crc = rom_code[0]
        serial = rom_code[1:7]
        serial_bytes = rom_code_bytes[1:7]
        family_code = rom_code[7]

        # print("Serial number:", end=" ")
        # for abyte in serial:
        #     print(hex(abyte), end=" ")
        # print()

        # print("Family code:", end=" ")
        # if family_code == 0x10:
        #     print("DS18S20")
        # elif family_code == 0x28:
        #     print("DS18B20")
        # else:
        #     print("Unknown")
        return serial_bytes

    def get_power_supply(self):
        self.send_command(Ds18b20.SKIP_ROM_BROADCAST, Ds18b20.READ_POWER_SUPPLY)
        if self.send_byte(0xff) == 0xff:
            print("All devices connected to proper power")
        else:
            print("Some devices connected as parasitic")

    def set_accuracy(self, accuracy):
        """
        9-12 allowed, 12 default
        """
        if accuracy < 9 or accuracy > 12:
            raise Exception("Only an accuracy of 9-12 bits is allowed")
        scratchpad = ds.get_scratchpad() # get the current scratchpad data so we can pass tl and th the same as currently set
        set_accuracy = accuracy - 9
        set_accuracy = set_accuracy << 5
        # OR to clear the accuracy bits then AND the new setting back in
        new_config = (scratchpad["configuration"] & 0b10011111) | set_accuracy
        ds.write_scratchpad(th=scratchpad["th_register"], tl=scratchpad["tl_register"], config=new_config)


def main():
    devices = {
        b'\x01\x20\x10\xd9\x17\x38': "downstairs",
        b'\x01\x20\x10\xeb\xce\xa0': "office"
    }
    # ds.set_accuracy(12)

    print('timestamp,device,temperature')
    while True:
        usb_ttys = glob.glob("/dev/ttyUSB*")
        for port in usb_ttys:
            ds = Ds18b20(port)
            # ds.connect()
            # print(time.ctime())
            # ds.get_power_supply()
            serial_num = ds.get_single_rom_code()
            if serial_num in devices:
                device = devices[serial_num]
            else:
                device = serial_num.hex()
            # print(ds.get_scratchpad())
            temperature = ds.get_temperature()
            ds.close()
            print(f'{time.time()},{device},{temperature}')
        time.sleep(60)

if __name__ == "__main__":
    main()
