#!/usr/bin/env python3
"""
Minimal Producer script for MVP.
Usage: python tools/make_ad_video.py /path/to/run_dir

Expectations:
- `run_dir/storyboard.json` exists following schema/schema
- optional `run_dir/voiceover.mp3` or `run_dir/voiceover.wav`
- optional `run_dir/subtitles.srt`
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd):
    print('RUN:', ' '.join(cmd))
    subprocess.check_call(cmd)


def make_segment_from_image(img_path: Path, duration: float, out_path: Path):
    # create a short video from an image
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(img_path), "-t", str(duration), "-vf", "scale=1280:720,format=yuv420p", "-pix_fmt", "yuv420p", str(out_path)])


def trim_video(src: Path, duration: float, out_path: Path):
    run(["ffmpeg", "-y", "-ss", "0", "-i", str(src), "-t", str(duration), "-c", "copy", str(out_path)])


def concat_segments(list_file: Path, out_path: Path):
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)])


def burn_subtitles(in_video: Path, subs: Path, out_video: Path):
    run(["ffmpeg", "-y", "-i", str(in_video), "-vf", f"subtitles={str(subs)}", "-c:a", "copy", str(out_video)])


def main():
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.').resolve()
    storyboard = json.loads((run_dir / 'storyboard.json').read_text())
    tmp = run_dir / 'render'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    segment_paths = []
    for i, shot in enumerate(storyboard.get('shots', [])):
        typ = shot.get('type')
        dur = float(shot.get('duration', 2))
        src = run_dir / shot.get('path') if shot.get('path') else None
        out_seg = tmp / f'seg_{i:03d}.mp4'
        if typ == 'image' and src and src.exists():
            make_segment_from_image(src, dur, out_seg)
        elif typ == 'video' and src and src.exists():
            trim_video(src, dur, out_seg)
        else:
            # fallback: generate a blank clip with text (not implemented)
            make_segment_from_image(src if src and src.exists() else Path(__file__).parent / 'placeholder.png', dur, out_seg)
        segment_paths.append(out_seg)

    # write concat list
    list_file = tmp / 'concat.txt'
    with list_file.open('w') as f:
        for p in segment_paths:
            f.write(f"file '{p}'\n")

    interim = tmp / 'interim.mp4'
    concat_segments(list_file, interim)

    final = run_dir / 'final.mp4'
    subs = run_dir / 'subtitles.srt'
    if subs.exists():
        burn_subtitles(interim, subs, final)
    else:
        shutil.move(str(interim), str(final))

    # optional: mix voiceover (naive replacement if present)
    voice = run_dir / 'voiceover.mp3'
    if voice.exists():
        mixed = run_dir / 'final_with_audio.mp4'
        run(["ffmpeg", "-y", "-i", str(final), "-i", str(voice), "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", str(mixed)])
        mixed.replace(final)

    print('Output:', final)


if __name__ == '__main__':
    main()
