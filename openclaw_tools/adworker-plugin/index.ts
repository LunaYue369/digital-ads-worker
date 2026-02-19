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
      "使用Seedance 1.5 Pro AI从中文prompt生成广告视频（2-12秒），支持音画同步：对白（多语言/方言口型同步）、环境音效、BGM、画外音",
    parameters: {
      type: "object",
      required: ["prompt"],
      properties: {
        prompt: {
          type: "string",
          description:
            "中文视频描述prompt，包含画面描述和声音描述（对白、音效、BGM等）",
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
        camera_fixed: {
          type: "boolean",
          description: "是否固定镜头，默认由模型自动判断",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { prompt, duration, ratio, watermark, camera_fixed } = params;

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
        if (camera_fixed !== undefined) {
          args.push("--camera_fixed", String(camera_fixed));
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

  // ========================================================================
  // biz_save_summary 工具：保存商业分析摘要到本地
  // ========================================================================
  api.registerTool({
    name: "biz_save_summary",
    description:
      "将商业分析摘要保存到本地JSON文件。每7天调用一次，存储分析后的KPI、趋势和建议，不是原始对话",
    parameters: {
      type: "object",
      required: ["industry", "period_start", "period_end", "summary", "kpis"],
      properties: {
        industry: {
          type: "string",
          description:
            "行业标识，如: seafood_restaurant, noodle_shop, car_dealer, real_estate, ecommerce",
        },
        period_start: {
          type: "string",
          description: "周期开始日期，格式 YYYY-MM-DD",
        },
        period_end: {
          type: "string",
          description: "周期结束日期，格式 YYYY-MM-DD",
        },
        summary: {
          type: "string",
          description: "这段时间的整体分析总结（2-3句话）",
        },
        kpis: {
          type: "string",
          description:
            "关键指标JSON字符串，如: {\"total_revenue\": 199500, \"avg_daily\": 28500}",
        },
        trends: {
          type: "string",
          description: "趋势分析文字描述",
        },
        recommendations: {
          type: "string",
          description:
            "建议列表JSON数组，如: [\"减少帝王蟹备货30%\", \"推出春季套餐\"]",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const {
        industry,
        period_start,
        period_end,
        summary,
        kpis,
        trends,
        recommendations,
      } = params;

      try {
        console.log(`\n📊 保存商业分析摘要`);

        const args = [
          "--industry", industry,
          "--period_start", period_start,
          "--period_end", period_end,
          "--summary", summary,
          "--kpis", kpis,
        ];
        if (trends !== undefined) {
          args.push("--trends", trends);
        }
        if (recommendations !== undefined) {
          args.push("--recommendations", recommendations);
        }

        const result = await runPythonScript(
          `${ROOT}/tools/biz_save_summary.py`,
          args,
          60 * 1000 // 1分钟超时
        );

        if (result.exitCode !== 0) {
          return {
            content: [
              {
                type: "text",
                text: `❌ 保存失败:\n${result.stderr || result.stdout}`,
              },
            ],
            isError: true,
          };
        }

        return {
          content: [
            {
              type: "text",
              text: `✅ 分析摘要已保存!\n\n${result.stdout}`,
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
  // biz_query_history 工具：查询历史商业分析数据
  // ========================================================================
  api.registerTool({
    name: "biz_query_history",
    description:
      "查询本地存储的历史商业分析数据。当需要跨session对比历史数据时使用",
    parameters: {
      type: "object",
      required: [],
      properties: {
        last_n: {
          type: "number",
          description: "返回最近N条记录，默认4",
        },
        industry: {
          type: "string",
          description: "按行业过滤，如: seafood_restaurant",
        },
        keyword: {
          type: "string",
          description: "搜索关键词，在摘要、趋势、建议中搜索",
        },
        period: {
          type: "string",
          description: "查询特定周期，如: 2026-W08",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { last_n, industry, keyword, period } = params;

      try {
        console.log(`\n📊 查询历史商业数据`);

        const args: string[] = [];
        if (last_n !== undefined) {
          args.push("--last_n", String(last_n));
        }
        if (industry !== undefined) {
          args.push("--industry", industry);
        }
        if (keyword !== undefined) {
          args.push("--keyword", keyword);
        }
        if (period !== undefined) {
          args.push("--period", period);
        }

        const result = await runPythonScript(
          `${ROOT}/tools/biz_query_history.py`,
          args,
          30 * 1000 // 30秒超时
        );

        if (result.exitCode !== 0) {
          return {
            content: [
              {
                type: "text",
                text: `❌ 查询失败:\n${result.stderr || result.stdout}`,
              },
            ],
            isError: true,
          };
        }

        return {
          content: [
            {
              type: "text",
              text: result.stdout,
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
