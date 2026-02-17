#!/usr/bin/env python3
"""
Reddit Browser Automation Client
Uses Playwright to post videos to Reddit via browser automation.
"""
import time
import random
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

SESSION_DIR_DEFAULT = Path(__file__).parent.parent / 'reddit_session'
REDDIT_BASE = 'https://www.reddit.com'


class RedditBrowser:
    def __init__(self, session_dir: str = None, headless: bool = True):
        self.session_dir = Path(session_dir or SESSION_DIR_DEFAULT)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self._playwright = None
        self._context = None

    def _ensure_browser(self):
        """Launch persistent Chromium context if not already running."""
        if self._context is None:
            self._playwright = sync_playwright().start()
            # Always use headed mode - Reddit blocks headless browsers.
            # For automated runs, use args to start minimized.
            launch_args = []
            if self.headless:
                launch_args = ['--start-minimized']
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_dir),
                headless=False,  # Reddit blocks headless, always use headed
                viewport={'width': 1280, 'height': 900},
                locale='en-US',
                slow_mo=300,
                args=launch_args,
            )
        return self._context

    def is_logged_in(self) -> bool:
        """Check if the persistent session has a valid Reddit login."""
        context = self._ensure_browser()
        page = context.new_page()
        try:
            page.goto(REDDIT_BASE, wait_until='domcontentloaded', timeout=30_000)
            # Wait a moment for dynamic content
            page.wait_for_timeout(2000)
            # Check for logged-in indicators: user menu button or username display
            logged_in = page.locator(
                'button[aria-label="Open user navigation"], '
                '[data-testid="user-drawer-button"], '
                '#USER_DROPDOWN_ID, '
                'a[href*="/user/"]'
            ).first.is_visible(timeout=5000)
            return logged_in
        except (PlaywrightTimeout, Exception):
            return False
        finally:
            page.close()

    def post_video(
        self,
        video_path: Path,
        subreddit: str,
        title: str,
        flair: Optional[str] = None,
        nsfw: bool = False,
        timeout_ms: int = 180_000,
    ) -> str:
        """
        Post a video to a Reddit subreddit.
        Returns: URL of the created post.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Check file size (Reddit limit: 1GB)
        file_size_mb = video_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 1024:
            raise ValueError(f"Video file too large: {file_size_mb:.0f}MB (Reddit limit: 1GB)")

        context = self._ensure_browser()
        page = context.new_page()

        try:
            # Step 1: Navigate to subreddit submit page
            submit_url = f"{REDDIT_BASE}/r/{subreddit}/submit"
            print(f"Navigating to {submit_url}...")
            page.goto(submit_url, wait_until='domcontentloaded', timeout=30_000)
            page.wait_for_timeout(2000)

            # Step 2: Check if redirected to login
            if '/login' in page.url or '/register' in page.url:
                raise RuntimeError(
                    "Reddit session expired. Run 'python tools/reddit_login.py' to log in."
                )

            # Step 3: Select Images & Video tab
            print("Selecting video upload tab...")
            page.locator('[role="tab"]:has-text("Images & Video")').click(timeout=10_000)
            page.wait_for_timeout(1500)

            # Step 4: Upload video file via the combined image+video file input
            print(f"Uploading video: {video_path.name} ({file_size_mb:.1f}MB)...")
            # Use the file input that accepts both images and videos
            media_input = page.locator(
                'input[type="file"][accept*="video/mp4"][accept*="image/"]'
            ).first
            media_input.set_input_files(str(video_path.resolve()))

            # Step 5: Wait for video upload to complete
            print("Waiting for video upload to complete...")
            # Wait for "Uploading..." text to appear then disappear
            try:
                page.locator('text=Uploading').wait_for(state='visible', timeout=10_000)
            except PlaywrightTimeout:
                pass  # Maybe it uploaded too fast
            # Now wait for upload to finish (Uploading text disappears or video preview appears)
            page.locator('text=Uploading').wait_for(state='hidden', timeout=timeout_ms)
            page.wait_for_timeout(2000)
            print("Video upload complete.")
            page.wait_for_timeout(random.randint(500, 1500))

            # Step 6: Enter title
            print(f"Entering title: {title}")
            # The visible title field - try multiple selectors
            title_input = page.locator(
                'textarea[name="title"], '
                'input[name="title"], '
                '[contenteditable="true"][aria-label*="title" i], '
                '[placeholder*="Title"]'
            ).first
            title_input.click(timeout=10_000)
            title_input.fill(title)
            page.wait_for_timeout(random.randint(300, 800))

            # Step 7: Set flair if provided
            if flair:
                try:
                    flair_button = page.locator(
                        'button:has-text("Flair"), '
                        '[data-testid="flair-picker"], '
                        'button:has-text("Add flair")'
                    ).first
                    if flair_button.is_visible(timeout=3000):
                        flair_button.click()
                        page.wait_for_timeout(500)
                        page.locator(f'text="{flair}"').first.click()
                        page.wait_for_timeout(500)
                        apply_btn = page.locator('button:has-text("Apply")').first
                        if apply_btn.is_visible(timeout=2000):
                            apply_btn.click()
                except (PlaywrightTimeout, Exception):
                    print(f"Warning: Could not set flair '{flair}', continuing without it.")

            # Step 8: Mark NSFW if needed
            if nsfw:
                try:
                    nsfw_toggle = page.locator('button:has-text("NSFW")').first
                    if nsfw_toggle.is_visible(timeout=3000):
                        nsfw_toggle.click()
                except (PlaywrightTimeout, Exception):
                    print("Warning: Could not set NSFW flag.")

            # Step 9: Click Post button
            print("Submitting post...")
            page.wait_for_timeout(random.randint(500, 1000))
            post_button = page.locator('button:has-text("Post")').last
            post_button.click()

            # Step 10: Wait for post creation
            print("Waiting for post to be created...")
            # Reddit may redirect to /comments/ID or to subreddit with ?created=t3_ID
            page.wait_for_url(
                lambda url: '/comments/' in url or 'created=' in url,
                timeout=60_000
            )
            current_url = page.url
            # Extract post URL from redirect
            if 'created=' in current_url:
                import re
                match = re.search(r'created=(t3_\w+)', current_url)
                if match:
                    post_id = match.group(1).replace('t3_', '')
                    post_url = f"{REDDIT_BASE}/r/{subreddit}/comments/{post_id}/"
                else:
                    post_url = current_url
            else:
                post_url = current_url
            print(f"Post created: {post_url}")
            return post_url

        except PlaywrightTimeout as e:
            # Take screenshot for debugging
            screenshot_path = self.session_dir / 'error_screenshot.png'
            try:
                page.screenshot(path=str(screenshot_path))
                print(f"Error screenshot saved: {screenshot_path}")
            except Exception:
                pass
            raise RuntimeError(f"Timeout during Reddit posting: {e}")
        finally:
            page.close()

    def close(self):
        """Clean up browser resources."""
        if self._context:
            self._context.close()
            self._context = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
