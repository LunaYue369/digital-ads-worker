#!/usr/bin/env python3
"""
简化的资产写入工具
只负责写入inputs.json到运行目录

Usage:
    python tools/write_assets.py --run runs/xxx --inputs '{"product_name":"..."}'
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='写入inputs.json到运行目录')
    parser.add_argument('--run', required=True, help='运行目录路径')
    parser.add_argument('--inputs', required=True, help='inputs JSON字符串')

    args = parser.parse_args()

    # 创建运行目录
    run_dir = Path(args.run)
    run_dir.mkdir(parents=True, exist_ok=True)

    # 解析inputs
    inputs = json.loads(args.inputs)

    # 写入inputs.json
    inputs_path = run_dir / 'inputs.json'
    inputs_path.write_text(
        json.dumps(inputs, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )

    print(f"✅ 已写入: {inputs_path}")


if __name__ == '__main__':
    main()
