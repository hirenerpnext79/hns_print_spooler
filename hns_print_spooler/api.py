import frappe
from frappe.frappeclient import FrappeClient, AuthError
import re

def _get_clean_error_message(e):
    error_msg = str(e)
    if "TimestampMismatchError" in repr(e) or "has been modified" in error_msg:
        match = re.search(r'Error: Document has been modified.*?Please refresh to get the latest document\.', error_msg)
        if match:
            return match.group(0)
        return "Document has been modified after you opened it. Please refresh to get the latest document."
    elif "PermissionError" in repr(e) or "Does not have permission" in error_msg:
        return "Permission Denied: You do not have access to this document or printer."
    return error_msg

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    try:
        url = frappe.utils.get_url()
        client = FrappeClient(url)
        client._login(usr, pwd)
        
        sid = client.session.cookies.get('sid')
        if not sid:
            raise Exception("Authentication failed: No session ID returned by FrappeClient")

        user = frappe.get_doc('User', usr)

        return {
            "status": "success",
            "message": "Authentication Success",
            "sid": sid,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name
        }
    except Exception as e:
        error_msg = _get_clean_error_message(e)
        frappe.log_error(title="API Login Error", message=error_msg)
        return {
            "status": "error",
            "message": "Invalid login credentials."
        }

@frappe.whitelist(allow_guest=True)
def get_print_spooler_jobs(session_id=None, status="All"):
    try:
        url = frappe.utils.get_url()
        client = FrappeClient(url)
        
        # Set the SID passed explicitly from the mobile app
        if session_id:
            client.session.cookies.set('sid', session_id)
        
        filters = {}
        if status != "All":
            filters["status"] = status
            
        jobs = client.get_list(
            "HNS Print Spooler",
            filters=filters,
            fields=["name", "status", "site_name", "printer_name", "attachment_pdf", "created_at"]
        )
        return {'status': 'success', 'message': jobs}
    except Exception as e:
        error_msg = _get_clean_error_message(e)
        frappe.log_error(title="API Error", message=f"Error in get_print_spooler_jobs: {error_msg}")
        return {'status': 'error', 'message': error_msg}

@frappe.whitelist(allow_guest=True)
def update_print_job(session_id, job_name, status, printer_name=None):
    try:
        url = frappe.utils.get_url()
        client = FrappeClient(url)
        
        if session_id:
            client.session.cookies.set('sid', session_id)
        
        doc = client.get_doc('HNS Print Spooler', job_name)
        doc['status'] = status
        if printer_name:
            doc['printer_name'] = printer_name
            
        res = client.update(doc)
        return {'status': 'success', 'message': res}
    except Exception as e:
        error_msg = _get_clean_error_message(e)
        frappe.log_error(title="API Error", message=f"Error in update_print_job: {error_msg}")
        return {'status': 'error', 'message': error_msg}

import os
import subprocess
import requests
import urllib.parse
from pathlib import Path
import re

@frappe.whitelist(allow_guest=True)
def print_job_server(session_id, job_name):
    doc = None
    client = None
    try:
        url = frappe.utils.get_url()
        client = FrappeClient(url)
        if session_id:
            client.session.cookies.set('sid', session_id)
        
        doc = client.get_doc('HNS Print Spooler', job_name)
        
        # Set status to Processing initially
        doc['status'] = 'Processing'
        client.update(doc)
        
        file_url = doc.get('attachment_pdf')
        printer_name = doc.get('printer_name')
        
        if not file_url or not printer_name:
            error_msg = 'Missing attachment or printer_name'
            frappe.log_error(title="Server Print Error", message=error_msg)
            doc = client.get_doc('HNS Print Spooler', job_name)
            doc['status'] = 'Error'
            doc['error'] = error_msg
            client.update(doc)
            return {'status': 'error', 'message': error_msg}
            
        temp_dir = Path("temp_print_jobs")
        temp_dir.mkdir(exist_ok=True)
        
        full_url = urllib.parse.urljoin(url, file_url)
        cookies = {'sid': session_id} if session_id else {}
        
        local_filename = temp_dir / file_url.split('/')[-1]
        
        resp = requests.get(full_url, cookies=cookies)
        if resp.status_code == 200:
            with open(local_filename, 'wb') as f:
                f.write(resp.content)
        else:
            error_msg = f'Failed to download file: {resp.status_code}'
            frappe.log_error(title="Server Print Error", message=error_msg)
            doc = client.get_doc('HNS Print Spooler', job_name)
            doc['status'] = 'Error'
            doc['error'] = error_msg
            client.update(doc)
            return {'status': 'error', 'message': error_msg}
            
        abs_path = os.path.abspath(local_filename)
        
        # Execute CUPS print command
        command = ['lp', '-d', printer_name, abs_path]
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            job_id = ""
            match = re.search(r'request id is (\S+)', result.stdout)
            if match:
                job_id = match.group(1)
                
            doc = client.get_doc('HNS Print Spooler', job_name)
            doc['status'] = 'Queued'
            doc['cups_job_id'] = job_id
            doc['error'] = ''
            client.update(doc)
            
            try:
                os.remove(abs_path)
            except:
                pass
                
            return {'status': 'success', 'message': f'Job queued successfully with ID {job_id}'}
        else:
            error_msg = f'Print failed: {result.stderr}'
            frappe.log_error(title="Server Print Error", message=error_msg)
            doc = client.get_doc('HNS Print Spooler', job_name)
            doc['status'] = 'Error'
            doc['error'] = error_msg
            client.update(doc)
            
            try:
                os.remove(abs_path)
            except:
                pass
            return {'status': 'error', 'message': error_msg}
            
    except Exception as e:
        error_msg = _get_clean_error_message(e)
            
        frappe.log_error(title="Server Print Error", message=error_msg)
        if client and job_name:
            try:
                doc = client.get_doc('HNS Print Spooler', job_name)
                doc['status'] = 'Error'
                doc['error'] = error_msg
                client.update(doc)
            except:
                pass
        return {'status': 'error', 'message': error_msg}

@frappe.whitelist(allow_guest=True)
def check_print_status(job_name):
    try:
        url = frappe.utils.get_url()
        client = FrappeClient(url)
        doc = client.get_doc('HNS Print Spooler', job_name)
        
        job_id = doc.get("cups_job_id")
        if not job_id:
            return {'status': 'error', 'message': 'No CUPS Job ID found for this document.'}
            
        command = ['lpstat', '-o']
        result = subprocess.run(command, capture_output=True, text=True)
        
        if job_id in result.stdout:
            return {'status': 'success', 'print_status': 'Printing/Queued'}
        else:
            # The job is no longer in the active queue, meaning it has finished processing.
            if doc.get('status') != 'Printed':
                doc = client.get_doc('HNS Print Spooler', job_name)
                doc['status'] = 'Printed'
                doc['processed_at'] = frappe.utils.now()
                client.update(doc)
            return {'status': 'success', 'print_status': 'Completed'}
                
    except Exception as e:
        error_msg = _get_clean_error_message(e)
        return {'status': 'error', 'message': error_msg}
