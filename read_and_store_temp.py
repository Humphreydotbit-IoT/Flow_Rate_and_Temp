import os
import serial
import time
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv

# --- BCD/Frame Parsing Functions (unchanged, with all debug prints) ---
def bcd_to_int(bcd_byte):
    return ((bcd_byte >> 4) * 10) + (bcd_byte & 0x0F)

def bcd_bytes_to_int(b1, b2):
    return ((b1 >> 4) * 1000 + (b1 & 0x0F) * 100 + (b2 >> 4) * 10 + (b2 & 0x0F))

def parse_frame(frame):
    if len(frame) != 8:
        print(f"[Error] Frame length is not 8: {len(frame)}")
        return
    if frame[0] != 0x02:
        print(f"[Error] Invalid frame start: {frame[0]:02X}")
        return
    t1 = (frame[2] << 8 | frame[3]) / 10.0
    t2 = (frame[4] << 8 | frame[5]) / 10.0
    print(f"[T1] {t1:.2f} °C, [T2] {t2:.2f} °C | Frame: {' '.join(f'{b:02X}' for b in frame)}")

def parse_temperature(frame):
    if len(frame) < 8:
        print(f"[Error] Frame too short: {len(frame)} bytes")
        return None
    if frame[0] != 0x02:
        print(f"[Error] Invalid start byte: {frame[0]:02X}")
        return None
    display_mode = frame[2]
    sign = -1 if (display_mode & 0x04) else 1
    decimal_point = display_mode & 0x03
    digit1_raw = frame[3]
    digit2_raw = frame[4]
    digit3_raw = frame[5]
    digit4_raw = frame[6]
    digit1 = bcd_to_int(digit1_raw)
    digit2 = bcd_to_int(digit2_raw)
    digit3 = bcd_to_int(digit3_raw)
    digit4 = bcd_to_int(digit4_raw)
    print(f"[Debug] Raw BCD bytes: {digit1_raw:02X} {digit2_raw:02X} {digit3_raw:02X} {digit4_raw:02X}")
    print(f"[Debug] Parsed BCD digits: {digit1} {digit2} {digit3} {digit4}")
    print(f"[Debug] sign: {sign}, decimal_point: {decimal_point}")
    value = digit1 * 1000 + digit2 * 100 + digit3 * 10 + digit4
    temperature = sign * (value / (10 ** decimal_point))
    print(f"[Debug] Parsed temperature: {temperature:.2f} °C from frame: {' '.join(f'{b:02X}' for b in frame)}")
    return temperature

def find_frame(buffer):
    found_any = False
    for i in range(len(buffer) - 7):
        if buffer[i] == 0x02:
            candidate = buffer[i:i+8]
            print(f"[Debug] 8-byte sequence from 0x02: {' '.join(f'{b:02X}' for b in candidate)}")
            found_any = True
            if candidate[7] == 0x03:
                print(f"[Debug] Found valid frame: {' '.join(f'{b:02X}' for b in candidate)}")
                return candidate, i+8
    if not found_any:
        print("[Debug] No 8-byte sequence starting with 0x02 found in buffer.")
    return None, 0

# --- Supabase Setup ---
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
if not all([SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Missing Supabase credentials in environment variables")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Main Loop ---
def main():
    print("[DEBUG] read_and_store_temp.py main() starting...")
    print(f"[DEBUG] SERIAL_PORT_TEMP: {os.getenv('SERIAL_PORT_TEMP', '/dev/ttyUSB1')}")
    port_name = os.getenv('SERIAL_PORT_TEMP', '/dev/ttyUSB1')  # Can override with env var
    baud_rate = int(os.getenv('BAUD_RATE_TEMP', '9600'))
    # --- Change the reading/upload rate here (in seconds) ---
    READ_INTERVAL = 900  # <-- Set to 900 for 15 minutes. Change this value to adjust the rate.
    # -------------------------------------------------------
    try:
        ser = serial.Serial(
            port=port_name,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        print(f"[Opened] Serial port {port_name} at {baud_rate} baud")
        print("[Info] Waiting for device to stabilize...")
        time.sleep(2)
        buffer = bytearray()
        consecutive_errors = 0
        last_valid_frame = None
        while True:
            ser.write(b'A')
            print("\n[Sent] Command 'A'")
            time.sleep(0.2)
            chunk = ser.read(32)
            if chunk:
                print(f"[Received] {len(chunk)} bytes")
                print(f"[Raw] {' '.join(f'{b:02X}' for b in chunk)}")
                buffer += chunk
                print(f"[Debug] Full buffer: {' '.join(f'{b:02X}' for b in buffer)}")
                for i in range(len(buffer) - 7):
                    candidate = buffer[i:i+8]
                    if candidate[0] == 0x02:
                        parse_frame(candidate)
                # Only upload the correct T1/T2 (second line) to Supabase
                t1_to_upload = None
                t2_to_upload = None
                found = 0
                for i in range(len(buffer) - 7):
                    candidate = buffer[i:i+8]
                    if candidate[0] == 0x02:
                        t1 = (candidate[2] << 8 | candidate[3]) / 10.0
                        t2 = (candidate[4] << 8 | candidate[5]) / 10.0
                        found += 1
                        if found == 2:  # The second valid frame
                            t1_to_upload = t1
                            t2_to_upload = t2
                            break
                if t1_to_upload is not None and t2_to_upload is not None:
                    if 10 <= t1_to_upload <= 100 and 10 <= t2_to_upload <= 100:
                        now = datetime.now(timezone.utc).isoformat()
                        data_to_upload = {
                            'timestamp': now,
                            't1': t1_to_upload,
                            't2': t2_to_upload
                        }
                        print(f"[DEBUG] Data to upload: {data_to_upload}")
                        # Upload to Supabase
                        try:
                            response = supabase.table('temperature_data').insert(data_to_upload).execute()
                            if response.data:
                                print(f"[Uploaded] T1: {t1_to_upload:.2f} °C, T2: {t2_to_upload:.2f} °C at {now}")
                            else:
                                print("[Upload failed] Empty response from Supabase")
                        except Exception as e:
                            print(f"[Supabase error] {str(e)}")
                    else:
                        print(f"[DEBUG] Skipped upload: T1={t1_to_upload}, T2={t2_to_upload} (out of range)")
                # Keep only the last 32 bytes if buffer is growing too large
                if len(buffer) > 32:
                    buffer = buffer[-32:]
            else:
                print("[No data received]")
                consecutive_errors += 1
            if consecutive_errors >= 5:
                print("[Error] Too many consecutive errors - consider checking device connection")
                if last_valid_frame:
                    print(f"[Info] Last valid frame was: {' '.join(f'{b:02X}' for b in last_valid_frame)}")
                break
            # --- Wait for the next reading/upload ---
            time.sleep(READ_INTERVAL)
    except serial.SerialException as e:
        print(f"[Error] Serial port issue: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("[Closed] Serial port")

if __name__ == '__main__':
    main() 