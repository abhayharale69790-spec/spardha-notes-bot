"""Unit Tests for Web Scrapers and 3-Point Bilingual Summary Generation."""

import pytest
from database.models import ExamCategory, MaterialType
from scraper.portal_watcher import (
    MPSCWatcher,
    MahaGRWatcher,
    PoliceBhartiWatcher,
    generate_3point_bilingual_summary,
)

SAMPLE_MPSC_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="announcement-wrapper">
        <div class="announcement-item">
            <a href="/uploads/Advt_01_2024_Rajyaseva_Syllabus.pdf">
                Advt No 01/2024 Maharashtra Civil Services Combined Preliminary Exam 2024 Syllabus
            </a>
            <span class="date">01/03/2024</span>
        </div>
        <div class="announcement-item">
            <a href="/uploads/Group_B_Combine_2023_Question_Paper.pdf">
                Maharashtra Non-Gazetted Group B Combine Exam 2023 Question Paper
            </a>
            <span class="date">15/02/2024</span>
        </div>
    </div>
</body>
</html>
"""

SAMPLE_MAHAGR_HTML = """
<!DOCTYPE html>
<html>
<body>
    <table>
        <tr>
            <td>General Administration Department</td>
            <td><a href="/Download.ashx?ID=GR_20240315120000.pdf">शासन निर्णय क्रमांक संकीर्ण-2024/प्र.क्र.12/कार्यासन-18</a></td>
            <td>15/03/2024</td>
        </tr>
    </table>
</body>
</html>
"""

SAMPLE_POLICE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="recruitment-list">
        <a href="/files/police_constable_physical_test_2024.pdf">
            Maharashtra Police Constable Recruitment 2024 Ground Physical Test Guidelines
        </a>
    </div>
</body>
</html>
"""


def test_3point_bilingual_summary_generator():
    """Test 3-point structured summary formatting."""
    summary = generate_3point_bilingual_summary(
        title="MPSC Rajyaseva 2024 Notification",
        department="महाराष्ट्र लोकसेवा आयोग (MPSC)",
        notice_type="Syllabus & Pattern",
        details="Official preliminary examination scheme 2024",
        exam_tag="MPSC",
    )
    assert "1️⃣" in summary
    assert "2️⃣" in summary
    assert "3️⃣" in summary
    assert "महाराष्ट्र लोकसेवा आयोग" in summary
    assert "MPSC" in summary


def test_mpsc_watcher_parsing():
    """Test parsing HTML notices from MPSC portal."""
    watcher = MPSCWatcher()
    notices = watcher.parse_notices(SAMPLE_MPSC_HTML)

    assert len(notices) == 2

    # Check first notice (Syllabus)
    assert "Syllabus" in notices[0].title
    assert notices[0].pdf_url.endswith("Advt_01_2024_Rajyaseva_Syllabus.pdf")
    assert notices[0].exam_category == ExamCategory.MPSC
    assert notices[0].material_type == MaterialType.SYLLABUS
    assert notices[0].year == 2024

    # Check second notice (PYQ)
    assert "Question Paper" in notices[1].title
    assert notices[1].material_type == MaterialType.PYQ
    assert notices[1].year == 2023


def test_maha_gr_watcher_parsing():
    """Test parsing GR notices from Maharashtra Government portal."""
    watcher = MahaGRWatcher()
    notices = watcher.parse_notices(SAMPLE_MAHAGR_HTML)

    assert len(notices) >= 1
    assert "शासन निर्णय" in notices[0].title or "GR" in notices[0].pdf_url
    assert notices[0].material_type == MaterialType.GR
    assert notices[0].exam_category == ExamCategory.GENERAL


def test_police_bharti_watcher_parsing():
    """Test parsing recruitment notices from Police Bharti portal."""
    watcher = PoliceBhartiWatcher()
    notices = watcher.parse_notices(SAMPLE_POLICE_HTML)

    assert len(notices) == 1
    assert "Police Constable" in notices[0].title
    assert notices[0].exam_category == ExamCategory.POLICE_BHARTI
    assert notices[0].year == 2024
