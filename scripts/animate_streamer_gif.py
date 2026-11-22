#!/usr/bin/env python3
"""
Animate 3 pixel-locked green-screen gaming streamer poses (idle, talk, hype)
into a seamless looping GIF using FFmpeg 2-pass palettegen/paletteuse.

Usage:
    python3 scripts/animate_streamer_gif.py \
      --idle focused.jpg --talk talking.jpg --hype hyped.jpg \
      --output gaming_streamer_animated.gif
"""

from __future__ import annotations

import argparse
import math
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def load_bgr(path: Path, size: int) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)


def blend_bgr(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    t = float(np.clip(t, 0.0, 1.0))
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    return np.clip(a.astype(np.float32) * (1.0 - t) + b.astype(np.float32) * t, 0, 255).astype(np.uint8)


def pose_for_time(t: float, idle: np.ndarray, talk: np.ndarray, hype: np.ndarray) -> tuple[np.ndarray, float]:
    fade = 0.14
    if t < 0.75 - fade:
        return idle, 0.15
    if t < 0.75:
        u = (t - (0.75 - fade)) / fade
        return blend_bgr(idle, talk, u), 0.15 + 0.45 * u
    if t < 1.75 - fade:
        return talk, 0.60
    if t < 1.75:
        u = (t - (1.75 - fade)) / fade
        return blend_bgr(talk, hype, u), 0.60 + 0.40 * u
    if t < 3.05 - fade:
        return hype, 1.00
    if t < 3.05:
        u = (t - (3.05 - fade)) / fade
        return blend_bgr(hype, talk, u), 1.00 - 0.40 * u
    if t < 3.70 - fade:
        return talk, 0.60
    if t < 3.70:
        u = (t - (3.70 - fade)) / fade
        return blend_bgr(talk, idle, u), 0.60 - 0.45 * u
    return idle, 0.15


def animate_frame(bgr: np.ndarray, t: float, duration: float, energy: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    phase = 2.0 * math.pi * (t / duration)
    dy = 2.0 * math.sin(phase * 2.0) - 4.0 * energy * abs(math.sin(phase * 6.0)) + 3.0
    dx = 2.0 * math.sin(phase)
    angle_deg = 0.85 * energy * math.sin(phase * 3.0)
    scale = 1.035 + 0.018 * energy * (0.5 + 0.5 * math.sin(phase * 4.0))

    M = cv2.getRotationMatrix2D((w * 0.5, h * 0.96), angle_deg, scale)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a looping green-screen streamer GIF.")
    parser.add_argument("--idle", type=Path, required=True)
    parser.add_argument("--talk", type=Path, required=True)
    parser.add_argument("--hype", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("gaming_streamer_animated.gif"))
    parser.add_argument("--size", type=int, default=480)
    parser.add_argument("--fps", type=int, default=18)
    parser.add_argument("--duration", type=float, default=4.0)
    args = parser.parse_args()

    idle = load_bgr(args.idle, args.size)
    talk = load_bgr(args.talk, args.size)
    hype = load_bgr(args.hype, args.size)
    num_frames = int(args.fps * args.duration)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i in range(num_frames):
            t = i / args.fps
            base, energy = pose_for_time(t, idle, talk, hype)
            cv2.imwrite(str(tmp / f"frame_{i:04d}.png"), animate_frame(base, t, args.duration, energy))

        palette = tmp / "palette.png"
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(tmp / "frame_%04d.png"),
             "-vf", "palettegen=stats_mode=diff", str(palette)],
            check=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(tmp / "frame_%04d.png"),
             "-i", str(palette), "-lavfi", "paletteuse=dither=sierra2_4a", "-loop", "0", str(args.output)],
            check=True,
        )
    print(f"[DONE] Saved animated GIF -> {args.output}")


if __name__ == "__main__":
    main()
