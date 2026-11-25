---
name: faceless-shorts
description: Make narrated faceless YouTube Shorts / TikToks / Reels fully in code on the user's computer, with a free local AI voice and word-synced captions, $0. Six styles - Deep Dive 3D (Zack D. Films-like 3D "what happens if" body/science explainers), Night File 3D (unsolved mysteries, true crime), Inside Out (flat 2D x-ray explainers), Stick Story (stick-figure "what would you do if" survival steps), Paper Atlas (history in cut paper with maps), Tall Tale 3D (funny true stories with flat 2D cartoon people in a sunny 3D world, one-word captions). Use whenever someone wants a faceless short, a what-if or what-happens-if explainer, a Zack D. Films style video, a mystery or true-crime short, a stick-figure story, a history short, a funny true story or storytime cartoon short, or a video in one of these styles, even from just a topic.
---

# Faceless Shorts for Google Antigravity

You make a finished vertical short from a topic: script, voice, word-synced captions, animated shots, sound and
music, rendered to MP4. **Everything is code**: canvas drawing, headless Chrome capture, FFmpeg, a local Kokoro voice,
local Whisper word timing, NumPy procedural sound. No AI images or video, no paid API keys, no credits.
`SKILL` = the folder this file is in (`.agents/skills/faceless-shorts`).
Projects live in `~/faceless-shorts/<short-name>/` (on Windows: `%USERPROFILE%\faceless-shorts\<short-name>\`).

| style | what it makes | length · aspect |
|---|---|---|
| **Deep Dive 3D** `deep-dive` | the flagship, Zack D. Films-like: sculpted 3D people in sunlit sets, glowing x-ray bodies, camera journeys through blood vessels, shallow focus. "What happens if…?" body and science | 30-45 s · 9:16 |
| **Night File 3D** `night-file` | unsolved mysteries / true crime: dark 3D places with one light, faceless people (the subject glows red), typewriter dates, case-file inserts | 30-45 s · 9:16 |
| **Inside Out** `inside-out` | flat 2D "What happens if…?" explainer: a simple hero, x-ray cutaways, bold 1-3 word captions, punchy cuts | 25-40 s · 9:16 |
| **Stick Story** `stick-story` | "What would you do if…?" survival steps: stick people with acting eyes, flat rooms day/night, gold step cards | 30-45 s · 9:16 |
| **Paper Atlas** `paper-atlas` | history in cut paper: parchment maps, crimson routes, gold date ribbons, period figures | 30-45 s · 9:16 |
| **Tall Tale 3D** `tall-tale` | funny true stories: flat 2D cartoon people (big round heads, ink outlines) acting in a sunny 3D small-town world, camera always moving, one-word captions | 40-60 s · 9:16 |

Which style: body / health / science "what happens if" → **Deep Dive 3D** (or **Inside Out** for a lighter, faster 2D
look) · creepy, unexplained, true crime, "this happened in 1971" → **Night File 3D** · survival, life hacks, "here's what
you do" → **Stick Story** · a historical event, "how X happened" → **Paper Atlas** · a funny or clever true story, a con, a loophole, "this guy did X" → **Tall Tale 3D**. If it isn't obvious, ask once.

Each style = `styles/<style>/style-sheet.png` (the look in one image, drawn by the style's own code) + `STYLE.md` (the rules + the engine manual) +
`example/` (a complete project that renders as-is). **Read the style's STYLE.md in full before planning.**

## 0. First use on a computer
Run the cross-platform setup script:
- On Windows (PowerShell): `python SKILL/scripts/setup.py` (or `bash SKILL/scripts/setup.sh` in Git Bash)
  Verifies Node.js 22+, FFmpeg, Google Chrome; configures the isolated Python venv at `~/.faceless-shorts/venv`;
  verifies or downloads the Kokoro ONNX voice models (~340 MB) and Whisper small.en (~0.5 GB).
- Then verify the installation: `python SKILL/scripts/selftest.py --check-only`
  (Must print **ALL SYSTEM CHECKS PASSED**).

## 1. Intake (ONE message, defaults filled in)
Ask only what's unknown, all at once:
- Topic (or "you pick 3 ideas")
- Style (e.g. `deep-dive`, `inside-out`, etc.)
- Length (default ~30 s)
- Voice (default `am_michael`; check available with `python SKILL/scripts/voice.py --list`)
- Voiceover mode:
  - **AI voice** (default, local Kokoro TTS)
  - **Their own recording** (they record after seeing the script; `python SKILL/scripts/words.py --audio <file>`)
  - **Captions-only** (no voice; `python SKILL/scripts/estimate.py`)
- Music: built-in procedural bed (`bed`, `tension`, `bounce`) · `none` · their own audio file
- End line / handle.
"Just go" = use standard defaults.

## 2. The plan (ONE screen, then wait)
Show:
1. Title
2. Full narration, one line per cut, with caption chunks (`WHAT IF *YOU | SWALLOW *GUM?`)
3. Shot list (one line each: what we see, what moves, which word it lands on)
4. New components to add to the kit, if any
5. Facts and their reliable sources.
Ask **"Build it?"** and wait for user confirmation.

**Script rules:**
- Write it the way a person actually talks to a friend: full, flowing sentences with connecting words ("Well,", "where", "but", "so", "which means"), not a list of short caption-like statements. ~90-110 words for 35 s.
- **A line is a CUT, not a sentence**: split each sentence into 1-3 lines at natural pauses (commas, "and", "where"), so the picture changes every 1.5-3.5 s while the voice keeps flowing.
- Shape: hook question, escalation, a myth or surprise, a twist ("but if you…"), punchy last line that loops.
- Numbers written as words ("seven"). Original writing only. No gore, accurate facts.

## 3. Build
1. Create project folder:
   `python SKILL/scripts/new_video.py <style> <short-name>`
   (or on Linux/macOS: `bash SKILL/scripts/new_video.sh <style> <short-name>`)
2. Write `script.json` in the project directory (lines + caps + gaps; see the style's `STYLE.md`).
3. Generate audio & timings:
   Using the virtualenv Python (`~/.faceless-shorts/venv/Scripts/python.exe` on Windows or `~/.faceless-shorts/venv/bin/python` on POSIX, or helper `SKILL/scripts/py.cmd`):
   ```bash
   python SKILL/scripts/voice.py <proj>
   python SKILL/scripts/words.py <proj>
   ```
   (For own recording: `python SKILL/scripts/words.py <proj> --audio <user_file>`)
   (For captions-only draft: `python SKILL/scripts/estimate.py <proj>`)
4. Rewrite `src/shots.js` in the project:
   One shot per line (or two for long lines), each placed with `cut(i)` and key moments placed on words with `Wd('word', line)`. Reuse `src/core/kit.js`.
5. Verify and compile:
   In the project folder:
   - Check scenes: `node tools/capture.mjs check` (must say `CHECK OK`)
   - Export audio cues: `node tools/capture.mjs cues`
   - Mix procedural soundtrack: `python tools/mix.py .`
   - Visual QA (section 4 below): `node tools/capture.mjs sheet review/all.jpg 0.5 10`
   - Render final video: `node tools/capture.mjs video renders/<name>.mp4`
   (For iterating on single shots: `node tools/capture.mjs frames review/f "4.2,4.6"`)

## 4. Visual QA: inspect before finalizing
Generate contact sheet:
```bash
node tools/capture.mjs sheet review/all.jpg 0.5 10
```
Use Antigravity's multimodal inspection tool (`read_file` on `review/all.jpg` or individual frame JPEGs in `review/frames/`) to inspect the visual rendering:
- **Visual logic:** Consistent visual mode per shot (x-ray is completely x-ray; props stay anchored to hands until released).
- **Audio-visual sync:** Cuts trigger on or slightly before line transitions; key visual reveals land on their target word.
- **No collisions:** Overlays and props do not overlap captions (caption zone: y 1250-1550) or face areas.
- **Captions:** 1-3 words per chunk, exactly one highlighted yellow word (`*WORD`), correct spelling, easily readable on mobile.
- **Style consistency:** Adheres strictly to the style palette, cyan x-ray, red danger.
- **Sound:** Clear voiceover above the music bed; soft rounded sound effects.

## 5. Deliver
1. Provide link to the final MP4 in `renders/<name>.mp4`.
2. Provide web preview option: `node tools/capture.mjs preview` (opens local server at `http://127.0.0.1:8765/`).
3. Deliver title, description, and 5-8 relevant hashtags.
4. If video file is large (> 35 MB), generate a web-optimized copy:
   `ffmpeg -i renders/<name>.mp4 -c:v libx264 -crf 21 -preset slow -c:a aac -b:a 160k -movflags +faststart renders/<name>_share.mp4`

## 6. YouTube & Social Publishing (Only when requested)
Antigravity does not rely on third-party cloud middleware or proprietary Zapier tools.
When the user explicitly asks to upload:
1. Always confirm metadata first: Title, description, tags, category ID (e.g. Comedy=23, Education=27), and privacy status (`private`, `unlisted`, or `public`).
2. Use standard YouTube Data API v3 upload via a local Python script (`google-api-python-client`) or guide the user to upload via YouTube Studio with pre-formatted title, description, and cover frame.

## 7. 3D Styles Rendering Performance
3D styles (`deep-dive`, `night-file`, `tall-tale`) render Three.js in headless Chrome.
- On machines with hardware acceleration, rendering is fast (~30-60 seconds for a full short).
- On environments without GPU acceleration, set software rendering:
  `$env:SOFTWARE_GL=1; $env:QS='&res=0.6&aa=0&shadow=1024'; $env:FPS=24; node tools/capture.mjs ...`

## Never
- Never generate images or video with third-party generative AI services.
- Never spend user money or call paid APIs.
- Never upload to YouTube or any host without user confirmation.
- Never overwrite an existing user project directory without confirmation.
- Never finalize a video without inspecting the QA contact sheet.
