// @ts-nocheck
import { spawn } from "child_process";

const PYTHON = "/Users/clawbot-runner/adworker/venv/bin/python3";
const ROOT = "/Users/clawbot-runner/adworker";

// ── Slack status DM ────────────────────────────────────────────────────────────
// Posts a status message to the owner's DM during long-running tool execution.
const SLACK_BOT_TOKEN    = "REDACTED_BOT_TOKEN";
const SLACK_STATUS_CHANNEL = "C0AJ332T19N";   // owner DM channel

async function postSlackStatus(text: string): Promise<void> {
  try {
    await fetch("https://slack.com/api/chat.postMessage", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${SLACK_BOT_TOKEN}`,
      },
      body: JSON.stringify({ channel: SLACK_STATUS_CHANNEL, text }),
    });
  } catch (_) {
    // Non-critical — never block the tool if status post fails
  }
}

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
        await postSlackStatus(`⏳ 正在生成 AI 视频，通常需要 3–8 分钟，请稍候...\nGenerating AI video, usually takes 3–8 mins — please wait...`);

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
          `${ROOT}/tools/video/make_ad_video.py`,
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
        await postSlackStatus(`⏳ 正在生成 AI 图片，请稍候...\nGenerating AI image, please wait...`);

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
          `${ROOT}/tools/image/make_ad_image.py`,
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
            "视频文件路径，通常是 data/media/{timestamp}/final.mp4",
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
        await postSlackStatus(`⏳ 正在上传到 YouTube，请稍候...\nUploading to YouTube, please wait...`);

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
          `${ROOT}/tools/youtube/publish_youtube.py`,
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
        await postSlackStatus(`⏳ 正在发布到 Reddit r/${subreddit}，请稍候...\nPosting to Reddit r/${subreddit}, please wait...`);

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
          `${ROOT}/tools/reddit/publish_reddit.py`,
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
  // biz_fetch_today 工具：读取 POS 近期营业数据
  // ========================================================================
  api.registerTool({
    name: "biz_fetch_today",
    description:
      "从本地SQLite POS数据库读取近期营业数据，返回每日汇总、商品排行、小时分布、成本率和周同比。用于开始分析前快速获取店铺数据概览",
    parameters: {
      type: "object",
      required: [],
      properties: {
        industry: {
          type: "string",
          description: "行业标识，如: seafood_restaurant（默认）",
        },
        date: {
          type: "string",
          description: "目标日期 YYYY-MM-DD（默认取数据库最新日期）",
        },
        days: {
          type: "number",
          description: "往前取几天数据，默认1（仅当天），最大90",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { industry, date, days } = params;
      try {
        console.log(`\n📊 读取 POS 营业数据`);
        await postSlackStatus(`⏳ 正在读取营业数据...\nFetching business data...`);
        const args: string[] = [];
        if (industry !== undefined) args.push("--industry", industry);
        if (date     !== undefined) args.push("--date",     date);
        if (days     !== undefined) args.push("--days",     String(days));

        const result = await runPythonScript(
          `${ROOT}/tools/biz/biz_fetch_today.py`,
          args,
          30 * 1000
        );

        if (result.exitCode !== 0) {
          return {
            content: [{ type: "text", text: `❌ 读取失败:\n${result.stderr || result.stdout}` }],
            isError: true,
          };
        }
        return { content: [{ type: "text", text: result.stdout }] };
      } catch (error) {
        return { content: [{ type: "text", text: `❌ 错误: ${error.message}` }], isError: true };
      }
    },
  });

  // ========================================================================
  // biz_query_raw 工具：按维度分组查询 POS 数据
  // ========================================================================
  api.registerTool({
    name: "biz_query_raw",
    description:
      "对 POS SQLite 数据库执行分组聚合查询。可按商品、类别、日期、小时、星期、员工、支付方式、订单类型分组，返回营收/销量/成本等指标。用于精确回答老板的具体数据问题",
    parameters: {
      type: "object",
      required: ["group_by"],
      properties: {
        group_by: {
          type: "string",
          enum: ["item", "category", "day", "hour", "weekday", "employee", "payment", "order_type"],
          description: "分组维度",
        },
        industry: {
          type: "string",
          description: "行业标识，默认 seafood_restaurant",
        },
        date_from: {
          type: "string",
          description: "起始日期 YYYY-MM-DD（默认最近30天）",
        },
        date_to: {
          type: "string",
          description: "截止日期 YYYY-MM-DD（默认最新）",
        },
        limit: {
          type: "number",
          description: "返回行数上限，默认30",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { group_by, industry, date_from, date_to, limit } = params;
      try {
        console.log(`\n📊 POS 分组查询: ${group_by}`);
        await postSlackStatus(`⏳ 正在查询数据（按 ${group_by} 分组）...\nQuerying database (grouped by ${group_by})...`);
        const args = ["--group_by", group_by];
        if (industry  !== undefined) args.push("--industry",  industry);
        if (date_from !== undefined) args.push("--date_from", date_from);
        if (date_to   !== undefined) args.push("--date_to",   date_to);
        if (limit     !== undefined) args.push("--limit",     String(limit));

        const result = await runPythonScript(
          `${ROOT}/tools/biz/biz_query_raw.py`,
          args,
          30 * 1000
        );

        if (result.exitCode !== 0) {
          return {
            content: [{ type: "text", text: `❌ 查询失败:\n${result.stderr || result.stdout}` }],
            isError: true,
          };
        }
        return { content: [{ type: "text", text: result.stdout }] };
      } catch (error) {
        return { content: [{ type: "text", text: `❌ 错误: ${error.message}` }], isError: true };
      }
    },
  });

  // ========================================================================
  // biz_update 工具：写操作 — 改价格/上下架/新增商品/录入交易/撤单
  // ========================================================================
  api.registerTool({
    name: "biz_update",
    description:
      "对 POS 数据库执行写操作，修改后 dashboard 自动刷新反映变化。支持：update_price（改价）、toggle_item（上下架）、add_item（新增商品）、add_transaction（录入新交易）、void_last（撤销最近交易）、list_catalog（查看当前菜单/商品 ID）",
    parameters: {
      type: "object",
      required: ["action"],
      properties: {
        action: {
          type: "string",
          enum: ["update_price", "toggle_item", "add_item",
                 "add_transaction", "void_last", "list_catalog"],
          description: "操作类型",
        },
        industry: {
          type: "string",
          description: "行业标识，默认 seafood_restaurant",
        },
        item_id: {
          type: "string",
          description: "商品 ID（update_price / toggle_item / add_item 必填）。不确定 ID 时先调 list_catalog",
        },
        price: {
          type: "number",
          description: "新售价（update_price 必填）",
        },
        cost: {
          type: "number",
          description: "新成本（update_price 可选）",
        },
        active: {
          type: "string",
          description: "true / false，上架或下架（toggle_item 必填）",
        },
        name: {
          type: "string",
          description: "商品名称（add_item 必填）",
        },
        category: {
          type: "string",
          description: "商品分类（add_item 必填）",
        },
        covers: {
          type: "number",
          description: "桌/人数（add_transaction 可选，默认随机1-4）",
        },
        employee_id: {
          type: "string",
          description: "员工/销售 ID（add_transaction 可选，如 sales_james）",
        },
        order_type: {
          type: "string",
          description: "订单类型（add_transaction 可选：dine_in / takeout / delivery / in_person 等）",
        },
        payment_method: {
          type: "string",
          description: "支付方式（add_transaction 可选：credit_card / cash / apple_pay 等）",
        },
        item_ids: {
          type: "string",
          description: "商品 ID，逗号分隔（add_transaction 可选，如 compact_suv,ext_warranty）",
        },
        subtotal: {
          type: "number",
          description: "税前小计（add_transaction 可选；提供后 discount/tax/tip/total 也应同时提供）",
        },
        discount: {
          type: "number",
          description: "折扣金额（add_transaction 可选，默认0）",
        },
        tax: {
          type: "number",
          description: "税额（add_transaction 可选，默认0）",
        },
        tip: {
          type: "number",
          description: "小费（add_transaction 可选，默认0）",
        },
        total: {
          type: "number",
          description: "实收总额（add_transaction 可选；不填则自动计算 subtotal - discount + tax + tip）",
        },
        n: {
          type: "number",
          description: "撤销最近几笔（void_last，默认1）",
        },
      },
    },
    async execute(_toolCallId: string, params: any) {
      const { action, industry, item_id, price, cost, active,
              name, category, covers, employee_id, order_type,
              payment_method, item_ids, subtotal, discount, tax, tip, total,
              n } = params;
      try {
        console.log(`\n✏️  POS 写操作: ${action}`);
        await postSlackStatus(`⏳ 正在执行操作：${action}...\nExecuting: ${action}...`);
        const args = ["--action", action];
        if (industry        !== undefined) args.push("--industry",        industry);
        if (item_id         !== undefined) args.push("--item_id",         item_id);
        if (price           !== undefined) args.push("--price",           String(price));
        if (cost            !== undefined) args.push("--cost",            String(cost));
        if (active          !== undefined) args.push("--active",          active);
        if (name            !== undefined) args.push("--name",            name);
        if (category        !== undefined) args.push("--category",        category);
        if (covers          !== undefined) args.push("--covers",          String(covers));
        if (employee_id     !== undefined) args.push("--employee_id",     employee_id);
        if (order_type      !== undefined) args.push("--order_type",      order_type);
        if (payment_method  !== undefined) args.push("--payment_method",  payment_method);
        if (item_ids        !== undefined) args.push("--item_ids",        item_ids);
        if (subtotal        !== undefined) args.push("--subtotal",        String(subtotal));
        if (discount        !== undefined) args.push("--discount",        String(discount));
        if (tax             !== undefined) args.push("--tax",             String(tax));
        if (tip             !== undefined) args.push("--tip",             String(tip));
        if (total           !== undefined) args.push("--total",           String(total));
        if (n               !== undefined) args.push("--n",              String(n));

        const result = await runPythonScript(
          `${ROOT}/tools/biz/biz_update.py`,
          args,
          30 * 1000
        );

        if (result.exitCode !== 0) {
          return {
            content: [{ type: "text", text: `❌ 操作失败:\n${result.stderr || result.stdout}` }],
            isError: true,
          };
        }
        return { content: [{ type: "text", text: result.stdout }] };
      } catch (error) {
        return { content: [{ type: "text", text: `❌ 错误: ${error.message}` }], isError: true };
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
        await postSlackStatus(`⏳ 正在保存分析摘要...\nSaving business summary...`);

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
          `${ROOT}/tools/biz/biz_save_summary.py`,
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
        await postSlackStatus(`⏳ 正在查询历史数据...\nQuerying historical records...`);

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
          `${ROOT}/tools/biz/biz_query_history.py`,
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
