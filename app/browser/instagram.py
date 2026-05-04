import os
import logging

from app.browser.base import BrowserAction

logger = logging.getLogger(__name__)


class InstagramBrowser(BrowserAction):

    def change_profile_picture(self, page, image_path: str, caption: str = ""):
        page.goto("https://www.instagram.com/accounts/edit/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        try:
            change_btn = page.locator('button:has-text("Change"), button:has-text("profile photo")')
            if change_btn.count() > 0:
                change_btn.first.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
        file_input.set_input_files(os.path.abspath(image_path))
        page.wait_for_timeout(4000)

        logger.info("Instagram profile picture changed")

        if caption:
            self._update_bio(page, caption)

    def _update_bio(self, page, bio_text: str):
        """Set the bio on the Instagram profile edit page."""
        try:
            page.goto(
                "https://www.instagram.com/accounts/edit/",
                wait_until="domcontentloaded", timeout=30000,
            )
            page.wait_for_timeout(2500)

            bio_textarea = page.locator(
                'textarea[name="biography"], textarea[aria-label="Bio"]'
            )
            if bio_textarea.count() == 0:
                logger.warning("Instagram bio textarea not found - skipping bio update")
                return

            bio_textarea.first.fill(bio_text)
            page.wait_for_timeout(800)

            for label in ("Submit", "Save", "Done"):
                try:
                    btn = page.locator(f'button:has-text("{label}")')
                    if btn.count() > 0:
                        btn.first.click()
                        page.wait_for_timeout(2500)
                        break
                except Exception:
                    continue
            logger.info("Instagram bio updated")
        except Exception:
            logger.exception("Instagram bio update failed")

    def upload_content(self, page, file_path: str, metadata: dict,
                       progress_callback=None) -> tuple[bool, str]:
        try:
            if progress_callback:
                progress_callback(10, "upload", "Navigating...")

            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback(20, "upload", "Opening upload...")

            try:
                create_btn = page.locator('svg[aria-label="New post"], [aria-label="New Post"]')
                if create_btn.count() > 0:
                    create_btn.first.click()
                    page.wait_for_timeout(2000)
                else:
                    page.locator('span:has-text("Create")').first.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            if progress_callback:
                progress_callback(30, "upload", "Selecting file...")

            file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
            file_input.set_input_files(os.path.abspath(file_path))
            page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback(50, "upload", "Processing...")

            for _ in range(2):
                try:
                    next_btn = page.locator('button:has-text("Next")')
                    if next_btn.count() > 0:
                        next_btn.first.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    break

            if progress_callback:
                progress_callback(70, "upload", "Adding caption...")

            caption = metadata.get("caption", "")
            if caption:
                try:
                    caption_el = page.locator('textarea[aria-label="Write a caption..."], [contenteditable="true"]').first
                    caption_el.fill(caption)
                    page.wait_for_timeout(1000)
                except Exception:
                    logger.warning("Could not set caption")

            try:
                page.locator('button:has-text("Share")').first.click()
                page.wait_for_timeout(8000)
            except Exception:
                pass

            if progress_callback:
                progress_callback(100, "done", "Published")

            return True, "Uploaded to Instagram"
        except Exception as e:
            logger.exception("Instagram upload failed")
            if progress_callback:
                progress_callback(0, "error", str(e))
            return False, f"Instagram upload failed: {e}"
