---
name: ucuts
description: Unified 22-tool open-source VOD-to-Shorts & Agentic AI Clips Generator skill. Use whenever a user asks to clip YouTube/Twitch/local VODs or streams into vertical 9:16 Reels/Shorts/TikToks, detect viral highlights, track faces or active speakers, composite green-screen gaming streamer overlays, isolate voice from game music, clean mic noise, generate word-level pop-up captions, upscale or slow-mo clips, or architect an agentic AI video-clipping SaaS.
version: 1.0.0
license: MIT
---

# Ucuts — Unified 22-Tool VOD-to-Shorts & Agentic AI Clips Skill

Orchestrate an end-to-end open-source video-clipping pipeline (`Stream/VOD in -> Highlight -> Track & Crop 9:16 -> Audio Cleanup -> Pop-Up Captions -> Edit & Polish -> Export`) powered by 22 specialized open-source repositories.

## Quick Routing (8-Stage Default Stack)

| Stage | Default Tool(s) | Escape Hatch / Alternative | Reference |
| --- | --- | --- | --- |
| **1. Grab** | `yt-dlp` (VODs/URLs), `OBS Studio` (live capture) | `--download-sections` to avoid pulling multi-hour VODs | `references/tools-catalog.md` |
| **2. Find the Moment** | `Whisper` + `stable-ts` (word alignment), `AI Shorts Generator` (auto-rank) | `whisper.cpp` (CPU laptops), `pyannote-audio` (multi-speaker podcasts) | `references/stage-playbooks.md` |
| **3. Track + Crop** | `OpenCV` + `Norfair` (EMA smoothing + deadzone) | `Supervision` (bounding-box debug overlays), YuNet (`FaceDetectorYN`) on OpenCV 5+ | `references/stage-playbooks.md` |
| **4. Audio** | `DeepFilterNet` (mic cleanup), `Demucs` (voice vs. game music) | Separate OBS audio tracks at capture time to skip Demucs | `references/stage-playbooks.md` |
| **5. Captions** | `pysubs2` (`.ass` styling) + `libass` (FFmpeg `ass=` filter) | Pango/HarfBuzz PNG compositor fallback if FFmpeg lacks `libass` | `references/stage-playbooks.md` |
| **6. Edit** | `Editly` (code/JSON batch edits), `OpenCut` (browser timeline) | `Kdenlive` (keyframe desktop cuts), `Shotcut` (lightweight track mixing) | `references/tools-catalog.md` |
| **7. Polish** | `Real-ESRGAN` (upscale blurry crops), `RIFE` (smooth slow-mo) | Run **only** on trimmed final clips, never on full VODs | `references/stage-playbooks.md` |
| **8. Export** | `PyAV` / `FFmpeg` (`1080x1920`, H.264/AAC, `-14 LUFS`) | `Mediabunny` (client-side browser conversion/export) | `references/stage-playbooks.md` |

## Bundled Resources

Read only the reference file needed for the current task to keep context lean:

- `references/tools-catalog.md` — Complete directory of all 22 upstream GitHub repositories, roles, install commands, and maintenance notes.
- `references/stage-playbooks.md` — Exact CLI/Python patterns, green-screen streamer overlay compositing, and battle-tested OS/library workarounds.
- `references/saas-architecture.md` — Full-stack blueprint for launching **Ucuts** as a multi-tenant SaaS & Agentic AI Clips Generator.
- `scripts/ucuts_pipeline.py` — Production-tested Python CLI that executes Stages 1, 2, 3, 5, and 8 end-to-end (including audio-reactive green-screen corner streamer overlay).
- `scripts/animate_streamer_gif.py` — Builds a seamless looping green-screen streamer GIF from 3 expression frames (focused, talking, hyped).

## Standard Execution Workflow

1. **Inspect target & constraints first:** Confirm source (URL or local file), target clip timestamps or auto-highlight mode, language/script (e.g., English, Hindi Devanagari, Hinglish), and framing style (full-screen face-tracked 9:16, split-screen gameplay + facecam, or transparent green-screen corner streamer overlay).
2. **Slice before heavy compute:** Always use `yt-dlp --download-sections "*HH:MM:SS-HH:MM:SS" --force-keyframes-at-cuts` (or FFmpeg trim) before running Whisper, Demucs, Real-ESRGAN, or RIFE.
3. **Run the bundled pipeline (`scripts/ucuts_pipeline.py`):**
   ```bash
   python3 scripts/ucuts_pipeline.py \
     --url "https://youtu.be/VIDEO_ID" \
     --reels 1,2,3 \
     --model small \
     --language hi \
     --cookies-from-browser chrome \
     --avatar-idle focused.jpg --avatar-talk talking.jpg --avatar-hype hyped.jpg \
     --avatar-corner bottom-left
   ```
4. **Verify output specs before delivery:** Confirm `1080x1920` (9:16), H.264 (`yuv420p`), AAC `192k`, `-14 LUFS` loudnorm, `+faststart`, and visually inspect at least one rendered frame per reel to verify caption alignment and green-screen edges.

## Critical Production Gotchas

- **OpenCV 5+ removed `cv2.CascadeClassifier`:** Detect `hasattr(cv2, "CascadeClassifier")` and automatically fall back to `cv2.FaceDetectorYN` (YuNet ONNX, ~230 KB).
- **Norfair 2.x distance function name:** Use `distance_function="mean_euclidean"` (not `"euclidean"`, which raises `ValueError`).
- **Homebrew FFmpeg on macOS often lacks `libass`:** Check `ffmpeg -filters` for `ass`; if absent, render styled captions with `pango-view` (with `LANG=en_US.UTF-8` for Indic/Devanagari HarfBuzz shaping) and composite via OpenCV while still exporting the `.ass` file.
- **Green-screen corner cutouts without interior pinholes:** Use border-connected `cv2.connectedComponents` on the green mask so dark shirt/face shadows never turn transparent, then apply edge-only green despill.
- **YouTube `HTTP 429` / bot checks on sequential downloads:** Pass `--cookies-from-browser chrome` (or `safari`) and `--force-overwrites` to `yt-dlp`.
- **Hindi/multilingual transcription accuracy:** Whisper `base` frequently hallucinates non-Hindi scripts over loud game SFX; use `small`, `medium`, or `large-v3` (or isolate vocals first with `Demucs`).
- **Upstream maintenance:** `stable-ts` and `facebookresearch/demucs` are archived upstream—pin tested versions in a dedicated virtual environment.
