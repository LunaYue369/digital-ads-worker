#!/usr/bin/env python3
"""
Publish video to Reddit via browser automation.

Usage:
    python tools/publish_reddit.py --video_path runs/xxx/final.mp4 \
        --subreddit testingground4bots --title "My Video"

Requirements:
    - First run: python tools/reddit_login.py
    - playwright installed: pip install playwright && playwright install chromium
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from reddit_browser import RedditBrowser


def main():
    parser = argparse.ArgumentParser(description='Publish video to Reddit')
    parser.add_argument('--video_path', required=True, help='Video file path')
    parser.add_argument('--subreddit', required=True, help='Target subreddit (without r/)')
    parser.add_argument('--title', required=True, help='Post title')
    parser.add_argument('--flair', default=None, help='Post flair text (optional)')
    parser.add_argument('--nsfw', action='store_true', help='Mark post as NSFW')

    args = parser.parse_args()

    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"Video file not found: {video_path}")
        sys.exit(1)

    # Strip r/ prefix if accidentally included
    subreddit = args.subreddit.lstrip('r/')

    client = RedditBrowser(headless=True)
    try:
        if not client.is_logged_in():
            print("Not logged in to Reddit.")
            print("Run 'python tools/reddit_login.py' to log in first.")
            sys.exit(1)

        post_url = client.post_video(
            video_path=video_path,
            subreddit=subreddit,
            title=args.title,
            flair=args.flair,
            nsfw=args.nsfw,
        )
        print(f"Reddit post URL: {post_url}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Reddit publishing failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Reddit publishing failed: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == '__main__':
    main()
