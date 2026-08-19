"""Unit Tests for Inline Keyboard Factories and Callback Serialization."""

from bot.keyboards.inline_menus import (
    NavAction,
    CategoryNavCallback,
    MaterialDownloadCallback,
    StagingApprovalCallback,
    get_main_menu_keyboard,
    get_categories_keyboard,
    get_subjects_keyboard,
    get_years_or_materials_keyboard,
    get_materials_list_keyboard,
    get_staging_action_keyboard,
)
from database.models import ExamCategory, MaterialType, StudyMaterial


def test_callback_serialization():
    """Test aiogram CallbackData pack and unpack roundtrips."""
    cb = CategoryNavCallback(
        action=NavAction.SELECT_SUBJ.value,
        category="MPSC",
        subject="Polity",
        year=2024,
        page=2,
    )
    packed = cb.pack()
    unpacked = CategoryNavCallback.unpack(packed)

    assert unpacked.action == NavAction.SELECT_SUBJ.value
    assert unpacked.category == "MPSC"
    assert unpacked.subject == "Polity"
    assert unpacked.year == 2024
    assert unpacked.page == 2

    # Material download callback
    dl_cb = MaterialDownloadCallback(material_id=42)
    dl_packed = dl_cb.pack()
    dl_unpacked = MaterialDownloadCallback.unpack(dl_packed)
    assert dl_unpacked.material_id == 42

    # Staging approval callback
    stg_cb = StagingApprovalCallback(action="approve", staging_id=101)
    stg_packed = stg_cb.pack()
    stg_unpacked = StagingApprovalCallback.unpack(stg_packed)
    assert stg_unpacked.action == "approve"
    assert stg_unpacked.staging_id == 101


def test_main_menu_keyboard():
    """Test generating root navigation keyboard."""
    kb = get_main_menu_keyboard()
    assert kb.inline_keyboard is not None
    assert len(kb.inline_keyboard) >= 3


def test_categories_keyboard():
    """Test category selection keyboard contains all categories and back button."""
    kb = get_categories_keyboard()
    total_buttons = sum(len(row) for row in kb.inline_keyboard)
    assert total_buttons >= len(ExamCategory) + 1


def test_subjects_keyboard():
    """Test subjects keyboard generation."""
    subjects = ["Polity", "History", "Geography"]
    kb = get_subjects_keyboard("MPSC", subjects)
    assert len(kb.inline_keyboard) == len(subjects) + 1


def test_materials_list_keyboard_pagination():
    """Test paginated materials list keyboard with next and prev buttons."""
    mock_materials = [
        StudyMaterial(
            id=i,
            title=f"Sample Material #{i}",
            exam_category=ExamCategory.MPSC,
            subject="General",
            material_type=MaterialType.GR,
            file_path="https://example.com/test.pdf",
            year=2024,
        )
        for i in range(1, 6)
    ]

    kb = get_materials_list_keyboard(
        materials=mock_materials,
        category="MPSC",
        subject="General",
        page=2,
        has_next=True,
    )
    # Materials + nav buttons (Prev, Page 2, Next) + back buttons
    assert len(kb.inline_keyboard) == len(mock_materials) + 2


def test_staging_action_keyboard():
    """Test staging moderation buttons."""
    kb = get_staging_action_keyboard(staging_id=77)
    assert len(kb.inline_keyboard) == 1
    assert len(kb.inline_keyboard[0]) == 2
    assert "Approve" in kb.inline_keyboard[0][0].text
    assert "Discard" in kb.inline_keyboard[0][1].text
