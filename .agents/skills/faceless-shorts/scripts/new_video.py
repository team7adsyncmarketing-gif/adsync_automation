#!/usr/bin/env python3
"""Start a new video from a style's working example (engine + shots + script).

Usage:
  python scripts/new_video.py <style> <short-name> [--dir <parent>]
  python scripts/new_video.py --list
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
STYLES_DIR = SKILL_DIR / 'styles'


def list_styles():
    if not STYLES_DIR.exists():
        return []
    return [d.name for d in sorted(STYLES_DIR.iterdir()) if d.is_dir()]


def main():
    styles = list_styles()
    parser = argparse.ArgumentParser(
        description="Create a new faceless short project from a style template."
    )
    parser.add_argument('style', nargs='?', help=f"Style name ({', '.join(styles)})")
    parser.add_argument('name', nargs='?', help="Name for the new short project")
    parser.add_argument(
        '--dir',
        default=str(Path.home() / 'faceless-shorts'),
        help="Parent directory for projects (default: ~/faceless-shorts)",
    )
    parser.add_argument('--list', action='store_true', help="List available styles")

    args = parser.parse_args()

    if args.list:
        for s in styles:
            print(s)
        return

    if not args.style or not args.name:
        parser.print_help()
        sys.exit(2)

    if args.style not in styles:
        print(f"Error: unknown style '{args.style}'. Available styles: {', '.join(styles)}", file=sys.stderr)
        sys.exit(2)

    src = STYLES_DIR / args.style / 'example'
    if not src.exists():
        print(f"Error: style example directory missing: {src}", file=sys.stderr)
        sys.exit(2)

    parent_dir = Path(args.dir).expanduser().resolve()
    dst = parent_dir / args.name

    if dst.exists():
        print(f"Error: destination '{dst}' already exists: choose another name.", file=sys.stderr)
        sys.exit(2)

    parent_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    (dst / 'renders').mkdir(exist_ok=True)
    (dst / 'review').mkdir(exist_ok=True)

    # Clean previous audio artifacts
    for f in ['data/narration.wav', 'data/mix.wav']:
        p = dst / f
        if p.exists():
            p.unlink()

    print(str(dst))
    print(f"style: {args.style}. Read {SKILL_DIR / 'styles' / args.style / 'STYLE.md'}, then rewrite script.json + src/shots.js")


if __name__ == '__main__':
    main()

