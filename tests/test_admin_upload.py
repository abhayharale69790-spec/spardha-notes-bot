"""Unit Tests for Admin Document Upload & Keyboard Generators."""

import pytest
from bot.handlers.admin_upload import (
    AdminUploadCallback,
    get_categories_keyboard,
    get_subjects_keyboard,
    get_action_keyboard,
)


def test_admin_upload_callback_serialization():
    """Verify AdminUploadCallback pack and unpack."""
    cb = AdminUploadCallback(step="cat", category="mpsc", uid="up123456")
    packed = cb.pack()
    unpacked = AdminUploadCallback.unpack(packed)
    assert unpacked.step == "cat"
    assert unpacked.category == "mpsc"
    assert unpacked.uid == "up123456"


def test_admin_upload_keyboards():
    """Verify keyboards contain appropriate buttons."""
    cat_kb = get_categories_keyboard(upload_id="up123456")
    assert len(cat_kb.inline_keyboard) >= 3

    subj_kb = get_subjects_keyboard(category="mpsc", upload_id="up123456")
    assert len(subj_kb.inline_keyboard) >= 2

    act_kb = get_action_keyboard(category="mpsc", subject="Polity", upload_id="up123456")
    assert len(act_kb.inline_keyboard) == 3
