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
