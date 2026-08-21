import os
import sys
import time
import requests
import subprocess
import urllib.parse
from pathlib import Path

# ==========================================
# CONFIGURATION - FILL THESE IN!
# ==========================================
ERP_URL = "https://vcard.hnscloud.in/"
ERP_USER = "Administrator"
ERP_PASS = "admin"

POLL_INTERVAL_SECONDS = 10
TEMP_DIR = Path("temp_print_jobs")
PDFTOPRINTER_EXE = "PDFtoPrinter.exe"

# ==========================================

def get_session():
    """Logs into ERPNext and returns the session cookie."""
    print(f"[*] Logging into {ERP_URL} as {ERP_USER}...")
    login_url = urllib.parse.urljoin(ERP_URL, "/api/method/hns_print_spooler.api.login")
    resp = requests.post(login_url, data={'usr': ERP_USER, 'pwd': ERP_PASS})
    
    if resp.status_code == 200:
        data = resp.json().get('message', {})
        if data.get('status') == 'success':
            print("[+] Login successful!")
            return data.get('sid')
    
    print(f"[-] Login failed: {resp.text}")
    return None

def download_pdftoprinter():
    """Downloads PDFtoPrinter.exe if it doesn't exist locally."""
    if not os.path.exists(PDFTOPRINTER_EXE):
        print("[*] Downloading PDFtoPrinter.exe utility...")
        url = "https://www.columbia.edu/~em36/PDFtoPrinter.exe"
        try:
            r = requests.get(url, allow_redirects=True)
            with open(PDFTOPRINTER_EXE, 'wb') as f:
                f.write(r.content)
            print("[+] Download complete.")
        except Exception as e:
            print(f"[-] Failed to download PDFtoPrinter: {e}")
            sys.exit(1)

def poll_jobs(sid):
    """Polls the server for new print jobs."""
    url = urllib.parse.urljoin(ERP_URL, "/api/method/hns_print_spooler.api.get_print_spooler_jobs")
    resp = requests.post(url, data={'session_id': sid, 'status': 'Pending'})
    
    if resp.status_code == 200:
        data = resp.json().get('message', {})
        if data.get('status') == 'success':
            return data.get('message', [])
    return []

def download_pdf(pdf_url, sid):
    """Downloads the PDF from ERPNext."""
    full_url = urllib.parse.urljoin(ERP_URL, pdf_url)
    cookies = {'sid': sid}
    
    local_filename = TEMP_DIR / pdf_url.split('/')[-1]
    
    resp = requests.get(full_url, cookies=cookies)
    if resp.status_code == 200:
        with open(local_filename, 'wb') as f:
            f.write(resp.content)
        return local_filename
    return None

def print_pdf(local_path, printer_name):
    """Executes the Windows print command."""
    print(f"[*] Sending {local_path} to printer '{printer_name}' using Windows drivers...")
    try:
        # Get absolute path for Windows
        abs_path = os.path.abspath(local_path)
        
        # If running inside WSL, convert the path to a Windows-compatible format
        if '/' in abs_path:
            # simple trick to let Windows read the WSL path (Windows 10+ supports \\wsl$ or \\wsl.localhost)
            # Or since the file is downloaded to current directory, just use the relative filename
            win_path = str(local_filename).replace('/', '\\')
        else:
            win_path = abs_path
        
        cmd = [PDFTOPRINTER_EXE, win_path, printer_name]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[+] Print job spooled to Windows successfully.")
            return True
        else:
            print(f"[-] Print failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"[-] Error executing print: {e}")
        return False

def update_job_status(sid, job_name, status):
    """Updates the job status in ERPNext."""
    url = urllib.parse.urljoin(ERP_URL, "/api/method/hns_print_spooler.api.update_print_job")
    resp = requests.post(url, data={
        'session_id': sid,
        'job_name': job_name,
        'status': status
    })
    if resp.status_code == 200:
        print(f"[+] Job {job_name} updated to {status} on server.")
    else:
        print(f"[-] Failed to update job {job_name}.")

def main():
    print("==================================================")
    print("   ERPNext Windows Print Spooler Started          ")
    print("==================================================")
    
    TEMP_DIR.mkdir(exist_ok=True)
    download_pdftoprinter()
    
    sid = get_session()
    if not sid:
        print("[-] Cannot start polling without valid login.")
        return
        
    print(f"[*] Polling {ERP_URL} every {POLL_INTERVAL_SECONDS} seconds...\n")
    
    while True:
        try:
            jobs = poll_jobs(sid)
            for job in jobs:
                job_name = job.get('name')
                pdf_url = job.get('attachment_pdf')
                printer_name = job.get('printer_name')
                
                # IMPORTANT: For this to work, printer_name must exactly match the name in your Windows "Printers & Scanners"
                if not pdf_url or not printer_name:
                    continue
                    
                print(f"[*] Found pending job: {job_name} -> {printer_name}")
                
                local_path = download_pdf(pdf_url, sid)
                if local_path:
                    # Execute Windows print
                    success = print_pdf(local_path, printer_name)
                    if success:
                        update_job_status(sid, job_name, "Printed")
                    else:
                        update_job_status(sid, job_name, "Error")
                    
                    # Cleanup downloaded file
                    try:
                        os.remove(local_path)
                    except:
                        pass
                
        except Exception as e:
            print(f"[-] Unexpected error during polling: {e}")
            
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
