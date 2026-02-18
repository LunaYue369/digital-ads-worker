#!/usr/bin/env python3
"""
AI广告图片生成器 - 火山引擎 Seedream

Usage:
    # 文生图
    python tools/make_ad_image.py --prompt "咖啡广告海报，暖色调"

    # 图生图（单张参考图）
    python tools/make_ad_image.py --prompt "将背景改为海滩" --image input.jpg

    # 多图融合
    python tools/make_ad_image.py --prompt "将图1的服装换为图2的服装" --image model.jpg --image dress.jpg

    # 文生组图
    python tools/make_ad_image.py --prompt "四季庭院插画" --multi true --max_images 4

    # 图生组图
    python tools/make_ad_image.py --prompt "人物四个不同场景" --image character.jpg --multi true --max_images 4

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

# 导入 Seedream 客户端
from seedream_client import SeedreamClient


def main():
    """主流程"""

    parser = argparse.ArgumentParser(description='AI广告图片生成器')
    parser.add_argument('--prompt', required=True, help='中文图片描述prompt')
    parser.add_argument('--image', action='append', default=[], help='参考图路径（可多次指定）')
    parser.add_argument('--size', default='2K', help='图片尺寸: 2K/4K/宽x高像素')
    parser.add_argument('--watermark', default='false', help='是否添加水印，true/false')
    parser.add_argument('--multi', default='false', help='是否生成组图，true/false')
    parser.add_argument('--max_images', type=int, default=4, help='组图数量（multi=true时有效）')

    args = parser.parse_args()

    prompt = args.prompt
    image_paths = [Path(p) for p in args.image] if args.image else []
    size = args.size
    watermark = args.watermark.lower() == 'true'
    multi = args.multi.lower() == 'true'
    max_images = args.max_images

    # 创建运行目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = Path(f'runs/{timestamp}')
    run_dir.mkdir(parents=True, exist_ok=True)

    # 确定模式
    has_images = len(image_paths) > 0
    if has_images and multi:
        mode = f"图生组图 ({len(image_paths)}张参考图 → {max_images}张)"
    elif has_images:
        mode = f"图生图 ({len(image_paths)}张参考图)"
    elif multi:
        mode = f"文生组图 (→ {max_images}张)"
    else:
        mode = "文生图"

    print(f"\n{'='*60}")
    print("🎨 AI广告图片生成器 - Powered by Seedream")
    print(f"{'='*60}\n")

    print(f"📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"🖼️  模式: {mode}")
    print(f"📐 尺寸: {size}")
    print(f"💧 水印: {'是' if watermark else '否'}")
    if image_paths:
        for i, p in enumerate(image_paths):
            print(f"📎 参考图{i+1}: {p}")
    print()

    # 检查API Key
    api_key = os.getenv('VOLCENGINE_API_KEY')
    if not api_key:
        print("❌ 错误: 未配置API Key")
        print("   请在 .env 文件中设置: VOLCENGINE_API_KEY=your_key")
        sys.exit(1)

    # 验证参考图存在
    for p in image_paths:
        p_str = str(p)
        if not (p_str.startswith('http://') or p_str.startswith('https://')):
            if not p.exists():
                print(f"❌ 错误: 参考图不存在: {p}")
                sys.exit(1)

    # 初始化客户端
    client = SeedreamClient(api_key=api_key)

    try:
        print(f"🚀 开始生成图片...\n")

        if has_images and multi:
            paths = client.image_to_images(
                prompt=prompt, image_paths=image_paths, output_dir=run_dir,
                max_images=max_images, size=size, watermark=watermark
            )
        elif has_images:
            paths = client.image_to_image(
                prompt=prompt, image_paths=image_paths, output_dir=run_dir,
                size=size, watermark=watermark
            )
        elif multi:
            paths = client.text_to_images(
                prompt=prompt, output_dir=run_dir,
                max_images=max_images, size=size, watermark=watermark
            )
        else:
            paths = client.text_to_image(
                prompt=prompt, output_dir=run_dir,
                size=size, watermark=watermark
            )

        print(f"\n{'='*60}")
        print("✅ 图片生成完成!")
        print(f"{'='*60}")
        for p in paths:
            file_size = p.stat().st_size / 1024
            print(f"🖼️  输出: {p} ({file_size:.1f} KB)")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ 图片生成失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
