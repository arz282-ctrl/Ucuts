# Ucuts

**About:** Unified 22-tool open-source VOD-to-Shorts skill and Agentic AI Clips Generator engine for turning long-form streams and videos into vertical 9:16 Reels, Shorts, and TikToks.

## Description

Ucuts combines 22 specialized open-source media, speech, computer-vision, and editing projects into one universal Agent Skill (`SKILL.md` + `references/` + `scripts/`). Any LLM or AI coding agent can install it in a single command (`npx skills add arz282-ctrl/Ucuts`), and it serves as the core engine for the upcoming **Ucuts SaaS & Agentic AI Clips Generator**.

## Install

### Agent Skills CLI (Claude Code, Cursor, Codex, OpenClaw, Gemini)
```bash
npx skills add arz282-ctrl/Ucuts
```

### Local Python Setup
```bash
git clone https://github.com/arz282-ctrl/Ucuts.git
cd Ucuts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Quickstart CLI

```bash
python3 scripts/ucuts_pipeline.py \
  --url "https://youtu.be/VIDEO_ID" \
  --sections "00:10:40-00:11:40,02:02:01-02:03:01" \
  --model small --language hi --cookies-from-browser chrome \
  --avatar-idle focused.jpg --avatar-talk talking.jpg --avatar-hype hyped.jpg \
  --avatar-corner bottom-left
```

## The 22-Tool Open-Source Stack

| Stage | Tools |
| --- | --- |
| **1. Grab** | `yt-dlp`, `OBS Studio` |
| **2. Find the Moment** | `AI Shorts Generator`, `Whisper`, `whisper.cpp`, `stable-ts`, `pyannote-audio` |
| **3. Track + Crop** | `OpenCV`, `Supervision`, `Norfair` |
| **4. Audio** | `DeepFilterNet`, `Demucs` |
| **5. Captions** | `pysubs2`, `libass` |
| **6. Edit** | `OpenCut`, `Editly`, `Kdenlive`, `Shotcut` |
| **7. Polish** | `Real-ESRGAN`, `RIFE` |
| **8. Export** | `PyAV`, `Mediabunny` |

## License

MIT — see `LICENSE`. All 22 upstream repositories retain their respective open-source licenses.
