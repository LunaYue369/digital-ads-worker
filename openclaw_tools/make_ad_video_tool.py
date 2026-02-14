#!/usr/bin/env python3
"""
OpenClaw wrapper for make_ad_video tool.
Reads JSON from stdin with fields: {"run_dir":"runs/..."}
Calls tools/make_ad_video.py and returns JSON. Writes audit log to run_dir/logs/tool_calls.jsonl
"""
import json
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
    run_dir = Path(req.get('run_dir', '.'))
    start = time.time()
    cmd = [sys.executable, str(Path(__file__).parent.parent / 'tools' / 'make_ad_video.py'), str(run_dir)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    duration = time.time() - start
    entry = {
        'tool': 'make_ad_video',
        'cmd': ' '.join(cmd),
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
