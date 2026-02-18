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
  // make_ad_video 工具：生成AI视频
  // ========================================================================
  api.registerTool({
    name: "make_ad_video",
    description:
      "使用Seedance AI从中文prompt直接生成广告视频（2-12秒）",
    parameters: {
      type: "object",
      required: ["prompt"],
      properties: {
        prompt: {
          type: "string",
          description:
            "中文视频描述prompt，由clawdbot根据用户需求生成的详细画面描述",
        },
        duration: {
          type: "number",
          description: "视频时长（秒），2-12，默认12",
        },
        ratio: {
          type: "string",
          description:
            "画面比例: 16:9/4:3/1:1/3:4/9:16/21:9，默认16:9",
        },
        watermark: {
          type: "boolean",
          description: "是否添加水印，默认false",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { prompt, duration, ratio, watermark } = params;

      try {
        console.log(`\n🚀 开始生成AI视频`);

        const args = ["--prompt", prompt];
        if (duration !== undefined) {
          args.push("--duration", String(duration));
        }
        if (ratio !== undefined) {
          args.push("--ratio", ratio);
        }
        if (watermark !== undefined) {
          args.push("--watermark", String(watermark));
        }

        const result = await runPythonScript(
          `${ROOT}/tools/make_ad_video.py`,
          args,
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
              text: `✅ 视频生成完成!\n\n${result.stdout}`,
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
  // make_ad_image 工具：生成AI图片
  // ========================================================================
  api.registerTool({
    name: "make_ad_image",
    description:
      "使用Seedream AI从中文prompt生成广告图片，支持文生图、图生图（单图/多图参考）、组图生成",
    parameters: {
      type: "object",
      required: ["prompt"],
      properties: {
        prompt: {
          type: "string",
          description:
            "中文图片描述prompt，由clawdbot根据用户需求生成的详细画面描述",
        },
        image: {
          type: "string",
          description:
            "参考图路径，多张用逗号分隔（可选）。支持本地文件路径或URL",
        },
        size: {
          type: "string",
          description:
            "图片尺寸: 2K/4K/宽x高像素（如2048x2048），默认2K",
        },
        watermark: {
          type: "boolean",
          description: "是否添加水印，默认false",
        },
        multi: {
          type: "boolean",
          description: "是否生成组图（多张关联图片），默认false",
        },
        max_images: {
          type: "number",
          description: "组图数量，默认4，multi=true时有效",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { prompt, image, size, watermark, multi, max_images } = params;

      try {
        console.log(`\n🚀 开始生成AI图片`);

        const args = ["--prompt", prompt];
        if (image !== undefined) {
          // 支持逗号分隔的多张图
          const images = image.split(",").map((s: string) => s.trim());
          for (const img of images) {
            args.push("--image", img);
          }
        }
        if (size !== undefined) {
          args.push("--size", size);
        }
        if (watermark !== undefined) {
          args.push("--watermark", String(watermark));
        }
        if (multi !== undefined) {
          args.push("--multi", String(multi));
        }
        if (max_images !== undefined) {
          args.push("--max_images", String(max_images));
        }

        const result = await runPythonScript(
          `${ROOT}/tools/make_ad_image.py`,
          args,
          5 * 60 * 1000 // 5分钟超时
        );

        if (result.exitCode !== 0) {
          return {
            content: [
              {
                type: "text",
                text: `❌ 图片生成失败:\n${result.stderr || result.stdout}`,
              },
            ],
            isError: true,
          };
        }

        return {
          content: [
            {
              type: "text",
              text: `✅ 图片生成完成!\n\n${result.stdout}`,
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
  // publish_youtube 工具：发布视频到YouTube
  // ========================================================================
  api.registerTool({
    name: "publish_youtube",
    description:
      "将生成的广告视频发布到YouTube（通过YouTube Data API直接上传）",
    parameters: {
      type: "object",
      required: ["video_path", "title"],
      properties: {
        video_path: {
          type: "string",
          description:
            "视频文件路径，通常是 runs/{timestamp}/final.mp4",
        },
        title: {
          type: "string",
          description: "YouTube视频标题",
        },
        description: {
          type: "string",
          description: "YouTube视频描述",
        },
        tags: {
          type: "string",
          description: "标签，逗号分隔，如: coffee,ad,ai",
        },
        privacy: {
          type: "string",
          enum: ["private", "unlisted", "public"],
          description:
            "隐私级别: private(私密)/unlisted(不公开)/public(公开)，默认private",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { video_path, title, description, tags, privacy } = params;

      try {
        console.log(`\n📤 发布视频到YouTube`);

        const args = ["--video_path", video_path, "--title", title];
        if (description !== undefined) {
          args.push("--description", description);
        }
        if (tags !== undefined) {
          args.push("--tags", tags);
        }
        if (privacy !== undefined) {
          args.push("--privacy", privacy);
        }

        const result = await runPythonScript(
          `${ROOT}/tools/publish_youtube.py`,
          args,
          5 * 60 * 1000 // 5分钟超时
        );

        if (result.exitCode !== 0) {
          return {
            content: [
              {
                type: "text",
                text: `❌ YouTube发布失败:\n${result.stderr || result.stdout}`,
              },
            ],
            isError: true,
          };
        }

        return {
          content: [
            {
              type: "text",
              text: `✅ YouTube发布完成!\n\n${result.stdout}`,
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
  // publish_reddit 工具：发布内容到Reddit（浏览器自动化）
  // ========================================================================
  api.registerTool({
    name: "publish_reddit",
    description:
      "发布内容到Reddit指定的subreddit（通过浏览器自动化）。支持视频/图片帖（需video_path）和纯文本帖（只需title+body）",
    parameters: {
      type: "object",
      required: ["subreddit", "title"],
      properties: {
        video_path: {
          type: "string",
          description:
            "媒体文件路径（视频或图片）。省略则发纯文本帖",
        },
        subreddit: {
          type: "string",
          description: "目标subreddit名称（不含r/前缀），如: videos",
        },
        title: {
          type: "string",
          description: "Reddit帖子标题",
        },
        body: {
          type: "string",
          description:
            "帖子正文。媒体帖时作为评论发布；纯文本帖时作为帖子正文（必填）",
        },
        flair: {
          type: "string",
          description: "帖子flair标签（可选，取决于subreddit设置）",
        },
        nsfw: {
          type: "boolean",
          description: "是否标记为NSFW，默认false",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { video_path, subreddit, title, body, flair, nsfw } = params;

      try {
        const postType = video_path ? "媒体" : "文本";
        console.log(`\n📤 发布${postType}到Reddit r/${subreddit}`);

        const args = [
          "--subreddit", subreddit,
          "--title", title,
        ];
        if (video_path !== undefined) {
          args.push("--video_path", video_path);
        }
        if (body !== undefined) {
          args.push("--body", body);
        }
        if (flair !== undefined) {
          args.push("--flair", flair);
        }
        if (nsfw === true) {
          args.push("--nsfw");
        }

        const result = await runPythonScript(
          `${ROOT}/tools/publish_reddit.py`,
          args,
          5 * 60 * 1000 // 5分钟超时
        );

        if (result.exitCode !== 0) {
          return {
            content: [
              {
                type: "text",
                text: `❌ Reddit发布失败:\n${result.stderr || result.stdout}`,
              },
            ],
            isError: true,
          };
        }

        return {
          content: [
            {
              type: "text",
              text: `✅ Reddit发布完成!\n\n${result.stdout}`,
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
