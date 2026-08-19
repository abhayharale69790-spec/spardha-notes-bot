"""Master Bulk Study Materials Ingestion Script across All Major Exam Tiers."""

import asyncio
from datetime import datetime
import os
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from database.models import ExamCategory, MaterialType
from database.session import get_session, init_db
from database import crud


BULK_MATERIALS = [
    # --------------------------------------------------------------------------
    # 1. UPSC Civil Services (IAS / IPS / IFS)
    # --------------------------------------------------------------------------
    {
        "title": "UPSC Prelims GS Paper 1: मागील १० वर्षांच्या प्रश्नपत्रिकांचे विषयवार वर्गीकरण व उत्तरे",
        "exam_category": ExamCategory.UPSC,
        "subject": "Prelims GS",
        "material_type": MaterialType.PYQ,
        "file_path": "https://upsc.gov.in/examinations/previous-question-papers",
        "year": 2024,
    },
    {
        "title": "UPSC Prelims Paper 2: CSAT अंकगणित, बुद्धिमत्ता व आकलन क्षमता Quick Revision Capsule",
        "exam_category": ExamCategory.UPSC,
        "subject": "CSAT",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://upsc.gov.in/examinations/previous-question-papers",
        "year": 2024,
    },
    {
        "title": "UPSC Mains GS 1 to 4: समग्र अभ्यासक्रम, विषयवार संदर्भ सूची आणि आदर्श उत्तरलेखन आराखडा",
        "exam_category": ExamCategory.UPSC,
        "subject": "Mains GS",
        "material_type": MaterialType.SYLLABUS,
        "file_path": "https://upsc.gov.in/examinations/revised-syllabus-scheme",
        "year": 2024,
    },
    {
        "title": "Indian Polity & Constitution High-Yield Summary (UPSC & MPSC Special)",
        "exam_category": ExamCategory.UPSC,
        "subject": "Indian Polity",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://upsc.gov.in",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 2. MPSC (Rajyaseva & Combine Group B / Group C)
    # --------------------------------------------------------------------------
    {
        "title": "MPSC राज्यसेवा व संयुक्त पूर्व परीक्षा - भारतीय राज्यघटना व पंचायत राज हस्तलिखित नोट्स",
        "exam_category": ExamCategory.MPSC,
        "subject": "राज्यशास्त्र (Polity)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/announcements",
        "year": 2024,
    },
    {
        "title": "महाराष्ट्राचा इतिहास व समाजसुधारक विशेष संदर्भ संच (MPSC Group B & C)",
        "exam_category": ExamCategory.MPSC,
        "subject": "इतिहास (History)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/announcements",
        "year": 2024,
    },
    {
        "title": "महाराष्ट्राचा व भारताचा समग्र भूगोल व पर्यावरण नकाशानिहाय नोट्स",
        "exam_category": ExamCategory.MPSC,
        "subject": "भूगोल (Geography)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/announcements",
        "year": 2024,
    },
    {
        "title": "भारतीय अर्थव्यवस्था, बँकिंग प्रणाली व अर्थसंकल्प २०२४-२५ ठळक मुद्दे",
        "exam_category": ExamCategory.MPSC,
        "subject": "अर्थशास्त्र (Economics)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/announcements",
        "year": 2024,
    },
    {
        "title": "MPSC सामान्य विज्ञान - भौतिकशास्त्र, रसायनशास्त्र व जीवशास्त्र Quick Revision",
        "exam_category": ExamCategory.MPSC,
        "subject": "सामान्य विज्ञान (Science)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/announcements",
        "year": 2024,
    },
    {
        "title": "MPSC चालू घडामोडी २०२४ (राष्ट्रीय, आंतरराष्ट्रीय व महाराष्ट्र विशेष घडामोडी)",
        "exam_category": ExamCategory.MPSC,
        "subject": "चालू घडामोडी (Current Affairs)",
        "material_type": MaterialType.CURRENT_AFFAIRS,
        "file_path": "https://mpsc.gov.in/announcements",
        "year": 2024,
    },
    {
        "title": "MPSC संयुक्त गट 'ब' पूर्व परीक्षा २०२३ मूळ प्रश्नपत्रिका व अंतिम उत्तरतालिका",
        "exam_category": ExamCategory.MPSC,
        "subject": "मागील प्रश्नपत्रिका (PYQ)",
        "material_type": MaterialType.PYQ,
        "file_path": "https://mpsc.gov.in/announcements",
        "year": 2023,
    },

    # --------------------------------------------------------------------------
    # 3. महाराष्ट्र पोलीस भरती (Police Bharti)
    # --------------------------------------------------------------------------
    {
        "title": "पोलीस भरती संपूर्ण अंकगणित सूत्रे, शॉर्टकट ट्रिक्स व १०० सराव प्रश्न",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "अंकगणित (Maths)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahapolice.gov.in",
        "year": 2024,
    },
    {
        "title": "पोलीस भरती बुद्धिमत्ता चाचणी - दिशा, नातेसंबंध, बैठक व्यवस्था व आकृत्या सराव",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "बुद्धिमत्ता (Reasoning)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahapolice.gov.in",
        "year": 2024,
    },
    {
        "title": "पोलीस भरती मराठी व्याकरण - संधी, समास, अलंकार, म्हणी व शब्दसंग्रह",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "मराठी व्याकरण (Marathi)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahapolice.gov.in",
        "year": 2024,
    },
    {
        "title": "मुंबई पोलीस शिपाई भरती २०२३ मूळ प्रश्नपत्रिका व सविस्तर स्पष्टीकरणासह उत्तरे",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "सराव पेपर (Practice Papers)",
        "material_type": MaterialType.PYQ,
        "file_path": "https://mahapolice.gov.in",
        "year": 2023,
    },

    # --------------------------------------------------------------------------
    # 4. सरळ सेवा (Saral Seva / Talathi / ZP / Nagar Parishad)
    # --------------------------------------------------------------------------
    {
        "title": "तलाठी भरती TCS / IBPS पॅटर्न संभाव्य सराव प्रश्नसंच व उत्तरतालिका",
        "exam_category": ExamCategory.SARAL_SEVA,
        "subject": "तलाठी सराव संच (Talathi PYQ)",
        "material_type": MaterialType.TEST_PAPER,
        "file_path": "https://mahabhumi.gov.in/mahabhumilink",
        "year": 2024,
    },
    {
        "title": "सरळ सेवा भरती - महाराष्ट्र सामान्य ज्ञान व चालू घडामोडी ५०० वन लाइनर नोट्स",
        "exam_category": ExamCategory.SARAL_SEVA,
        "subject": "सामान्य ज्ञान (GK)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahabhumi.gov.in/mahabhumilink",
        "year": 2024,
    },
    {
        "title": "English Grammar & Vocabulary Guide for Talathi, ZP and Saral Seva Exams",
        "exam_category": ExamCategory.SARAL_SEVA,
        "subject": "इंग्रजी व्याकरण (English)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahabhumi.gov.in/mahabhumilink",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 5. National Engineering (JEE Main & Advanced)
    # --------------------------------------------------------------------------
    {
        "title": "JEE Main & Advanced Physics Complete Formula Compendium & Quick Revision Handbook",
        "exam_category": ExamCategory.JEE,
        "subject": "Physics",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://jeemain.nta.nic.in",
        "year": 2024,
    },
    {
        "title": "JEE Chemistry: Organic Reaction Mechanisms, Inorganic Trends & Physical Chemistry Formulas",
        "exam_category": ExamCategory.JEE,
        "subject": "Chemistry",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://jeemain.nta.nic.in",
        "year": 2024,
    },
    {
        "title": "JEE Mathematics: Calculus, Vectors & 3D, Algebra Short Tricks & Cheat Sheet",
        "exam_category": ExamCategory.JEE,
        "subject": "Mathematics",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://jeemain.nta.nic.in",
        "year": 2024,
    },
    {
        "title": "JEE Main Past 5 Years Chapterwise Solved Question Papers (NTA Official)",
        "exam_category": ExamCategory.JEE,
        "subject": "JEE PYQs",
        "material_type": MaterialType.PYQ,
        "file_path": "https://jeemain.nta.nic.in",
        "year": 2023,
    },

    # --------------------------------------------------------------------------
    # 6. National Medical (NEET UG)
    # --------------------------------------------------------------------------
    {
        "title": "NEET UG Biology: Complete NCERT Line-by-Line Chapterwise High-Yield Notes",
        "exam_category": ExamCategory.NEET,
        "subject": "Biology",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://neet.nta.nic.in",
        "year": 2024,
    },
    {
        "title": "NEET Chemistry: Inorganic NCERT Tables, Organic Reactions & Past 10 Years PYQs",
        "exam_category": ExamCategory.NEET,
        "subject": "Chemistry",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://neet.nta.nic.in",
        "year": 2024,
    },
    {
        "title": "NEET Physics: Mechanics, Electrodynamics & Optics Formulas + Conceptual Derivations",
        "exam_category": ExamCategory.NEET,
        "subject": "Physics",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://neet.nta.nic.in",
        "year": 2024,
    },
    {
        "title": "NEET UG 2023 Original Question Paper with Detailed Step-by-Step Solutions",
        "exam_category": ExamCategory.NEET,
        "subject": "NEET PYQs",
        "material_type": MaterialType.PYQ,
        "file_path": "https://neet.nta.nic.in",
        "year": 2023,
    },

    # --------------------------------------------------------------------------
    # 7. School & Foundation (10th & 12th Board - SSC / HSC)
    # --------------------------------------------------------------------------
    {
        "title": "Maharashtra SSC Class 10th Mathematics & Science Official Question Bank & Solutions",
        "exam_category": ExamCategory.BOARD_10_12,
        "subject": "10th SSC Board",
        "material_type": MaterialType.TEST_PAPER,
        "file_path": "https://www.mahahsscboard.in",
        "year": 2024,
    },
    {
        "title": "Maharashtra HSC Class 12th Science: Physics, Chemistry & Biology Model Question Papers",
        "exam_category": ExamCategory.BOARD_10_12,
        "subject": "12th HSC Science",
        "material_type": MaterialType.TEST_PAPER,
        "file_path": "https://www.mahahsscboard.in",
        "year": 2024,
    },
    {
        "title": "Maharashtra HSC Class 12th Commerce: Book-Keeping, Economics & OCM Revision Notes",
        "exam_category": ExamCategory.BOARD_10_12,
        "subject": "12th HSC Commerce",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://www.mahahsscboard.in",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 8. NCERT Textbooks & Solutions (Class 6 to 12)
    # --------------------------------------------------------------------------
    {
        "title": "NCERT Class 6 to 10 General Science Summary & Core Concepts Handbook",
        "exam_category": ExamCategory.NCERT,
        "subject": "NCERT Science",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ncert.nic.in/textbook.php",
        "year": 2024,
    },
    {
        "title": "NCERT Class 6 to 10 Social Science (History, Geography, Civics) Foundation Capsule",
        "exam_category": ExamCategory.NCERT,
        "subject": "NCERT Social Science",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ncert.nic.in/textbook.php",
        "year": 2024,
    },
    {
        "title": "NCERT Class 11 & 12 Physics, Chemistry & Biology Official Core Textbooks Guide",
        "exam_category": ExamCategory.NCERT,
        "subject": "NCERT Higher Secondary",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ncert.nic.in/textbook.php",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 9. Banking & Financial Sector (IBPS / SBI / RBI)
    # --------------------------------------------------------------------------
    {
        "title": "Banking Quantitative Aptitude: Speed Maths, Arithmetic & Data Interpretation Guide",
        "exam_category": ExamCategory.BANKING,
        "subject": "Quantitative Aptitude",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ibps.in",
        "year": 2024,
    },
    {
        "title": "Reasoning Ability Puzzles, Syllogism & High-Level Seating Arrangement Capsule",
        "exam_category": ExamCategory.BANKING,
        "subject": "Reasoning Ability",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ibps.in",
        "year": 2024,
    },
    {
        "title": "Banking & Financial Awareness: RBI Monetary Policy & Economic Terms 2024",
        "exam_category": ExamCategory.BANKING,
        "subject": "Banking Awareness",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://rbi.org.in",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 10. Staff Selection Commission (SSC CGL / CHSL / GD / MTS)
    # --------------------------------------------------------------------------
    {
        "title": "SSC CGL / CHSL Quantitative Aptitude: Advanced Maths (Geometry, Mensuration, Algebra)",
        "exam_category": ExamCategory.SSC,
        "subject": "Quantitative Aptitude",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ssc.gov.in",
        "year": 2024,
    },
    {
        "title": "SSC General Awareness & Static GK 1000 High-Frequency Questions",
        "exam_category": ExamCategory.SSC,
        "subject": "General Awareness",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ssc.gov.in",
        "year": 2024,
    },
    {
        "title": "SSC English Language & Comprehension: 100 Essential Grammar Rules & Vocabulary",
        "exam_category": ExamCategory.SSC,
        "subject": "English",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ssc.gov.in",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 11. Government Resolutions & General (GR)
    # --------------------------------------------------------------------------
    {
        "title": "शासन निर्णय: महाराष्ट्र शासकीय नोकरभरती परीक्षा पद्धती व नवीन मार्गदर्शक सूचना २०२४",
        "exam_category": ExamCategory.GENERAL,
        "subject": "शासन निर्णय (GR)",
        "material_type": MaterialType.GR,
        "file_path": "https://www.maharashtra.gov.in/1145/Government-Resolutions",
        "year": 2024,
    },
    {
        "title": "शासन निर्णय: स्पर्धा परीक्षांसाठी वयोमर्यादा शिथिलीकरण व समांतर आरक्षण नियमावली",
        "exam_category": ExamCategory.GENERAL,
        "subject": "शासन निर्णय (GR)",
        "material_type": MaterialType.GR,
        "file_path": "https://www.maharashtra.gov.in/1145/Government-Resolutions",
        "year": 2024,
    },
]


async def seed_bulk_materials():
    """Seed all categorized materials into the database."""
    print("Initializing database schema...")
    await init_db()
    
    count_added = 0
    count_skipped = 0

    async with get_session() as session:
        for item in BULK_MATERIALS:
            is_known = await crud.is_url_already_known(session, item["file_path"], item["title"])
            if not is_known:
                await crud.create_study_material(
                    session=session,
                    title=item["title"],
                    exam_category=item["exam_category"],
                    subject=item["subject"],
                    material_type=item["material_type"],
                    file_path=item["file_path"],
                    year=item["year"],
                )
                count_added += 1
            else:
                count_skipped += 1

    print("\n[OK] Bulk Ingestion Complete across All Major Exam Tiers!")
    print(f"   * Added: {count_added} new materials")
    print(f"   * Skipped (Already existed): {count_skipped}")


if __name__ == "__main__":
    asyncio.run(seed_bulk_materials())
