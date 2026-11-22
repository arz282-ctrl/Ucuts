# Ucuts 22-Tool Open-Source Catalog

Complete reference of all 22 open-source repositories integrated into the **Ucuts** VOD-to-Shorts & Agentic AI Clips Generator stack, organized across 8 pipeline stages.

---

## Stage 1 — Grab (Ingest & Capture)

1. **yt-dlp** — Pulls any VOD, livestream, or timestamped clip
   - Repository: https://github.com/yt-dlp/yt-dlp
   - Runtime: Python CLI
   - Install: `pip install yt-dlp`
   - Role: Download targeted timestamp slices (`--download-sections "*00:10:40-00:11:40" --force-keyframes-at-cuts`) without downloading multi-hour VODs.

2. **OBS Studio** — Local gameplay + facecam capture
   - Repository: https://github.com/obsproject/obs-studio
   - Runtime: Desktop app (C/C++)
   - Role: Capture live streams or local recordings with multi-track audio (Track 1: mic, Track 2: game audio) so downstream cleanup and transcription stay clean.

---

## Stage 2 — Find the Moment (Transcribe, Diarize & Rank Highlights)

3. **AI Shorts Generator** — Automated highlight discovery + 9:16 auto-crop
   - Repository: https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator
   - Runtime: Python
   - Role: End-to-end open-source alternative to paid clipping SaaS using Whisper transcription + LLM highlight scoring + vertical reframing.

4. **Whisper** — Multilingual speech-to-text transcription
   - Repository: https://github.com/openai/whisper
   - Runtime: Python / PyTorch
   - Install: `pip install openai-whisper`
   - Role: Accurate speech recognition across 99+ languages (use `small`/`medium`/`large-v3` for Hindi & Hinglish gaming commentary).

5. **whisper.cpp** — Offline CPU/Apple Silicon transcription
   - Repository: https://github.com/ggml-org/whisper.cpp
   - Runtime: C/C++ (Metal / CoreML / CUDA)
   - Role: Fast, low-memory local transcription on laptops and edge servers without PyTorch overhead.

6. **stable-ts** — Word-level forced alignment for pop-up captions
   - Repository: https://github.com/jianfch/stable-ts
   - Runtime: Python
   - Install: `pip install stable-ts`
   - Role: Dynamic Time Warping + Silero VAD timestamp refinement for tight word-by-word caption sync. *(Note: archived upstream; pin tested versions.)*

7. **pyannote-audio** — Speaker diarization ("who is talking when")
   - Repository: https://github.com/pyannote/pyannote-audio
   - Runtime: Python / PyTorch
   - Install: `pip install pyannote.audio`
   - Role: Labels speaker turns in multi-person podcasts or co-op streams so active-speaker reframing and captions follow whoever is talking.

---

## Stage 3 — Track + Crop (9:16 Reframing & Face Lock)

8. **OpenCV** — Core video I/O, cropping, chroma-key, and compositing
   - Repository: https://github.com/opencv/opencv
   - Runtime: Python / C++
   - Install: `pip install opencv-python`
   - Role: Frame reading, 9:16 (`1080x1920`) cropping, YuNet (`FaceDetectorYN`) face detection on OpenCV 5+, split-screen layouts, and green-screen streamer cutouts.

9. **Supervision** — Detection utilities and visual debugging overlays
   - Repository: https://github.com/roboflow/supervision
   - Runtime: Python
   - Install: `pip install supervision`
   - Role: Clean detection wrappers, bounding-box/label annotators, and zone utilities for CV pipelines.

10. **Norfair** — Lightweight multi-object face tracker
    - Repository: https://github.com/tryolabs/norfair
    - Runtime: Python
    - Install: `pip install norfair`
    - Role: Maintains stable subject IDs across frames (`distance_function="mean_euclidean"`) so EMA smoothing + deadzone logic keeps the 9:16 camera smooth.

---

## Stage 4 — Audio (Voice Isolation & Mic Cleanup)

11. **DeepFilterNet** — Full-band (48 kHz) mic noise suppression
    - Repository: https://github.com/Rikorose/DeepFilterNet
    - Runtime: Rust / Python
    - Install: `pip install deepfilternet`
    - Role: Removes keyboard clatter, fan hum, and room noise from commentary tracks.

12. **Demucs** — Hybrid Transformer vocal/music source separation
    - Repository: https://github.com/facebookresearch/demucs
    - Runtime: Python / PyTorch
    - Install: `pip install demucs`
    - Role: Separates commentary vocals (`htdemucs`) from loud game SFX/music when both are baked into a single stereo track. *(Note: archived upstream; pin versions.)*

---

## Stage 5 — Captions (Styling & Burning)

13. **pysubs2** — Programmatic `.ass` / `.srt` caption generator
    - Repository: https://github.com/tkarabela/pysubs2
    - Runtime: Python
    - Install: `pip install pysubs2`
    - Role: Converts word-level timestamps into styled SubStation Alpha (`.ass`) files with explicit `PlayResX: 1080`, `PlayResY: 1920`, pop-up color highlights, and scale bounce.

14. **libass** — Portable ASS/SSA subtitle renderer
    - Repository: https://github.com/libass/libass
    - Runtime: C library (integrated into FFmpeg `ass=` filter)
    - Role: Renders crisp outlines, drop shadows, animations, and custom fonts (including Indic/Devanagari via HarfBuzz) directly onto exported video frames.

---

## Stage 6 — Edit (Timeline & Programmatic Assembly)

15. **OpenCut** — Open-source browser timeline editor
    - Repository: https://github.com/OpenCut-app/OpenCut
    - Runtime: TypeScript / Next.js
    - Role: CapCut-style web timeline editor; ideal frontend foundation for the **Ucuts SaaS** visual studio.

16. **Editly** — Declarative code-driven video assembly
    - Repository: https://github.com/mifi/editly
    - Runtime: Node.js / FFmpeg
    - Install: `npm install -g editly`
    - Role: Builds repeatable multi-clip edits, transitions, overlays, and audio mixes from JSON specs.

17. **Kdenlive** — Desktop non-linear editor for keyframe-heavy cuts
    - Repository: https://github.com/KDE/kdenlive
    - Runtime: Desktop app (Qt / MLT)
    - Role: Manual final polish, complex keyframed punch-ins, and multi-track effects.

18. **Shotcut** — Lightweight cross-platform track mixer & editor
    - Repository: https://github.com/mltframework/shotcut
    - Runtime: Desktop app (Qt / MLT)
    - Role: Fast multi-track audio/video mixing and filter chains on desktop.

---

## Stage 7 — Polish (Super-Resolution & Frame Interpolation)

19. **Real-ESRGAN** — AI video/image super-resolution
    - Repository: https://github.com/xinntao/Real-ESRGAN
    - Runtime: Python / PyTorch (or ncnn-vulkan)
    - Role: Rescues blurry zoomed-in facecams or low-bitrate cropped VOD segments on trimmed final clips.

20. **RIFE (ECCV2022-RIFE)** — Real-time frame interpolation for slow-mo
    - Repository: https://github.com/hzwer/ECCV2022-RIFE
    - Runtime: Python / PyTorch
    - Role: Generates smooth 2x–4x slow-motion replays for clutch gameplay highlights.

---

## Stage 8 — Export (Encoding & Client-Side Packaging)

21. **PyAV** — Pythonic FFmpeg library bindings
    - Repository: https://github.com/PyAV-Org/PyAV
    - Runtime: Python / Cython
    - Install: `pip install av`
    - Role: High-throughput programmatic demuxing, frame processing, and H.264/AAC encoding inside Python workers.

22. **Mediabunny** — Pure TypeScript browser media toolkit
    - Repository: https://github.com/Vanilagy/mediabunny
    - Runtime: TypeScript / WebCodecs
    - Install: `npm install mediabunny`
    - Role: Client-side browser conversion, muxing, and export without server round-trips—pairs directly with `OpenCut` in the Ucuts SaaS frontend.
