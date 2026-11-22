#!/usr/bin/env python3
"""
Ucuts Pipeline: Turn VODs/streams into vertical 9:16 Reels/Shorts with
face tracking, audio-reactive green-screen corner streamer overlays,
word-level pop-up captions, and -14 LUFS loudness normalization.

Usage:
    python3 scripts/ucuts_pipeline.py \
      --url "https://youtu.be/169ZzvPxvvM" \
      --sections "00:10:40-00:11:40,02:02:01-02:03:01" \
      --model small --language hi --cookies-from-browser chrome \
      --avatar-idle focused.jpg --avatar-talk talking.jpg --avatar-hype hyped.jpg \
      --avatar-corner bottom-left
"""

from __future__ import annotations

import argparse
import html
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pysubs2
import stable_whisper
from norfair import Detection, Tracker

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

YUNET_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)


@dataclass(frozen=True)
class ClipSpec:
    name: str
    start: str
    end: str


def run_cmd(cmd: List[str], env: Optional[dict] = None) -> None:
    print(f"[CMD] {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, env=env)


def check_dependencies() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("Required binary 'ffmpeg' not found on PATH.")


def ffmpeg_has_libass() -> bool:
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "ass":
                return True
    except Exception:
        pass
    return False


def download_section(
    url: str,
    start: str,
    end: str,
    out_path: Path,
    cookies_from_browser: Optional[str] = None,
) -> Path:
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-overwrites",
        "--download-sections",
        f"*{start}-{end}",
        "--force-keyframes-at-cuts",
        "-f",
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(out_path),
    ]
    if cookies_from_browser:
        cmd.extend(["--cookies-from-browser", cookies_from_browser])
    cmd.append(url)
    run_cmd(cmd)
    if not out_path.exists():
        raise FileNotFoundError(f"Expected downloaded clip not found: {out_path}")
    return out_path


def ensure_yunet_model(model_dir: Path) -> Path:
    import ssl
    import urllib.request

    model_path = model_dir / "face_detection_yunet_2023mar.onnx"
    if model_path.exists() and model_path.stat().st_size > 100_000:
        return model_path

    print(f"[INFO] Downloading YuNet face detector -> {model_path}", flush=True)
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    with urllib.request.urlopen(YUNET_MODEL_URL, context=ctx, timeout=60) as resp:
        model_path.write_bytes(resp.read())
    return model_path


def detect_faces_yunet(
    bgr_frame: np.ndarray,
    detector,
    scale_factor: float = 0.5,
) -> List[Detection]:
    small = cv2.resize(bgr_frame, (0, 0), fx=scale_factor, fy=scale_factor)
    sh, sw = small.shape[:2]
    detector.setInputSize((sw, sh))
    _, faces = detector.detect(small)

    detections: List[Detection] = []
    if faces is None:
        return detections

    inv_scale = 1.0 / scale_factor
    for row in faces:
        x, y, w, h = float(row[0]), float(row[1]), float(row[2]), float(row[3])
        cx = (x + w / 2.0) * inv_scale
        cy = (y + h / 2.0) * inv_scale
        area = (w * inv_scale) * (h * inv_scale)
        detections.append(
            Detection(points=np.array([[cx, cy]], dtype=np.float32), data={"area": area})
        )
    return detections


def detect_faces_haar(
    gray_frame: np.ndarray,
    cascade,
    scale_factor: float = 0.5,
) -> List[Detection]:
    small = cv2.resize(gray_frame, (0, 0), fx=scale_factor, fy=scale_factor)
    faces = cascade.detectMultiScale(
        small, scaleFactor=1.15, minNeighbors=5, minSize=(30, 30)
    )
    inv_scale = 1.0 / scale_factor
    detections: List[Detection] = []
    for (x, y, w, h) in faces:
        cx = (x + w / 2.0) * inv_scale
        cy = (y + h / 2.0) * inv_scale
        area = (w * inv_scale) * (h * inv_scale)
        detections.append(
            Detection(points=np.array([[cx, cy]], dtype=np.float32), data={"area": area})
        )
    return detections


def chroma_key_border_connected(image_path: Path, target_width: int = 440) -> np.ndarray:
    """
    Remove only the outer connected green-screen background (zero interior pinholes
    on dark shirts/faces), feather silhouette edges, and despill green reflections.
    """
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"Could not read avatar image: {image_path}")

    h, w = bgr.shape[:2]
    scale = target_width / float(w)
    bgr = cv2.resize(
        bgr,
        (target_width, max(1, int(round(h * scale)))),
        interpolation=cv2.INTER_AREA,
    )

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    b, g, r = cv2.split(bgr.astype(np.float32))
    excess_g = g - np.maximum(r, b)

    cand_hsv = cv2.inRange(hsv, (35, 65, 50), (90, 255, 255))
    cand_eg = (excess_g > 32.0).astype(np.uint8) * 255
    green_cand = cv2.bitwise_or(cand_hsv, cand_eg)

    _, labels = cv2.connectedComponents(green_cand, connectivity=8)
    border_labels = (
        set(np.unique(labels[0, :]))
        | set(np.unique(labels[:, 0]))
        | set(np.unique(labels[:, -1]))
    )
    border_labels.discard(0)
    bg_mask = np.isin(labels, list(border_labels)).astype(np.uint8) * 255

    alpha = cv2.bitwise_not(bg_mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha = cv2.erode(alpha, kernel, iterations=1)
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)

    edge_band = ((alpha > 5) & (alpha < 250)).astype(np.float32)
    edge_band = cv2.GaussianBlur(edge_band, (9, 9), 0)
    spill = np.maximum(0.0, g - np.maximum(r, b))
    despill_strength = np.clip(0.35 + 0.65 * edge_band, 0.0, 1.0)
    g_clean = g - spill * despill_strength
    clean_bgr = cv2.merge([b, np.clip(g_clean, 0, 255), r]).astype(np.uint8)

    ys, xs = np.where(alpha > 12)
    if len(xs) > 0 and len(ys) > 0:
        clean_bgr = clean_bgr[ys.min() :, xs.min() : xs.max() + 1]
        alpha = alpha[ys.min() :, xs.min() : xs.max() + 1]

    return np.dstack([clean_bgr, alpha])


def compute_frame_audio_rms(media_path: Path, fps: float, num_frames: int) -> np.ndarray:
    sr = 16000
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(media_path),
        "-ac", "1", "-ar", str(sr), "-f", "f32le", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, check=True)
    samples = np.frombuffer(res.stdout, dtype=np.float32)
    if samples.size == 0:
        return np.zeros(num_frames, dtype=np.float32)

    spf = max(1, int(round(sr / fps)))
    rms = np.zeros(num_frames, dtype=np.float32)
    for i in range(num_frames):
        s0 = i * spf
        s1 = min(samples.size, s0 + spf)
        if s0 < s1:
            rms[i] = float(np.sqrt(np.mean(samples[s0:s1] ** 2)))

    p95 = float(np.percentile(rms, 95)) or 1e-6
    rms = np.clip(rms / p95, 0.0, 1.5)
    win = max(1, int(round(fps * 0.16)))
    kernel = np.ones(win, dtype=np.float32) / win
    return np.convolve(rms, kernel, mode="same")


def composite_avatar_corner(
    frame: np.ndarray,
    avatar_bgra: np.ndarray,
    corner: str = "bottom-left",
    bounce_px: int = 0,
    margin_x: int = 12,
    margin_y: int = 12,
) -> None:
    fh, fw = frame.shape[:2]
    ah, aw = avatar_bgra.shape[:2]

    if corner == "bottom-left":
        x1, y1 = margin_x, fh - ah + bounce_px
    elif corner == "bottom-right":
        x1, y1 = fw - aw - margin_x, fh - ah + bounce_px
    elif corner == "top-left":
        x1, y1 = margin_x, margin_y - bounce_px
    else:
        x1, y1 = fw - aw - margin_x, margin_y - bounce_px

    fx1, fy1 = max(0, x1), max(0, y1)
    fx2, fy2 = min(fw, x1 + aw), min(fh, y1 + ah)
    ox1, oy1 = fx1 - x1, fy1 - y1
    ox2, oy2 = ox1 + (fx2 - fx1), oy1 + (fy2 - fy1)
    if fx2 <= fx1 or fy2 <= fy1:
        return

    roi = frame[fy1:fy2, fx1:fx2].astype(np.float32)
    ov = avatar_bgra[oy1:oy2, ox1:ox2]
    alpha = ov[:, :, 3:4].astype(np.float32) / 255.0
    blended = ov[:, :, :3].astype(np.float32) * alpha + roi * (1.0 - alpha)
    frame[fy1:fy2, fx1:fx2] = np.clip(blended, 0, 255).astype(np.uint8)


def track_and_crop_vertical(
    input_video: Path,
    output_video: Path,
    ema_alpha: float = 0.12,
    deadzone_px: float = 28.0,
    avatars: Optional[Dict[str, np.ndarray]] = None,
    avatar_corner: str = "bottom-left",
) -> None:
    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {input_video}")

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or int(fps * 65)

    audio_rms = (
        compute_frame_audio_rms(input_video, fps, total_frames + 120)
        if avatars
        else None
    )

    crop_w = min(src_w, int(round(src_h * (OUTPUT_WIDTH / OUTPUT_HEIGHT))))
    half_crop = crop_w / 2.0

    use_yunet = not hasattr(cv2, "CascadeClassifier")
    if use_yunet:
        model_path = ensure_yunet_model(output_video.parent)
        detector = cv2.FaceDetectorYN.create(
            str(model_path), "", (max(1, src_w // 2), max(1, src_h // 2)), 0.6, 0.3, 5000
        )
        face_cascade = None
    else:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        detector = None

    tracker = Tracker(
        distance_function="mean_euclidean",
        distance_threshold=max(60.0, src_w * 0.08),
        hit_counter_max=15,
    )

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_video), fourcc, fps, (OUTPUT_WIDTH, OUTPUT_HEIGHT))

    smooth_cx = src_w / 2.0
    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % 2 == 0:
                if use_yunet:
                    detections = detect_faces_yunet(frame, detector)
                else:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    detections = detect_faces_haar(gray, face_cascade)
            else:
                detections = []

            tracked_objects = tracker.update(detections=detections)
            target_cx: Optional[float] = None
            if tracked_objects:
                best_obj = max(
                    tracked_objects,
                    key=lambda obj: (
                        obj.last_detection.data.get("area", 0.0)
                        if obj.last_detection and obj.last_detection.data
                        else 0.0
                    ),
                )
                target_cx = float(best_obj.estimate[0][0])

            if target_cx is not None and abs(target_cx - smooth_cx) > deadzone_px:
                smooth_cx = (ema_alpha * target_cx) + ((1.0 - ema_alpha) * smooth_cx)

            x1 = max(0, min(src_w - crop_w, int(round(smooth_cx - half_crop))))
            cropped = frame[:, x1 : x1 + crop_w]
            resized = cv2.resize(
                cropped, (OUTPUT_WIDTH, OUTPUT_HEIGHT), interpolation=cv2.INTER_LANCZOS4
            )

            if avatars and audio_rms is not None:
                t = frame_idx / fps
                energy = float(audio_rms[min(frame_idx, len(audio_rms) - 1)])
                if energy >= 0.85 and "hype" in avatars:
                    pose = avatars["hype"]
                elif energy >= 0.28 and "talk" in avatars:
                    pose = avatars["talk"]
                elif "idle" in avatars:
                    pose = avatars["idle"]
                elif "talk" in avatars:
                    pose = avatars["talk"]
                else:
                    pose = next(iter(avatars.values()))

                breath = 2.0 * math.sin(2.0 * math.pi * t * 0.5)
                bounce = int(round(breath - min(7.0, energy * 6.0)))
                composite_avatar_corner(
                    resized, pose, corner=avatar_corner, bounce_px=bounce
                )

            writer.write(resized)
            frame_idx += 1
    finally:
        cap.release()
        writer.release()


def transcribe_words(
    model,
    media_path: Path,
    language: Optional[str] = None,
) -> List[Tuple[float, float, str]]:
    kwargs = {"regroup": True, "vad": True}
    if language:
        kwargs["language"] = language
    try:
        result = model.transcribe(str(media_path), **kwargs)
    except Exception as exc:
        print(f"[WARN] VAD transcription failed ({exc}); retrying with vad=False", flush=True)
        kwargs["vad"] = False
        result = model.transcribe(str(media_path), **kwargs)

    words: List[Tuple[float, float, str]] = []
    for segment in result.segments:
        for w in segment.words:
            text = w.word.strip()
            if text:
                words.append((float(w.start), float(w.end), text))
    return words


def build_popup_ass(
    words: List[Tuple[float, float, str]],
    ass_path: Path,
    font_name: str = "Noto Sans Devanagari",
    words_per_chunk: int = 3,
    margin_v: int = 360,
) -> Path:
    subs = pysubs2.SSAFile()
    subs.info["PlayResX"] = str(OUTPUT_WIDTH)
    subs.info["PlayResY"] = str(OUTPUT_HEIGHT)
    subs.info["ScaledBorderAndShadow"] = "yes"

    subs.styles["PopUp"] = pysubs2.SSAStyle(
        fontname=font_name,
        fontsize=74,
        bold=True,
        primarycolor=pysubs2.Color(255, 255, 255, 0),
        outlinecolor=pysubs2.Color(0, 0, 0, 0),
        backcolor=pysubs2.Color(0, 0, 0, 140),
        outline=6.0,
        shadow=3.0,
        alignment=pysubs2.Alignment.BOTTOM_CENTER,
        marginv=margin_v,
        marginl=60,
        marginr=60,
    )

    for i in range(0, len(words), words_per_chunk):
        chunk = words[i : i + words_per_chunk]
        for active_idx, (w_start, w_end, _) in enumerate(chunk):
            start_ms = max(0, int(round(w_start * 1000)))
            end_ms = max(start_ms + 80, int(round(w_end * 1000)))
            parts: List[str] = []
            for j, (_, _, token) in enumerate(chunk):
                safe = token.replace("{", "").replace("}", "")
                if j == active_idx:
                    parts.append(
                        r"{\c&H0000FFFF&\fscx108\fscy108\t(0,70,\fscx100\fscy100)}"
                        + safe
                        + r"{\rPopUp}"
                    )
                else:
                    parts.append(safe)
            subs.events.append(
                pysubs2.SSAEvent(start=start_ms, end=end_ms, style="PopUp", text=" ".join(parts))
            )

    subs.save(str(ass_path), encoding="utf-8")
    return ass_path


def render_pango_caption_rgba(
    chunk: List[Tuple[float, float, str]],
    active_idx: int,
    font_name: str,
    tmp_dir: Path,
    event_id: int,
) -> Optional[np.ndarray]:
    spans = [
        f'<span foreground="#FFFF00">{html.escape(tok)}</span>'
        if j == active_idx
        else f'<span foreground="#FFFFFF">{html.escape(tok)}</span>'
        for j, (_, _, tok) in enumerate(chunk)
    ]
    txt_path = tmp_dir / f"cap_{event_id}.txt"
    png_path = tmp_dir / f"cap_{event_id}.png"
    txt_path.write_text(" ".join(spans), encoding="utf-8")

    env = os.environ.copy()
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"

    subprocess.run(
        [
            "pango-view", "--no-display", "--background=transparent",
            "--markup", f"--font={font_name} Bold 54", "--width=940",
            "--align=center", "--margin=24", "-o", str(png_path), str(txt_path),
        ],
        check=True,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    img = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
    if img is None or img.shape[2] != 4:
        return None

    h, w = img.shape[:2]
    fg_bgr = img[:, :, :3].astype(np.float32)
    fg_a = img[:, :, 3].astype(np.float32) / 255.0

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    outline_a = cv2.dilate(img[:, :, 3], kernel, iterations=1).astype(np.float32) / 255.0
    shadow_a = np.zeros_like(outline_a)
    shadow_a[4:, 4:] = outline_a[:-4, :-4] * 0.55

    bg_a = np.clip(np.maximum(outline_a, shadow_a), 0.0, 1.0)
    out_a = np.clip(fg_a + bg_a * (1.0 - fg_a), 0.0, 1.0)
    out_bgr = np.zeros((h, w, 3), dtype=np.float32)
    mask = out_a > 1e-4
    for c in range(3):
        out_bgr[:, :, c][mask] = (fg_bgr[:, :, c][mask] * fg_a[mask]) / out_a[mask]

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, :3] = np.clip(out_bgr, 0, 255).astype(np.uint8)
    out[:, :, 3] = np.clip(out_a * 255.0, 0, 255).astype(np.uint8)
    return out


def burn_captions_pango_fallback(
    cropped_video: Path,
    words: List[Tuple[float, float, str]],
    captioned_video: Path,
    font_name: str,
    words_per_chunk: int = 3,
    bottom_margin: int = 360,
) -> None:
    events: List[Tuple[float, float, np.ndarray]] = []
    with tempfile.TemporaryDirectory(prefix="ucuts_pango_") as td:
        tmp_dir = Path(td)
        ev_id = 0
        for i in range(0, len(words), words_per_chunk):
            chunk = words[i : i + words_per_chunk]
            for active_idx, (w_start, w_end, _) in enumerate(chunk):
                rgba = render_pango_caption_rgba(chunk, active_idx, font_name, tmp_dir, ev_id)
                if rgba is not None:
                    events.append((w_start, max(w_start + 0.08, w_end), rgba))
                ev_id += 1

    cap = cv2.VideoCapture(str(cropped_video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    writer = cv2.VideoWriter(
        str(captioned_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (OUTPUT_WIDTH, OUTPUT_HEIGHT)
    )

    ev_idx = 0
    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            t = frame_idx / fps
            while ev_idx < len(events) and events[ev_idx][1] < t:
                ev_idx += 1
            if ev_idx < len(events):
                ev_start, ev_end, overlay = events[ev_idx]
                if ev_start <= t <= ev_end:
                    scale = 1.0 + 0.08 * max(0.0, 1.0 - (t - ev_start) / 0.07)
                    ov = (
                        cv2.resize(
                            overlay,
                            (max(1, int(round(overlay.shape[1] * scale))), max(1, int(round(overlay.shape[0] * scale)))),
                            interpolation=cv2.INTER_LINEAR,
                        )
                        if scale > 1.005
                        else overlay
                    )
                    oh, ow = ov.shape[:2]
                    x1 = (OUTPUT_WIDTH - ow) // 2
                    y1 = (OUTPUT_HEIGHT - bottom_margin) - oh
                    fx1, fy1 = max(0, x1), max(0, y1)
                    fx2, fy2 = min(OUTPUT_WIDTH, x1 + ow), min(OUTPUT_HEIGHT, y1 + oh)
                    ox1, oy1 = fx1 - x1, fy1 - y1
                    ox2, oy2 = ox1 + (fx2 - fx1), oy1 + (fy2 - fy1)
                    if fx2 > fx1 and fy2 > fy1:
                        roi = frame[fy1:fy2, fx1:fx2].astype(np.float32)
                        ov_crop = ov[oy1:oy2, ox1:ox2]
                        alpha = ov_crop[:, :, 3:4].astype(np.float32) / 255.0
                        frame[fy1:fy2, fx1:fx2] = np.clip(
                            ov_crop[:, :, :3].astype(np.float32) * alpha + roi * (1.0 - alpha), 0, 255
                        ).astype(np.uint8)
            writer.write(frame)
            frame_idx += 1
    finally:
        cap.release()
        writer.release()


def burn_captions_and_mux(
    cropped_video: Path,
    original_clip: Path,
    ass_path: Path,
    words: List[Tuple[float, float, str]],
    final_output: Path,
    font_name: str,
    work_dir: Path,
    bottom_margin: int = 360,
) -> None:
    if ffmpeg_has_libass():
        escaped_ass = (
            str(ass_path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        )
        video_in = cropped_video
        vf_args = ["-vf", f"ass='{escaped_ass}'"]
    else:
        print("[INFO] FFmpeg lacks libass; using Pango/HarfBuzz caption fallback.", flush=True)
        captioned_video = work_dir / f"{final_output.stem}_captioned.mp4"
        burn_captions_pango_fallback(
            cropped_video, words, captioned_video, font_name, bottom_margin=bottom_margin
        )
        video_in = captioned_video
        vf_args = []

    run_cmd([
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-i", str(original_clip),
        "-map", "0:v:0",
        "-map", "1:a:0?",
        *vf_args,
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest",
        str(final_output),
    ])


def parse_sections(raw: str) -> List[ClipSpec]:
    specs: List[ClipSpec] = []
    for idx, item in enumerate(raw.split(","), start=1):
        item = item.strip()
        if not item:
            continue
        start, end = [part.strip() for part in item.split("-", 1)]
        specs.append(ClipSpec(name=f"reel_{idx}", start=start, end=end))
    return specs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ucuts VOD-to-Shorts CLI pipeline.")
    parser.add_argument("--url", required=True, help="YouTube/Twitch VOD URL or local video path")
    parser.add_argument(
        "--sections",
        default="00:01:30-00:02:30",
        help="Comma-separated HH:MM:SS-HH:MM:SS ranges (e.g. 00:10:40-00:11:40,02:02:01-02:03:01)",
    )
    parser.add_argument("--model", default="small", help="Whisper model size (default: small)")
    parser.add_argument("--language", default="auto", help="Language code (e.g. en, hi, auto)")
    parser.add_argument("--font", default="Noto Sans Devanagari", help="Caption font name")
    parser.add_argument("--output-dir", type=Path, default=Path("reels_output"))
    parser.add_argument("--cookies-from-browser", default=None, help="Browser for yt-dlp cookies")
    parser.add_argument("--avatar-idle", type=Path, default=None)
    parser.add_argument("--avatar-talk", type=Path, default=None)
    parser.add_argument("--avatar-hype", type=Path, default=None)
    parser.add_argument(
        "--avatar-corner",
        default="bottom-left",
        choices=("bottom-left", "bottom-right", "top-left", "top-right"),
    )
    parser.add_argument("--avatar-width", type=int, default=440)
    parser.add_argument("--keep-temp", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    check_dependencies()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = args.output_dir / "_tmp_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    avatars: Dict[str, np.ndarray] = {}
    for key, path in (("idle", args.avatar_idle), ("talk", args.avatar_talk), ("hype", args.avatar_hype)):
        if path and path.exists():
            avatars[key] = chroma_key_border_connected(path, target_width=args.avatar_width)

    language = None if args.language.lower() == "auto" else args.language
    whisper_model = stable_whisper.load_model(args.model)

    specs = parse_sections(args.sections)
    try:
        for spec in specs:
            raw_clip = work_dir / f"{spec.name}_raw.mp4"
            cropped_clip = work_dir / f"{spec.name}_9x16.mp4"
            ass_file = args.output_dir / f"{spec.name}.ass"
            final_reel = args.output_dir / f"{spec.name}.mp4"

            if Path(args.url).exists():
                run_cmd([
                    "ffmpeg", "-y", "-ss", spec.start, "-to", spec.end,
                    "-i", args.url, "-c:v", "libx264", "-c:a", "aac", str(raw_clip),
                ])
            else:
                download_section(args.url, spec.start, spec.end, raw_clip, args.cookies_from_browser)

            track_and_crop_vertical(
                raw_clip, cropped_clip, avatars=avatars or None, avatar_corner=args.avatar_corner
            )
            words = transcribe_words(whisper_model, raw_clip, language=language)
            margin_v = 520 if (avatars and args.avatar_corner.startswith("bottom")) else 360
            build_popup_ass(words, ass_file, font_name=args.font, margin_v=margin_v)
            burn_captions_and_mux(
                cropped_clip, raw_clip, ass_file, words, final_reel, args.font, work_dir, bottom_margin=margin_v
            )
            print(f"[DONE] Saved -> {final_reel}", flush=True)
    finally:
        if not args.keep_temp and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
