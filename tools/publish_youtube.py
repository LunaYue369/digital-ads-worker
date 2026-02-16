#!/usr/bin/env python3
"""
发布视频到 YouTube

Usage:
    python tools/publish_youtube.py --video_path runs/xxx/final.mp4 --title "视频标题" \
        [--description "描述"] [--tags "tag1,tag2"] [--privacy private]

要求:
    - client_secret.json (从 Google Cloud Console 下载)
    - 首次运行需要浏览器授权
"""
import argparse
import sys
from pathlib import Path

# 添加 tools 目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from youtube_client import YouTubeClient


def main():
    parser = argparse.ArgumentParser(description='发布视频到 YouTube')
    parser.add_argument('--video_path', required=True, help='视频文件路径')
    parser.add_argument('--title', required=True, help='视频标题')
    parser.add_argument('--description', default='', help='视频描述')
    parser.add_argument('--tags', default='', help='标签，逗号分隔')
    parser.add_argument(
        '--privacy', default='private',
        choices=['private', 'unlisted', 'public'],
        help='隐私级别 (默认 private)'
    )
    parser.add_argument('--category', default='22', help='YouTube分类ID (默认22)')

    args = parser.parse_args()

    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"❌ 视频文件不存在: {video_path}")
        sys.exit(1)

    tags = [t.strip() for t in args.tags.split(',') if t.strip()] if args.tags else []

    try:
        client = YouTubeClient()
        video_id, video_url = client.upload_video(
            video_path=video_path,
            title=args.title,
            description=args.description,
            tags=tags,
            privacy=args.privacy,
            category=args.category,
        )
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ YouTube 上传失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
