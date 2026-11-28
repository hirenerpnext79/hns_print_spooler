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
import tempfile
import subprocess
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


def _image_to_zpl(img, copies=1):
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.convert("RGBA").split()[3])
        img = bg
    w, h = img.size
    mono = ImageOps.invert(img.convert("L")).convert("1")
    bytes_per_row = (w + 7) // 8
    total_bytes = bytes_per_row * h
    hex_data = mono.tobytes().hex().upper()
    num_copies = int(copies) if copies and int(copies) > 0 else 1
    return (
        "^XA\n"
        "^LH0,0\n"
        "^PON\n"
        f"^PW{w}\n"
        f"^LL{h}\n"
        "^MNY\n"
        "~SD20\n"
        f"^FO0,0^GFA,{total_bytes},{total_bytes},{bytes_per_row},{hex_data}^FS\n"
        f"^PQ{num_copies},0,1,Y\n"
        "^XZ"
    )


def _parse_html_page_dimensions(html_content):
    w_match = re.search(r'name=["\']pdfkit-page-width["\']\s+content=["\']([^"\']+)["\']', html_content, re.I)
    h_match = re.search(r'name=["\']pdfkit-page-height["\']\s+content=["\']([^"\']+)["\']', html_content, re.I)
    if w_match and h_match:
        return w_match.group(1).strip(), h_match.group(1).strip()

    size_match = re.search(r'@page\s*\{[^}]*size:\s*([0-9.]+[a-zA-Z%]+)\s+([0-9.]+[a-zA-Z%]+)', html_content, re.I)
    if size_match:
        return size_match.group(1).strip(), size_match.group(2).strip()

    return None, None


def _pdf_to_zpl(pdf_source, dpi=203, copies=1):
    if isinstance(pdf_source, (bytes, bytearray)):
        doc = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        doc = fitz.open(pdf_source)
    zpl_parts = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        zpl_parts.append(_image_to_zpl(img, copies=copies))
    return "\n".join(zpl_parts)


def _html_to_zpl(
    html_content,
    page_width=None,
    page_height=None,
    margin_top=None,
    margin_bottom=None,
    margin_left=None,
    margin_right=None,
    orientation=None,
    dpi=203,
    print_copies=1,
):
    detected_w, detected_h = _parse_html_page_dimensions(html_content)
    w = page_width or detected_w
    h = page_height or detected_h

    html_content = re.sub(r'<div class="action-banner[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
    banner_hide_style = '<style>.action-banner, .print-hide { display: none !important; visibility: hidden !important; height: 0 !important; overflow: hidden !important; }</style>'
    if "</head>" in html_content:
        html_content = html_content.replace("</head>", f"{banner_hide_style}</head>", 1)
    else:
        html_content = f"{banner_hide_style}{html_content}"

    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as f_html:
        f_html.write(html_content)
        html_path = f_html.name

    pdf_path = html_path.replace(".html", ".pdf")
    try:
        cmd = [
            "wkhtmltopdf",
            "--load-error-handling", "ignore",
            "--load-media-error-handling", "ignore",
            "--quiet",
        ]

        if w and h:
            cmd.extend([
                "--page-width", str(w),
                "--page-height", str(h),
            ])

        cmd.extend([
            "-T", str(margin_top or "0"),
            "-B", str(margin_bottom or "0"),
            "-L", str(margin_left or "0"),
            "-R", str(margin_right or "0"),
        ])

        if orientation and str(orientation).lower() in ["landscape", "portrait"]:
            cmd.extend(["--orientation", str(orientation).capitalize()])

        cmd.extend([html_path, pdf_path])
        subprocess.run(cmd, check=False)

        dpi_val = int(dpi) if dpi else 203
        copies = int(print_copies) if print_copies else 1
        return _pdf_to_zpl(pdf_path, dpi=dpi_val, copies=copies)
    finally:
        if os.path.exists(html_path):
            os.remove(html_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def _convert_file_to_zpl(local_file_path):
    ext = Path(local_file_path).suffix.lower()
    if ext in [".zpl", ".prn", ".txt", ".lbl"]:
        with open(local_file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if ext == ".pdf":
        return _pdf_to_zpl(local_file_path)

    if ext in [".html", ".htm"]:
        with open(local_file_path, "r", encoding="utf-8", errors="ignore") as f:
            return _html_to_zpl(f.read())

    if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
        with Image.open(local_file_path) as img:
            return _image_to_zpl(img)

    with open(local_file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    if content.strip().startswith("^XA"):
        return content
    if content.strip().startswith("<"):
        return _html_to_zpl(content)
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


@frappe.whitelist()
def print_html_to_ip(
    ip_address,
    html_content,
    page_width=None,
    page_height=None,
    margin_top=None,
    margin_bottom=None,
    margin_left=None,
    margin_right=None,
    orientation=None,
    dpi=203,
    print_copies=1,
):
    try:
        if not ip_address:
            return {"success": False, "message": "Missing ip_address"}
        if not html_content:
            return {"success": False, "message": "Missing html_content"}

        host, port = _parse_ip_port(ip_address)
        zpl_data = _html_to_zpl(
            html_content,
            page_width=page_width,
            page_height=page_height,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            margin_right=margin_right,
            orientation=orientation,
            dpi=dpi,
            print_copies=print_copies,
        )
        _send_socket_data(host, port, zpl_data.encode("utf-8"))

        return {
            "success": True,
            "message": f"HTML printed to IP {host}:{port}",
            "data": {"ip": host, "port": port},
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="HTML IP Print Error", message=error_msg)
        return {"success": False, "message": error_msg}


def _is_zebra_label_format(print_format, page_width, page_height):
    if print_format and any(k in str(print_format).lower() for k in ["37 x 25", "25 x 37", "serial no"]):
        return True
    if page_width and page_height:
        w_val = re.sub(r"[^\d.]", "", str(page_width))
        h_val = re.sub(r"[^\d.]", "", str(page_height))
        if w_val in ["25", "37"] and h_val in ["25", "37"]:
            return True
    return False


@frappe.whitelist()
def generate_zebra_label_zpl(doctype, docname, print_copies=1):
    doc = frappe.get_doc(doctype, docname)

    qr_value = ""
    qr_keyword = getattr(doc, "qr_keyword", None)
    if qr_keyword and frappe.db.exists("Hns Asset Multi Master", qr_keyword):
        qr_master = frappe.get_doc("Hns Asset Multi Master", qr_keyword)
        qr_value = getattr(qr_master, "value", "") or ""

    qr_data = f"{doc.name}^^{qr_value}"

    item_name = getattr(doc, "item_short_name", None) or getattr(doc, "item_name", None) or ""
    if not item_name and getattr(doc, "item_code", None):
        item_name = frappe.db.get_value("Item", doc.item_code, "item_name") or doc.item_code

    copies = int(print_copies) if print_copies else 1

    lines = [
        "^XA",
        "^LH0,0",
        "^PON",
        "^PW296",
        "^LL200",
        "^MNY",
        "~SD20",
        f"^FO10,15^BQN,2,5^FDQA,{qr_data}^FS",
    ]

    if item_name:
        lines.append(f"^FO130,20^A0B,24,24^FD{item_name}^FS")
        lines.append(f"^FO162,20^A0B,22,22^FD{doc.name}^FS")
    elif "-" in doc.name:
        parts = doc.name.rsplit("-", 1)
        lines.append(f"^FO130,20^A0B,24,24^FD{parts[0]}-^FS")
        lines.append(f"^FO160,20^A0B,24,24^FD{parts[1]}^FS")
    else:
        lines.append(f"^FO135,20^A0B,26,26^FD{doc.name}^FS")

    lines.append(f"^PQ{copies},0,1,Y")
    lines.append("^XZ")

    return "\n".join(lines)


@frappe.whitelist()
def print_doc_format_to_ip(
    doctype,
    docname,
    ip_address,
    print_format=None,
    letterhead=None,
    page_width=None,
    page_height=None,
    margin_top=None,
    margin_bottom=None,
    margin_left=None,
    margin_right=None,
    orientation=None,
    dpi=203,
    print_copies=1,
):
    try:
        if not doctype or not docname:
            return {"success": False, "message": "Missing doctype or docname"}
        if not ip_address:
            return {"success": False, "message": "Missing ip_address"}

        host, port = _parse_ip_port(ip_address)

        from frappe.www.printview import get_html_and_style

        data = get_html_and_style(
            doc=doctype,
            name=docname,
            print_format=print_format or None,
            letterhead=letterhead or None,
            no_letterhead=0 if letterhead else 1,
        )
        body_html = data.get("html") or ""
        style_css = data.get("style") or ""
        base_url = frappe.utils.get_url()

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<base href="{base_url}">
<style>
{style_css}
.action-banner, .print-hide {{
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    overflow: hidden !important;
}}
html, body {{
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
}}
.print-format {{
    margin: 0 !important;
    padding: 0 !important;
}}
</style>
</head>
<body>
<div class="print-format">
{body_html}
</div>
</body>
</html>"""

        return print_html_to_ip(
            ip_address=ip_address,
            html_content=html_content,
            page_width=page_width,
            page_height=page_height,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            margin_right=margin_right,
            orientation=orientation,
            dpi=dpi,
            print_copies=print_copies,
        )
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="Print Doc Format To IP Error", message=error_msg)
        return {"success": False, "message": error_msg}






@frappe.whitelist()
def print_zebra_design_to_ip(doctype, docname, ip_address, print_copies=1):
    try:
        if not doctype or not docname:
            return {"success": False, "message": "Missing doctype or docname"}
        if not ip_address:
            return {"success": False, "message": "Missing ip_address"}

        host, port = _parse_ip_port(ip_address)
        zpl_data = generate_zebra_label_zpl(doctype, docname, print_copies=print_copies)
        _send_socket_data(host, port, zpl_data.encode("utf-8"))

        return {
            "success": True,
            "message": f"Zebra Design printed to IP {host}:{port}",
            "data": {"ip": host, "port": port},
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="Print Zebra Design IP Error", message=error_msg)
        return {"success": False, "message": error_msg}


@frappe.whitelist()
def get_zebra_design_zpl(doctype, docname, print_copies=1):
    try:
        if not doctype or not docname:
            return {"success": False, "message": "Missing doctype or docname"}
        zpl_data = generate_zebra_label_zpl(doctype, docname, print_copies=print_copies)
        return {
            "success": True,
            "zpl": zpl_data,
            "message": "ZPL generated successfully",
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="Get Zebra ZPL Error", message=error_msg)
        return {"success": False, "message": error_msg}


@frappe.whitelist()
def get_print_html(doctype, docname, print_format=None, letterhead=None):
    try:
        if not doctype or not docname:
            return {"success": False, "message": "Missing doctype or docname"}

        from frappe.www.printview import get_html_and_style

        data = get_html_and_style(
            doc=doctype,
            name=docname,
            print_format=print_format or None,
            letterhead=letterhead or None,
            no_letterhead=0 if letterhead else 1,
        )
        body_html = data.get("html") or ""
        style_css = data.get("style") or ""
        base_url = frappe.utils.get_url()

        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<base href="{base_url}">
<style>
{style_css}
html, body {{
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
}}
.print-format {{
    margin: 0 !important;
    padding: 0 !important;
}}
</style>
</head>
<body>
<div class="print-format">
{body_html}
</div>
</body>
</html>"""

        return {
            "success": True,
            "html": full_html,
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="Get Print HTML Error", message=error_msg)
        return {"success": False, "message": error_msg}


@frappe.whitelist(allow_guest=True)
def print_job_server(session_id=None, job_name=None):
    if not job_name:
        return {"status": "error", "message": "Missing job_name"}
    res = print_job_direct(job_name)
    status = "success" if res.get("success") else "error"
    return {"status": status, "message": res.get("message")}


@frappe.whitelist()
def auto_print_on_save(doctype, docname, printer_name=None, print_format=None):
    try:
        doc = frappe.get_doc(doctype, docname)
        target_printer = printer_name or getattr(doc, "printer_name", None) or "192.168.0.182"

        if not _is_ip_printer(target_printer):
            return {
                "success": False,
                "message": f"Printer {target_printer} is not an IP address printer",
            }

        host, port = _parse_ip_port(target_printer)
        zpl_data = generate_zebra_label_zpl(doctype, docname, print_copies=1)
        _send_to_windows_spooler("TSC TE210 (Copy 1)", docname, zpl_data)
        _send_socket_data(host, port, zpl_data.encode("utf-8"))

        if doctype == "HNS Print Spooler":
            doc.status = "Printed"
            doc.processed_at = frappe.utils.now()
            doc.error = ""
            doc.save(ignore_permissions=True)

        return {
            "success": True,
            "message": f"Automatically printed to {host}:{port}",
            "printer": f"{host}:{port}",
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="Auto Print On Save Error", message=error_msg)
        if doctype == "HNS Print Spooler":
            try:
                doc = frappe.get_doc(doctype, docname)
                doc.status = "Error"
                doc.error = error_msg
                doc.save(ignore_permissions=True)
            except Exception:
                pass
        return {"success": False, "message": error_msg}


def _send_to_windows_spooler(printer_name, doc_name, raw_data):
    try:
        script = f"""
$code = @"
using System;
using System.Runtime.InteropServices;
public class RawPrinterHelper {{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    public class DOCINFOA {{
        [MarshalAs(UnmanagedType.LPStr)] public string pDocName;
        [MarshalAs(UnmanagedType.LPStr)] public string pOutputFile;
        [MarshalAs(UnmanagedType.LPStr)] public string pDataType;
    }}
    [DllImport("winspool.Drv", EntryPoint = "OpenPrinterA", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true)]
    public static extern bool OpenPrinter(string szPrinter, out IntPtr hPrinter, IntPtr pd);
    [DllImport("winspool.Drv", EntryPoint = "ClosePrinter", SetLastError = true, ExactSpelling = true)]
    public static extern bool ClosePrinter(IntPtr hPrinter);
    [DllImport("winspool.Drv", EntryPoint = "StartDocPrinterA", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true)]
    public static extern bool StartDocPrinter(IntPtr hPrinter, Int32 level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOA di);
    [DllImport("winspool.Drv", EntryPoint = "EndDocPrinter", SetLastError = true, ExactSpelling = true)]
    public static extern bool EndDocPrinter(IntPtr hPrinter);
    [DllImport("winspool.Drv", EntryPoint = "StartPagePrinter", SetLastError = true, ExactSpelling = true)]
    public static extern bool StartPagePrinter(IntPtr hPrinter);
    [DllImport("winspool.Drv", EntryPoint = "EndPagePrinter", SetLastError = true, ExactSpelling = true)]
    public static extern bool EndPagePrinter(IntPtr hPrinter);
    [DllImport("winspool.Drv", EntryPoint = "WritePrinter", SetLastError = true, ExactSpelling = true)]
    public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, Int32 dwCount, out Int32 dwWritten);
    public static bool SendStringToPrinter(string szPrinterName, string szString, string docName) {{
        IntPtr pBytes = Marshal.StringToCoTaskMemAnsi(szString);
        bool success = SendBytesToPrinter(szPrinterName, pBytes, szString.Length, docName);
        Marshal.FreeCoTaskMem(pBytes);
        return success;
    }}
    public static bool SendBytesToPrinter(string szPrinterName, IntPtr pBytes, Int32 dwCount, string docName) {{
        IntPtr hPrinter = IntPtr.Zero;
        DOCINFOA di = new DOCINFOA();
        di.pDocName = docName;
        di.pDataType = "RAW";
        bool bSuccess = false;
        if (OpenPrinter(szPrinterName, out hPrinter, IntPtr.Zero)) {{
            if (StartDocPrinter(hPrinter, 1, di)) {{
                if (StartPagePrinter(hPrinter)) {{
                    Int32 dwWritten = 0;
                    bSuccess = WritePrinter(hPrinter, pBytes, dwCount, out dwWritten);
                    EndPagePrinter(hPrinter);
                }}
                EndDocPrinter(hPrinter);
            }}
            ClosePrinter(hPrinter);
        }}
        return bSuccess;
    }}
}}
"@
if (-not ([System.Management.Automation.PSTypeName]'RawPrinterHelper').Type) {{
    Add-Type -TypeDefinition $code
}}
$data = @'
{raw_data}
'@
[RawPrinterHelper]::SendStringToPrinter("{printer_name}", $data, "{doc_name}")
"""
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", encoding="utf-8", delete=False) as tf:
            tf.write(script)
            ps_path = tf.name

        win_path = subprocess.run(["wslpath", "-w", ps_path], capture_output=True, text=True).stdout.strip()
        res = subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", win_path], capture_output=True, text=True)
        try:
            os.remove(ps_path)
        except Exception:
            pass
        return "True" in res.stdout
    except Exception as e:
        frappe.log_error(title="Windows Spooler Print Error", message=str(e))
        return False


@frappe.whitelist()
def direct_silent_print(doctype, docname, print_format=None, ip_address=None, print_copies=1):
    try:
        if not doctype or not docname:
            return {"success": False, "message": "Missing doctype or docname"}

        doc = frappe.get_doc(doctype, docname)
        target_ip = ip_address or getattr(doc, "printer_name", None) or "192.168.0.182"
        copies = int(print_copies) if print_copies else 1

        zpl_data = generate_zebra_label_zpl(doctype, docname, print_copies=copies)

        spool_name = "TSC TE210 (Copy 1)"
        if not _is_ip_printer(target_ip):
            spool_name = target_ip

        _send_to_windows_spooler(spool_name, docname, zpl_data)

        host, port = _parse_ip_port(target_ip)
        if host:
            try:
                _send_socket_data(host, port, zpl_data.encode("utf-8"))
            except Exception:
                pass

        if doctype == "HNS Print Spooler":
            doc.status = "Printed"
            doc.processed_at = frappe.utils.now()
            doc.error = ""
            doc.save(ignore_permissions=True)

        return {
            "success": True,
            "message": f"Printed to {spool_name} queue & {host}:{port}",
            "printer": spool_name,
            "copies": copies,
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(title="Direct Silent Print Error", message=error_msg)
        if doctype == "HNS Print Spooler":
            try:
                doc = frappe.get_doc(doctype, docname)
                doc.status = "Error"
                doc.error = error_msg
                doc.save(ignore_permissions=True)
            except Exception:
                pass
        return {"success": False, "message": error_msg}


@frappe.whitelist()
def print_job_direct(job_name):
    try:
        doc = frappe.get_doc("HNS Print Spooler", job_name)
        if not doc.printer_name:
            return {"success": False, "message": "Missing printer_name"}

        if doc.attachment_pdf:
            file_path = _resolve_file_path(doc.attachment_pdf)
            if file_path and os.path.exists(file_path):
                res = print_to_ip(doc.printer_name, file_path)
                if res.get("success"):
                    doc.status = "Printed"
                    doc.processed_at = frappe.utils.now()
                    doc.error = ""
                    doc.save(ignore_permissions=True)
                    return res

        return auto_print_on_save("HNS Print Spooler", job_name, doc.printer_name)
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

