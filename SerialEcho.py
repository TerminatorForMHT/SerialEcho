import sys
import time
import serial
import argparse
import re

VERSION = "2.0.0"
DESCRIPTION = """
    SerialEcho 是一个命令行工具，用于：
    向物理/虚拟串口直接发送命令，并接收回显响应。
    支持对低速串口设备进行逐字符发送。
"""
EXAMPLE = """
    SerialEcho send -p Port/DevicePath -c Command with options
    SerialEcho send_ls -p Port/DevicePath -c Command with options
"""

parser = argparse.ArgumentParser(description=DESCRIPTION, usage=EXAMPLE,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
subparsers = parser.add_subparsers(dest="subcommand")

# 串口命令 (正常发送)
send_parser = subparsers.add_parser("send", help="发送串口命令")
send_parser.add_argument("-p", "--port", type=str, required=True, help="Serial port (e.g., COM3, /dev/ttyUSB0)")
send_parser.add_argument("-c", "--command", type=str, nargs=argparse.REMAINDER, required=True,
                         help="Command to send to the device")
send_parser.add_argument("-b", "--baudrate", type=int, default=9600, help="Baud rate (default: 9600)")
send_parser.add_argument("--timeout", type=int, default=2, help="超时（秒），用于检测无新数据时退出")
send_parser.add_argument("-d", "--debug", action="store_true", help="启用调试输出")

# 串口命令 (逐字符发送，适合极慢串口/1字节缓冲)
send_ls_parser = subparsers.add_parser("send_ls", help="逐字符发送串口命令,适用于低速小缓存区串口")
send_ls_parser.add_argument("-p", "--port", type=str, required=True, help="Serial port (e.g., COM3, /dev/ttyUSB0)")
send_ls_parser.add_argument("-c", "--command", type=str, nargs=argparse.REMAINDER, required=True,
                            help="Command to send to the device")
send_ls_parser.add_argument("-b", "--baudrate", type=int, default=115200, help="Baud rate (default: 115200)")
send_ls_parser.add_argument("--timeout", type=int, default=2, help="超时（秒），用于检测无新数据时退出")
send_ls_parser.add_argument("-d", "--debug", action="store_true", help="启用调试输出")

ARGS = parser.parse_args()


def remove_ansi_escape_sequences(text):
    """
    移除 ANSI 转义序列
    """
    ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


def print_serial_log(data):
    """
    格式化打印串口日志
    """
    if isinstance(data, list):
        for i in data:
            print(remove_ansi_escape_sequences(i).replace("\r\n", "\n"))
    else:
        print("============= serial log ============")
        data = data.split("\r\n")[1:-1]
        data = "\n".join([i for i in data if i != ""])
        print(remove_ansi_escape_sequences(data).replace("\r\n", "\n"))


# ============== 串口类 ==============
class SerialLink:
    def __init__(self, port, baudrate, timeout, debug=False):
        """Initialize the serial connection"""
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baudrate
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 1
        self.timeout = timeout
        self.debug = debug
        self.open_connection()

    def open_connection(self):
        try:
            self.ser.open()
            if self.ser.is_open and self.debug:
                print(f"Connected to {self.ser.portstr}")
        except serial.SerialException as e:
            sys.exit(f"Error opening serial port: {e}")

    def send_cmd(self, cmd):
        try:
            self.ser.write((cmd + "\r\n").encode("utf-8"))
            time.sleep(0.5)
            return self.read_stream()
        except Exception as e:
            sys.exit(f"Error sending command: {e}")

    def send_cmd_char_by_char(self, cmd):
        """逐字符发送命令"""
        try:
            if self.debug:
                print("Waking up shell...")
            self.ser.write(b"\r\n")
            time.sleep(1)

            if self.ser.in_waiting > 0:
                self.ser.read(self.ser.in_waiting)

            txcmd = cmd + "\r\n"
            if self.debug:
                print(f"Sending cmd char by char: {cmd}")

            for char in txcmd:
                self.ser.write(char.encode("utf-8"))
                time.sleep(0.15)
            return self.read_stream()
        except Exception as e:
            sys.exit(f"Error in char-by-char sending: {e}")

    def read_stream(self):
        """Read from the serial port and exit after timeout seconds of inactivity"""
        rbuf = bytes()
        last_data_time = time.time()
        try:
            while True:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    rbuf += chunk
                    last_data_time = time.time()
                elif time.time() - last_data_time > self.timeout:
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.send_ctrl_c()
            sys.exit("\nStopped manually.")
        log_msg = rbuf.strip().decode("utf-8", "ignore")
        print_serial_log(log_msg)
        return rbuf

    def send_ctrl_c(self):
        """Send Ctrl+C"""
        try:
            self.ser.write(b"\x03")
            if self.debug:
                print("Sent Ctrl+C")
        except Exception as e:
            sys.exit(f"Error sending Ctrl+C: {e}")

    def close(self):
        if self.ser.is_open:
            self.ser.close()
            if self.debug:
                print("Serial connection closed.")

    def __del__(self):
        self.close()


# ============== 主入口 ==============
if __name__ == "__main__":
    if ARGS.subcommand == "send":
        ser = SerialLink(ARGS.port, ARGS.baudrate, ARGS.timeout, ARGS.debug)
        cmd_str = " ".join(ARGS.command)
        ser.send_cmd(cmd_str)
        ser.close()
    elif ARGS.subcommand == "send906":
        ser = SerialLink(ARGS.port, ARGS.baudrate, ARGS.timeout, ARGS.debug)
        if ARGS.command == ['Ctrl+C']:
            ser.send_ctrl_c()
        else:
            cmd_str = " ".join(ARGS.command)
            ser.send_cmd_char_by_char(cmd_str)
            ser.close()
    else:
        parser.print_help()
        sys.exit(1)
