import os
import logging

from app.browser.base import BrowserAction

logger = logging.getLogger(__name__)


class YouTubeBrowser(BrowserAction):

    def change_profile_picture(self, page, image_path: str, caption: str = ""):
        page.goto("https://studio.youtube.com/channel/UC/editing/images", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)

        try:
            upload_area = page.locator('div:has-text("UPLOAD"), div:has-text("Upload")')
            if upload_area.count() > 0:
                upload_area.first.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
        file_input.set_input_files(os.path.abspath(image_path))
        page.wait_for_timeout(4000)

        try:
            done_btn = page.locator('button:has-text("DONE"), button:has-text("Done")')
            if done_btn.count() > 0:
                done_btn.first.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        try:
            publish_btn = page.locator('button:has-text("PUBLISH"), button:has-text("Publish")')
            if publish_btn.count() > 0:
                publish_btn.first.click()
                page.wait_for_timeout(3000)
        except Exception:
            pass

        logger.info("YouTube profile picture changed")

        if caption:
            self._update_bio(page, caption)

    def _update_bio(self, page, bio_text: str):
        """Set the channel description (the YouTube equivalent of a bio).

        Channel description lives in YouTube Studio at
        ``studio.youtube.com/channel/UC/editing/details``.
        """
        try:
            page.goto(
                "https://studio.youtube.com/channel/UC/editing/details",
                wait_until="domcontentloaded", timeout=30000,
            )
            page.wait_for_timeout(3500)

            desc_textarea = page.locator(
                'textarea[aria-label="Description"], '
                '#description-textarea textarea, '
                'ytcp-form-input-container[id="description"] textarea'
            )
            if desc_textarea.count() == 0:
                logger.warning("YouTube channel description textarea not found")
                return

            desc_textarea.first.fill(bio_text)
            page.wait_for_timeout(800)

            for label in ("PUBLISH", "Publish", "SAVE", "Save"):
                try:
                    btn = page.locator(f'button:has-text("{label}")')
                    if btn.count() > 0:
                        btn.first.click()
                        page.wait_for_timeout(3000)
                        break
                except Exception:
                    continue
            logger.info("YouTube channel description updated")
        except Exception:
            logger.exception("YouTube bio (description) update failed")

    def upload_content(self, page, file_path: str, metadata: dict,
                       progress_callback=None) -> tuple[bool, str]:
        try:
            if progress_callback:
                progress_callback(10, "upload", "Navigating...")

            page.goto("https://studio.youtube.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            try:
                create_btn = page.locator('#create-icon, [id="create-icon"]')
                if create_btn.count() > 0:
                    create_btn.first.click()
                    page.wait_for_timeout(2000)
                    upload_item = page.locator('tp-yt-paper-item:has-text("Upload")')
                    if upload_item.count() > 0:
                        upload_item.first.click()
                        page.wait_for_timeout(2000)
                else:
                    page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)
            except Exception:
                page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback(20, "upload", "Selecting file...")

            file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
            file_input.set_input_files(os.path.abspath(file_path))
            page.wait_for_timeout(5000)

            if progress_callback:
                progress_callback(40, "upload", "Setting metadata...")

            title = metadata.get("title", "")
            if title:
                try:
                    title_el = page.locator('#textbox[aria-label="Add a title"]')
                    if title_el.count() > 0:
                        title_el.first.fill("")
                        title_el.first.fill(title)
                        page.wait_for_timeout(500)
                except Exception:
                    pass

            description = metadata.get("description", "")
            if description:
                try:
                    desc_el = page.locator('#textbox[aria-label="Tell viewers about your video"]')
                    if desc_el.count() > 0:
                        desc_el.first.fill(description)
                        page.wait_for_timeout(500)
                except Exception:
                    pass

            if progress_callback:
                progress_callback(60, "upload", "Setting visibility...")

            for _ in range(3):
                try:
                    next_btn = page.locator('#next-button')
                    if next_btn.count() > 0:
                        next_btn.first.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    break

            if progress_callback:
                progress_callback(80, "upload", "Publishing...")

            try:
                public_radio = page.locator('tp-yt-paper-radio-button[name="PUBLIC"]')
                if public_radio.count() > 0:
                    public_radio.first.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            try:
                done_btn = page.locator('#done-button')
                if done_btn.count() > 0:
                    done_btn.first.click()
                    page.wait_for_timeout(8000)
            except Exception:
                pass

            if progress_callback:
                progress_callback(100, "done", "Published")

            return True, "Uploaded to YouTube"
        except Exception as e:
            logger.exception("YouTube upload failed")
            if progress_callback:
                progress_callback(0, "error", str(e))
            return False, f"YouTube upload failed: {e}"
