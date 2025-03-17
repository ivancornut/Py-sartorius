import serial
import re
import matplotlib.pyplot as plt
from datetime import datetime
import pandas as pd
import threading
from nicegui import ui
import math

filesaving = False
x = 0
y = 0
meas_done = False

def start_recording():
    global filesaving
    filesaving = not filesaving
    if filesaving:
        record_button.set_text("Stop datalogging")
    else:
        record_button.set_text("Start datalogging")

def extract_float(data):
    # extracts float from string
    float_numbers = re.findall(r'-?\d+\.\d+', data)
    return [float(num) for num in float_numbers]

class Sartorius:

    def __init__(self,port):
        self.baudrate = 9600
        self.timeout = 1
        self.port = port
        self.first_time_file = True

    def read_serial_port(self):
        global filesaving
        global x
        global y
        global meas_done
        print("Trying to open up serial port")
        try:
            print("Opening up")
            # Open serial port
            with serial.Serial(self.port, self.baudrate, timeout=self.timeout) as ser:
                while True:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        print(line)
                        if filesaving:
                            if self.first_time_file:
                                self.filename = "data_"+datetime.now().strftime("%Y-%m-%d_%H:%M")
                                self.first_time_file = False
                                self.startime = datetime.now().timestamp()
                                with open(self.filename, 'w') as file:
                                    file.write("DateTime,Mass\n")
                                    floats = extract_float(line)
                                    if floats:
                                        file.write(datetime.now().strftime("%Y-%m-%d_%H:%M:%S") +","+ str(floats[0]) + "\n")
                                        now = datetime.now()
                                        x = (now.timestamp() - self.startime)/60
                                        y = floats[0]
                                        meas_done = True
                            else:
                                with open(self.filename, 'a') as file:
                                    floats = extract_float(line)
                                    if floats:
                                        print(line, floats)
                                        file.write(datetime.now().strftime("%Y-%m-%d_%H-%M-%S") +","+ str(floats[0]) + "\n")
                                        now = datetime.now()
                                        x = (now.timestamp() - self.startime)/60
                                        y = floats[0]
                                        meas_done = True
        except Exception as e:
            print(f"Serial port error: {e}")

    def run_read(self):
        serial_thread = threading.Thread(target=self.read_serial_port)
        serial_thread.daemon = True
        serial_thread.start()
        #self.read_serial_port()
        print("Started")


# Bouton pour démarrer/arrêter l'enregistrement
# Configuration de l'interface graphique avec nicegui
ui.label('Reading Sartorius Balance').style('font-size: 24px; font-weight: bold')
record_button = ui.button('Start datalogging', on_click=start_recording)

line_plot = ui.line_plot(n=1, limit=2000, figsize=(6, 6), update_every = 2).with_legend(["Values"])
line_plot.fig.gca().set_ylabel("Mass (g)")
line_plot.fig.gca().set_xlabel("Time since start (min)")
line_plot.fig.set_layout_engine("tight")
line_plot.update()

def update_line_plot() -> None:
    global x
    global y
    global meas_done
    if meas_done:
        print("yes")
        line_plot.push([x], [[y]])
        meas_done = not meas_done
    line_plot.fig.gca().set_ylim(-1.1, 1.1)
    line_plot._convert_to_html()

line_updates = ui.timer(2, update_line_plot, active=False)
line_checkbox = ui.checkbox('active').bind_value(line_updates, 'active')

ui.add_css('''
    :root {
        --nicegui-default-padding: 5rem;
        --nicegui-default-gap: 3rem;
    }
''')
ui.run()

s = Sartorius('/dev/ttyACM0')
s.run_read()

