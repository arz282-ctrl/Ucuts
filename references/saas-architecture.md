# Ucuts SaaS & Agentic AI Clips Generator Architecture

Blueprint for evolving the **Ucuts** 22-tool agent skill into a multi-tenant SaaS product and Agentic AI Clips Generator.

---

## 1. High-Level System Architecture

```text
[User / AI Agent]
   │  (Web UI, REST API, or MCP / LLM Skill)
   ▼
[Web Studio: Next.js + OpenCut + Mediabunny]
   │  - Paste VOD URL or upload recording
   │  - Interactive timeline tweaks & instant client-side preview/export
   ▼
[Control Plane API: FastAPI + Postgres + Redis]
   │  - Auth, credits/Stripe billing, project state, job orchestration
   │  - Agentic Planner (LLM selects highlight windows, layout, caption style, avatar)
   ▼
[Distributed Worker Pools (Celery / Temporal)]
   ├── CPU Pool: yt-dlp ingest, OpenCV/Norfair tracking, pysubs2 + libass, PyAV/FFmpeg export
   └── GPU Pool: Whisper/stable-ts, pyannote-audio, Demucs, DeepFilterNet, Real-ESRGAN, RIFE
   ▼
[Object Storage (S3 / Cloudflare R2) + CDN]
   └── Raw slices, .ass caption tracks, transparent streamer assets, final 9:16 MP4s
```

---

## 2. Mapping the 22 Open-Source Tools to SaaS Services

| SaaS Layer | Open-Source Tools Used | Scaling Strategy |
| --- | --- | --- |
| **Ingest Service** | `yt-dlp`, `OBS Studio` (creator plugin/companion) | Stateless CPU workers; range-download only candidate windows; cache source chunks in R2. |
| **Highlight & Transcript Engine** | `AI Shorts Generator`, `Whisper`, `whisper.cpp`, `stable-ts`, `pyannote-audio` | GPU batch workers (`faster-whisper` / `stable-ts`) + LLM viral-hook scoring over diarized transcripts. |
| **Smart Reframe & Avatar Engine** | `OpenCV`, `Norfair`, `Supervision` | CPU workers for face/speaker lock, split-screen gaming templates, and reactive green-screen streamer overlays. |
| **Audio Mastering Service** | `Demucs`, `DeepFilterNet` | On-demand GPU step triggered only for noisy single-track gaming/podcast clips; `-14 LUFS` loudnorm at mux. |
| **Caption & Brand Engine** | `pysubs2`, `libass` | Brand-kit presets (fonts, safe zones, pop-up highlight colors, Hinglish/Devanagari/RTL shaping). |
| **Browser Studio & Programmatic Edit** | `OpenCut`, `Editly`, `Mediabunny` | Users tweak AI-generated cuts in `OpenCut`, batch-render templates with `Editly`, or export in-browser via `Mediabunny`. |
| **Pro Polish Add-On (Paid Tier)** | `Real-ESRGAN`, `RIFE` | Metered GPU add-on for 4K facecam upscale and 120fps slow-mo replays. |
| **Media I/O Core** | `PyAV` | Unified Python FFmpeg bindings inside worker containers for deterministic encoding. |

---

## 3. Agent-Native Distribution (Dual Surface)

1. **Agent Skill (`SKILL.md`):** Any LLM or coding agent installs `arz282-ctrl/Ucuts` in one prompt to run local or cloud-backed clipping workflows immediately.
2. **Hosted MCP Server (`ucuts-mcp`):** Expose `ucuts_analyze_vod`, `ucuts_generate_shorts`, `ucuts_apply_streamer_overlay`, and `ucuts_export_reel` so external AI agents can trigger Ucuts SaaS jobs programmatically with API keys and credit metering.

---

## 4. Phased Launch Roadmap

- **Phase 1 (Current — v1.0):** Unified 22-tool Agent Skill (`SKILL.md` + `references/` + working CLI pipeline `scripts/ucuts_pipeline.py`).
- **Phase 2 (MVP SaaS):** FastAPI job orchestrator + GPU worker container (Whisper + OpenCV/Norfair + libass) + Next.js dashboard with paste-URL-to-3-Reels flow.
- **Phase 3 (Creator Studio):** Embed `OpenCut` + `Mediabunny` for browser timeline editing, custom streamer avatar packs, and brand caption kits.
- **Phase 4 (Agentic API & Marketplace):** Hosted Ucuts MCP server, webhook publishing to YouTube Shorts/Instagram/TikTok, and usage-based Stripe billing.
