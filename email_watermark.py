#!/usr/bin/env python3
"""
email_watermark.py — Overlay an email address onto a video at 20% opacity.

The email is shown in each of the video's 4 corners, one corner per quarter
of the video's duration, in a random order.

Works with any input format ffmpeg can read (mp4, mov, mkv, webm, avi,
m4v, mpg, ts, gif, ...). The output format is chosen from the output file
extension, so you can also convert between formats:

    python email_watermark.py clip.mov user@example.com              # -> clip_watermarked.mov
    python email_watermark.py clip.avi user@example.com -o out.mp4   # avi in, mp4 out
    python email_watermark.py clip.webm user@example.com             # keeps webm (VP9/Opus)

Requires: ffmpeg + ffprobe on PATH. No Python dependencies.
"""

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PADDING = 20  # px from the edges
BAR_WIDTH = 36

# Corner name -> (x expression, y expression) using ffmpeg drawtext variables
CORNERS = {
    "top-left":     (f"{PADDING}", f"{PADDING}"),
    "top-right":    (f"w-tw-{PADDING}", f"{PADDING}"),
    "bottom-left":  (f"{PADDING}", f"h-th-{PADDING}"),
    "bottom-right": (f"w-tw-{PADDING}", f"h-th-{PADDING}"),
}

VIDEO_ENCODE_SETTINGS = {
    "preset": "fast",
    "profile": "main",
    "level": "4.0",
    "crf": 36,
    "tune": "",
    "extra": "",
    "optimize": True,
}

# Output extension -> (video codec args, audio codec args)
CODECS = {
    ".mp4":  (["-c:v", "libx264", "-preset", VIDEO_ENCODE_SETTINGS["preset"],
               "-profile:v", VIDEO_ENCODE_SETTINGS["profile"],
               "-level", VIDEO_ENCODE_SETTINGS["level"],
               "-crf", str(VIDEO_ENCODE_SETTINGS["crf"]),
               "-pix_fmt", "yuv420p"] + (["-movflags", "+faststart"] if VIDEO_ENCODE_SETTINGS["optimize"] else []),
              ["-c:a", "aac"]),
    ".m4v":  (["-c:v", "libx264", "-preset", VIDEO_ENCODE_SETTINGS["preset"],
               "-profile:v", VIDEO_ENCODE_SETTINGS["profile"],
               "-level", VIDEO_ENCODE_SETTINGS["level"],
               "-crf", str(VIDEO_ENCODE_SETTINGS["crf"]),
               "-pix_fmt", "yuv420p"],
              ["-c:a", "aac"]),
    ".mov":  (["-c:v", "libx264", "-preset", VIDEO_ENCODE_SETTINGS["preset"],
               "-profile:v", VIDEO_ENCODE_SETTINGS["profile"],
               "-level", VIDEO_ENCODE_SETTINGS["level"],
               "-crf", str(VIDEO_ENCODE_SETTINGS["crf"]),
               "-pix_fmt", "yuv420p"],
              ["-c:a", "aac"]),
    ".mkv":  (["-c:v", "libx264", "-preset", VIDEO_ENCODE_SETTINGS["preset"],
               "-profile:v", VIDEO_ENCODE_SETTINGS["profile"],
               "-level", VIDEO_ENCODE_SETTINGS["level"],
               "-crf", str(VIDEO_ENCODE_SETTINGS["crf"]),
               "-pix_fmt", "yuv420p"],
              ["-c:a", "aac"]),
    ".webm": (["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32"], ["-c:a", "libopus"]),
    ".avi":  (["-c:v", "libx264", "-preset", VIDEO_ENCODE_SETTINGS["preset"],
               "-profile:v", VIDEO_ENCODE_SETTINGS["profile"],
               "-level", VIDEO_ENCODE_SETTINGS["level"],
               "-crf", str(VIDEO_ENCODE_SETTINGS["crf"]),
               "-pix_fmt", "yuv420p"],
              ["-c:a", "libmp3lame"]),
    ".gif":  (["-c:v", "gif"], []),
}
DEFAULT_CODECS = (["-c:v", "libx264", "-preset", VIDEO_ENCODE_SETTINGS["preset"],
                   "-profile:v", VIDEO_ENCODE_SETTINGS["profile"],
                   "-level", VIDEO_ENCODE_SETTINGS["level"],
                   "-crf", str(VIDEO_ENCODE_SETTINGS["crf"]),
                   "-pix_fmt", "yuv420p"],
                  ["-c:a", "aac"])

# Containers where copying the source audio untouched is usually safe.
AUDIO_COPY_SAFE = {".mkv", ".mov", ".mp4", ".m4v"}


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def check_dependencies():
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(f"'{tool}' not found on PATH. Please install ffmpeg.")


def probe(video: Path) -> dict:
    """Return duration and stream info for the input file."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=codec_type,codec_name",
            "-of", "json",
            str(video),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        die(f"ffprobe could not read '{video}':\n{result.stderr.strip()}")
    data = json.loads(result.stdout)

    streams = data.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not has_video:
        die(f"'{video}' contains no video stream")

    try:
        duration = float(data["format"]["duration"])
    except (KeyError, ValueError):
        die(f"could not determine duration of '{video}' (is it a live stream?)")

    return {"duration": duration, "has_audio": has_audio}


def escape_drawtext(text: str) -> str:
    """Escape characters that are special inside a drawtext text= value."""
    for ch in ("\\", ":", "'", "%"):
        text = text.replace(ch, "\\" + ch)
    return text


def build_filter(email: str, duration: float, opacity: float, fontsize: int, seed=None):
    rng = random.Random(seed)
    order = list(CORNERS.keys())
    rng.shuffle(order)

    quarter = duration / 4.0
    text = escape_drawtext(email)

    parts = []
    for i, corner in enumerate(order):
        x, y = CORNERS[corner]
        start = i * quarter
        # Last segment runs past the end to avoid rounding gaps
        end = duration + 1 if i == 3 else (i + 1) * quarter
        parts.append(
            f"drawtext=text='{text}'"
            f":fontcolor=white:alpha={opacity}"
            f":fontsize={fontsize}"
            f":x={x}:y={y}"
            f":enable='between(t,{start:.3f},{end:.3f})'"
        )
    return ",".join(parts), order


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def draw_bar(fraction: float, elapsed: float):
    fraction = min(max(fraction, 0.0), 1.0)
    filled = int(BAR_WIDTH * fraction)
    bar = "#" * filled + "-" * (BAR_WIDTH - filled)
    if 0 < fraction < 1:
        eta = elapsed * (1 - fraction) / fraction
        tail = f"elapsed {fmt_time(elapsed)}  eta {fmt_time(eta)}"
    else:
        tail = f"elapsed {fmt_time(elapsed)}" + " " * 12
    sys.stdout.write(f"\r[{bar}] {fraction * 100:5.1f}%  {tail}")
    sys.stdout.flush()


def run_ffmpeg(video: Path, output: Path, vf: str, audio_args, duration: float):
    """Run ffmpeg, rendering a progress bar. Returns (returncode, stderr_text)."""
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-nostats",
        "-progress", "pipe:1",
        "-i", str(video), "-vf", vf,
    ]
    vcodec, _ = CODECS.get(output.suffix.lower(), DEFAULT_CODECS)
    cmd += vcodec + audio_args + [str(output)]

    start = time.monotonic()
    with tempfile.TemporaryFile(mode="w+") as errf:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf, text=True)
        draw_bar(0.0, 0.0)
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_us="):
                value = line.split("=", 1)[1]
                if value.isdigit():
                    done = int(value) / 1_000_000
                    draw_bar(done / duration, time.monotonic() - start)
            elif line == "progress=end":
                draw_bar(1.0, time.monotonic() - start)
        proc.wait()
        errf.seek(0)
        stderr = errf.read()
    print()  # move past the progress bar line
    return proc.returncode, stderr


def main():
    parser = argparse.ArgumentParser(
        description="Overlay an email watermark on a video, rotating through the 4 corners."
    )
    parser.add_argument("video", type=Path, help="Path to the input video (any ffmpeg-readable format)")
    parser.add_argument("email", help="Email address to overlay")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output path; its extension picks the format "
                             "(default: <input>_watermarked.<same ext>)")
    parser.add_argument("--opacity", type=float, default=0.45,
                        help="Watermark opacity 0-1 (default: 0.45)")
    parser.add_argument("--fontsize", type=int, default=28,
                        help="Font size in px (default: 28)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible corner order")
    args = parser.parse_args()

    check_dependencies()

    if not args.video.is_file():
        die(f"input video not found: {args.video}")
    if not (0.0 < args.opacity <= 1.0):
        die("--opacity must be between 0 and 1")

    output = args.output or args.video.with_name(
        f"{args.video.stem}_watermarked{args.video.suffix or '.mp4'}"
    )
    ext = output.suffix.lower()

    info = probe(args.video)
    duration = info["duration"]
    vf, order = build_filter(args.email, duration, args.opacity, args.fontsize, args.seed)

    print(f"Input:     {args.video}")
    print(f"Duration:  {duration:.2f}s (each corner shown ~{duration / 4:.2f}s)")
    print(f"Corners:   {' -> '.join(order)}")
    print(f"Output:    {output}")

    _, audio_encode = CODECS.get(ext, DEFAULT_CODECS)

    if not info["has_audio"] or ext == ".gif":
        code, stderr = run_ffmpeg(args.video, output, vf,
                                  ["-an"] if ext == ".gif" else [], duration)
    elif ext in AUDIO_COPY_SAFE:
        # Try passing audio through untouched first; fall back to re-encoding
        code, stderr = run_ffmpeg(args.video, output, vf, ["-c:a", "copy"], duration)
        if code != 0:
            print("note: audio passthrough failed, re-encoding audio instead")
            code, stderr = run_ffmpeg(args.video, output, vf, audio_encode, duration)
    else:
        code, stderr = run_ffmpeg(args.video, output, vf, audio_encode, duration)

    if code != 0:
        die(f"ffmpeg failed:\n{stderr[-2000:]}")

    print("Done.")


if __name__ == "__main__":
    main()
