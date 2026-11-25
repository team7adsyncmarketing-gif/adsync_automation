"""Generator module to convert an approved concept or topic into a full Faceless Short."""
import os
import sys
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trend_engine.analysis.creative_director import AICreativeDirector, CreativeBrief

SKILL_DIR = PROJECT_ROOT / ".agents" / "skills" / "faceless-shorts"
SHORTS_OUT_DIR = PROJECT_ROOT / "output" / "shorts_projects"
VIDEOS_OUT_DIR = PROJECT_ROOT / "output" / "videos"
VENV_PYTHON = Path.home() / ".faceless-shorts" / "venv" / "Scripts" / "python.exe"


def build_shots_for_project(proj_dir: Path, style: str, lines: List[Dict[str, str]], brief: Any):
    """Generates a dynamic src/shots.js customized for the generated script lines."""
    shots_js_path = proj_dir / "src" / "shots.js"
    if not shots_js_path.parent.exists():
        return

    lines_count = len(lines)
    
    if style == "deep-dive":
        # Dynamic 3D shot planner for Deep Dive (Three.js 3D human, x-ray, and camera paths)
        js_code = """// AdSync AI Creative Director — Dynamic Deep Dive 3D Shot Planner
import * as THREE from 'three';
import { ctx, W, H, clamp, lerp, seg, eo, eio, eob } from './core/lib.js';
import { L, T } from './core/timing.js';
import { camera } from './core/engine.js';
import { Human } from './core/human.js';
import * as SETS from './core/sets.js';
import { label, pill, warning } from './core/look2d.js';

const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const lerpV = (a, b, k) => a.clone().lerp(b, k);
function screen(p, cam) { const v = p.clone().project(cam); return [(v.x + 1) / 2 * W, (1 - v.y) / 2 * H]; }

export function buildShots(E) {
  const S = [], CUES = [], add = (o) => (S.push(o), o), cue = (t, type, o = {}) => CUES.push({ t: +t.toFixed(3), type, ...o });
  const cut = (i) => (i === 0 ? 0 : L(i) - 0.08);
  const cam = camera(30);
  const KLOOK = { aperture: 0.003, maxblur: 0.01, bloom: 0.2 }, XLOOK = { aperture: 0.0015, bloom: 0.55, bloomThreshold: 0.4, vignette: 0.45 };

  const K = SETS.kitchen(E), hero = new Human({}); hero.group.position.set(0.1, 0, -0.6); K.scene.add(hero.group);
  const X = SETS.xrayStage(E), xh = new Human({}), xmat = SETS.xrayMaterial(); xh.setBodyMaterial(xmat); const I = SETS.insides(); xh.spine.add(I.group); X.scene.add(xh.group);
  const CYAN = new THREE.Color('#4FD1E8'), RED = new THREE.Color('#FF3B3B');
  const chest = (h, k) => h.parts[0].scale.set(1 + 0.03 * k, 1 + 0.012 * k, 1 + 0.08 * k);
  const lungs = (k) => I.lungs.forEach((l) => l.scale.set(1 + 0.12 * k, 1 + 0.1 * k, 1 + 0.12 * k));
  const reset = () => { hero.pose({}); chest(hero, 0); xh.pose({}); chest(xh, 0); lungs(0); I.heart.scale.setScalar(1); xmat.uniforms.uCol.value.copy(CYAN); };
  const kitchenRender = (focus, extra = {}) => E.render(K.scene, cam, { ...KLOOK, focus, ...extra });
  const FACE = V3(0.1, 1.68, -0.6);

"""
        for i in range(lines_count):
            raw_badge = lines[i].get("caps", "ADSYNC *INSIGHT").split("|")[0].replace("*", "").strip()[:20]
            badge_str = json.dumps(raw_badge)
            if i == 0:
                js_code += f"""  // Scene 1: Opening Hook
  add({{ id: 'S01', at: 0, note: 'opening hook', draw(lt, d, t, blit) {{
    reset(); const k = eo(seg(lt, 0.1, 1.1));
    hero.pose({{ head: [-8 * k, 4, 0], look: [0, -4 * k] }}); chest(hero, k);
    cam.position.copy(lerpV(V3(0.42, 1.72, 0.45), V3(0.3, 1.7, 0.12), eio(lt / d))); cam.lookAt(FACE); kitchenRender(cam.position.distanceTo(FACE)); blit();
    pill({badge_str}, 540, 1180, eob(seg(lt, 0, 0.25)), '#FFD43B', 'rgba(12,14,20,0.8)', 64);
  }} }});
  cue(0.1, 'inhale', {{ dur: 1.0 }});

"""
            elif i == lines_count - 1:
                js_code += f"""  // Scene {i+1}: Resolution & CTA
  {{ const st = cut({i});
    add({{ id: 'S{i+1:02d}', at: st, note: 'resolution', draw(lt, d, t, blit) {{
      reset(); hero.pose({{ head: [0, 0, 0], look: [0, 0] }});
      cam.position.set(0.1, 1.55, 1.2); cam.lookAt(FACE); kitchenRender(cam.position.distanceTo(FACE)); blit();
      pill({badge_str}, 540, 1180, eob(seg(lt, 0.1, 0.35)), '#00E676', 'rgba(12,14,20,0.8)', 70);
      warning(540, 520, eob(seg(lt, 0.4, 0.8)));
    }} }});
    cue(st, 'whoosh'); cue(st + 0.5, 'pop');
  }}

"""
            elif i % 2 == 1:
                js_code += f"""  // Scene {i+1}: 3D X-Ray Cutaway
  {{ const st = cut({i});
    add({{ id: 'S{i+1:02d}', at: st, note: 'xray step {i}', draw(lt, d, t, blit) {{
      reset(); lungs(1 + Math.sin(lt * 3) * 0.05); chest(xh, 1);
      cam.position.copy(lerpV(V3(0.55, 1.5, 1.6), V3(0.3, 1.42, 1.1), eio(lt / d))); cam.lookAt(0, 1.33, 0);
      E.render(X.scene, cam, {{ ...XLOOK, focus: cam.position.distanceTo(V3(0, 1.33, 0)) }}); blit();
      const [lx, ly] = screen(V3(0.1, 1.42, 0.05), cam); label({badge_str}, 760, 520, lx, ly, eob(seg(lt, 0.2, 0.45)));
    }} }});
    cue(st, 'whoosh'); cue(st + 0.1, 'pop', {{ gain: 0.5 }});
  }}

"""
            else:
                js_code += f"""  // Scene {i+1}: 3D Camera Orbit
  {{ const st = cut({i});
    add({{ id: 'S{i+1:02d}', at: st, note: 'room step {i}', draw(lt, d, t, blit) {{
      reset(); hero.pose({{ head: [2, Math.sin(lt * 2) * 3, 0] }}); chest(hero, 1);
      const a = lerp(0.55, 0.2, eio(lt / d)); cam.position.set(0.1 + Math.sin(a) * 2.1, 1.45, -0.6 + Math.cos(a) * 2.1); cam.lookAt(0.1, 1.25, -0.6); kitchenRender(2.1); blit();
      pill({badge_str}, 540, 1180, eob(seg(lt, 0, 0.25)), '#FFD43B', 'rgba(12,14,20,0.8)', 64);
    }} }});
    cue(st, 'whoosh'); cue(st + 0.05, 'pop', {{ gain: 0.6 }});
  }}

"""
        js_code += """  return { shots: S, cues: CUES };
}
"""
    else:
        # Default 2D stick-story shot planner
        js_code = """// AdSync AI Creative Director — Dynamic Shot Planner
import { ctx, W, H, clamp, lerp, seg, eo, eio, eob, rnd, rr, circle, ell, line } from './core/lib.js';
import { L, Le, T } from './core/timing.js';
import * as K from './core/kit.js';
const { P, GROUND } = K;

export function buildShots() {
  const S = [], CUES = [], add = (o) => (S.push(o), o), cue = (t, type, o = {}) => CUES.push({ t: +t.toFixed(3), type, ...o });
  const cut = (i) => (i === 0 ? 0 : L(i) - 0.08);
  const blink = (t) => ((t % 3.1) < 0.12 ? 1 : 0);

"""

        for i in range(lines_count):
            step_num = i if i <= 3 else 3
            raw_badge = lines[i].get("caps", "ADSYNC *INSIGHT").split("|")[0].replace("*", "").strip()[:20]
            badge_str = json.dumps(raw_badge)
            
            if i == 0:
                js_code += f"""  // Scene 1: Opening Hook
  add({{ id: 'S01', at: 0, cam: [540, 1100], note: 'opening hook', draw(lt, d, t) {{
    K.livingRoom({{ night: true, lampOn: true }});
    const up = lt > d * 0.5;
    K.person({{ glow: true, x: 520, y: GROUND, h: 840, mood: up ? 'worried' : 'calm', look: up ? [0.2, -0.8] : [0.5, 0.5], blink: blink(t), arms: {{ L: [-6, 14], R: [65, 55] }}, hold: (x, y) => K.phone(x + 12, y - 40, 0.55, true) }});
    K.counterPill({badge_str}, 540, 300, eob(seg(lt, 0.2, 0.5)) * 1.3);
  }} }});
  cue(0.2, 'pop', {{ gain: 0.5 }});

"""
            elif i == lines_count - 1:
                js_code += f"""  // Scene {i+1}: Closing Call to Action
  {{ const st = cut({i});
    add({{ id: 'S{i+1:02d}', at: st, cam: [540, 1000], zoom: 0.1, note: 'resolution & CTA', draw(lt, d, t) {{
      K.livingRoom({{ night: false }});
      K.person({{ x: 500, y: GROUND, h: 860, mood: 'happy', look: [0, 0], blink: blink(t), arms: {{ L: [130, 40], R: [130, 40] }} }});
      K.counterPill({badge_str}, 540, 320, eob(seg(lt, 0.1, 0.35)) * 1.3);
      K.check(540, 520, eob(seg(lt, 0.8, 1.1)) * 1.5);
    }} }});
    cue(st, 'whoosh');
    cue(st + 0.8, 'sparkle', {{ dur: 1.2 }});
  }}

"""
            else:
                js_code += f"""  // Scene {i+1}: Educational / Action Step
  {{ const st = cut({i});
    add({{ id: 'S{i+1:02d}', at: st, cam: [540, 1050], zoom: 0.08, note: 'step {i}', draw(lt, d, t) {{
      K.kitchen({{ night: true }});
      ctx.fillStyle = 'rgba(5,8,18,0.35)';
      ctx.fillRect(-300, -300, W + 600, H + 600);
      K.person({{ glow: true, x: 500, y: GROUND, h: 840, dir: 1, mood: 'determined', look: [0.2, -0.4], arms: {{ L: [-10, 20], R: [80, 40] }}, blink: blink(t) }});
      K.stepCard({step_num}, {badge_str}, 540, 300, eob(seg(lt, 0.05, 0.3)));
    }} }});
    cue(st, 'whoosh');
    cue(st + 0.05, 'pop');
  }}

"""

        js_code += """  return { shots: S, cues: CUES };
}
"""
    with open(shots_js_path, "w", encoding="utf-8") as f:
        f.write(js_code)


def generate_short(
    topic: str,
    style: str = "stick-story",
    voice: str = "am_puck",
    speed: float = 1.0,
    music: str = "bed",
    lines: Optional[List[Dict[str, str]]] = None,
    custom_name: Optional[str] = None
) -> Dict[str, Any]:
    """Build a faceless short project end-to-end using AICreativeDirector and skill scripts."""
    SHORTS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    slug = custom_name or (
        "".join(c if c.isalnum() else "-" for c in topic.lower())
        .strip("-")[:32]
        + f"-{uuid.uuid4().hex[:6]}"
    )
    proj_dir = SHORTS_OUT_DIR / slug

    # 1. Use AICreativeDirector to plan script and creative brief
    director = AICreativeDirector(output_dir=SHORTS_OUT_DIR)
    brief = director.create_brief_from_user_prompt(
        prompt=topic,
        style=style,
        voice=voice,
        music=music,
        duration=35,
        save_project=False
    )

    chosen_lines = lines or brief.script_lines
    chosen_style = brief.decisions.video_style or style
    chosen_voice = brief.decisions.voice or voice
    chosen_music = brief.decisions.music or music

    # 2. Initialize project workspace from style
    new_video_script = SKILL_DIR / "scripts" / "new_video.py"
    cmd_init = [
        sys.executable,
        str(new_video_script),
        chosen_style,
        slug,
        "--dir",
        str(SHORTS_OUT_DIR)
    ]
    res_init = subprocess.run(cmd_init, capture_output=True, text=True)
    if res_init.returncode != 0 and not proj_dir.is_dir():
        raise RuntimeError(f"Failed to initialize project: {res_init.stderr}")

    # 3. Write official script.json and creative_brief.json in project dir
    script_data = {
        "title": brief.topic.title(),
        "style": chosen_style,
        "voice": chosen_voice,
        "speed": speed,
        "lead": 0.35,
        "outro": 1.0,
        "gap": 0.26,
        "music": chosen_music,
        "sources": [
            "AdSync Marketing Intelligence & Performance Benchmarks",
            f"AdSync Creative Director — {brief.decisions.target_category}"
        ],
        "lines": chosen_lines
    }

    script_path = proj_dir / "script.json"
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2)

    brief.project_directory = str(proj_dir)
    brief.rendering_config = script_data
    brief_path = proj_dir / "creative_brief.json"
    with open(brief_path, "w", encoding="utf-8") as f:
        json.dump(brief.to_dict(), f, indent=2)

    # 4. Generate dynamic src/shots.js for the chosen style and lines
    build_shots_for_project(proj_dir, chosen_style, chosen_lines, brief)

    # 5. Generate Audio & Timestamps
    py_bin = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable
    voice_script = SKILL_DIR / "scripts" / "voice.py"
    words_script = SKILL_DIR / "scripts" / "words.py"

    res_voice = subprocess.run([py_bin, str(voice_script), str(proj_dir)], capture_output=True, text=True)
    if res_voice.returncode != 0:
        raise RuntimeError(f"Voice generation failed: {res_voice.stderr or res_voice.stdout}")

    res_words = subprocess.run([py_bin, str(words_script), str(proj_dir)], capture_output=True, text=True)
    if res_words.returncode != 0:
        raise RuntimeError(f"Word timing synchronization failed: {res_words.stderr or res_words.stdout}")

    # 6. Mix soundtrack
    mix_script = proj_dir / "tools" / "mix.py"
    if mix_script.is_file():
        subprocess.run([py_bin, str(mix_script), str(proj_dir)], capture_output=True, text=True)

    # 7. Render MP4 via capture.mjs
    mp4_name = f"{slug}.mp4"
    final_mp4 = VIDEOS_OUT_DIR / mp4_name
    capture_script = proj_dir / "tools" / "capture.mjs"
    
    cmd_render = ["node", str(capture_script), "video", str(final_mp4)]
    res_render = subprocess.run(cmd_render, capture_output=True, text=True)
    if res_render.returncode != 0 or not final_mp4.is_file():
        raise RuntimeError(f"Rendering failed: {res_render.stderr or res_render.stdout}")

    return {
        "slug": slug,
        "project_dir": str(proj_dir),
        "video_path": str(final_mp4),
        "video_name": mp4_name,
        "title": script_data["title"],
        "lines_count": len(chosen_lines),
        "category": brief.decisions.target_category,
        "audience": brief.decisions.target_audience,
        "cta": brief.decisions.call_to_action,
        "script_path": str(script_path),
        "brief_path": str(brief_path),
    }

