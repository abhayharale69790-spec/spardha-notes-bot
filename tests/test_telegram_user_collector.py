"""Unit & Integration Tests for Telegram MTProto User-Account Collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.models import ChannelAuthStatus, ExamCategory, MaterialType, SourceType, TelegramChannelSource
from collectors.telegram_channel_registry import TelegramChannelRegistry, ApprovedChannelConfig
from collectors.telegram_user_collector import TelegramUserCollector


@pytest.mark.asyncio
async def test_telegram_channel_registry_initialization():
    registry = TelegramChannelRegistry()
    mock_session = AsyncMock()

    with patch("database.crud.get_or_create_telegram_channel", new_callable=AsyncMock) as mock_crud:
        mock_crud.return_value = TelegramChannelSource(
            id=1,
            channel_id=-100123456,
            channel_username="test_mpsc_channel",
            title="Test MPSC Channel",
            exam_category=ExamCategory.MPSC,
            authorization_status=ChannelAuthStatus.AUTHORIZED,
        )

        sources = await registry.initialize_defaults(mock_session)
        assert len(sources) > 0
        assert mock_crud.call_count >= 5


def test_telegram_content_classification():
    collector = TelegramUserCollector()
    exam_cat, subject, topic, mtype, year = collector.classify_telegram_content(
        caption="MPSC Rajyaseva Combine Group B History PYQ 2024 Solved Papers",
        text_preview="आधुनिक महाराष्ट्राचा इतिहास व समाजसुधारक प्रश्नसंच",
        filename="MPSC_History_PYQ.pdf",
        channel_category=ExamCategory.MPSC,
    )

    assert exam_cat == ExamCategory.MPSC
    assert mtype == MaterialType.PYQ
    assert year == 2024
    assert "इतिहास" in subject or "History" in subject


@pytest.mark.asyncio
async def test_non_pdf_rejection_in_collector():
    collector = TelegramUserCollector()
    ch_source = TelegramChannelSource(
        id=1,
        channel_id=-100123456,
        channel_username="test_channel",
        title="Test Channel",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    )

    # Corrupt or non-PDF bytes
    fake_bytes = b"NOT_A_PDF_DOCUMENT_GARBAGE"
    result = await collector.process_document_bytes(
        raw_pdf_bytes=fake_bytes,
        original_filename="fake.pdf",
        caption="Fake file",
        channel_source=ch_source,
        msg_id=101,
    )
    assert result is None


@pytest.mark.asyncio
async def test_administrative_noise_rejection():
    collector = TelegramUserCollector()
    ch_source = TelegramChannelSource(
        id=1,
        channel_id=-100123456,
        channel_username="test_channel",
        title="Test Channel",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    )

    # Valid PDF bytes but administrative tender noise
    from reportlab.pdfgen import canvas
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "निविदा सूचना (Tender Notice) - खरेदी बाबत")
    c.drawString(100, 700, "कार्यालयासाठी संगणक खरेदी बाबत ई-निविदा दरपत्रक.")
    c.save()
    raw_pdf_bytes = buf.getvalue()

    result = await collector.process_document_bytes(
        raw_pdf_bytes=raw_pdf_bytes,
        original_filename="Tender_Notice.pdf",
        caption="निविदा सूचना ई-निविदा",
        channel_source=ch_source,
        msg_id=102,
    )
    assert result is None
