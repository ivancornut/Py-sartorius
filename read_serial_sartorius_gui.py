import time
import threading
import os
import re
import pandas as pd
import serial
import serial.tools.list_ports
from nicegui import ui, app
from datetime import datetime

# Configuration parameters
MAX_POINTS = 100  # Maximum number of points to display on the graph
SAMPLING_RATE = 0.1  # Time between samples in seconds
SAVE_INTERVAL = 10  # Save to CSV after this many new values

class SerialMonitor:
    def __init__(self):
        self.serial_port = None
        self.is_running = False
        self.thread = None
        self.data = pd.DataFrame(columns=['timestamp', 'elapsed_time', 'value'])
        self.start_time = None
        self.available_ports = []
        self.values_since_save = 0
        self.csv_filename = None
        self.csv_directory = "data"
        self.meas_done = False
        self.is_connected = False
        
        # Create directory for CSV files if it doesn't exist
        if not os.path.exists(self.csv_directory):
            os.makedirs(self.csv_directory)
            
        self.refresh_ports()
        
    def refresh_ports(self):
        """Refresh the list of available serial ports"""
        self.available_ports = [port.device for port in serial.tools.list_ports.comports()]
        return self.available_ports
    
    def connect(self, port, baud_rate=9600):
        """Connect to the specified serial port"""
        try:
            self.serial_port = serial.Serial(port, baud_rate, timeout=1)
            # Use ui.notify in a thread-safe way
            ui.timer(0.1, lambda: ui.notify(f"Connected to {port}", color="positive"), once=True)
            self.is_connected = True
            return True
        except Exception as e:
            # Use ui.notify in a thread-safe way
            error_msg = str(e)
            ui.timer(0.1, lambda: ui.notify(f"Error connecting to port: {error_msg}", color="negative"), once=True)
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the serial port"""
        if self.serial_port and self.serial_port.is_open:
            self.stop_reading()
            self.serial_port.close()
            self.serial_port = None
            self.is_connected = False
            return True
        return False
    
    def save_to_csv(self):
        """Save the current dataframe to a CSV file"""
        if self.data.empty:
            print("no saving")
            return
            
        # CSV filename is created at start_reading, so it should always exist
        if self.csv_filename is None:
            # Fallback just in case
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.csv_filename = os.path.join(self.csv_directory, f"sartorius_data_{timestamp}.csv")
            
        # Save the dataframe to CSV
        self.data.to_csv(self.csv_filename, index=False)
        print("saving")
        
    def start_reading(self):
        """Start reading from the serial port in a separate thread"""
        if not self.serial_port or not self.serial_port.is_open:
            ui.notify("Serial port not connected", color="negative")
            return False
        
        if self.is_running:
            return True
        
        self.is_running = True
        self.start_time = time.time()
        
        # Create CSV filename with start datetime
        start_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_filename = os.path.join(self.csv_directory, f"sartorius_data_{start_datetime}.csv")
        
        # Reset the dataframe and counter
        self.data = pd.DataFrame(columns=['timestamp', 'elapsed_time', 'value'])
        self.values_since_save = 0
        
        # Update UI to show we're starting
        ui.timer(0.1, lambda: ui.notify("Monitoring started", color="positive"), once=True)
        
        self.thread = threading.Thread(target=self.read_serial_data)
        self.thread.daemon = True
        self.thread.start()
        return True
    
    def stop_reading(self):
        """Stop reading from the serial port"""
        if not self.is_running:
            return False
            
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
            
        # Save any remaining data
        if self.values_since_save > 0:
            self.save_to_csv()
            self.values_since_save = 0
        
        self.csv_filename = None
        return True
    
    def read_serial_data(self):
        """Read data from the serial port and
         extract float values"""
        while self.is_running:
            try:
                if self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8').strip()
                    self.meas_done = True
                    try:
                        # Print the raw line for debugging
                        print(f"Raw serial data: '{line}'")
                        
                        # Try different regex patterns to extract a float
                        # First, look for a pattern that handles common formats with optional spaces
                        #float_match = re.search(r'[-+]?\s*\d*[.,]?\d+', line)
                        weight_value = re.findall(r'-?\d+\.\d+', line)

                        value = float(weight_value[0])
                        print(f"Converted float value: {value}")
                            
                        current_time = time.time()
                        elapsed_time = current_time - self.start_time
                        timestamp = datetime.now()
                            
                        # Add the data point to the dataframe
                        new_row = pd.DataFrame({
                            'timestamp': [timestamp],
                            'elapsed_time': [elapsed_time],
                            'value': [value]})
                        self.data = pd.concat([self.data, new_row], ignore_index=True)
                            
                        # Increment counter for saving to CSV
                        self.values_since_save += 1
                            
                        # Check if it's time to save to CSV
                        if self.values_since_save >= SAVE_INTERVAL:
                            # Use a thread-safe way to save and notify
                            self.save_to_csv()
                            #ui.timer(0.1, main_thread_save, once=True)
                            self.values_since_save = 0
                    except Exception as e:
                        # Catch all exceptions for robust error handling
                        print(f"Error processing value: '{line}' - {str(e)}")
                
                time.sleep(SAMPLING_RATE)
                
            except Exception as e:
                print(f"Error reading from serial port: {str(e)}")
                self.is_running = False
                break

# Create the SerialMonitor instance
monitor = SerialMonitor()

# GUI setup
with ui.card().classes('w-full'):
    ui.label('Sartorius datalogging interface').classes('text-xl font-bold')
    
    with ui.row():
        port_dropdown = ui.select(monitor.available_ports, label='Serial Port')
        refresh_button = ui.button('Refresh', on_click=lambda: refresh_ports_dropdown())
        baud_rate = ui.select([9600, 19200, 38400, 57600, 115200], label='Baud Rate', value=9600)
        
    # Function to refresh the ports dropdown
    def refresh_ports_dropdown():
        available_ports = monitor.refresh_ports()
        port_dropdown.options = available_ports
        port_dropdown.update()
    
    with ui.row():
        connect_button = ui.button('Connect', on_click=lambda: connect_to_port())
        disconnect_button = ui.button('Disconnect', on_click=lambda: disconnect_port())
    
    # Function to connect to port and update button appearance
    def connect_to_port():
        if monitor.connect(port_dropdown.value, int(baud_rate.value)):
            connect_button.style('background-color: #4CAF50')  # Green color
            update_button_states()
    
    # Function to disconnect and update button appearance
    def disconnect_port():
        if monitor.disconnect():
            connect_button.style('background-color: none')  # Reset color
            update_button_states()
    
    # Function to update button states based on connection
    def update_button_states():
        if monitor.is_connected:
            connect_button.style('background-color: #4CAF50')  # Green color
            connect_button.disable()
            disconnect_button.enable()
        else:
            connect_button.style('background-color: none')  # Reset color
            connect_button.enable()
            disconnect_button.disable()
    
    # Initialize button states
    update_button_states()
    
    with ui.row():
        start_button = ui.button('Start Monitoring', on_click=lambda: start_monitoring())
        stop_button = ui.button('Stop Monitoring', on_click=lambda: stop_monitoring())
        
    # Function to start monitoring and update button appearance
    def start_monitoring():
        if monitor.start_reading():
            start_button.style('background-color: #4CAF50')  # Green color
            update_monitoring_buttons()
    
    # Function to stop monitoring and clear the graph
    def stop_monitoring():
        # Stop the monitoring process
        if monitor.stop_reading():
            start_button.style('background-color: none')  # Reset color
            update_monitoring_buttons()
        # Clear the line plot
        line_plot.clear()
        
    # Function to update monitoring button states
    def update_monitoring_buttons():
        if monitor.is_running:
            start_button.style('background-color: #4CAF50')  # Green color
            start_button.disable()
            stop_button.enable()
        else:
            start_button.style('background-color: none')  # Reset color
            start_button.enable()
            stop_button.disable()
            
    # Initialize monitoring button states
    update_monitoring_buttons()
    
    # Create a line chart to display the data
    with ui.card().classes('w-full'):
        ui.label('Real-time Weight Graph').classes('text-lg font-bold')
        line_plot = ui.line_plot(n=1, limit=2000, figsize=(8, 4), update_every=1).with_legend(['Weight (g)'], loc='upper left')
        line_plot.fig.gca().set_ylabel("Mass (g)")
        line_plot.fig.gca().set_xlabel("Time since start (min)")
        line_plot.fig.set_layout_engine("tight")
        line_plot.update()

    
    # Function to update the plot
    def update_plot():
        if not monitor.data.empty and len(monitor.data) > 0:
            try:
                # Get the latest data point
                latest = monitor.data.iloc[-1]
                x_value = latest['elapsed_time']/60 # so in minutes instead of seconds
                y_value = latest['value']
                
                # Update the plot when measurement is ready
                if monitor.meas_done:
                    # Push the new point to the plot
                    line_plot.push([x_value], [[y_value]])
                    line_plot._convert_to_html()
                    monitor.meas_done = not monitor.meas_done
            except Exception as e:
                print(f"Error updating plot: {str(e)}")

    
    # Create a timer to update the plot every 100ms
    ui.timer(0.5, update_plot)
    
    # Display some statistics
    with ui.row():
        stats_container = ui.card().classes('w-full')
        
        with stats_container:
            ui.label('Statistics').classes('font-bold')
            
            with ui.row():
                with ui.column():
                    current_value_label = ui.label('Current Value: --')
                
                with ui.column():
                    min_value_label = ui.label('Min Value: --')
                
                with ui.column():
                    max_value_label = ui.label('Max Value: --')
                
                with ui.column():
                    avg_value_label = ui.label('Avg Value: --')
                    
                with ui.column():
                    slope_label = ui.label('Slope: -- mg/min')
                    
                with ui.column():
                    data_points_label = ui.label('Data Points: 0')
                    
                with ui.column():
                    save_status_label = ui.label('Next save in: 0')
            
            # Function to update statistics
            def update_stats():
                if not monitor.data.empty:
                    values = monitor.data['value']
                    current = values.iloc[-1]
                    min_val = values.min()
                    max_val = values.max()
                    avg_val = values.mean()
                    count = len(values)
                    
                    # Calculate slope (rate of change) for the last 10 minutes of data
                    TEN_MINUTES_IN_SECONDS = 10 * 60
                    current_time = time.time()
                    cutoff_time = current_time - monitor.start_time - TEN_MINUTES_IN_SECONDS
                    
                    # Filter data to get only the last 10 minutes
                    recent_data = monitor.data[monitor.data['elapsed_time'] >= max(0, cutoff_time)]
                    
                    # Calculate slope only if we have enough data points
                    if len(recent_data) >= 2:
                        # Use linear regression to calculate slope
                        # Convert to minutes for better readability
                        x = recent_data['elapsed_time'] / 60  # Convert seconds to minutes
                        y = recent_data['value']
                        
                        if len(x) > 0 and x.max() > x.min():  # Ensure we have variation in x
                            # Calculate slope using numpy polyfit
                            try:
                                import numpy as np
                                slope, _ = np.polyfit(x, y, 1)
                                # Convert from g/min to mg/min (multiply by 1000)
                                slope_mg_min = slope * 1000
                                slope_label.text = f'Slope: {slope_mg_min:.3f} mg/min'
                            except:
                                # Fallback method if numpy is not available
                                # Simple calculation based on first and last point
                                x_first, y_first = x.iloc[0], y.iloc[0]
                                x_last, y_last = x.iloc[-1], y.iloc[-1]
                                if x_last > x_first:  # Avoid division by zero
                                    slope = (y_last - y_first) / (x_last - x_first)
                                    # Convert from g/min to mg/min (multiply by 1000)
                                    slope_mg_min = slope * 1000
                                    slope_label.text = f'Slope: {slope_mg_min:.3f} mg/min'
                    
                    current_value_label.text = f'Current Value: {current:.2f}'
                    min_value_label.text = f'Min Value: {min_val:.2f}'
                    max_value_label.text = f'Max Value: {max_val:.2f}'
                    avg_value_label.text = f'Avg Value: {avg_val:.2f}'
                    data_points_label.text = f'Data Points: {count}'
                    save_status_label.text = f'Next save in: {SAVE_INTERVAL - monitor.values_since_save}'
            
            # Create a timer to update the statistics every 500ms
            ui.timer(3, update_stats)
            
    # Display the CSV file info
    with ui.row():
        csv_info = ui.card().classes('w-full')
        
        with csv_info:
            ui.label('CSV File Information').classes('font-bold')
            csv_filename_label = ui.label('Current CSV: Not saving yet')
            
            def update_csv_info():
                if monitor.csv_filename:
                    csv_filename_label.text = f'Current CSV: {os.path.basename(monitor.csv_filename)}'
                    
            ui.timer(10, update_csv_info)

# Add a page cleanup handler
@app.on_shutdown
def shutdown():
    if monitor.is_running:
        monitor.stop_reading()
    if monitor.serial_port and monitor.serial_port.is_open:
        monitor.serial_port.close()

# Start the app
ui.run(title="Sartorius datalogging interface", port=8080)