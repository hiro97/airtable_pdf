import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = os.path.join(BASE_DIR, "app", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "app", "static")

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)

class PDFService:
    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Load style.css for inline embedding (ensures reliable rendering in headless chromium)
        css_file = os.path.join(STATIC_DIR, "css", "style.css")
        if os.path.exists(css_file):
            with open(css_file, "r", encoding="utf-8") as f:
                self.inline_css = f.read()
        else:
            self.inline_css = ""

    def render_html(self, data: dict) -> str:
        """Render PO data into HTML using Jinja2"""
        template = jinja_env.get_template("po_template.html")
        data["inline_css"] = self.inline_css
        return template.render(**data)

    async def generate_pdf(self, data: dict, output_filename: str) -> Path:
        """Generate A4 PDF from PO data using Playwright Headless Chromium"""
        html_content = self.render_html(data)
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
            context = await browser.new_context()
            page = await context.new_page()

            # Set content and wait until network/fonts are loaded
            await page.set_content(html_content, wait_until="networkidle")

            # Generate PDF with standard A4 specs and print-background enabled
            await page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
            )
            await browser.close()

        logger.info(f"PDF generated successfully at: {output_path}")
        return output_path
