# Ucuts Stage-by-Stage Playbooks & Production Gotchas

Battle-tested CLI patterns, Python snippets, and OS/library workarounds across all 8 stages.

---

## Stage 1 — Targeted VOD Slicing (`yt-dlp`)

Download only the target highlight window instead of pulling a multi-hour VOD:

```bash
yt-dlp \
  --force-overwrites \
  --cookies-from-browser chrome \
  --download-sections "*00:10:40-00:11:40" \
  --force-keyframes-at-cuts \
  -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/best" \
  --merge-output-format mp4 \
  -o "clip_raw.mp4" \
  "https://youtu.be/VIDEO_ID"
```

- **Rate-limit / bot check fix:** If YouTube returns `HTTP Error 429` or `"Sign in to confirm you're not a bot"`, pass `--cookies-from-browser chrome` (or `safari`) and avoid firing rapid duplicate metadata requests.

---

## Stage 2 — Word-Level Transcription (`stable-ts` / `faster-whisper`)

- **Default (`stable-ts`):**
  ```python
  import stable_whisper
  model = stable_whisper.load_model("small")  # use medium or large-v3 for best Hindi
  result = model.transcribe("clip_raw.mp4", language="hi", regroup=True, vad=True)
  ```
- **CPU / Fast Worker alternative (`faster-whisper`):**
  ```python
  from faster_whisper import WhisperModel
  model = WhisperModel("small", device="cpu", compute_type="int8")
  segments, _ = model.transcribe("clip_raw.mp4", language="hi", word_timestamps=True, vad_filter=True)
  ```
- **Gotcha:** Avoid `base` or `tiny` on Hindi/Hinglish gaming audio—loud SFX causes multilingual script hallucinations. Use `small` or larger, or isolate vocals with `Demucs` first.

---

## Stage 3 — Face Tracking, 9:16 Reframing & Corner Streamer Cutout

### OpenCV 5+ Face Detection Fallback
OpenCV 5.0+ removed legacy `cv2.CascadeClassifier`. Always branch cleanly:
```python
if hasattr(cv2, "CascadeClassifier"):
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
else:
    detector = cv2.FaceDetectorYN.create("face_detection_yunet_2023mar.onnx", "", (sw, sh), 0.6, 0.3, 5000)
```

### Norfair 2.x Smooth Camera Lock
- Use `distance_function="mean_euclidean"` (not `"euclidean"`).
- Layer a deadzone (`~28px`) + exponential moving average (`alpha=0.10–0.12`) over Norfair centroids so the 9:16 viewport never jitters.

### Border-Connected Green-Screen Streamer Overlay (Zero Pinholes)
When keying a bright green-screen streamer portrait (`#00FF00`) for a transparent corner overlay:
1. Build a green candidate mask (`HSV` H:35–90, S>=65, V>=50 OR excess green `G - max(R, B) > 32`).
2. Run `cv2.connectedComponents` and remove **only** green components touching the top, left, or right image borders—this prevents dark t-shirt or beard shadows from turning into transparent pinholes.
3. Erode 1px + Gaussian blur 5×5 for soft hair/headset edges, then apply edge-weighted green despill.
4. Drive pose switching (`idle` -> `talk` -> `hype`) and subtle vertical bounce from per-frame audio RMS extracted via FFmpeg (`-f f32le -ac 1 -ar 16000`).

---

## Stage 4 — Audio Cleanup (`Demucs` + `DeepFilterNet`)

Run **only** on trimmed 30–90s clips:

```bash
# 1. Separate commentary vocals from loud game music/SFX
demucs --two-stems=vocals -n htdemucs clip_raw.mp4 -o stems/

# 2. Optional mic denoise (test raw isolated vocals vs. denoised before STT)
deepFilter stems/htdemucs/clip_raw/vocals.wav -o cleaned/
```

---

## Stage 5 — Pop-Up Captions (`pysubs2` + `libass` / Pango Fallback)

- Always set `PlayResX = 1080` and `PlayResY = 1920` in `pysubs2` so font sizes and safe-zone margins scale predictably.
- Place captions at `MarginV = 360` for standard 9:16 clips, or `MarginV = 520–540` when a bottom-corner streamer overlay is present so they never collide.
- **macOS Homebrew FFmpeg Gotcha:** Default Homebrew FFmpeg builds may omit `libass` (`ffmpeg -filters | grep ' ass '`). When `ass` is unavailable, render Pango markup PNGs via `pango-view --markup --background=transparent` with `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8` (for full HarfBuzz Devanagari shaping), add an OpenCV dilated black outline + drop shadow, and composite before FFmpeg H.264/AAC export.

---

## Stage 7 — Selective Polish (`Real-ESRGAN` + `RIFE`)

- Never run super-resolution or frame interpolation on full VODs.
- Apply `Real-ESRGAN` only to cropped facecams or low-bitrate clips `< 720p`.
- Apply `RIFE` only to 3–8 second slow-motion highlight beats.

---

## Stage 8 — Platform-Ready Export Specs

Target specs for YouTube Shorts, Instagram Reels, and TikTok:

```bash
ffmpeg -y -i video_9x16.mp4 -i audio_src.mp4 \
  -map 0:v:0 -map 1:a:0? \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart -shortest \
  final_short.mp4
```
