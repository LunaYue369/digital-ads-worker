#!/usr/bin/env python3
"""
Reddit Browser Automation Client
Uses Playwright to post videos to Reddit via browser automation.
"""
import re
import random
from pathlib import Path
from typing import Optional, List
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

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

    # ── Flair helpers ──────────────────────────────────────────────

    def _open_flair_picker(self, page: Page) -> bool:
        """Try to open the flair picker modal. Returns True if opened."""
        flair_button = page.locator(
            'button:has-text("Flair"), '
            'button:has-text("Add flair"), '
            'button:has-text("Select flair"), '
            '[data-testid="flair-picker"]'
        ).first
        try:
            if flair_button.is_visible(timeout=3000):
                flair_button.click()
                page.wait_for_timeout(800)
                return True
        except (PlaywrightTimeout, Exception):
            pass
        return False

    def _read_available_flairs(self, page: Page) -> List[str]:
        """Read all flair options from the open flair picker modal."""
        flairs = []
        # Reddit flair picker uses various structures: radio buttons, divs, labels
        # Try multiple selector strategies
        selectors = [
            # Radio-button style flair list (common)
            'div[data-testid="flair_picker"] label',
            # Newer Reddit flair modal items
            '[class*="flair"] [class*="label"]',
            '[class*="flair"] span',
            # Generic: items inside the flair modal/dropdown
            '[role="radiogroup"] label',
            '[role="listbox"] [role="option"]',
            # Flair text inside modal (flair-picker modal)
            'flair-picker flair-item',
        ]
        for selector in selectors:
            items = page.locator(selector)
            try:
                count = items.count()
                if count > 0:
                    for i in range(count):
                        text = items.nth(i).inner_text(timeout=2000).strip()
                        if text and text not in ('Clear Flair', 'Apply', 'Cancel', ''):
                            flairs.append(text)
                    if flairs:
                        break
            except (PlaywrightTimeout, Exception):
                continue

        # Fallback: grab all visible text items inside any flair-related container
        if not flairs:
            try:
                modal = page.locator(
                    '[class*="FlairPicker"], '
                    '[class*="flair-picker"], '
                    '[aria-label*="flair" i], '
                    '#FLAIR_MODAL, '
                    'r-post-flairs-modal'
                ).first
                if modal.is_visible(timeout=2000):
                    all_text = modal.inner_text(timeout=3000)
                    for line in all_text.split('\n'):
                        line = line.strip()
                        if line and line not in ('Clear Flair', 'Apply', 'Cancel',
                                                  'Select flair', 'Add flair', ''):
                            flairs.append(line)
            except (PlaywrightTimeout, Exception):
                pass

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for f in flairs:
            if f not in seen:
                seen.add(f)
                unique.append(f)
        return unique

    def _click_flair_option(self, page: Page, flair_text: str) -> bool:
        """Click on a specific flair option inside the open flair picker."""
        # Try exact match first, then partial match
        for exact in [True, False]:
            if exact:
                locator = page.locator(
                    f'label:has-text("{flair_text}"), '
                    f'[role="option"]:has-text("{flair_text}"), '
                    f'div:has-text("{flair_text}")'
                ).first
            else:
                locator = page.get_by_text(flair_text, exact=False).first
            try:
                if locator.is_visible(timeout=2000):
                    locator.click()
                    page.wait_for_timeout(500)
                    return True
            except (PlaywrightTimeout, Exception):
                continue
        return False

    def _apply_flair(self, page: Page) -> None:
        """Click the Apply button if present to confirm flair selection."""
        try:
            apply_btn = page.locator(
                'button:has-text("Apply"), '
                'button:has-text("Save"), '
                'button[type="submit"]'
            ).first
            if apply_btn.is_visible(timeout=2000):
                apply_btn.click()
                page.wait_for_timeout(500)
        except (PlaywrightTimeout, Exception):
            pass

    def _try_editable_flair(self, page: Page, flair_text: str) -> bool:
        """
        Try to fill in an editable flair text input field.
        Some subreddits allow or require users to type custom flair text.
        Returns True if an editable field was found and filled.
        """
        editable_selectors = [
            'input[name="flairText"]',
            'input[placeholder*="flair" i]',
            'input[placeholder*="Edit flair" i]',
            '[contenteditable="true"][class*="flair" i]',
            'textarea[name="flairText"]',
        ]
        for selector in editable_selectors:
            try:
                field = page.locator(selector).first
                if field.is_visible(timeout=1500):
                    field.click()
                    field.fill(flair_text)
                    page.wait_for_timeout(300)
                    print(f"Filled editable flair field with: '{flair_text}'")
                    return True
            except (PlaywrightTimeout, Exception):
                continue
        return False

    def _handle_flair(self, page: Page, flair: Optional[str]) -> Optional[str]:
        """
        Handle flair selection on the submit page.

        Strategy:
        1. Open flair picker. If none exists → skip.
        2. Read available predefined flair options.
        3a. If predefined options exist → match user flair or auto-select first.
        3b. If NO predefined options but editable text field exists →
            type user-provided flair, or use a generic default.
        4. Apply and close.

        Returns the flair that was set, or None.
        """
        if not self._open_flair_picker(page):
            print("No flair picker found on this subreddit.")
            return None

        available = self._read_available_flairs(page)

        # Case A: No predefined options — check for editable flair text field
        if not available:
            flair_text = flair or "OC"  # Default to "OC" (Original Content) if nothing specified
            if self._try_editable_flair(page, flair_text):
                self._apply_flair(page)
                print(f"Flair set (custom text): '{flair_text}'")
                return flair_text
            else:
                print("Flair picker opened but no options or editable field found.")
                page.keyboard.press('Escape')
                page.wait_for_timeout(300)
                return None

        # Case B: Predefined flair options exist
        print(f"Available flairs: {available}")

        selected = None
        if flair:
            # Try exact match (case-insensitive)
            flair_lower = flair.lower()
            for af in available:
                if af.lower() == flair_lower:
                    selected = af
                    break
            # Try partial match
            if not selected:
                for af in available:
                    if flair_lower in af.lower() or af.lower() in flair_lower:
                        selected = af
                        break
            if selected:
                print(f"Matched flair: '{selected}'")
            else:
                print(f"Flair '{flair}' not found. Selecting first available: '{available[0]}'")
                selected = available[0]
        else:
            # No flair specified, pick the first one
            selected = available[0]
            print(f"Auto-selecting first flair: '{selected}'")

        if self._click_flair_option(page, selected):
            # After selecting a predefined flair, check if it has an editable text field
            # (some flairs are "templates" where you select then customize the text)
            if flair and selected != flair:
                # User wanted specific text — try to edit if the field allows
                self._try_editable_flair(page, flair)
            self._apply_flair(page)
            print(f"Flair set: '{selected}'")
            return selected
        else:
            print(f"Warning: Could not click flair '{selected}'.")
            page.keyboard.press('Escape')
            page.wait_for_timeout(300)
            return None

    def _detect_flair_required_error(self, page: Page) -> bool:
        """Check if the page shows a 'flair required' error after posting."""
        error_patterns = [
            'text=/flair/i',
            'text=/select a flair/i',
            'text=/please select flair/i',
            'text=/flair is required/i',
            'text=/choose a flair/i',
            'text=/must have flair/i',
        ]
        for pattern in error_patterns:
            try:
                if page.locator(pattern).first.is_visible(timeout=1000):
                    return True
            except (PlaywrightTimeout, Exception):
                continue
        return False

    def _extract_post_url(self, page: Page, subreddit: str) -> str:
        """Extract the post URL from the current page after successful submission."""
        current_url = page.url
        if 'created=' in current_url:
            match = re.search(r'created=(t3_\w+)', current_url)
            if match:
                post_id = match.group(1).replace('t3_', '')
                return f"{REDDIT_BASE}/r/{subreddit}/comments/{post_id}/"
        return current_url

    # ── Main posting method ─────────────────────────────────────

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
            media_input = page.locator(
                'input[type="file"][accept*="video/mp4"][accept*="image/"]'
            ).first
            media_input.set_input_files(str(video_path.resolve()))

            # Step 5: Wait for video upload to complete
            print("Waiting for video upload to complete...")
            try:
                page.locator('text=Uploading').wait_for(state='visible', timeout=10_000)
            except PlaywrightTimeout:
                pass  # Maybe it uploaded too fast
            page.locator('text=Uploading').wait_for(state='hidden', timeout=timeout_ms)
            page.wait_for_timeout(2000)
            print("Video upload complete.")
            page.wait_for_timeout(random.randint(500, 1500))

            # Step 6: Enter title
            print(f"Entering title: {title}")
            title_input = page.locator(
                'textarea[name="title"], '
                'input[name="title"], '
                '[contenteditable="true"][aria-label*="title" i], '
                '[placeholder*="Title"]'
            ).first
            title_input.click(timeout=10_000)
            title_input.fill(title)
            page.wait_for_timeout(random.randint(300, 800))

            # Step 7: Handle flair (auto-detect, match, or auto-select)
            print("Checking flair options...")
            selected_flair = self._handle_flair(page, flair)
            page.wait_for_timeout(random.randint(300, 600))

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

            # Step 10: Wait for post creation (with flair-required retry)
            print("Waiting for post to be created...")
            try:
                page.wait_for_url(
                    lambda url: '/comments/' in url or 'created=' in url,
                    timeout=15_000
                )
            except PlaywrightTimeout:
                # Post didn't go through — check if flair is required
                if not selected_flair and self._detect_flair_required_error(page):
                    print("Flair is required! Attempting to auto-select flair...")
                    retry_flair = self._handle_flair(page, flair)
                    if retry_flair:
                        page.wait_for_timeout(random.randint(500, 1000))
                        post_button = page.locator('button:has-text("Post")').last
                        post_button.click()
                        page.wait_for_url(
                            lambda url: '/comments/' in url or 'created=' in url,
                            timeout=60_000
                        )
                    else:
                        raise RuntimeError(
                            f"Subreddit r/{subreddit} requires flair but no options available."
                        )
                else:
                    # Not a flair issue, wait longer for slow processing
                    page.wait_for_url(
                        lambda url: '/comments/' in url or 'created=' in url,
                        timeout=45_000
                    )

            post_url = self._extract_post_url(page, subreddit)
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
