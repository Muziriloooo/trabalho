"""Adaptador MediaMTX: destinos fixados pelo operador, TLS e proxy preservados."""
import ipaddress
import json
import re
import time
from urllib.parse import urlsplit

import requests
from flask import current_app, url_for

from .vault import SecretUnavailable, credentials

SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SAFE_ASSET = re.compile(r"^[A-Za-z0-9_-]{1,140}\.(?:m3u8|mp4|m4s|ts)$")


class GatewayError(Exception):
    def __init__(self, code, status=502):
        self.code, self.status = code, status
        super().__init__(code)


def source_name(camera):
    if not SAFE_NAME.fullmatch(camera.gateway_path):
        raise GatewayError("invalid_gateway_path", 503)
    # O administrador de uma organização nunca escolhe o namespace de outra.
    return f"org-{camera.organization_id}--{camera.gateway_path}"


def base_url(kind):
    raw = current_app.config.get(f"MEDIA_GATEWAY_{kind}_URL", "")
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
        port = parsed.port or 443
    except ValueError:
        raise GatewayError("gateway_not_configured", 503) from None
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
            or host.lower() not in current_app.config["MEDIA_GATEWAY_ALLOWED_HOSTS"]
            or port not in current_app.config["MEDIA_GATEWAY_ALLOWED_PORTS"]
            or host.lower() in {"localhost", "metadata.google.internal", "metadata"}):
        raise GatewayError("gateway_not_configured", 503)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
            raise GatewayError("gateway_destination_denied", 503)
    return raw.rstrip("/")


def fetch(camera, kind, suffix, max_bytes):
    if not SAFE_NAME.fullmatch(camera.gateway_path):
        raise GatewayError("invalid_gateway_path", 503)
    url = base_url(kind) + suffix
    try:
        auth = credentials(camera)
    except SecretUnavailable:
        raise GatewayError("credentials_unavailable", 503) from None
    try:
        # requests mantém HTTP(S)_PROXY e o CA bundle herdados. Sem redirects,
        # retries automáticos ou log de URL/corpo/credenciais.
        started = time.monotonic()
        with requests.get(url, auth=auth, timeout=current_app.config["MEDIA_GATEWAY_TIMEOUT"],
                          allow_redirects=False, stream=True) as response:
            if response.status_code in {401, 403}:
                raise GatewayError("gateway_auth_failed")
            if response.status_code == 404:
                raise GatewayError("source_unavailable")
            if response.status_code != 200:
                raise GatewayError("gateway_unavailable")
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=65536):
                if time.monotonic() - started > 15:
                    raise GatewayError("gateway_timeout", 504)
                size += len(chunk)
                if size > max_bytes:
                    raise GatewayError("gateway_response_too_large")
                chunks.append(chunk)
            return b"".join(chunks)
    except requests.Timeout:
        raise GatewayError("gateway_timeout", 504) from None
    except requests.RequestException:
        raise GatewayError("gateway_unreachable") from None


def probe(camera):
    data = fetch(camera, "API", f"/v3/paths/get/{source_name(camera)}", 64 * 1024)
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise GatewayError("invalid_gateway_response") from None
    if not isinstance(payload, dict):
        raise GatewayError("invalid_gateway_response")
    key = "online" if "online" in payload else "ready"
    if not isinstance(payload.get(key), bool):
        raise GatewayError("invalid_gateway_response")
    return payload[key]


def rewrite_manifest(data, camera_id):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise GatewayError("invalid_manifest") from None
    if not text.startswith("#EXTM3U") or "\x00" in text:
        raise GatewayError("invalid_manifest")

    def local(asset):
        if not SAFE_ASSET.fullmatch(asset):
            raise GatewayError("unsafe_manifest")
        return url_for("monitoring.media", camera_id=camera_id, asset=asset)

    lines = []
    allowed_tags = {"#EXTM3U", "#EXT-X-VERSION", "#EXT-X-TARGETDURATION", "#EXT-X-MEDIA-SEQUENCE",
                    "#EXT-X-DISCONTINUITY-SEQUENCE", "#EXTINF", "#EXT-X-ENDLIST", "#EXT-X-PLAYLIST-TYPE",
                    "#EXT-X-INDEPENDENT-SEGMENTS", "#EXT-X-DISCONTINUITY", "#EXT-X-MAP", "#EXT-X-BYTERANGE",
                    "#EXT-X-PROGRAM-DATE-TIME", "#EXT-X-STREAM-INF", "#EXT-X-MEDIA", "#EXT-X-GAP"}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            tag = line.split(":", 1)[0]
            # Somente HLS fMP4/MPEG-TS convencional. LL-HLS e chaves externas
            # não são encaminhados. Tags desconhecidas poderiam carregar URLs.
            if tag not in allowed_tags:
                raise GatewayError("unsupported_manifest")
            if re.search(r"(?:https?|rtsp)s?://|@", line, re.I):
                raise GatewayError("unsafe_manifest")
            line = re.sub(r'URI="([^"]*)"', lambda m: 'URI="' + local(m.group(1)) + '"', line)
            if "URI=" in line and not re.search(r'URI="/monitoring/', line):
                raise GatewayError("unsafe_manifest")
        else:
            line = local(line)
        lines.append(line)
    return ("\n".join(lines) + "\n").encode()
