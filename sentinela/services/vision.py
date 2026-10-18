"""Detecção não identificadora em amostras limitadas; nenhum frame persistido."""
import os
import re
import tempfile
import time
from pathlib import Path

# O decodificador só recebe arquivos locais; playlists/URLs não são entradas.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "protocol_whitelist;file"

import cv2

from . import gateway

cv2.setNumThreads(1)


class AnalysisFailure(Exception):
    pass


def classify_frames(frames, policy):
    previous = None
    motion_hits = obstruction_hits = seen = 0
    for frame in frames:
        if frame is None or frame.ndim != 3:
            raise AnalysisFailure("invalid_frame")
        frame = cv2.resize(frame, (320, 180))
        x, y = int(policy.roi_x * 320), int(policy.roi_y * 180)
        w, h = max(1, int(policy.roi_w * 320)), max(1, int(policy.roi_h * 180))
        gray = cv2.cvtColor(frame[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if gray.mean() < 12 or gray.std() < 6:
            obstruction_hits += 1
        if previous is not None:
            difference = cv2.absdiff(previous, gray)
            ratio = float((difference > 20).mean())
            if ratio >= policy.motion_ratio:
                motion_hits += 1
        previous = gray
        seen += 1
    if seen < 3:
        raise AnalysisFailure("insufficient_frames")
    result = []
    if policy.motion_enabled and motion_hits >= 2:
        result.append("motion")
    if policy.obstruction_enabled and obstruction_hits >= 3:
        result.append("obstruction")
    return result


def read_frames(path):
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    started = time.monotonic()
    try:
        if not capture.isOpened():
            raise AnalysisFailure("video_unreadable")
        for _ in range(72):
            if time.monotonic() - started > 10:
                raise AnalysisFailure("analysis_timeout")
            ok, frame = capture.read()
            if not ok:
                break
            yield frame
    finally:
        capture.release()


def sample_gateway(camera):
    """Uma playlist e no máximo um segmento, sempre pelo gateway autorizado."""
    source = gateway.source_name(camera)
    manifest = gateway.fetch(camera, "HLS", f"/{source}/index.m3u8", 256 * 1024)
    for depth in range(2):
        try:
            text = manifest.decode("utf-8")
        except UnicodeDecodeError:
            raise AnalysisFailure("invalid_manifest") from None
        if not text.startswith("#EXTM3U"):
            raise AnalysisFailure("invalid_manifest")
        assets = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
        if not assets or any(not gateway.SAFE_ASSET.fullmatch(asset) for asset in assets):
            raise AnalysisFailure("unsafe_manifest")
        if assets[0].endswith(".m3u8") and depth == 0:
            manifest = gateway.fetch(camera, "HLS", f"/{source}/{assets[0]}", 256 * 1024)
            continue
        if any(asset.endswith(".m3u8") for asset in assets):
            raise AnalysisFailure("unsupported_manifest")
        # Reutiliza a validação estrita de URI/tags do relay, sem encaminhar seu output.
        gateway.rewrite_manifest(manifest, camera.id)
        init = re.search(r'#EXT-X-MAP:URI="([^"]+)"', text)
        prefix = b""
        if init:
            if not gateway.SAFE_ASSET.fullmatch(init.group(1)):
                raise AnalysisFailure("unsafe_manifest")
            prefix = gateway.fetch(camera, "HLS", f"/{source}/{init.group(1)}", 1024 * 1024)
        segment = gateway.fetch(camera, "HLS", f"/{source}/{assets[-1]}", 12 * 1024 * 1024)
        return prefix + segment
    raise AnalysisFailure("unsupported_manifest")


def analyze_camera(camera, policy):
    if camera.protocol == "demo":
        return classify_frames(read_frames(Path(__file__).resolve().parent.parent / "media" / "demo.mp4"), policy)
    data = sample_gateway(camera)
    is_mp4 = len(data) >= 12 and data[4:8] == b"ftyp"
    is_ts = len(data) >= 377 and all(data[offset] == 0x47 for offset in (0, 188, 376))
    if not (is_mp4 or is_ts):
        raise AnalysisFailure("unsupported_container")
    # Diretório temporário privado; removido mesmo em falha. Sem armazenamento
    # permanente de frames, screenshots ou gravação de transmissões.
    with tempfile.TemporaryDirectory(prefix="sentinela-analysis-") as folder:
        path = Path(folder) / "sample.mp4"
        path.write_bytes(data)
        return classify_frames(read_frames(path), policy)
