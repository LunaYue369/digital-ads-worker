#!/usr/bin/env python3
"""
AI广告视频生成器 - 火山引擎 Seedance 1.5 Pro
直接接收中文prompt生成视频（支持音画同步：对白、音效、BGM）

Usage:
    python tools/make_ad_video.py --prompt "中文视频描述" [--duration 12] [--ratio 16:9] [--watermark false] [--camera_fixed false]

要求:
    - .env 文件中配置 VOLCENGINE_API_KEY
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 导入 Seedance 客户端
from seedance_client import SeedanceClient


def main():
    """主流程"""

    # 参数解析
    parser = argparse.ArgumentParser(description='AI广告视频生成器')
    parser.add_argument('--prompt', required=True, help='中文视频描述prompt')
    parser.add_argument('--duration', type=int, default=12, help='视频时长（秒），2-12')
    parser.add_argument('--ratio', default='16:9', help='画面比例，如16:9/9:16/1:1')
    parser.add_argument('--watermark', default='false', help='是否添加水印，true/false')
    parser.add_argument('--camera_fixed', default=None, help='是否固定镜头，true/false（不指定则由模型自动判断）')

    args = parser.parse_args()

    # 处理参数
    prompt = args.prompt
    duration = min(max(args.duration, 2), 12)  # 限制2-12秒
    ratio = args.ratio
    watermark = args.watermark.lower() == 'true'
    camera_fixed = None
    if args.camera_fixed is not None:
        camera_fixed = args.camera_fixed.lower() == 'true'

    # 创建运行目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = Path(f'runs/{timestamp}')
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("🎬 AI广告视频生成器 - Powered by Seedance 1.5 Pro")
    print(f"{'='*60}\n")

    print(f"📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"⏱️  时长: {duration}秒")
    print(f"📐 比例: {ratio}")
    print(f"💧 水印: {'是' if watermark else '否'}\n")

    # 检查API Key
    api_key = os.getenv('VOLCENGINE_API_KEY')
    if not api_key:
        print("❌ 错误: 未配置API Key")
        print("   请在 .env 文件中设置: VOLCENGINE_API_KEY=your_key")
        sys.exit(1)

    # 初始化Seedance客户端
    client = SeedanceClient(api_key=api_key)

    # 生成视频
    output_path = run_dir / 'final.mp4'

    try:
        print(f"🚀 开始生成视频...\n")

        client.generate_video_from_text(
            prompt=prompt,
            output_path=output_path,
            duration=duration,
            ratio=ratio,
            watermark=watermark,
            camera_fixed=camera_fixed,
            timeout=300  # 5分钟超时
        )

        print(f"\n{'='*60}")
        print("✅ 视频生成完成!")
        print(f"{'='*60}")
        print(f"📹 输出路径: {output_path}")

        file_size = output_path.stat().st_size / (1024 * 1024)
        print(f"📊 文件大小: {file_size:.2f} MB")
        print(f"⏱️  视频时长: {duration}秒")
        print(f"📐 画面比例: {ratio}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ 视频生成失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
