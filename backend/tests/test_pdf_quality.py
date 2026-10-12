import base64
import io
import socket
from email.message import Message
from types import SimpleNamespace
from unittest.mock import Mock

import fitz
import pytest
from PIL import Image
from fastapi import HTTPException

from app.routers import html_to_pdf


def pdf_bytes(pages=1):
    with fitz.open() as doc:
        for _ in range(pages):
            doc.new_page(width=200, height=300)
        return doc.tobytes()


def image_bytes(mode="RGB", size=(200, 100), color="red"):
    image = Image.new(mode, size, color)
    stream = io.BytesIO()
    image.save(stream, "PNG")
    return stream.getvalue()


def test_preview_pagination_and_dimensions(client):
    data = pdf_bytes(55)
    first = client.post("/api/preview", files={"file": ("x.pdf", data, "application/pdf")}).json()
    assert first["numPages"] == 55 and len(first["pages"]) == 50 and first["hasMore"]
    last = client.post("/api/preview", files={"file": ("x.pdf", data, "application/pdf")},
                       data={"offset": 50, "limit": 10}).json()
    assert last["numPages"] == 55 and len(last["pages"]) == 5 and not last["hasMore"]
    assert [page["page"] for page in last["pages"]] == list(range(50, 55))
    assert all(page["width"] == 200 and page["height"] == 300 for page in last["pages"])


@pytest.mark.parametrize("options", [{"offset": -1}, {"limit": 0}, {"limit": 51}])
def test_preview_rejects_invalid_window(client, options):
    response = client.post("/api/preview", files={"file": ("x.pdf", pdf_bytes(), "application/pdf")},
                           data=options)
    assert response.status_code == 422


@pytest.mark.parametrize("page_size,orientation,expected", [
    ("A4", "portrait", (595.276, 841.89)),
    ("A3", "landscape", (1190.551, 841.89)),
    ("Letter", "landscape", (792, 612)),
    ("fit", "portrait", (144, 72)),
])
def test_image_page_settings(client, page_size, orientation, expected):
    response = client.post("/api/jpg-to-pdf", files={"files": ("x.png", image_bytes(), "image/png")},
                           data={"pageSize": page_size, "orientation": orientation, "margin": "none"})
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        assert doc[0].rect.width == pytest.approx(expected[0], abs=0.01)
        assert doc[0].rect.height == pytest.approx(expected[1], abs=0.01)
        bbox = doc[0].get_image_rects(doc[0].get_images()[0][0])[0]
        assert bbox.width / bbox.height == pytest.approx(2, abs=0.00001)


def test_image_margin_and_transparency(client):
    transparent = image_bytes("RGBA", color=(255, 0, 0, 0))
    response = client.post("/api/scan-to-pdf", files={"files": ("x.png", transparent, "image/png")},
                           data={"pageSize": "fit", "margin": "small"})
    assert response.status_code == 200
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        page = doc[0]
        assert page.rect.width == pytest.approx(144 + 2 * 14.173, abs=0.01)
        bbox = page.get_image_rects(page.get_images()[0][0])[0]
        assert bbox.x0 == pytest.approx(14.173, abs=0.01)
        assert min(page.get_pixmap().samples) == 255


@pytest.mark.parametrize("options", [{"orientation": "up"}, {"pageSize": "foo"}, {"margin": "huge"}])
def test_image_invalid_settings(client, options):
    response = client.post("/api/jpg-to-pdf", files={"files": ("x.png", image_bytes(), "image/png")},
                           data=options)
    assert response.status_code == 400


def test_compression_preserves_image_and_text(client):
    # Uncompressed image forces the actual recompression path, unlike blank PDFs.
    with fitz.open() as doc:
        page = doc.new_page(width=400, height=400)
        page.insert_image(fitz.Rect(0, 0, 300, 300),
                          stream=image_bytes(size=(600, 600), color=(210, 35, 25)))
        page.insert_text((30, 350), "Still searchable")
        data = doc.tobytes()
    sizes = []
    for quality in ("low", "medium", "high"):
        response = client.post("/api/compress", files={"file": ("x.pdf", data, "application/pdf")},
                               data={"quality": quality})
        assert response.status_code == 200, response.text
        assert len(response.content) <= len(data)
        sizes.append(len(response.content))
        with fitz.open(stream=response.content, filetype="pdf") as compressed:
            assert "Still searchable" in compressed[0].get_text()
            red, green, blue = compressed[0].get_pixmap().pixel(150, 150)
            assert red > 180 and green < 65 and blue < 55
            assert compressed[0].get_images()
    assert sizes[0] < len(data)


def test_compression_never_enlarges_tiny_pdf(client):
    data = pdf_bytes()
    response = client.post("/api/compress", files={"file": ("x.pdf", data, "application/pdf")})
    assert response.status_code == 200
    assert len(response.content) <= len(data)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.169.254",
                                      "0.0.0.0", "::1", "fc00::1"])
def test_html_blocks_private_dns_answers(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))])
    with pytest.raises(HTTPException) as exc:
        html_to_pdf.validate_public_url("https://public-looking.example/path")
    assert exc.value.status_code == 400


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x",
                                  "http://user:password@example.com", "http://example.com:8080"])
def test_html_blocks_unsafe_urls(url):
    with pytest.raises(HTTPException) as exc:
        html_to_pdf.validate_public_url(url)
    assert exc.value.status_code == 400


def test_html_rechecks_redirect_and_pins_connection(monkeypatch):
    def resolve(host, port, **kwargs):
        address = "127.0.0.1" if host == "localhost" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    connect = Mock(return_value=object())
    monkeypatch.setattr(socket, "create_connection", connect)
    response = SimpleNamespace(status=302, getheader=lambda name: "http://localhost/private")
    connection = Mock()
    connection.getresponse.return_value = response
    factory = Mock(return_value=connection)
    monkeypatch.setattr(html_to_pdf.http.client, "HTTPConnection", factory)
    with pytest.raises(HTTPException) as exc:
        html_to_pdf.fetch_public_resource("http://example.com")
    assert exc.value.status_code == 400
    connect.assert_called_once_with(("93.184.216.34", 80), timeout=10)
    factory.assert_called_once()


def test_html_resource_size_limit(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))])
    monkeypatch.setattr(socket, "create_connection", Mock())
    monkeypatch.setattr(html_to_pdf, "MAX_FILE_SIZE", 10)
    response = Mock(status=200)
    response.read.return_value = b"x" * 11
    connection = Mock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(html_to_pdf.http.client, "HTTPConnection", Mock(return_value=connection))
    with pytest.raises(HTTPException) as exc:
        html_to_pdf.fetch_public_resource("http://example.com")
    assert exc.value.status_code == 413
    response.read.assert_called_once_with(11)


def test_html_embedded_image_does_not_use_network(monkeypatch):
    connect = Mock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(socket, "create_connection", connect)
    data = image_bytes()
    result = html_to_pdf.fetch_public_resource("data:image/png;base64," + base64.b64encode(data).decode())
    assert result["string"] == data
    assert result["mime_type"] == "image/png"
    connect.assert_not_called()
