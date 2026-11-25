# Faceless Shorts for Google Antigravity

Narrated faceless shorts (YouTube Shorts, TikTok, Reels) made 100% in code on your computer:
script, local AI voice, word-synced captions, animation, sound effects, and music, rendered to MP4.
No paid AI video generation, no external API keys, no credits.

---

## 6 Visual Styles Included

1. **Deep Dive 3D** (Flagship): Zack D. Films-like 3D medical and science explainers with glowing x-ray anatomy and shallow depth-of-field.
2. **Night File 3D**: Unsolved mysteries and true-crime cases in dark 3D rooms with dramatic spotlighting.
3. **Inside Out**: Flat 2D vector x-ray explainers with punchy cuts.
4. **Stick Story**: Stick-figure survival scenarios and decision steps.
5. **Paper Atlas**: Historical documentaries using textured parchment maps and period cutaways.
6. **Tall Tale 3D**: Cartoon people with ink outlines acting in a sunny 3D small-town world.

---

## Architecture & Technology Stack

- **Graphics & Animation:** HTML5 Canvas 2D + Three.js WebGL (ACES tone mapping, UnrealBloom, Bokeh depth of field).
- **Audio Synthesis:**
  - Voice: Local Kokoro-82M ONNX TTS (`kokoro-onnx`).
  - Subtitles / Alignment: Local Faster-Whisper (`small.en`, int8 CPU).
  - Sound Effects & Music: Procedural audio synthesized via NumPy and SciPy (`mix.py`).
- **Rendering Pipeline:** Headless Google Chrome (via Chrome DevTools Protocol / WebSockets) streaming canvas frames directly to FFmpeg (`image2pipe`).

---

## Quick Reference (Windows / Antigravity)

### 1. Verify Prerequisites & System Health
```powershell
python .agents/skills/faceless-shorts/scripts/selftest.py
```

### 2. Create a New Video Project
```powershell
python .agents/skills/faceless-shorts/scripts/new_video.py <style> <project-name>
# Example:
python .agents/skills/faceless-shorts/scripts/new_video.py deep-dive knuckle-cracking
```

### 3. Edit Script & Generate Narration
Edit `~/faceless-shorts/<project-name>/script.json`:
```powershell
python .agents/skills/faceless-shorts/scripts/voice.py ~/faceless-shorts/<project-name>
python .agents/skills/faceless-shorts/scripts/words.py ~/faceless-shorts/<project-name>
```

### 4. Build, QA & Render
Navigate to your project directory:
```powershell
cd ~/faceless-shorts/<project-name>

# 1. Verify shots and captions
node tools/capture.mjs check

# 2. Extract sound cues & synthesize soundtrack
node tools/capture.mjs cues
python tools/mix.py .

# 3. Visual QA (Inspect contact sheet)
node tools/capture.mjs sheet review/all.jpg 0.5 10

# 4. Render final 1080x1920 MP4
node tools/capture.mjs video renders/output.mp4
```
