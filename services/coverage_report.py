"""Coverage Reporting & Dashboard Formatter.

Renders high-clarity visual console dashboards, structured markdown tables,
and Telegram-optimized HTML cards for syllabus coverage telemetry.
"""

from typing import Any, Dict, List

from database.models import ExamCategory
from services.topic_matrix import CoverageMatrix, ExamMetrics, SubjectMetrics, TopicMetrics, TopicStatus


def render_progress_bar(pct: float, length: int = 10) -> str:
    """Generate visual ASCII progress bar."""
    filled = int(round(length * pct / 100))
    filled = max(0, min(length, filled))
    return "▓" * filled + "░" * (length - filled)


def generate_console_coverage_report(matrix: CoverageMatrix) -> str:
    """Generate detailed ASCII console coverage dashboard."""
    lines = []
    lines.append("=" * 105)
    lines.append(" 📊 SYLLABUS-DRIVEN CONTENT COVERAGE DASHBOARD")
    lines.append(f" 🌟 Overall Platform Coverage: {matrix.overall_platform_coverage_pct}% | Total Verified Materials: {matrix.total_catalog_materials}")
    lines.append(f" 🚀 Ready Exams: {matrix.ready_exam_count} / {len(matrix.exam_matrices)} | Generated: {matrix.generated_at[:19]} UTC")
    lines.append("=" * 105)

    for cat, em in sorted(matrix.exam_matrices.items(), key=lambda x: x[0].value):
        ready_badge = "✅ READY FOR LAUNCH" if em.is_ready else f"⏳ PRE-LAUNCH ({em.gap_topics} Gaps, {em.weak_topics} Weak)"
        pbar = render_progress_bar(em.overall_coverage_pct)
        lines.append(f"\n🏛️ [{em.exam_category.value}] {em.display_name}")
        lines.append(f"   Progress: {pbar} {em.overall_coverage_pct}% | Materials: {em.total_materials} | Status: {ready_badge}")
        lines.append("-" * 105)
        lines.append(f"   {'SUBJECT / TOPIC':<55} | {'COUNT':<6} | {'COVERAGE':<10} | {'MISSING TYPES':<20}")
        lines.append("-" * 105)

        for sm in em.subject_metrics:
            s_pbar = render_progress_bar(sm.coverage_pct, length=6)
            lines.append(f"   📂 {sm.subject_name:<52} | {sm.total_materials:<6} | {s_pbar} {sm.coverage_pct}% |")

            for tm in sm.topic_metrics:
                status_icon = "🟢" if tm.status == TopicStatus.READY else ("🟡" if tm.status == TopicStatus.WEAK else "🔴")
                missing_str = ", ".join(tm.missing_material_types) if tm.missing_material_types else "None (Full)"
                lines.append(f"      {status_icon} {tm.topic_name:<50} | {tm.material_count:<6} | {tm.coverage_pct:>5.1f}%     | {missing_str:<20}")

        lines.append("." * 105)

    lines.append("\n" + "=" * 105)
    return "\n".join(lines)


def format_telegram_overview_card(matrix: CoverageMatrix) -> str:
    """Format Telegram HTML overview card for /coverage command."""
    lines = [
        "📊 <b>अभ्यासक्रम घटक निहाय कव्हरेज अहवाल (Syllabus Coverage)</b>\n",
        f"🌟 <b>एकूण प्लॅटफॉर्म कव्हरेज:</b> <code>{matrix.overall_platform_coverage_pct}%</code>",
        f"📁 <b>प्रमाणित अभ्यास साहित्य:</b> <code>{matrix.total_catalog_materials} PDFs</code>",
        f"🚀 <b>लाँचसाठी सज्ज परीक्षा:</b> <code>{matrix.ready_exam_count} / {len(matrix.exam_matrices)}</code>\n",
        "──────────────────────────────",
    ]

    for cat, em in sorted(matrix.exam_matrices.items(), key=lambda x: x[0].value):
        status_badge = "✅ <b>READY</b>" if em.is_ready else "⏳ <b>PRE-LAUNCH</b>"
        pbar = render_progress_bar(em.overall_coverage_pct, length=8)
        lines.append(
            f"🏛️ <b>#{em.exam_category.value}</b>: {pbar} <code>{em.overall_coverage_pct}%</code>\n"
            f"   └ साहित्य: <code>{em.total_materials}</code> • स्थिती: {status_badge}"
        )

    lines.append("──────────────────────────────")
    lines.append("<i>💡 सविस्तर विषय व घटक निहाय माहितीसाठी खालील बटणावर क्लिक करा:</i>")
    return "\n".join(lines)


def format_telegram_exam_drilldown_card(em: ExamMetrics) -> str:
    """Format Telegram HTML drilldown card for a specific exam."""
    ready_badge = "✅ <b>READY FOR LAUNCH</b>" if em.is_ready else f"⏳ <b>PRE-LAUNCH ({em.gap_topics} Gaps, {em.weak_topics} Weak)</b>"
    pbar = render_progress_bar(em.overall_coverage_pct, length=10)

    lines = [
        f"🏛️ <b>{em.display_name} (#{em.exam_category.value})</b>\n",
        f"📊 <b>एकूण कव्हरेज:</b> {pbar} <code>{em.overall_coverage_pct}%</code>",
        f"📄 <b>प्रमाणित साहित्य संख्या:</b> <code>{em.total_materials} PDFs</code>",
        f"🎯 <b>लाँच निकष स्थिती:</b> {ready_badge}\n",
        "──────────────────────────────",
        "<b>📖 विषय व घटक निहाय तपशील (Subject Breakdown):</b>\n",
    ]

    for sm in em.subject_metrics:
        s_pbar = render_progress_bar(sm.coverage_pct, length=6)
        lines.append(f"📂 <b>{sm.subject_name}</b> ({s_pbar} <code>{sm.coverage_pct}%</code>)")

        for tm in sm.topic_metrics:
            status_icon = "🟢" if tm.status == TopicStatus.READY else ("🟡" if tm.status == TopicStatus.WEAK else "🔴")
            missing_text = f" (आवश्यक: {', '.join(tm.missing_material_types)})" if tm.missing_material_types else ""
            lines.append(f"  {status_icon} <i>{tm.topic_name}</i>: <code>{tm.coverage_pct}%</code> [{tm.material_count} साहित्य]{missing_text}")
        lines.append("")

    lines.append("──────────────────────────────")
    return "\n".join(lines)
