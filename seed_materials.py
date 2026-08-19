"""Seed Initial Production Study Materials into Database."""

import asyncio
from config.settings import get_settings
from database.models import ExamCategory, MaterialType
from database.session import get_session, init_db
from database import crud


async def seed():
    await init_db()
    async with get_session() as session:
        materials = [
            # MPSC Materials
            {
                "title": "MPSC राज्यसेवा पूर्व परीक्षा भारतीय राज्यघटना व पंचायत राज",
                "exam_category": ExamCategory.MPSC,
                "subject": "राज्यशास्त्र (Polity)",
                "material_type": MaterialType.SHORT_NOTES,
                "file_path": "https://mpsc.gov.in/uploads/MPSC_Polity_Guide_2024.pdf",
                "year": 2024,
            },
            {
                "title": "MPSC संयुक्त पूर्व परीक्षा (Group B & C) मागील ५ वर्षांच्या प्रश्नपत्रिका",
                "exam_category": ExamCategory.MPSC,
                "subject": "मागील प्रश्नपत्रिका (PYQ)",
                "material_type": MaterialType.PYQ,
                "file_path": "https://mpsc.gov.in/uploads/Combine_Group_B_PYQ.pdf",
                "year": 2023,
            },
            {
                "title": "महाराष्ट्राचा भूगोल व पर्यावरण विशेष संदर्भ पुस्तक",
                "exam_category": ExamCategory.MPSC,
                "subject": "भूगोल (Geography)",
                "material_type": MaterialType.SHORT_NOTES,
                "file_path": "https://mpsc.gov.in/uploads/Maharashtra_Geography.pdf",
                "year": 2024,
            },
            # Police Bharti Materials
            {
                "title": "महाराष्ट्र पोलीस भरती संपूर्ण अंकगणित व बुद्धिमत्ता सराव संच",
                "exam_category": ExamCategory.POLICE_BHARTI,
                "subject": "अंकगणित व बुद्धिमत्ता (Maths & Reasoning)",
                "material_type": MaterialType.TEST_PAPER,
                "file_path": "https://mahapolice.gov.in/uploads/Police_Maths_Practice_2024.pdf",
                "year": 2024,
            },
            {
                "title": "महाराष्ट्र पोलीस भरती मराठी व्याकरण व शब्दसंग्रह नोट्स",
                "exam_category": ExamCategory.POLICE_BHARTI,
                "subject": "मराठी व्याकरण (Marathi Grammar)",
                "material_type": MaterialType.SHORT_NOTES,
                "file_path": "https://mahapolice.gov.in/uploads/Marathi_Vyakaran.pdf",
                "year": 2024,
            },
            # Government Resolutions (GR)
            {
                "title": "शासन निर्णय: स्पर्धा परीक्षांच्या वयोमर्यादा व आरक्षण नियमावली २०२४",
                "exam_category": ExamCategory.GENERAL,
                "subject": "शासन निर्णय (GR)",
                "material_type": MaterialType.GR,
                "file_path": "https://maharashtra.gov.in/GR_Age_Limit_Rules_2024.pdf",
                "year": 2024,
            },
            {
                "title": "शासन निर्णय: शासकीय नोकरभरती परीक्षा पद्धती व सामान्य प्रशासन परिपत्रक",
                "exam_category": ExamCategory.GENERAL,
                "subject": "शासन निर्णय (GR)",
                "material_type": MaterialType.GR,
                "file_path": "https://maharashtra.gov.in/GR_Recruitment_Process_2024.pdf",
                "year": 2024,
            },
            # Saral Seva / Talathi Materials
            {
                "title": "तलाठी भरती व जिल्हा परिषद सामान्य ज्ञान व चालू घडामोडी २०२४",
                "exam_category": ExamCategory.SARAL_SEVA,
                "subject": "चालू घडामोडी (Current Affairs)",
                "material_type": MaterialType.CURRENT_AFFAIRS,
                "file_path": "https://mahabhumi.gov.in/Talathi_Current_Affairs_2024.pdf",
                "year": 2024,
            },
            # Banking Materials
            {
                "title": "Banking Quantitative Aptitude & Data Interpretation Guide",
                "exam_category": ExamCategory.BANKING,
                "subject": "Quantitative Aptitude",
                "material_type": MaterialType.SHORT_NOTES,
                "file_path": "https://ibps.in/uploads/Banking_Quant_Guide.pdf",
                "year": 2024,
            },
        ]

        for m in materials:
            is_known = await crud.is_url_already_known(session, m["file_path"], m["file_path"])
            if not is_known:
                await crud.create_study_material(
                    session=session,
                    title=m["title"],
                    exam_category=m["exam_category"],
                    subject=m["subject"],
                    material_type=m["material_type"],
                    file_path=m["file_path"],
                    year=m["year"],
                )

    print("Initial production study materials seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
