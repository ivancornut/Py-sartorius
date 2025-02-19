import serial
from datetime import datetime
import re

def extract_float(data):
    # extracts float from string
    float_numbers = re.findall(r'-?\d+\.\d+', data)
    return [float(num) for num in float_numbers]

def read_serial_port(port, baudrate=9600, timeout=1):
    # read serial port data
    # 9600 is the default on sartorius scale
    try:
        # Open serial port
        with serial.Serial(port, baudrate, timeout=timeout) as ser:
            print(f"Reading serial port {port} at {baudrate} bauds...")

            # create a file name with date and time
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"serial_data_{timestamp}.csv"

            with open(filename, 'w') as file:
                file.write("DateTime,Mass\n")
                while True:
                    # Lire une ligne du port série
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        print(f"Received data: {line}")
                        floats = extract_float(line)
                        if floats:
                            file.write(datetime.now().strftime("%Y-%m-%d_%H-%M-%S") +","+ str(floats[0]) + "\n")
                            print(f"Mass value: {floats}")
    except serial.SerialException as e:
        print(f"Serial port error: {e}")

read_serial_port('/dev/ttyACM0')  # this works for ubuntu might be different for your system