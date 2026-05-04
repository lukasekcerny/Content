import os
import logging

from app.browser.base import BrowserAction

logger = logging.getLogger(__name__)


class TikTokBrowser(BrowserAction):

    def change_profile_picture(self, page, image_path: str, caption: str = ""):
        page.goto("https://www.tiktok.com/setting/edit-profile", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
        file_input.set_input_files(os.path.abspath(image_path))
        page.wait_for_timeout(3000)

        try:
            save_btn = page.locator('button:has-text("Apply"), button:has-text("Save")')
            if save_btn.count() > 0:
                save_btn.first.click()
                page.wait_for_timeout(3000)
        except Exception:
            pass

        logger.info("TikTok profile picture changed")

        if caption:
            self._update_bio(page, caption)

    def _update_bio(self, page, bio_text: str):
        """Set the bio on the TikTok edit-profile page."""
        try:
            page.goto(
                "https://www.tiktok.com/setting/edit-profile",
                wait_until="domcontentloaded", timeout=30000,
            )
            page.wait_for_timeout(2500)

            bio_textarea = page.locator(
                'textarea[maxlength="80"], textarea[placeholder*="Bio"], textarea[aria-label*="Bio"]'
            )
            if bio_textarea.count() == 0:
                logger.warning("TikTok bio textarea not found - skipping bio update")
                return

            bio_textarea.first.fill(bio_text)
            page.wait_for_timeout(800)

            for label in ("Save", "Apply", "Done"):
                try:
                    btn = page.locator(f'button:has-text("{label}")')
                    if btn.count() > 0:
                        btn.first.click()
                        page.wait_for_timeout(2500)
                        break
                except Exception:
                    continue
            logger.info("TikTok bio updated")
        except Exception:
            logger.exception("TikTok bio update failed")

    def upload_content(self, page, file_path: str, metadata: dict,
                       progress_callback=None) -> tuple[bool, str]:
        try:
            if progress_callback:
                progress_callback(10, "upload", "Navigating...")

            page.goto("https://www.tiktok.com/upload", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback(20, "upload", "Selecting file...")

            file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
            file_input.set_input_files(os.path.abspath(file_path))
            page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback(40, "upload", "File selected...")

            caption = metadata.get("caption", "")
            if caption:
                try:
                    caption_el = page.locator('[data-text="true"], [contenteditable="true"], .public-DraftEditor-content').first
                    caption_el.fill(caption)
                    page.wait_for_timeout(1000)
                except Exception:
                    logger.warning("Could not set caption")

            if progress_callback:
                progress_callback(60, "upload", "Uploading...")

            page.wait_for_timeout(5000)

            try:
                post_btn = page.locator('button:has-text("Post"), button:has-text("Upload")')
                if post_btn.count() > 0:
                    post_btn.first.click()
                    page.wait_for_timeout(8000)
            except Exception:
                pass

            if progress_callback:
                progress_callback(100, "done", "Published")

            return True, "Uploaded to TikTok"
        except Exception as e:
            logger.exception("TikTok upload failed")
            if progress_callback:
                progress_callback(0, "error", str(e))
            return False, f"TikTok upload failed: {e}"
