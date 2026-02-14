# Ad Creator Agent — 完整模板与 Claude 输出规范

## 目标概述
本 Agent 在 OpenClaw 中作为“编排大脑”：接收结构化需求（`inputs.json`），调用 Claude 生成结构化产物（脚本/分镜/字幕/元数据），将产物写入 run folder，调用本地或远端 Producer 生成视频，最后调用 Publisher 上传并记录结果。

## 运行产物（必须写入 run folder）
- `script.md` — 人类可读的广告脚本
- `storyboard.json` — 机器可读的分镜（必须严格符合下方 `OUTPUT JSON` 规范）
- `subtitles.srt` — 字幕（可选）
- `voiceover.txt` — 配音文本（Producer 可用 TTS 服务生成音频）
- `metadata.json` — 包含 `title`、`description`、`tags`、`privacy`、`variant` 等

建议目录结构（每次 run）：
```
runs/<run_id>/
	inputs.json
	script.md
	storyboard.json
	subtitles.srt
	voiceover.txt
	assets/...
	render/
	final.mp4
	thumbnail.png
	publish/youtube.json
	metrics.json
```

## 工具契约（tools）
- `write_assets(run_dir, payload)`：把 Agent 生成的 JSON/text 写入 `run_dir` 并可选下载 `assets`。
- `make_ad_video(run_dir)`：读取 `storyboard.json`、`assets`、`voiceover`，输出 `final.mp4` 与 `thumbnail.png`。
- `publish_youtube(video_path, metadata)`：上传并返回 `{video_id, url}`。
- `generate_tts(text, run_dir)`（可选）：调用 TTS 服务，输出 `voiceover.mp3`。

在 OpenClaw 中注册时，tool 的返回值应为 JSON，可被 Agent 直接消费并写入 `publish/` 或 `render/` 子目录。

## 错误、重试与审计
- Producer 失败：默认重试 1 次；若仍失败，写入 `render/error.log` 并将错误摘要回传给用户 session。
- Publisher（网络/API）失败：指数退避重试 3 次；失败时记录 `publish/error.json` 与最后一次响应。
- 所有 tool 调用必须返回可序列化日志（时间戳、命令/请求详情、status、message）。

## 合规与安全检查（Agent 层）
- 在写入 assets 或调用外部生成服务前，Agent 必须验证 `payload` 中每个素材的 `source` 与 `license` 字段。
- 强制检查 `inputs.json.constraints.forbidden_words`，禁止生成含黑名单词汇的文本与字幕。

## Claude 输出（SYSTEM & USER 指令模板）
下面是 Agent 调用 Claude（或其他 LLM）时推荐的 `system` + `user` 指令模板，确保输出是严格的 JSON 且可被 Producer 直接消费。

System prompt (固定)：
"""
You are an assistant that MUST produce strictly-formatted JSON matching the OUTPUT JSON schema below. Do NOT output any explanation or any extra text. Only output valid JSON (no markdown). If you encounter invalid input, output a JSON object with `error` and `message` fields.
Follow `max_shots` and `length_seconds` constraints from inputs. Each `shot` must include `id`, `type` (image|video|text), `duration` (seconds), and either `path` (relative) or `source` (search suggestion). Include `text_overlay` for any on-screen text. Provide `notes` for asset selection.
"""

User prompt (example):
"""
Inputs: {inputs_json}
Produce:
1) `script_md`: full script text.
2) `storyboard`: a JSON object following the OUTPUT JSON schema below.
3) `subtitles_srt` (optional) as a string.
4) `metadata` including `title`, `description`, `tags`, `privacy`.
Return a single JSON object with keys: `script_md`, `storyboard`, `subtitles_srt`, `metadata`.
"""

替换 `{inputs_json}` 为实际 `inputs.json` 内容（结构化）。

## OUTPUT JSON（必须精确匹配）
Agent 要求 Claude 输出一个 JSON 对象，示例如下（字段说明在后）：

{
	"script_md": "...",
	"subtitles_srt": "...",
	"metadata": {"title":"...","description":"...","tags":[".."],"privacy":"public"},
	"storyboard": {
		"run_id": "<string>",
		"title": "<string>",
		"shots": [
			{
				"id": "shot1",
				"type": "image",        // image|video|text
				"source": "suggested-search-or-stock-id",
				"path": "assets/img1.jpg", // optional if local path provided
				"duration": 3.5,
				"text_overlay": "Short overlay text",
				"transition": "cut|fade|slide",
				"notes": "selection notes for producer"
			}
		],
		"voiceover": {"text_path":"voiceover.txt"},
		"metadata": {"variant":"hook_A"}
	}
}

字段说明要点：
- `shots[*].id`: 唯一镜头 id。
- `type`: `image`（使用静帧并拉伸为 clip）、`video`（截取片段）、`text`（纯文字镜头，Producer 可生成背景）。
- `source`: 建议的素材来源（stock id / search query / URL）。Producer 若能下载则写入 `assets/` 并填 `path`。
- `duration`: 单位秒（float）。

重要：Agent 必须在收到模型产物后做一次 JSON Schema 校验（使用 `schema/storyboard.schema.json`），若不合格则返回错误到 session 并要求模型重试或人工修正。

## 示例流程（Agent 实现概要）
1. 接收外部输入 `inputs.json`（来自 Web UI / Slack / CLI）。
2. 调用 Claude（使用上面 System+User 模板）并获取 JSON 响应。立即校验 JSON。
3. 调用 `write_assets(run_dir, payload)` 将 `script_md`、`storyboard` 等写入磁盘；并将 `metadata` 写入 `metadata.json`。
4. 如果 `voiceover.txt` 存在并且 Agent 配置为自动 TTS，则调用 `generate_tts` 生成 `voiceover.mp3`。
5. 调用 `make_ad_video(run_dir)` 生成 `final.mp4`。
6. 调用 `publish_youtube`（或其他 Publisher）并保存返回值到 `publish/`。
7. 将结果与日志回传给触发的 session（UI/Slack）。

## 安全与审查（Agent 必须实现）
- 在调用 publish 前，对最终 `script_md` 与 `subtitles_srt` 做合规词表检查。若触发黑名单，必须暂停并要求人工复核。
- 记录每次 run 的 `model_version`、`prompt_hash` 与 `inputs.json` 用于审计。

## 调试与本地测试
- 在本地测试时，Agent 可以绕过网络 TTS，直接使用 `voiceover.txt` 并让 Producer 生成静音 MP4 或占位音频。
- 推荐先用 `runs/sample_run` 进行端到端本地跑通（`tools/write_assets.py` + `tools/make_ad_video.py`）。

---
如需我把上面 System+User 模板直接转换为 OpenClaw agent 的 `agent.md` 填充段（包括可复制到 `.openclaw/agents/.../agent/agent.md` 的完整内容），我可以继续生成。当前文件已给出完整规范并包含严格的输出 JSON 模板，接下来你打算我：
- 生成 OpenClaw agent 目录并把 `agent.md` 放入？ 或
- 直接把 System/User prompt 片段写成一个 `.prompt` 文件供你粘贴进 OpenClaw？

