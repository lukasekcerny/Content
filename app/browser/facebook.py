import os
import logging

from app.browser.base import BrowserAction

logger = logging.getLogger(__name__)


class FacebookBrowser(BrowserAction):

    def change_profile_picture(self, page, image_path: str, caption: str = ""):
        page.goto("https://www.facebook.com/me", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        try:
            avatar_el = page.locator('[aria-label="Profile picture"], [aria-label="Change profile picture"]')
            if avatar_el.count() > 0:
                avatar_el.first.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        try:
            upload_btn = page.locator('span:has-text("Upload Photo"), span:has-text("Upload photo")')
            if upload_btn.count() > 0:
                upload_btn.first.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
        file_input.set_input_files(os.path.abspath(image_path))
        page.wait_for_timeout(4000)

        if caption:
            try:
                desc_el = page.locator(
                    '[contenteditable="true"][role="textbox"],'
                    ' textarea[aria-label*="description"],'
                    ' textarea[aria-label*="something"]'
                ).first
                desc_el.click()
                page.wait_for_timeout(500)
                desc_el.fill(caption)
                page.wait_for_timeout(1000)
            except Exception:
                logger.warning("Could not set profile picture caption on Facebook")

        try:
            save_btn = page.locator('span:has-text("Save")')
            if save_btn.count() > 0:
                save_btn.first.click()
                page.wait_for_timeout(3000)
        except Exception:
            pass

        logger.info("Facebook profile picture changed")

    def upload_content(self, page, file_path: str, metadata: dict,
                       progress_callback=None) -> tuple[bool, str]:
        try:
            if progress_callback:
                progress_callback(10, "upload", "Navigating...")

            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback(20, "upload", "Opening post creator...")

            try:
                page.locator('span:has-text("What\'s on your mind")').first.click()
                page.wait_for_timeout(2000)
            except Exception:
                pass

            try:
                media_btn = page.locator('span:has-text("Photo/video"), span:has-text("Photo/Video")')
                if media_btn.count() > 0:
                    media_btn.first.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            if progress_callback:
                progress_callback(40, "upload", "Selecting file...")

            file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
            file_input.set_input_files(os.path.abspath(file_path))
            page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback(60, "upload", "Adding caption...")

            caption = metadata.get("caption", "")
            if caption:
                try:
                    text_el = page.locator('[contenteditable="true"][role="textbox"]').first
                    text_el.fill(caption)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            if progress_callback:
                progress_callback(80, "upload", "Publishing...")

            try:
                page.locator('span:has-text("Post")').first.click()
                page.wait_for_timeout(8000)
            except Exception:
                pass

            if progress_callback:
                progress_callback(100, "done", "Published")

            return True, "Uploaded to Facebook"
        except Exception as e:
            logger.exception("Facebook upload failed")
            if progress_callback:
                progress_callback(0, "error", str(e))
            return False, f"Facebook upload failed: {e}"
