#!/usr/bin/env python3
"""Generate a short Ken-Burns-style MP4 loop from a static image.

Usage:
    python scripts/generate_ken_burns_video.py assets/hero.jpg assets/hero-bg.mp4 --duration 10 --fps 15
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def crop_resize(img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    h, w = img.shape[:2]
    src_ratio = w / h
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        # image is wider: crop width
        new_w = int(h * dst_ratio)
        x = (w - new_w) // 2
        cropped = img[:, x : x + new_w]
    else:
        # image is taller: crop height
        new_h = int(w / dst_ratio)
        y = (h - new_h) // 2
        cropped = img[y : y + new_h, :]
    return cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)


def generate(
    input_path: Path,
    output_path: Path,
    duration: float,
    fps: int,
    width: int,
    height: int,
    start_scale: float,
    end_scale: float,
    pan_x: float,
    pan_y: float,
) -> None:
    img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if img is None:
        print(f"Cannot read image: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Prepare an oversized canvas so we can pan/zoom without black borders.
    oversize = max(width, height) * 2
    base = crop_resize(img, oversize, oversize)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        print(f"Cannot open video writer: {output_path}", file=sys.stderr)
        sys.exit(1)

    total_frames = int(duration * fps)
    for i in range(total_frames):
        t = i / max(total_frames - 1, 1)
        scale = start_scale + (end_scale - start_scale) * t
        # center offset in oversized image
        cx = oversize // 2 + int(pan_x * t * oversize)
        cy = oversize // 2 + int(pan_y * t * oversize)
        # crop box
        crop_w = int(width * scale)
        crop_h = int(height * scale)
        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)
        x2 = min(oversize, x1 + crop_w)
        y2 = min(oversize, y1 + crop_h)
        cropped = base[y1:y2, x1:x2]
        frame = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_LINEAR)
        writer.write(frame)

    writer.release()
    print(f"Wrote {total_frames} frames to {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Ken Burns MP4 from an image")
    parser.add_argument("input", type=Path, help="Input image path")
    parser.add_argument("output", type=Path, help="Output MP4 path")
    parser.add_argument("--duration", type=float, default=10, help="Loop duration in seconds")
    parser.add_argument("--fps", type=int, default=15, help="Frames per second")
    parser.add_argument("--width", type=int, default=886, help="Output width")
    parser.add_argument("--height", type=int, default=665, help="Output height")
    parser.add_argument("--start-scale", type=float, default=1.0, help="Start crop scale")
    parser.add_argument("--end-scale", type=float, default=1.12, help="End crop scale")
    parser.add_argument("--pan-x", type=float, default=0.05, help="Horizontal pan fraction")
    parser.add_argument("--pan-y", type=float, default=0.03, help="Vertical pan fraction")
    args = parser.parse_args()

    generate(
        args.input,
        args.output,
        args.duration,
        args.fps,
        args.width,
        args.height,
        args.start_scale,
        args.end_scale,
        args.pan_x,
        args.pan_y,
    )


if __name__ == "__main__":
    main()
