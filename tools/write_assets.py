#!/usr/bin/env python3
"""
Simple utility to write agent outputs into a run folder.
Usage: python tools/write_assets.py --run runs/sample_run --payload payload.json

payload.json example keys:
  storyboard (object)
  script_md (string)
  subtitles_srt (string)
  voiceover_txt (string)
  assets: [{"url": "http://...", "path": "assets/img1.png"}]
  metadata (object)
"""
import argparse
import json
import os
from pathlib import Path
import urllib.request


def download(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', required=True)
    p.add_argument('--payload', required=True)
    args = p.parse_args()
    run_dir = Path(args.run)
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(Path(args.payload).read_text())

    if 'storyboard' in payload:
        (run_dir / 'storyboard.json').write_text(json.dumps(payload['storyboard'], indent=2, ensure_ascii=False))
    if 'script_md' in payload:
        (run_dir / 'script.md').write_text(payload['script_md'], encoding='utf-8')
    if 'subtitles_srt' in payload:
        (run_dir / 'subtitles.srt').write_text(payload['subtitles_srt'], encoding='utf-8')
    if 'voiceover_txt' in payload:
        (run_dir / 'voiceover.txt').write_text(payload['voiceover_txt'], encoding='utf-8')
    if 'metadata' in payload:
        (run_dir / 'metadata.json').write_text(json.dumps(payload['metadata'], indent=2, ensure_ascii=False))

    for a in payload.get('assets', []):
        url = a.get('url')
        path = a.get('path')
        if url and path:
            try:
                download(url, run_dir / path)
            except Exception:
                print('Failed to download', url)

    print('Wrote assets to', run_dir)


if __name__ == '__main__':
    main()
