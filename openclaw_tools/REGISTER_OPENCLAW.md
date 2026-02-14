# Register adworker tools in OpenClaw (MVP)

Use `openclaw_tools/openclaw_tool_registry.json` as the source of truth for the 3 tools.

## Tool entries (absolute paths)

- `write_assets` -> `/usr/bin/python3 /Users/clawbot-runner/adworker/openclaw_tools/write_assets_tool.py`
- `make_ad_video` -> `/usr/bin/python3 /Users/clawbot-runner/adworker/openclaw_tools/make_ad_video_tool.py`
- `publish_youtube` -> `/usr/bin/python3 /Users/clawbot-runner/adworker/openclaw_tools/publish_youtube_tool.py`

## Registration mapping

If your OpenClaw tool UI/registry asks for these fields, map directly:

- `name`: from `tools[*].name`
- `description`: from `tools[*].description`
- `exec` or `command`: from `tools[*].exec`
- `input schema`: from `tools[*].input_schema`
- `output schema`: from `tools[*].output_schema`
- transport: `stdin JSON -> stdout JSON`

## Quick local smoke tests

From repo root:

```bash
python3 openclaw_tools/write_assets_tool.py <<'JSON'
{"run_dir":"runs/sample_run","payload":{"metadata":{"title":"t","description":"d"}}}
JSON
```

```bash
python3 openclaw_tools/make_ad_video_tool.py <<'JSON'
{"run_dir":"runs/sample_run"}
JSON
```

```bash
python3 openclaw_tools/publish_youtube_tool.py <<'JSON'
{"video_path":"runs/sample_run/final.mp4","run_dir":"runs/sample_run","metadata":{"title":"MVP test","description":"MVP desc","privacy":"private"}}
JSON
```

## Notes

- OpenClaw workspace in your current install is `../.openclaw/workspace`, so use absolute paths above to avoid path mismatch.
- `publish_youtube` requires `client_secrets.json` and a valid OAuth token flow.
- All wrappers append audit logs to `<run_dir>/logs/tool_calls.jsonl`.
