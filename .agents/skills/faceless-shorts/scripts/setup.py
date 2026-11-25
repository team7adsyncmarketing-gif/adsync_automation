#!/usr/bin/env python3
"""Cross-platform environment setup for Faceless Shorts in Google Antigravity.

Configures:
- System prerequisites verification (Node 22+, FFmpeg, FFprobe, Chrome, Python 3.10+)
- Private Python virtual environment at ~/.faceless-shorts/venv
- Installs numpy, scipy, kokoro-onnx, faster-whisper
- Prepares Kokoro ONNX and Faster-Whisper local model downloads

Usage:
  python scripts/setup.py                     # Check system, build venv, install pip packages
  python scripts/setup.py --download-models   # Also download Kokoro & Whisper models (~0.85 GB)
  python scripts/setup.py --check             # Report status of all components without installing
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
FACELESS_HOME = Path(os.environ.get('FACELESS_HOME', Path.home() / '.faceless-shorts'))
VENV_DIR = FACELESS_HOME / 'venv'
if sys.platform == 'win32':
    VENV_PYTHON = VENV_DIR / 'Scripts' / 'python.exe'
    VENV_PIP = VENV_DIR / 'Scripts' / 'pip.exe'
else:
    VENV_PYTHON = VENV_DIR / 'bin' / 'python'
    VENV_PIP = VENV_DIR / 'bin' / 'pip'

KOKORO_DIR = FACELESS_HOME / 'kokoro'

REQUIRED_PIP_PACKAGES = ['numpy', 'scipy', 'kokoro-onnx', 'faster-whisper']


def print_status(name, ok, msg=""):
    tag = "[OK]     " if ok else "[MISSING]"
    print(f"{tag} {name:<16} {msg}")


def check_node():
    try:
        out = subprocess.run(['node', '-v'], capture_output=True, text=True, check=True).stdout.strip()
        version = int(out.lstrip('v').split('.')[0])
        return version >= 22, f"{out} (requires >= 22)"
    except Exception as e:
        return False, f"Not found or error ({e}). Install Node.js 22+ from nodejs.org"


def check_ffmpeg():
    try:
        out = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=True).stdout
        first_line = out.splitlines()[0] if out else ""
        ver = first_line.split()[2] if len(first_line.split()) > 2 else "installed"
        return True, f"ffmpeg {ver}"
    except Exception as e:
        return False, "Not found. Install ffmpeg and ensure it is in PATH"


def check_ffprobe():
    try:
        out = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True, check=True).stdout
        first_line = out.splitlines()[0] if out else ""
        ver = first_line.split()[2] if len(first_line.split()) > 2 else "installed"
        return True, f"ffprobe {ver}"
    except Exception as e:
        return False, "Not found. Install ffprobe and ensure it is in PATH"


def find_chrome():
    env_ch = os.environ.get('CHROME')
    candidates = [
        env_ch,
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
        'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return True, str(c)
    which_ch = shutil.which('google-chrome') or shutil.which('chrome') or shutil.which('chromium')
    if which_ch:
        return True, which_ch
    return False, "Google Chrome not found. Install from google.com/chrome or set CHROME env var"


def check_python_host():
    ver = sys.version_info
    ok = (ver.major == 3 and ver.minor >= 10)
    return ok, f"Python {ver.major}.{ver.minor}.{ver.micro} (requires >= 3.10)"


def ensure_venv():
    FACELESS_HOME.mkdir(parents=True, exist_ok=True)
    if not VENV_PYTHON.is_file():
        print(f"Creating isolated Python venv at {VENV_DIR}...")
        import venv
        venv.create(VENV_DIR, with_pip=True)
    return VENV_PYTHON.is_file()


def check_venv_packages():
    if not VENV_PYTHON.is_file():
        return False, "venv python not created yet"
    code = "import numpy, scipy, kokoro_onnx, faster_whisper; print('OK')"
    res = subprocess.run([str(VENV_PYTHON), '-c', code], capture_output=True, text=True)
    if res.returncode == 0:
        return True, "All required packages installed"
    return False, f"Missing packages in venv ({res.stderr.strip() or 'import failure'})"


def install_venv_packages():
    print(f"Installing {', '.join(REQUIRED_PIP_PACKAGES)} into {VENV_DIR}...")
    # Upgrade pip first quietly
    subprocess.run([str(VENV_PYTHON), '-m', 'pip', 'install', '-q', '--upgrade', 'pip'])
    cmd = [str(VENV_PYTHON), '-m', 'pip', 'install', '-q'] + REQUIRED_PIP_PACKAGES
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Failed to install packages:\n{res.stderr}", file=sys.stderr)
        return False
    return True


def check_models():
    # Kokoro
    k1 = KOKORO_DIR / 'kokoro-v1.0.onnx'
    k2 = KOKORO_DIR / 'voices-v1.0.bin'
    kokoro_ok = k1.is_file() and k1.stat().st_size > 1_000_000 and k2.is_file() and k2.stat().st_size > 100_000

    # Whisper small.en check via faster_whisper cache
    whisper_ok = False
    if VENV_PYTHON.is_file():
        check_code = (
            "import os, sys\n"
            "from huggingface_hub import try_to_load_from_cache\n"
            "try:\n"
            "    from faster_whisper import WhisperModel\n"
            "    # test local cached files without downloading\n"
            "    m = WhisperModel('small.en', device='cpu', compute_type='int8', local_files_only=True)\n"
            "    print('FOUND')\n"
            "except Exception:\n"
            "    sys.exit(1)\n"
        )
        res = subprocess.run([str(VENV_PYTHON), '-c', check_code], capture_output=True, text=True)
        whisper_ok = (res.returncode == 0 and 'FOUND' in res.stdout)

    return kokoro_ok, whisper_ok


def download_models():
    print("\nPreparing model downloads (Kokoro ~340 MB, Whisper ~0.5 GB)...")
    if not VENV_PYTHON.is_file():
        print("[ERROR] venv not initialized. Run setup without --download-models first.")
        return False

    # Download Kokoro models
    print("Fetching Kokoro-82M ONNX model files...")
    KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    voice_py = SKILL_DIR / 'scripts' / 'voice.py'
    res = subprocess.run([str(VENV_PYTHON), str(voice_py), '--download'], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Kokoro download failed: {res.stderr}")
        return False
    print("[OK] Kokoro models downloaded to", KOKORO_DIR)

    # Download Whisper model
    print("Fetching Faster-Whisper small.en model...")
    w_code = "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"
    res = subprocess.run([str(VENV_PYTHON), '-c', w_code], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Whisper download failed: {res.stderr}")
        return False
    print("[OK] Faster-Whisper small.en model ready.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Setup Faceless Shorts environment for Google Antigravity.")
    parser.add_argument('--check', action='store_true', help="Check system status without installing anything")
    parser.add_argument('--download-models', action='store_true', help="Download Kokoro and Whisper model weights")
    args = parser.parse_args()

    print("=" * 60)
    print(" Faceless Shorts Environment Setup (Google Antigravity)")
    print("=" * 60)

    # Checks
    all_ok = True
    node_ok, node_msg = check_node()
    print_status("Node.js", node_ok, node_msg)
    all_ok = all_ok and node_ok

    py_ok, py_msg = check_python_host()
    print_status("Host Python", py_ok, py_msg)
    all_ok = all_ok and py_ok

    ff_ok, ff_msg = check_ffmpeg()
    print_status("FFmpeg", ff_ok, ff_msg)
    all_ok = all_ok and ff_ok

    ffp_ok, ffp_msg = check_ffprobe()
    print_status("FFprobe", ffp_ok, ffp_msg)
    all_ok = all_ok and ffp_ok

    ch_ok, ch_msg = find_chrome()
    print_status("Google Chrome", ch_ok, ch_msg)
    all_ok = all_ok and ch_ok

    if not all_ok:
        print("\n[!] Please resolve the missing system prerequisites listed above.")
        if args.check:
            sys.exit(1)
        sys.exit(1)

    if args.check:
        v_ok, v_msg = check_venv_packages()
        print_status("Venv Packages", v_ok, f"({VENV_DIR}) {v_msg}")
        k_ok, w_ok = check_models()
        print_status("Kokoro Model", k_ok, f"{'Ready' if k_ok else 'Not downloaded (~340 MB)'}")
        print_status("Whisper Model", w_ok, f"{'Ready' if w_ok else 'Not downloaded (~0.5 GB)'}")
        print("\nSystem check complete.")
        return

    # Configure venv
    ensure_venv()
    v_ok, _ = check_venv_packages()
    if not v_ok:
        install_venv_packages()
        v_ok, v_msg = check_venv_packages()
        print_status("Venv Packages", v_ok, v_msg)
    else:
        print_status("Venv Packages", True, f"({VENV_DIR}) Already installed")

    k_ok, w_ok = check_models()
    print_status("Kokoro Model", k_ok, f"{'Ready' if k_ok else 'Not downloaded (~340 MB)'}")
    print_status("Whisper Model", w_ok, f"{'Ready' if w_ok else 'Not downloaded (~0.5 GB)'}")

    if args.download_models:
        if not (k_ok and w_ok):
            download_models()
    else:
        if not (k_ok and w_ok):
            print("\n[NOTE] Large models (~0.85 GB total) have not been downloaded yet.")
            print("To download the models, run:")
            print("  python scripts/setup.py --download-models")

    print("\n[SUCCESS] Environment setup verified!")


if __name__ == '__main__':
    main()

