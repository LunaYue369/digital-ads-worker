# OpenClaw tool wrappers for adworker

This folder contains small Python wrapper scripts that adapt local tools into an OpenClaw-friendly, auditable interface.

Files:
- `write_assets_tool.py`: wrapper for `tools/write_assets.py`. Reads JSON from stdin `{run_dir, payload}` and returns JSON.
- `make_ad_video_tool.py`: wrapper for `tools/make_ad_video.py`. Reads JSON from stdin `{run_dir}` and returns JSON.
- `publish_youtube_tool.py`: wrapper for `tools/publish_youtube.py`. Reads JSON from stdin `{video_path, metadata, run_dir}` and returns JSON.
- `openclaw_tool_registry.json`: ready-to-register tool definitions with absolute paths for this machine.
- `REGISTER_OPENCLAW.md`: field mapping + smoke test commands.

Audit logs:
Each wrapper appends an entry to `<run_dir>/logs/tool_calls.jsonl` with fields: `tool`, `cmd`, `timestamp`, `duration`, `status`, `summary`, `stderr`.

Example: registering a tool in OpenClaw
1. Ensure these scripts are executable: `chmod +x openclaw_tools/*.py`
2. In your OpenClaw agent code or tool registry, register a tool command that runs the wrapper. The wrapper accepts JSON on stdin and prints JSON to stdout.

Example invocation (for testing):
```bash
python3 openclaw_tools/write_assets_tool.py <<'JSON'
{"run_dir":"runs/sample_run","payload": {"storyboard": {}}}
JSON
```

OpenClaw tool manifest (conceptual)
```json
{
  "name": "write_assets",
  "exec": "/usr/bin/python3 /absolute/path/to/adworker/openclaw_tools/write_assets_tool.py",
  "description": "Writes agent outputs into a run folder and downloads assets",
  "input": "JSON",
  "output": "JSON"
}
```

How to let `clawdbot` call these tools
- In your agent action code (OpenClaw), when you need to call a tool, run the registered exec command and pass a JSON payload on stdin. Parse JSON response from stdout. This avoids embedding raw shell commands in prompts and centralizes auditing.
