import sys
import time
import serial
import argparse

VERSION = "1.0.2"
DESCRIPTION = """
    SerialEcho is a command-line tool for sending commands directly to a minicom virtual serial port 
and receiving echoed responses. This tool is useful for debugging and communication needs, supporting
options to specify serial port, baud rate, and command to send.
"""
EXAMPLE = """
    SerialEcho -p Port/DevicePath -c Command with options
    SerialEcho -p Port/DevicePath -b Baudrate -c Command with options
"""

parser = argparse.ArgumentParser(description=DESCRIPTION, usage=EXAMPLE,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('-p', '--port', type=str, required=True, help="Serial port name, e.g., COM3, /dev/ttyUSB0")
parser.add_argument('-c', '--command', type=str, nargs=argparse.REMAINDER,
                    help="Command to send to the device, including options."
                         "To interrupt the execution, enter -c Ctrl+C."
                         " This parameter must be input last!")
parser.add_argument('-b', '--baudrate', type=int, default=9600, help="Baud rate (default: 9600)")
parser.add_argument('--timeout', type=int, default=2, help="Timeout for detecting end of output (in seconds)")
parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {VERSION}')
parser.add_argument('-d', '--debug', type=bool, default=False, help="ARGS.debug mode switch")

ARGS = parser.parse_args()


class SerialLink:
    def __init__(self, port, baudrate, timeout):
        """Initialize the serial connection"""
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baudrate
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 1  # 1-second timeout for reading
        self.timeout = timeout  # Set timeout for detecting end of data
        self.open_connection()

    def open_connection(self):
        """Open the serial port connection"""
        try:
            self.ser.open()
            if self.ser.is_open:
                if ARGS.debug:
                    print(f"Connected to {self.ser.portstr}")
            else:
                sys.exit(f"Failed to open port: {self.ser.portstr}")
        except serial.SerialException as e:
            self.ser.close()
            sys.exit(f"Error opening serial port: {e}")

    def send_cmd(self, cmd):
        """Send a command and start reading the response"""
        try:
            self.ser.write((cmd + "\n").encode())
            time.sleep(0.5)  # Small delay for device to start responding
            self.read_stream()
        except serial.SerialTimeoutException:
            sys.exit("Command timeout, no response from the device.")
        except Exception as e:
            sys.exit(f"Error sending command: {e}")

    def send_ctrl_c(self):
        """Send Ctrl+C to the device"""
        try:
            self.ser.write(b'\x03')  # Send ASCII code 3 (Ctrl+C)
            if ARGS.debug:
                print("Sent Ctrl+C to the device.")
        except Exception as e:
            sys.exit(f"Error sending Ctrl+C: {e}")

    def read_stream(self):
        """Read from the serial port and exit after timeout seconds of inactivity"""
        last_data_time = time.time()  # Track the last time data was received
        try:
            while True:
                if self.ser.in_waiting > 0:
                    output = self.ser.read(self.ser.in_waiting).decode(errors='ignore')
                    print(output, end='')  # Real-time output without newline
                    last_data_time = time.time()  # Update last data time
                elif time.time() - last_data_time > self.timeout:
                    # Exit if no data received within the timeout period
                    break
                time.sleep(0.1)  # Small delay to avoid high CPU usage
        except KeyboardInterrupt:
            self.send_ctrl_c()
            sys.exit("\nManually stop reading the output.")
        except Exception as e:
            sys.exit(f"Error in reading process: {e}")

    def close(self):
        """Close the serial connection"""
        if self.ser.is_open:
            self.ser.close()
            if ARGS.debug:
                print("Serial connection closed.")

    def __del__(self):
        """Ensure serial port is closed when the object is deleted"""
        self.close()


if __name__ == '__main__':
    if ARGS.port:
        ser = SerialLink(ARGS.port, ARGS.baudrate, ARGS.timeout)
        command_str = ''
        if ARGS.command:
            if ARGS.command == ['Ctrl+C']:
                ser.send_ctrl_c()
            else:
                command_str = ' '.join(ARGS.command)
        ser.send_cmd(command_str)
        ser.close()
    else:
        parser.print_help()
        sys.exit(1)
