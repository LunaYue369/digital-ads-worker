#!/usr/bin/env python3
"""
Reddit Browser Automation Client
Uses Playwright to post videos to Reddit via browser automation.
"""
import re
import random
import time
from pathlib import Path
from typing import Optional, List
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

SESSION_DIR_DEFAULT = Path(__file__).parent.parent.parent / 'data' / 'reddit_session'
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
            launch_args = [
                '--disable-blink-features=AutomationControlled',
            ]
            if self.headless:
                launch_args.append('--start-minimized')
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_dir),
                headless=False,  # Reddit blocks headless, always use headed
                viewport={'width': 1280, 'height': 900},
                locale='en-US',
                args=launch_args,
            )
            # Hide webdriver flag on every new page
            self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
        return self._context

    # ── Human-like behavior helpers ──────────────────────────────

    def _human_delay(self, min_ms: int = 300, max_ms: int = 1200):
        """Sleep for a random human-like duration."""
        time.sleep(random.randint(min_ms, max_ms) / 1000.0)

    def _human_type(self, page: Page, locator, text: str):
        """Type text character by character with random delays, like a human."""
        locator.click()
        self._human_delay(200, 500)
        for char in text:
            page.keyboard.type(char, delay=random.randint(30, 150))
            # Occasional longer pause (simulates thinking/reading)
            if random.random() < 0.05:
                self._human_delay(300, 800)

    def _human_click(self, locator):
        """Click with a small random delay before and after, like a human."""
        self._human_delay(200, 600)
        locator.click()
        self._human_delay(150, 400)

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
                self._human_click(flair_button)
                self._human_delay(500, 1000)
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
                    self._human_click(locator)
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
                self._human_click(apply_btn)
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
                    self._human_type(page, field, flair_text)
                    self._human_delay(200, 500)
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
                self._human_delay(200, 500)
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
            self._human_delay(200, 500)
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

    # ── Comment helper ────────────────────────────────────────────

    def _post_comment(self, page: Page, post_url: str, body: str) -> bool:
        """Navigate to a post and add a comment with the given body text."""
        print(f"Adding comment to post...")

        # Always navigate to the actual post page to ensure comment box is present
        page.goto(post_url, wait_until='domcontentloaded', timeout=30_000)
        self._human_delay(3000, 5000)

        # Scroll down to ensure the comment area is in view
        page.evaluate('window.scrollBy(0, 400)')
        self._human_delay(1500, 2500)

        try:
            # New Reddit uses web components (shadow DOM) for the comment composer.
            # Playwright's visibility checks fail on these custom elements, so we
            # use JavaScript to interact with them directly.
            #
            # Two-stage flow:
            # 1. Collapsed: <faceplate-textarea-input data-testid="trigger-button">
            #    — click to expand the editor
            # 2. Expanded: <shreddit-composer> with <div slot="rte" contenteditable>
            #    — the actual rich text editor to type into

            # Step 1: Click the trigger to expand the comment editor.
            # The trigger is a custom web component (faceplate-textarea-input)
            # rendered via shadow DOM. Use JS to scroll into view and click it.
            trigger_rect = page.evaluate('''() => {
                const trigger = document.querySelector(
                    'faceplate-textarea-input[data-testid="trigger-button"]'
                );
                if (trigger) {
                    trigger.scrollIntoView({ behavior: "smooth", block: "center" });
                    const r = trigger.getBoundingClientRect();
                    return { x: r.x, y: r.y, w: r.width, h: r.height };
                }
                return null;
            }''')
            if not trigger_rect:
                print("Warning: Could not find comment trigger button.")
                return False
            self._human_delay(500, 1000)

            # Click the trigger at its center using mouse coordinates
            page.mouse.click(
                trigger_rect['x'] + trigger_rect['w'] / 2,
                trigger_rect['y'] + trigger_rect['h'] / 2,
            )
            self._human_delay(2000, 3500)

            # Step 2: Find the expanded comment editor and click its center.
            # After expanding, the shreddit-composer should become visible.
            editor_rect = page.evaluate('''() => {
                const composers = document.querySelectorAll('shreddit-composer');
                for (const c of composers) {
                    if (c.offsetWidth > 0 && c.offsetHeight > 0) {
                        const r = c.getBoundingClientRect();
                        return { x: r.x, y: r.y, w: r.width, h: r.height };
                    }
                }
                return null;
            }''')
            if not editor_rect:
                print("Warning: Comment editor did not expand.")
                return False

            # Click at the center of the editor area
            page.mouse.click(
                editor_rect['x'] + editor_rect['w'] / 2,
                editor_rect['y'] + editor_rect['h'] / 2,
            )
            self._human_delay(500, 1000)

            # Step 3: Type the comment via keyboard
            for char in body:
                page.keyboard.type(char, delay=random.randint(30, 120))
                if random.random() < 0.05:
                    self._human_delay(200, 600)
            self._human_delay(800, 1500)

            # Step 4: Click the Comment submit button.
            # Find it via JS, get its rect, then mouse-click it.
            btn_rect = page.evaluate('''() => {
                const btns = [...document.querySelectorAll('button')];
                const commentBtn = btns.reverse().find(
                    b => b.textContent.trim() === 'Comment'
                );
                if (commentBtn) {
                    const r = commentBtn.getBoundingClientRect();
                    return { x: r.x, y: r.y, w: r.width, h: r.height };
                }
                return null;
            }''')
            if btn_rect:
                page.mouse.click(
                    btn_rect['x'] + btn_rect['w'] / 2,
                    btn_rect['y'] + btn_rect['h'] / 2,
                )
            else:
                # Fallback: JS click
                page.evaluate('''() => {
                    const btns = [...document.querySelectorAll('button')];
                    const commentBtn = btns.reverse().find(
                        b => b.textContent.trim() === 'Comment'
                    );
                    if (commentBtn) commentBtn.click();
                }''')
            self._human_delay(3000, 5000)
            print("Comment posted successfully.")
            return True
        except (PlaywrightTimeout, Exception) as e:
            print(f"Warning: Could not post comment: {e}")

        return False

    # ── Main posting method ─────────────────────────────────────

    def post_video(
        self,
        video_path: Path,
        subreddit: str,
        title: str,
        body: Optional[str] = None,
        flair: Optional[str] = None,
        nsfw: bool = False,
        timeout_ms: int = 180_000,
    ) -> str:
        """
        Post a video to a Reddit subreddit.
        If body is provided, it will be added as a comment after posting.
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
            self._human_delay(1500, 3000)  # "reading the page"

            # Step 2: Check if redirected to login
            if '/login' in page.url or '/register' in page.url:
                raise RuntimeError(
                    "Reddit session expired. Run 'python tools/reddit/reddit_login.py' to log in."
                )

            # Step 3: Select Images & Video tab
            print("Selecting video upload tab...")
            tab = page.locator('[role="tab"]:has-text("Images & Video")')
            self._human_click(tab)
            self._human_delay(1000, 2000)

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
            self._human_delay(1500, 3000)  # "checking the preview"
            print("Video upload complete.")

            # Step 6: Enter title (human-like typing)
            print(f"Entering title: {title}")
            title_input = page.locator(
                'textarea[name="title"], '
                'input[name="title"], '
                '[contenteditable="true"][aria-label*="title" i], '
                '[placeholder*="Title"]'
            ).first
            title_input.wait_for(state='visible', timeout=10_000)
            self._human_type(page, title_input, title)
            self._human_delay(500, 1200)  # "re-reading the title"

            # Step 7: Handle flair (auto-detect, match, or auto-select)
            print("Checking flair options...")
            selected_flair = self._handle_flair(page, flair)
            self._human_delay(400, 900)

            # Step 8: Mark NSFW if needed
            if nsfw:
                try:
                    nsfw_toggle = page.locator('button:has-text("NSFW")').first
                    if nsfw_toggle.is_visible(timeout=3000):
                        self._human_click(nsfw_toggle)
                except (PlaywrightTimeout, Exception):
                    print("Warning: Could not set NSFW flag.")

            # Step 9: Click Post button
            print("Submitting post...")
            self._human_delay(800, 2000)  # "final review before posting"
            post_button = page.locator('button:has-text("Post")').last
            self._human_click(post_button)

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
                    self._human_delay(500, 1200)
                    retry_flair = self._handle_flair(page, flair)
                    if retry_flair:
                        self._human_delay(600, 1500)
                        post_button = page.locator('button:has-text("Post")').last
                        self._human_click(post_button)
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

            # Add body text as a comment if provided
            if body:
                self._human_delay(1000, 2000)
                self._post_comment(page, post_url, body)

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

    def post_text(
        self,
        subreddit: str,
        title: str,
        body: str,
        flair: Optional[str] = None,
        nsfw: bool = False,
    ) -> str:
        """
        Post a text-only post to a Reddit subreddit.
        Returns: URL of the created post.
        """
        context = self._ensure_browser()
        page = context.new_page()

        try:
            # Step 1: Navigate to subreddit submit page
            submit_url = f"{REDDIT_BASE}/r/{subreddit}/submit"
            print(f"Navigating to {submit_url}...")
            page.goto(submit_url, wait_until='domcontentloaded', timeout=30_000)
            self._human_delay(1500, 3000)

            # Step 2: Check if redirected to login
            if '/login' in page.url or '/register' in page.url:
                raise RuntimeError(
                    "Reddit session expired. Run 'python tools/reddit/reddit_login.py' to log in."
                )

            # Step 3: The "Post" (text) tab is the default, but click it to be safe
            print("Selecting text post tab...")
            try:
                text_tab = page.locator('[role="tab"]:has-text("Post")').first
                if text_tab.is_visible(timeout=3000):
                    self._human_click(text_tab)
                    self._human_delay(800, 1500)
            except (PlaywrightTimeout, Exception):
                pass  # Already on the text tab

            # Step 4: Enter title
            print(f"Entering title: {title}")
            title_input = page.locator(
                'textarea[name="title"], '
                'input[name="title"], '
                '[contenteditable="true"][aria-label*="title" i], '
                '[placeholder*="Title"]'
            ).first
            title_input.wait_for(state='visible', timeout=10_000)
            self._human_type(page, title_input, title)
            self._human_delay(500, 1200)

            # Step 5: Enter body text in the rich text editor
            # The editor is a web component (shreddit-composer) with shadow DOM.
            # The slotted contenteditable div is invisible to Playwright, but the
            # shreddit-composer element itself IS visible. We click its center
            # coordinates with page.mouse.click() to focus the editor.
            print("Entering body text...")

            # Get bounding rect of the body shreddit-composer
            rect = page.evaluate('''() => {
                const composers = document.querySelectorAll('shreddit-composer');
                for (const c of composers) {
                    if (c.offsetWidth > 0 && c.offsetHeight > 0) {
                        const r = c.getBoundingClientRect();
                        return { x: r.x, y: r.y, w: r.width, h: r.height };
                    }
                }
                return null;
            }''')
            if not rect:
                raise RuntimeError("Could not find body text editor on page.")

            # Click at the center of the body editor area
            center_x = rect['x'] + rect['w'] / 2
            center_y = rect['y'] + rect['h'] / 2
            page.mouse.click(center_x, center_y)
            self._human_delay(500, 1000)

            # Type the body text via keyboard
            for char in body:
                page.keyboard.type(char, delay=random.randint(30, 120))
                if random.random() < 0.05:
                    self._human_delay(200, 600)
            self._human_delay(800, 1500)

            # Step 6: Handle flair
            print("Checking flair options...")
            selected_flair = self._handle_flair(page, flair)
            self._human_delay(400, 900)

            # Step 7: Mark NSFW if needed
            if nsfw:
                try:
                    nsfw_toggle = page.locator('button:has-text("NSFW")').first
                    if nsfw_toggle.is_visible(timeout=3000):
                        self._human_click(nsfw_toggle)
                except (PlaywrightTimeout, Exception):
                    print("Warning: Could not set NSFW flag.")

            # Step 8: Click Post button
            print("Submitting post...")
            self._human_delay(800, 2000)
            post_button = page.locator('button:has-text("Post")').last
            self._human_click(post_button)

            # Step 9: Wait for post creation (with flair-required retry)
            print("Waiting for post to be created...")
            try:
                page.wait_for_url(
                    lambda url: '/comments/' in url or 'created=' in url,
                    timeout=15_000
                )
            except PlaywrightTimeout:
                if not selected_flair and self._detect_flair_required_error(page):
                    print("Flair is required! Attempting to auto-select flair...")
                    self._human_delay(500, 1200)
                    retry_flair = self._handle_flair(page, flair)
                    if retry_flair:
                        self._human_delay(600, 1500)
                        post_button = page.locator('button:has-text("Post")').last
                        self._human_click(post_button)
                        page.wait_for_url(
                            lambda url: '/comments/' in url or 'created=' in url,
                            timeout=60_000
                        )
                    else:
                        raise RuntimeError(
                            f"Subreddit r/{subreddit} requires flair but no options available."
                        )
                else:
                    page.wait_for_url(
                        lambda url: '/comments/' in url or 'created=' in url,
                        timeout=45_000
                    )

            post_url = self._extract_post_url(page, subreddit)
            print(f"Post created: {post_url}")
            return post_url

        except PlaywrightTimeout as e:
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
