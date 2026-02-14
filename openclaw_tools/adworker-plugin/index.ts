// @ts-nocheck
import { spawn } from "child_process";

const PYTHON = "/usr/bin/python3";
const ROOT = "/Users/clawbot-runner/adworker";

async function runPythonScript(
  scriptPath: string,
  args: string[],
  timeoutMs = 10 * 60 * 1000
): Promise<{ exitCode: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON, [scriptPath, ...args], { cwd: ROOT });

    let stdout = "";
    let stderr = "";

    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error(`Script timed out after ${timeoutMs}ms`));
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

    child.on("close", (exitCode) => {
      clearTimeout(timer);
      resolve({ exitCode, stdout, stderr });
    });
  });
}

export default function register(api: any) {
  // ========================================================================
  // write_assets 工具：写入inputs.json
  // ========================================================================
  api.registerTool({
    name: "write_assets",
    description: "将用户需求写入inputs.json到运行目录",
    parameters: {
      type: "object",
      required: ["run_dir", "inputs"],
      properties: {
        run_dir: {
          type: "string",
          description: "运行目录路径，例如: runs/20260213_150000",
        },
        inputs: {
          type: "object",
          description: "广告需求信息",
          properties: {
            product_name: { type: "string", description: "产品名称" },
            target_audience: { type: "string", description: "目标受众" },
            key_benefits: {
              type: "array",
              items: { type: "string" },
              description: "核心卖点",
            },
            brand_tone: {
              type: "string",
              description: "品牌调性: energetic/professional/playful/serious",
            },
            length_seconds: {
              type: "number",
              description: "视频时长（秒），最多12秒",
            },
            offer: { type: "string", description: "促销信息（可选）" },
          },
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { run_dir, inputs } = params;

      try {
        const result = await runPythonScript(
          `${ROOT}/tools/write_assets.py`,
          ["--run", run_dir, "--inputs", JSON.stringify(inputs)],
          30000 // 30秒超时
        );

        if (result.exitCode !== 0) {
          return {
            content: [
              {
                type: "text",
                text: `❌ 写入失败:\n${result.stderr || result.stdout}`,
              },
            ],
            isError: true,
          };
        }

        return {
          content: [
            {
              type: "text",
              text: `✅ 已写入 inputs.json 到 ${run_dir}\n${result.stdout}`,
            },
          ],
        };
      } catch (error) {
        return {
          content: [{ type: "text", text: `❌ 错误: ${error.message}` }],
          isError: true,
        };
      }
    },
  });

  // ========================================================================
  // make_ad_video 工具：生成AI视频
  // ========================================================================
  api.registerTool({
    name: "make_ad_video",
    description:
      "使用Seedance AI从文字描述生成广告视频（2-12秒，无需拼接）",
    parameters: {
      type: "object",
      required: ["run_dir"],
      properties: {
        run_dir: {
          type: "string",
          description: "运行目录路径（必须包含inputs.json）",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { run_dir } = params;

      try {
        console.log(`\n🚀 开始生成AI视频: ${run_dir}`);

        const result = await runPythonScript(
          `${ROOT}/tools/make_ad_video.py`,
          [run_dir],
          10 * 60 * 1000 // 10分钟超时
        );

        if (result.exitCode !== 0) {
          return {
            content: [
              {
                type: "text",
                text: `❌ 视频生成失败:\n${result.stderr || result.stdout}`,
              },
            ],
            isError: true,
          };
        }

        return {
          content: [
            {
              type: "text",
              text: `✅ 视频生成完成!\n\n${result.stdout}\n\n视频路径: ${run_dir}/final.mp4`,
            },
          ],
        };
      } catch (error) {
        return {
          content: [{ type: "text", text: `❌ 错误: ${error.message}` }],
          isError: true,
        };
      }
    },
  });
}
