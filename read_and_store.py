import os
import serial
from collections import deque
import re
from datetime import datetime, timezone
import time
import pytz
from supabase import create_client
from dotenv import load_dotenv

class FlowmeterDataCollector:
    def __init__(self, port, baudrate=9600, buffer_size=1000):
        self.serial_port = port
        self.baudrate = baudrate
        self.buffer_size = buffer_size
        self.ring_buffer = deque(maxlen=buffer_size)
        self.current_record = {'timestamp': None, 'flow': None, 'velocity': None}
        self.ser = None
        self.bangkok_tz = pytz.timezone('Asia/Bangkok')
        
        # Load environment variables
        load_dotenv()
        
        # Supabase setup
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        if not all([self.supabase_url, self.supabase_key]):
            raise ValueError("Missing Supabase credentials in environment variables")
        
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        
    def connect_serial(self):
        """Establish serial connection with retries"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                self.ser = serial.Serial(
                    port=self.serial_port,
                    baudrate=self.baudrate,
                    timeout=1
                )
                print(f"Connected to {self.serial_port} at {self.baudrate} baud")
                return True
            except serial.SerialException as e:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to connect to serial port after {max_retries} attempts: {e}")
                    return False
            
    def parse_data_line(self, line):
        """Parse individual lines of data from the flowmeter"""
        line = line.strip()
        
        # Timestamp line
        timestamp_match = re.match(r'(\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            naive_dt = datetime.strptime(timestamp_match.group(1), '%y-%m-%d %H:%M:%S')
            localized_dt = self.bangkok_tz.localize(naive_dt)
            self.current_record['timestamp'] = localized_dt.isoformat()
            return False
            
        # Flow line
        flow_match = re.match(r'Flow\s+([\d.]+)\s+l/s', line)
        if flow_match:
            self.current_record['flow'] = float(flow_match.group(1))
            return False
            
        # Velocity line
        vel_match = re.match(r'Vel:\s+([\d.]+)\s+m/s', line)
        if vel_match:
            self.current_record['velocity'] = float(vel_match.group(1))
            return True
            
        return False
            
    def process_buffer(self):
        """Process all complete records in the ring buffer"""
        while self.ring_buffer:
            line = self.ring_buffer.popleft()
            if self.parse_data_line(line):
                if all(self.current_record.values()):
                    self.store_record()
                    self.current_record = {'timestamp': None, 'flow': None, 'velocity': None}
    
    def store_record(self):
        """Store a complete record in Supabase with error handling"""
        try:
            # Use UTC ISO 8601 timestamp
            utc_now = datetime.now(timezone.utc).isoformat()
            self.current_record['timestamp'] = utc_now
            response = self.supabase.table('flow_data').insert({
                'timestamp': self.current_record['timestamp'],
                'flow': self.current_record['flow'],
                'velocity': self.current_record['velocity'],
            }).execute()
            if response.data:
                local_dt = datetime.fromisoformat(self.current_record['timestamp'])
                print(f"Stored: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} | "
                      f"Flow: {self.current_record['flow']:.3f} l/s | "
                      f"Vel: {self.current_record['velocity']:.3f} m/s")
            else:
                print("Failed to store record - empty response")
        except Exception as e:
            print(f"Supabase error: {str(e)}")
                    
    def run(self):
        """Main loop to read from serial port and process data"""
        if not self.connect_serial():
            return
            
        print("Flowmeter data collector started. Press Ctrl+C to stop.")
        print(f"Supabase endpoint: {self.supabase_url}")
        
        try:
            while True:
                if self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('ascii', errors='ignore')
                        if line.strip():
                            self.ring_buffer.append(line)
                    except Exception as e:
                        print(f"Serial read error: {e}")
                        
                self.process_buffer()
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
        finally:
            self.process_buffer()
            if hasattr(self, 'ser') and self.ser and self.ser.is_open:
                self.ser.close()
            print("Flowmeter collector stopped.")

def main():
    print("[DEBUG] read_and_store.py main() starting...")
    print(f"[DEBUG] SERIAL_PORT: {os.getenv('SERIAL_PORT', '/dev/ttyUSB0')}")
    # Configuration - can be overridden by environment variables
    PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
    BAUD_RATE = int(os.getenv('BAUD_RATE', '9600'))
    BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '1000'))
    
    collector = FlowmeterDataCollector(
        port=PORT,
        baudrate=BAUD_RATE,
        buffer_size=BUFFER_SIZE
    )
    collector.run()

if __name__ == "__main__":
    main()