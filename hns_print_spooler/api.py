import frappe
from frappe.frappeclient import FrappeClient, AuthError

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
        frappe.log_error(title="API Login Error", message=str(e))
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
        frappe.log_error(title="API Error", message=f"Error in get_print_spooler_jobs: {str(e)}")
        return {'status': 'error', 'message': str(e)}

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
        frappe.log_error(title="API Error", message=f"Error in update_print_job: {str(e)}")
        return {'status': 'error', 'message': str(e)}

import os
import subprocess

@frappe.whitelist(allow_guest=True)
def print_job_server(session_id, job_name):
    try:
        url = frappe.utils.get_url()
        client = FrappeClient(url)
        if session_id:
            client.session.cookies.set('sid', session_id)
        
        doc = client.get_doc('HNS Print Spooler', job_name)
        file_url = doc.get('attachment_pdf')
        printer_name = doc.get('printer_name')
        
        if not file_url or not printer_name:
            return {'status': 'error', 'message': 'Missing attachment or printer_name'}
            
        # Get absolute file path from file URL
        file_path = frappe.get_site_path('public', file_url.lstrip('/'))
        
        if not os.path.exists(file_path):
            return {'status': 'error', 'message': f'File not found on server: {file_path}'}
            
        # Execute CUPS print command
        # lp -d "Printer_Name" "/path/to/file.pdf"
        command = ['lp', '-d', printer_name, file_path]
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            doc['status'] = 'Printed'
            client.update(doc)
            return {'status': 'success', 'message': f'Printed successfully to {printer_name}'}
        else:
            return {'status': 'error', 'message': f'Print failed: {result.stderr}'}
            
    except Exception as e:
        frappe.log_error(title="Server Print Error", message=str(e))
        return {'status': 'error', 'message': str(e)}
