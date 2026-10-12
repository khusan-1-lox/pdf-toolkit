import asyncio
import base64
import binascii
import http.client
import ipaddress
import os
import shutil
import socket
import ssl
import time
import uuid
from typing import Optional
from urllib.parse import unquote_to_bytes, urljoin, urlsplit, urlunsplit

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

try:
    from weasyprint import HTML
    HAS_WP = True
except (ImportError, OSError):
    HTML = None
    HAS_WP = False


def schedule_delete(path: str):
    import threading

    def delete():
        time.sleep(RETENTION_SECONDS)
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    threading.Thread(target=delete, daemon=True).start()


def validate_public_url(url: str):
    if any(ord(char) < 33 for char in url):
        raise HTTPException(400, "URL contains invalid characters")
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only public HTTP or HTTPS URLs are supported")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Credentials in URLs are not allowed")
        host = parsed.hostname.encode("idna").decode("ascii")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError("Only standard HTTP/HTTPS ports are allowed")
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(address[4][0] for address in addresses))
        if not ips or any(not ipaddress.ip_address(address).is_global for address in ips):
            raise ValueError("Private, loopback, reserved and local network URLs are blocked")
        return parsed, host, port, ips
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except socket.gaierror as exc:
        raise HTTPException(422, "Could not resolve the website address") from exc


def fetch_public_resource(url: str):
    """Resolve/check every hop, then connect to that exact IP (no DNS rebinding)."""
    if url.startswith("data:"):
        if len(url) > MAX_FILE_SIZE * 2:
            raise HTTPException(413, "Embedded resource is too large")
        metadata, separator, payload = url[5:].partition(",")
        mime = metadata.split(";")[0].lower()
        if not separator or mime not in {
            "image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
            "font/woff", "font/woff2", "font/ttf", "font/otf", "text/css",
        }:
            raise HTTPException(400, "Unsupported embedded resource")
        try:
            raw = unquote_to_bytes(payload)
            if metadata.lower().endswith(";base64"):
                raw = base64.b64decode(raw, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(400, "Invalid embedded resource") from exc
        if len(raw) > MAX_FILE_SIZE:
            raise HTTPException(413, "Embedded resource is too large")
        return {"string": raw, "mime_type": mime, "encoding": None, "redirected_url": url}
    for _ in range(6):
        parsed, host, port, ips = validate_public_url(url)
        connection = http.client.HTTPConnection(host, port, timeout=10)
        try:
            # HTTPConnection accepts an already connected socket. TLS retains
            # hostname verification and SNI even though the connection is IP-pinned.
            connection.sock = socket.create_connection((ips[0], port), timeout=10)
            if parsed.scheme == "https":
                connection.sock = ssl.create_default_context().wrap_socket(
                    connection.sock, server_hostname=host,
                )
            request_target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            connection.request("GET", request_target, headers={
                "User-Agent": "PDFToolkit/1.0", "Accept-Encoding": "identity",
            })
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise HTTPException(422, "Website returned a redirect without a destination")
                url = urljoin(url, location)
                continue
            if response.status >= 400:
                raise HTTPException(422, f"Website returned HTTP {response.status}")
            payload = response.read(MAX_FILE_SIZE + 1)
            if len(payload) > MAX_FILE_SIZE:
                raise HTTPException(413, "Fetched resource is too large")
            return {
                "string": payload,
                "mime_type": response.headers.get_content_type(),
                "encoding": response.headers.get_content_charset(),
                "redirected_url": url,
            }
        except HTTPException:
            raise
        except (OSError, http.client.HTTPException) as exc:
            raise HTTPException(422, "Could not download the website or one of its resources") from exc
        finally:
            connection.close()
    raise HTTPException(422, "Website redirected too many times")


async def convert_html(html_str: str, out_path: str, base_url: Optional[str] = None):
    def convert():
        if not HAS_WP:
            raise HTTPException(503, "HTML conversion requires WeasyPrint and its system rendering libraries on the server")
        blocked = []
        resource_count, resource_bytes = 0, 0
        deadline = time.monotonic() + 60

        def safe_fetcher(url, *args, **kwargs):
            nonlocal resource_count, resource_bytes
            resource_count += 1
            try:
                if resource_count > 100 or time.monotonic() > deadline:
                    raise HTTPException(413, "HTML contains too many external resources")
                result = fetch_public_resource(url)
                resource_bytes += len(result["string"])
                if resource_bytes > MAX_FILE_SIZE * 2:
                    raise HTTPException(413, "HTML external resources exceed the size limit")
                return result
            except HTTPException as exc:
                # WeasyPrint normally swallows fetch errors and keeps rendering.
                # A blocked local resource must be reported, not quietly omitted.
                if exc.status_code in {400, 413}:
                    blocked.append(exc)
                raise

        HTML(string=html_str, base_url=base_url, url_fetcher=safe_fetcher).write_pdf(out_path)
        if blocked:
            raise blocked[0]

    await asyncio.to_thread(convert)


@router.post("/api/html-to-pdf")
async def html_to_pdf(
    background_tasks: BackgroundTasks,
    html: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None),
):
    has_html = bool(html and html.strip())
    has_url = bool(url and url.strip())
    if sum((has_html, file is not None, has_url)) != 1:
        raise HTTPException(400, "Provide exactly one of html, file, or url")
    base_url = None
    if has_url:
        result = await asyncio.to_thread(fetch_public_resource, url.strip())
        if result["mime_type"] not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise HTTPException(400, "URL did not return an HTML document")
        encoding = result["encoding"] or "utf-8"
        try:
            html_str = result["string"].decode(encoding, errors="replace")
        except LookupError:
            html_str = result["string"].decode("utf-8", errors="replace")
        base_url = result["redirected_url"]
    elif file is not None:
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(413, "File too large")
        html_str = data.decode("utf-8", errors="replace")
    else:
        html_str = html
    if not html_str or not html_str.strip():
        raise HTTPException(400, "Empty HTML")
    if len(html_str.encode("utf-8")) > MAX_FILE_SIZE:
        raise HTTPException(413, "HTML too large")
    directory = os.path.join(TMP_ROOT, str(uuid.uuid4()))
    os.makedirs(directory, exist_ok=True)
    out_path = os.path.join(directory, "output.pdf")
    try:
        await convert_html(html_str, out_path, base_url)
        if not os.path.exists(out_path) or not os.path.getsize(out_path):
            raise ValueError("Conversion produced an empty file")
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(422, f"HTML to PDF conversion failed: {exc}") from exc
    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="output.pdf", media_type="application/pdf")
