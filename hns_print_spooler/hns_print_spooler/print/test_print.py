import socket
import logging

# Configure logging to save to a file and print to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("print_spooler.log"),
        logging.StreamHandler()
    ]
)

# nc -zv 192.168.0.208 9100
# nc -zv 192.168.0.208 631
# nc -zv 192.168.0.208 515

# network socket://192.168.0.208:9100
# network ipp://192.168.0.208/ipp/print

# lp -d "Canon_MF240" testprint.txt

PRINTER_IP = "192.168.0.208"
PRINTER_PORT = 9100

data = b"""
========================
       TEST PRINT
========================

Hello from Python!

Printer: Canon MF240
IP: 192.168.0.208

========================

"""

def send_to_printer(ip, port, print_data):
    try:
        logging.info(f"Connecting to printer at {ip}:{port}...")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((ip, port))
            logging.info("Connected successfully. Sending data...")
            s.sendall(print_data)
            
        logging.info("SUCCESS: Print data was transmitted to the printer memory.")
        return True
        
    except socket.timeout:
        logging.error(f"FAILED: Connection timed out. The printer at {ip} might be offline.")
        return False
    except ConnectionRefusedError:
        logging.error(f"FAILED: Connection refused by {ip}. Port {port} might be closed.")
        return False
    except Exception as e:
        logging.error(f"FAILED: An unexpected error occurred: {e}")
        return False

# Execute the print job
is_printed = send_to_printer(PRINTER_IP, PRINTER_PORT, data)

if is_printed:
    logging.info("Job marked as completed.")
else:
    logging.warning("Job failed and was not printed.")
