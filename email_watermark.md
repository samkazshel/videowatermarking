# Email Watermark Tool

Overlay an email address onto a video at a configurable opacity. The email appears in each of the video's 4 corners, one corner per quarter of the video's duration, in a random order.

## Requirements

- Python 3.8+
- ffmpeg + ffprobe on PATH

## Installation

No Python dependencies required. Just ensure ffmpeg is installed:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

## Basic Usage

```bash
python email_watermark.py <input_video> <email_address>
```

### Examples

```bash
# Basic usage - creates input_watermarked.mp4
python email_watermark.py video.mp4 user@example.com

# Specify output filename
python email_watermark.py video.mp4 user@example.com -o watermarked.mp4

# Convert between formats
python email_watermark.py video.avi user@example.com -o out.mp4
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output PATH` | Output file path | `<input>_watermarked.<ext>` |
| `--opacity FLOAT` | Watermark opacity (0-1) | 0.45 |
| `--fontsize INT` | Font size in pixels | 28 |
| `--seed INT` | Random seed for reproducible corner order | random |

### Opacity

Controls how transparent the watermark text appears.

```bash
# More visible (70% opacity)
python email_watermark.py video.mp4 user@example.com --opacity 0.7

# Less visible (25% opacity)
python email_watermark.py video.mp4 user@example.com --opacity 0.25
```

### Font Size

Adjust the text size if the watermark is too small or large for your video.

```bash
# Larger text
python email_watermark.py video.mp4 user@example.com --fontsize 48

# Smaller text
python email_watermark.py video.mp4 user@example.com --fontsize 18
```

### Reproducible Corner Order

By default, the corner order is random each run. Use `--seed` to get the same order every time.

```bash
# Same corner order every time
python email_watermark.py video.mp4 user@example.com --seed 42
```

## Supported Formats

Input: mp4, mov, mkv, webm, avi, m4v, mpg, ts, gif, and any other format ffmpeg supports.

Output format is determined by the file extension:
- `.mp4` - H.264 video with AAC audio
- `.mov` - H.264 video with AAC audio
- `.mkv` - H.264 video with AAC audio
- `.webm` - VP9 video with Opus audio
- `.avi` - H.264 video with MP3 audio
- `.gif` - GIF animation (no audio)

## Video Encode Settings

The tool uses these encoding settings by default (from `Standrad Video Encode.json`):

| Parameter | Value |
|-----------|-------|
| Preset | fast |
| Profile | main |
| Level | 4.0 |
| CRF | 36 |
| Pixel Format | yuv420p |
| Optimize for MP4 | yes (faststart) |

## How It Works

1. The video is analyzed to determine duration
2. The email address is randomly placed in one corner per quarter of the video
3. Each corner shows for approximately 1/4 of the total duration
4. The watermark cycles through all 4 corners before stopping
5. Audio is preserved or re-encoded as needed

## Troubleshooting

**"ffprobe could not read" error**
- Ensure ffmpeg and ffprobe are installed and on your PATH
- Verify the input file exists and is a valid video file

**Watermark not visible**
- Try increasing opacity: `--opacity 0.6` or higher
- Try increasing fontsize: `--fontsize 48`

**Output file too large**
- Use a slower preset: edit the CODECS dict in the script
- Lower quality: increase CRF value (e.g., `--crf 40`)

**Audio issues in output**
- For WebM output, audio may be re-encoded to Opus
- For GIF output, audio is stripped entirely
