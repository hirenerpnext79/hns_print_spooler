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
import re
import socket
import urllib.parse
from pathlib import Path
import fitz
from PIL import Image, ImageOps
import requests


def _is_ip_printer(printer_name):
    if not printer_name:
        return False
    return bool(re.match(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?$", str(printer_name).strip()))


def _parse_ip_port(printer_name, default_port=9100):
    match = re.match(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?$", str(printer_name).strip())
    if not match:
        return None, default_port
    host = match.group(1)
    port = int(match.group(2)) if match.group(2) else default_port
    return host, port


def _send_socket_data(host, port, data_bytes, timeout=10):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))
        s.sendall(data_bytes)


def _image_to_zpl(img):
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.convert("RGBA").split()[3])
        img = bg
    w, h = img.size
    mono = ImageOps.invert(img.convert("L")).convert("1")
    bytes_per_row = (w + 7) // 8
    total_bytes = bytes_per_row * h
    hex_data = mono.tobytes().hex().upper()
    return f"^XA^PW{w}^LL{h}^FO0,0^GFA,{total_bytes},{total_bytes},{bytes_per_row},{hex_data}^FS^XZ"


def _pdf_to_zpl(pdf_path):
    doc = fitz.open(pdf_path)
    zpl_parts = []
    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        zpl_parts.append(_image_to_zpl(img))
    return "\n".join(zpl_parts)


def _convert_file_to_zpl(local_file_path):
    ext = Path(local_file_path).suffix.lower()
    if ext in [".zpl", ".prn", ".txt", ".lbl"]:
        with open(local_file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if ext == ".pdf":
        return _pdf_to_zpl(local_file_path)

    if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
        with Image.open(local_file_path) as img:
            return _image_to_zpl(img)

    with open(local_file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    if content.strip().startswith("^XA"):
        return content
    return _pdf_to_zpl(local_file_path)


def _resolve_file_path(file_path):
    if not file_path:
        return None
    raw = str(file_path).strip()
    if os.path.exists(raw):
        return raw

    match = re.search(r"/(private/files/[^?#]+|files/[^?#]+)", raw)
    if match:
        rel = match.group(1)
        path = frappe.get_site_path("public", rel) if not rel.startswith("private/") else frappe.get_site_path(rel)
        if os.path.exists(path):
            return path
        file_doc = frappe.db.get_value("File", {"file_url": raw}, "name")
        if file_doc:
            return frappe.get_doc("File", file_doc).get_full_path()

    return raw if os.path.exists(raw) else None


@frappe.whitelist()
def print_to_ip(ip_address, file_path):
    try:
        if not ip_address:
            return {"success": False, "message": "Missing ip_address"}

        resolved_path = _resolve_file_path(file_path)
        if not resolved_path or not os.path.exists(resolved_path):
            return {"success": False, "message": f"File not found: {file_path}"}

        host, port = _parse_ip_port(ip_address)
        zpl_data = _convert_file_to_zpl(resolved_path)
        _send_socket_data(host, port, zpl_data.encode("utf-8"))

        return {
            "success": True,
            "message": f"Printed to IP {host}:{port}",
            "data": {
                "ip": host,
                "port": port,
                "file": resolved_path
            }
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="IP Print Error", message=error_msg)
        return {"success": False, "message": error_msg}


@frappe.whitelist(allow_guest=True)
def print_job_server(session_id=None, job_name=None):
    if not job_name:
        return {"status": "error", "message": "Missing job_name"}
    res = print_job_direct(job_name)
    status = "success" if res.get("success") else "error"
    return {"status": status, "message": res.get("message")}


@frappe.whitelist()
def print_job_direct(job_name):
    try:
        doc = frappe.get_doc("HNS Print Spooler", job_name)
        if not doc.printer_name:
            return {"success": False, "message": "Missing printer_name"}

        if not doc.attachment_pdf:
            return {"success": False, "message": "No attachment file found to print"}

        file_path = _resolve_file_path(doc.attachment_pdf)
        if not file_path or not os.path.exists(file_path):
            return {"success": False, "message": f"Attachment file not found: {doc.attachment_pdf}"}

        res = print_to_ip(doc.printer_name, file_path)
        if res.get("success"):
            doc.status = "Printed"
            doc.processed_at = frappe.utils.now()
            doc.error = ""
            doc.save(ignore_permissions=True)
        else:
            doc.status = "Error"
            doc.error = res.get("message")
            doc.save(ignore_permissions=True)
        return res
    except Exception as e:
        frappe.log_error(title="Print Job Direct Error", message=str(e))
        return {"success": False, "message": str(e)}





@frappe.whitelist()
def get_pending_jobs():
    try:
        jobs = frappe.db.get_all(
            "HNS Print Spooler",
            filters={"status": "Pending"},
            fields=["name", "site_name", "printer_name", "attachment_pdf", "status", "created_at"],
            order_by="creation asc",
        )
        return {"success": True, "message": "Pending jobs fetched", "data": jobs}
    except Exception as e:
        frappe.log_error(title="Get Pending Jobs Error", message=str(e))
        return {"success": False, "message": str(e), "data": []}


@frappe.whitelist()
def update_print_status(job_name, status, error=None, printer_name=None):
    try:
        if not frappe.db.exists("HNS Print Spooler", job_name):
            return {"success": False, "message": "Print job not found"}

        update_data = {
            "status": status,
            "error": error or "",
        }
        if status == "Printed":
            update_data["processed_at"] = frappe.utils.now()

        if printer_name:
            update_data["printer_name"] = printer_name

        frappe.db.set_value("HNS Print Spooler", job_name, update_data)
        return {"success": True, "message": "Print job updated", "data": update_data}
    except Exception as e:
        frappe.log_error(title="Update Print Status Error", message=str(e))
        return {"success": False, "message": str(e)}

