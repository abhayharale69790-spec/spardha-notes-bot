"""Automated PDF Branding & Watermarking Engine for HARALE DIGITAL STUDY POINT."""

import io
import logging
import os
from pathlib import Path
from typing import Optional, Union

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen import canvas
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def create_watermark_canvas(
    page_width: float,
    page_height: float,
    brand_name: str = "HARALE DIGITAL STUDY POINT",
    brand_tagline: str = "स्पर्धा परीक्षा डिजिटल अभ्यास केंद्र",
    channel: str = "@spardhanoteshub",
    bot_username: str = "@SpardhaNotes_bot",
    is_first_page: bool = False,
) -> io.BytesIO:
    """Generate in-memory PDF overlay canvas containing diagonal watermark, header, and footer banners."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # --------------------------------------------------------------------------
    # 1. Subtle Diagonal Center Watermark
    # --------------------------------------------------------------------------
    can.saveState()
    # Light subtle gray with high transparency
    can.setFillColor(Color(0.65, 0.65, 0.70, alpha=0.14))
    can.setFont("Helvetica-Bold", min(38.0, page_width / 14))

    # Translate to center of the page and rotate 45 degrees
    can.translate(page_width / 2.0, page_height / 2.0)
    can.rotate(45)
    can.drawCentredString(0, 0, brand_name)
    can.restoreState()

    # --------------------------------------------------------------------------
    # 2. Top Header Accent Banner (Only on first page)
    # --------------------------------------------------------------------------
    if is_first_page:
        can.saveState()
        # Top branding accent box
        can.setFillColor(HexColor("#1A365D"), alpha=0.90)
        can.rect(0, page_height - 24, page_width, 24, fill=1, stroke=0)

        can.setFillColor(HexColor("#FFFFFF"))
        can.setFont("Helvetica-Bold", 9)
        can.drawCentredString(
            page_width / 2.0,
            page_height - 16,
            f"★ {brand_name} • MPSC / UPSC / POLICE BHARTI / JEE / NEET ★",
        )
        can.restoreState()

    # --------------------------------------------------------------------------
    # 3. Bottom Footer Banner on Every Page
    # --------------------------------------------------------------------------
    can.saveState()
    # Footer separator line
    can.setStrokeColor(HexColor("#CBD5E1"))
    can.setLineWidth(0.75)
    can.line(20, 22, page_width - 20, 22)

    # Footer text with branding and direct Telegram channel link
    can.setFillColor(HexColor("#1E293B"))
    can.setFont("Helvetica-Bold", 8)
    footer_text = f"📚 {brand_name}  |  Telegram: {channel}  |  Bot: {bot_username}"
    can.drawCentredString(page_width / 2.0, 10, footer_text)
    can.restoreState()

    can.save()
    packet.seek(0)
    return packet


def apply_harale_branding_to_pdf(
    input_pdf_path: str,
    output_pdf_path: Optional[str] = None,
    brand_name: Optional[str] = None,
    channel: Optional[str] = None,
    bot_username: Optional[str] = None,
) -> str:
    """Stamp 'HARALE DIGITAL STUDY POINT' branding, watermark, and footer onto all pages of input PDF.
    
    Returns the path of the watermarked output PDF file.
    """
    if not os.path.exists(input_pdf_path):
        raise FileNotFoundError(f"Input PDF file not found: {input_pdf_path}")

    b_name = brand_name or settings.brand_name
    b_tagline = settings.brand_tagline
    b_channel = channel or settings.brand_channel
    b_bot = bot_username or settings.brand_bot

    if not output_pdf_path:
        out_dir = Path("downloads") / "branded"
        out_dir.mkdir(parents=True, exist_ok=True)
        in_stem = Path(input_pdf_path).stem
        output_pdf_path = str(out_dir / f"{in_stem}_HaraleStudyPoint.pdf")

    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        total_pages = len(reader.pages)
        logger.info(f"Watermarking {total_pages} pages for '{b_name}' -> {output_pdf_path}")

        for i, page in enumerate(reader.pages):
            page_w = float(page.mediabox.width)
            page_h = float(page.mediabox.height)

            overlay_packet = create_watermark_canvas(
                page_width=page_w,
                page_height=page_h,
                brand_name=b_name,
                brand_tagline=b_tagline,
                channel=b_channel,
                bot_username=b_bot,
                is_first_page=(i == 0),
            )

            overlay_reader = PdfReader(overlay_packet)
            overlay_page = overlay_reader.pages[0]

            # Merge overlay onto original page
            page.merge_page(overlay_page)
            writer.add_page(page)

        # Write branded output
        with open(output_pdf_path, "wb") as f_out:
            writer.write(f_out)

        logger.info(f"Successfully created branded PDF: {output_pdf_path}")
        return output_pdf_path

    except Exception as e:
        logger.error(f"Failed to watermark PDF {input_pdf_path}: {e}", exc_info=True)
        # Fallback to original path if watermarking fails
        return input_pdf_path
