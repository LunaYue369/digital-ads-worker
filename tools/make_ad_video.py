#!/usr/bin/env python3
"""
AI广告视频生成器 - 火山引擎 Seedance
纯文字生成视频，无需拼接

Usage:
    python tools/make_ad_video.py <run_dir>

要求:
    - run_dir/inputs.json 包含广告需求
    - .env 文件中配置 VOLCENGINE_API_KEY
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 导入 Seedance 客户端
from seedance_client import SeedanceClient


def generate_prompt_from_inputs(inputs: dict) -> str:
    """
    从inputs.json生成视频生成的prompt

    Args:
        inputs: 包含产品信息、受众、卖点等

    Returns:
        适合Seedance生成的完整prompt
    """
    product = inputs.get('product_name', '产品')
    audience = inputs.get('target_audience', '目标用户')
    benefits = inputs.get('key_benefits', [])
    tone = inputs.get('brand_tone', 'professional')
    offer = inputs.get('offer', '')

    # 构建prompt
    prompt_parts = []

    # 开场
    prompt_parts.append(f"{product}广告视频")

    # 核心卖点
    if benefits:
        benefits_str = '、'.join(benefits[:3])  # 最多3个卖点
        prompt_parts.append(f"展示{benefits_str}")

    # 使用场景
    if '年轻' in audience or '专业' in audience:
        prompt_parts.append("现代都市背景")

    # 品牌调性映射到视觉风格
    tone_mapping = {
        'energetic': '动感活力，快节奏剪辑',
        'professional': '专业高端，稳定镜头',
        'playful': '轻松有趣，色彩明亮',
        'serious': '严肃正式，商务风格'
    }
    style = tone_mapping.get(tone, '简洁大气')
    prompt_parts.append(style)

    # 促销信息
    if offer:
        prompt_parts.append(f"画面中展示促销信息: {offer}")

    # 结尾
    prompt_parts.append("结尾展示品牌logo")

    # 合并成完整prompt
    full_prompt = '，'.join(prompt_parts) + '。'

    return full_prompt


def main():
    """主流程"""

    # 参数解析
    if len(sys.argv) < 2:
        print("用法: python make_ad_video.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])

    if not run_dir.exists():
        print(f"❌ 错误: 运行目录不存在: {run_dir}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("🎬 AI广告视频生成器 - Powered by Seedance")
    print(f"{'='*60}\n")

    # 读取inputs.json
    inputs_path = run_dir / 'inputs.json'
    if not inputs_path.exists():
        print(f"❌ 错误: 找不到 {inputs_path}")
        sys.exit(1)

    inputs = json.loads(inputs_path.read_text(encoding='utf-8'))
    print(f"📋 产品: {inputs.get('product_name', 'N/A')}")
    print(f"🎯 受众: {inputs.get('target_audience', 'N/A')}")
    print(f"⏱️  时长: {inputs.get('length_seconds', 12)}秒\n")

    # 生成prompt
    prompt = generate_prompt_from_inputs(inputs)
    print(f"📝 生成提示词:")
    print(f"   {prompt}\n")

    # 检查API Key
    api_key = os.getenv('VOLCENGINE_API_KEY')
    if not api_key:
        print("❌ 错误: 未配置API Key")
        print("   请在 .env 文件中设置: VOLCENGINE_API_KEY=your_key")
        sys.exit(1)

    # 初始化Seedance客户端（使用.env中的配置）
    client = SeedanceClient(api_key=api_key)

    # 生成视频
    output_path = run_dir / 'final.mp4'
    duration = min(inputs.get('length_seconds', 12), 12)  # 最多12秒

    try:
        print(f"🚀 开始生成视频...\n")

        client.generate_video_from_text(
            prompt=prompt,
            output_path=output_path,
            duration=duration,
            timeout=300  # 5分钟超时
        )

        print(f"\n{'='*60}")
        print("✅ 视频生成完成!")
        print(f"{'='*60}")
        print(f"📹 输出路径: {output_path}")

        file_size = output_path.stat().st_size / (1024 * 1024)
        print(f"📊 文件大小: {file_size:.2f} MB")
        print(f"⏱️  视频时长: {duration}秒")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ 视频生成失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
