# Ad Creator MVP (OpenClaw integration)

Quick start (Python, local MVP):

1) Install system deps:
```bash
brew install ffmpeg
python3 -m pip install -r requirements.txt
```

2) Prepare Google API credentials (for YouTube upload):
- Create a Google Cloud project, enable YouTube Data API v3
- Create OAuth client ID (Desktop), download `client_secrets.json` to repo root

3) Example run flow:
- Place your assets and generated `storyboard.json` into `runs/<run_id>/`
- From repo root:
```bash
python tools/make_ad_video.py runs/<run_id>
python tools/publish_youtube.py runs/<run_id>/final.mp4 --title "My Ad" --desc "desc"
```

4) Next steps to integrate with OpenClaw:
- Add `tools/make_ad_video.py` and `tools/publish_youtube.py` as OpenClaw tools
- Create an agent that writes `storyboard.json` and calls these tools
