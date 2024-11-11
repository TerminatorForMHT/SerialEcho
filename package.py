import os
import sys

env_path = os.path.dirname(sys.executable)
command = f'{env_path}/pyinstaller SerialEcho.spec'.replace('/', os.sep)
os.system(command)