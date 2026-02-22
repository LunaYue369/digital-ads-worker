#!/usr/bin/env python3
"""
Reddit Login Helper - Run once to establish browser session.

Usage:
    python tools/reddit/reddit_login.py

Opens a Chromium browser window. Log in to Reddit manually.
Close the browser when done. Session cookies will be saved.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from reddit_browser import RedditBrowser


def main():
    print("=" * 50)
    print("Reddit Login - Browser Session Setup")
    print("=" * 50)
    print()
    print("A browser window will open. Please:")
    print("1. Log in to your Reddit account")
    print("2. Verify you can see your username")
    print("3. Close the browser window when done")
    print()

    client = RedditBrowser(headless=False)
    context = client._ensure_browser()
    page = context.new_page()
    page.goto('https://www.reddit.com/login')

    print("Waiting for you to log in and close the browser...")
    print("(Press Ctrl+C in terminal if browser doesn't close)")

    try:
        # Wait until all pages are closed (user closes browser)
        while len(context.pages) > 0:
            context.pages[0].wait_for_event('close', timeout=300_000)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception:
        pass

    # Reopen to verify login
    print("\nVerifying login status...")
    client.close()

    # Re-check with headless browser
    check = RedditBrowser(headless=True)
    if check.is_logged_in():
        print()
        print("Login successful! Session saved to data/reddit_session/")
        print("You can now use publish_reddit without logging in again.")
    else:
        print()
        print("Login may not have completed. Please try again.")
    check.close()


if __name__ == '__main__':
    main()
