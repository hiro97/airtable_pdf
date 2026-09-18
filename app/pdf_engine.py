import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = os.path.join(BASE_DIR, "app", "templates")

class PDFEngine:
    """Universal PDF rendering engine supporting multiple document templates"""

    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_ROOT),
            autoescape=True
        )

    def _get_inline_css(self, template_subpath: str, css_filename: str) -> str:
        """Load CSS content for inline embedding to ensure reliable font/style loading"""
        css_file = os.path.join(TEMPLATES_ROOT, template_subpath, css_filename)
        if os.path.exists(css_file):
            with open(css_file, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def render_html(self, template_subpath: str, template_filename: str, css_filename: str, data: dict) -> str:
        """Render any document template with its corresponding CSS"""
        full_template_path = os.path.join(template_subpath, template_filename)
        template = self.jinja_env.get_template(full_template_path)
        
        # Inject inline CSS into template data
        data_copy = dict(data)
        data_copy["inline_css"] = self._get_inline_css(template_subpath, css_filename)
        return template.render(**data_copy)

    async def generate_pdf(
        self,
        template_subpath: str,
        template_filename: str,
        css_filename: str,
        data: dict,
        output_filename: str,
        page_format: str = "A4",
        screenshot_filename: str | None = None
    ) -> Path:
        """Render HTML and convert to PDF via Playwright Headless Chromium"""
        html_content = self.render_html(template_subpath, template_filename, css_filename, data)
        output_path = self.storage_dir / output_filename

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--font-render-hinting=none"
                ]
            )
            context = await browser.new_context(
                viewport={"width": 794, "height": 1123},
                device_scale_factor=2
            )
            page = await context.new_page()

            await page.set_content(html_content, wait_until="networkidle")

            if screenshot_filename:
                screenshot_path = self.storage_dir / screenshot_filename
                await page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info(f"Generated preview screenshot: {screenshot_path}")

            await page.pdf(
                path=str(output_path),
                format=page_format,
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
            )
            await browser.close()

        logger.info(f"Generated PDF successfully: {output_path}")
        return output_path
