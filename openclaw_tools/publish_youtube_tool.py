#!/usr/bin/env python3
"""
OpenClaw wrapper for publish_youtube tool.
Reads JSON from stdin with fields: {"video_path":"...","metadata":{...}, "run_dir":"..."}
Calls tools/publish_youtube.py and returns structured JSON; writes audit log.
"""
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path


def log(run_dir: Path, entry: dict):
    logs = run_dir / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / 'tool_calls.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def main():
    req = json.load(sys.stdin)
    video = req.get('video_path')
    metadata = req.get('metadata', {})
    run_dir = Path(req.get('run_dir', '.'))
    title = metadata.get('title', '')
    desc = metadata.get('description', '')
    tags = metadata.get('tags', [])
    privacy = metadata.get('privacy', 'private')

    cmd = [sys.executable, str(Path(__file__).parent.parent / 'tools' / 'publish_youtube.py'), str(video), '--title', title, '--desc', desc, '--privacy', privacy]
    if tags:
        cmd += ['--tags'] + tags

    start = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    duration = time.time() - start
    entry = {
        'tool': 'publish_youtube',
        'cmd': ' '.join(shlex.quote(p) for p in cmd),
        'timestamp': int(start),
        'duration': duration,
        'status': 'success' if proc.returncode == 0 else 'error',
        'summary': out.strip()[:200],
        'stderr': err.strip()[:200]
    }
    log(run_dir, entry)
    resp = {'status': entry['status'], 'stdout': out, 'stderr': err, 'cmd': entry['cmd']}
    print(json.dumps(resp, ensure_ascii=False))


if __name__ == '__main__':
    main()
