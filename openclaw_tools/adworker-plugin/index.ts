// @ts-nocheck
import { spawn } from "child_process";

const PYTHON = "/usr/bin/python3";
const ROOT = "/Users/clawbot-runner/adworker";

const TOOLS = {
  write_assets: `${ROOT}/openclaw_tools/write_assets_tool.py`,
  make_ad_video: `${ROOT}/openclaw_tools/make_ad_video_tool.py`,
  publish_youtube: `${ROOT}/openclaw_tools/publish_youtube_tool.py`,
} as const;

function truncate(text: unknown, max = 800): string {
  const s = typeof text === "string" ? text : String(text ?? "");
  return s.length > max ? `${s.slice(0, max)}...` : s;
}

async function runJsonTool(toolPath: string, payload: unknown, timeoutMs = 20 * 60 * 1000): Promise<any> {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON, [toolPath], { stdio: ["pipe", "pipe", "pipe"] });

    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error(`Tool timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });

    child.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      const raw = stdout.trim();
      if (!raw) {
        reject(new Error(`Tool returned empty stdout (code=${code}) stderr=${truncate(stderr, 1200)}`));
        return;
      }
      try {
        const parsed = JSON.parse(raw);
        resolve(parsed);
      } catch {
        reject(new Error(`Tool stdout is not valid JSON (code=${code}) stdout=${truncate(raw, 1200)} stderr=${truncate(stderr, 1200)}`));
      }
    });

    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}

function summarize(result: any) {
  return {
    status: result?.status ?? "error",
    cmd: result?.cmd ?? "",
    stdout_preview: truncate(result?.stdout, 1200),
    stderr_preview: truncate(result?.stderr, 1200),
  };
}

export default function register(api: any) {
  api.registerTool(
    {
      name: "write_assets",
      description: "Write agent outputs into run_dir (storyboard/script/subtitles/voiceover/metadata) and optionally download assets.",
      parameters: {
        type: "object",
        required: ["run_dir", "payload"],
        properties: {
          run_dir: { type: "string", description: "Run folder, e.g. runs/run_001" },
          payload: { type: "object", description: "Agent output payload object" },
        },
      },
      async execute(_toolCallId: string, params: any) {
        const result = await runJsonTool(TOOLS.write_assets, params);
        const info = summarize(result);
        return {
          content: [{ type: "text", text: JSON.stringify(info) }],
          details: info,
        };
      },
    },
  );

  api.registerTool(
    {
      name: "make_ad_video",
      description: "Build ad video from run_dir/storyboard.json (+ optional subtitles and voiceover).",
      parameters: {
        type: "object",
        required: ["run_dir"],
        properties: {
          run_dir: { type: "string", description: "Run folder, e.g. runs/run_001" },
        },
      },
      async execute(_toolCallId: string, params: any) {
        const result = await runJsonTool(TOOLS.make_ad_video, params, 60 * 60 * 1000);
        const info = summarize(result);
        return {
          content: [{ type: "text", text: JSON.stringify(info) }],
          details: info,
        };
      },
    },
  );

  api.registerTool(
    {
      name: "publish_youtube",
      description: "Upload a video to YouTube with metadata.",
      parameters: {
        type: "object",
        required: ["video_path", "run_dir", "metadata"],
        properties: {
          video_path: { type: "string", description: "Path to final.mp4" },
          run_dir: { type: "string", description: "Run folder for audit logging" },
          metadata: {
            type: "object",
            required: ["title", "description"],
            properties: {
              title: { type: "string" },
              description: { type: "string" },
              tags: { type: "array", items: { type: "string" } },
              privacy: { type: "string", enum: ["private", "unlisted", "public"] },
            },
          },
        },
      },
      async execute(_toolCallId: string, params: any) {
        const result = await runJsonTool(TOOLS.publish_youtube, params, 60 * 60 * 1000);
        const info = summarize(result);
        return {
          content: [{ type: "text", text: JSON.stringify(info) }],
          details: info,
        };
      },
    },
  );
}
