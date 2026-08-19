"""Master Bulk Study Materials Ingestion Script."""

import asyncio
from datetime import datetime
from config.settings import get_settings
from database.models import ExamCategory, MaterialType
from database.session import get_session, init_db
from database import crud


BULK_MATERIALS = [
    # --------------------------------------------------------------------------
    # 1. MPSC (Rajyaseva & Combine Group B / Group C)
    # --------------------------------------------------------------------------
    {
        "title": "MPSC राज्यसेवा व संयुक्त पूर्व परीक्षा - भारतीय राज्यघटना व पंचायत राज हस्तलिखित नोट्स",
        "exam_category": ExamCategory.MPSC,
        "subject": "राज्यशास्त्र (Polity)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/uploads/MPSC_Indian_Polity_Notes_2024.pdf",
        "year": 2024,
    },
    {
        "title": "महाराष्ट्राचा इतिहास व समाजसुधारक विशेष संदर्भ संच (MPSC Group B & C)",
        "exam_category": ExamCategory.MPSC,
        "subject": "इतिहास (History)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/uploads/Maharashtra_History_Social_Reformers.pdf",
        "year": 2024,
    },
    {
        "title": "महाराष्ट्राचा व भारताचा समग्र भूगोल व पर्यावरण नकाशानिहाय नोट्स",
        "exam_category": ExamCategory.MPSC,
        "subject": "भूगोल (Geography)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/uploads/Maharashtra_Geography_Atlas.pdf",
        "year": 2024,
    },
    {
        "title": "भारतीय अर्थव्यवस्था, बँकिंग प्रणाली व अर्थसंकल्प २०२४-२५ ठळक मुद्दे",
        "exam_category": ExamCategory.MPSC,
        "subject": "अर्थशास्त्र (Economics)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/uploads/Indian_Economy_Budget_2024.pdf",
        "year": 2024,
    },
    {
        "title": "MPSC सामान्य विज्ञान - भौतिकशास्त्र, रसायनशास्त्र व जीवशास्त्र Quick Revision",
        "exam_category": ExamCategory.MPSC,
        "subject": "सामान्य विज्ञान (Science)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mpsc.gov.in/uploads/MPSC_General_Science_Revision.pdf",
        "year": 2024,
    },
    {
        "title": "MPSC चालू घडामोडी २०२४ (राष्ट्रीय, आंतरराष्ट्रीय व महाराष्ट्र विशेष घडामोडी)",
        "exam_category": ExamCategory.MPSC,
        "subject": "चालू घडामोडी (Current Affairs)",
        "material_type": MaterialType.CURRENT_AFFAIRS,
        "file_path": "https://mpsc.gov.in/uploads/Current_Affairs_Yearly_2024.pdf",
        "year": 2024,
    },
    {
        "title": "MPSC संयुक्त गट 'ब' पूर्व परीक्षा २०२३ मूळ प्रश्नपत्रिका व अंतिम उत्तरतालिका",
        "exam_category": ExamCategory.MPSC,
        "subject": "मागील प्रश्नपत्रिका (PYQ)",
        "material_type": MaterialType.PYQ,
        "file_path": "https://mpsc.gov.in/uploads/MPSC_Combine_Group_B_2023_Paper.pdf",
        "year": 2023,
    },
    {
        "title": "MPSC संयुक्त गट 'क' पूर्व परीक्षा २०२३ मूळ प्रश्नपत्रिका व अंतिम उत्तरतालिका",
        "exam_category": ExamCategory.MPSC,
        "subject": "मागील प्रश्नपत्रिका (PYQ)",
        "material_type": MaterialType.PYQ,
        "file_path": "https://mpsc.gov.in/uploads/MPSC_Combine_Group_C_2023_Paper.pdf",
        "year": 2023,
    },
    {
        "title": "MPSC राज्यसेवा पूर्व परीक्षा मागील ५ वर्षांच्या प्रश्नपत्रिकांचे विश्लेषण",
        "exam_category": ExamCategory.MPSC,
        "subject": "मागील प्रश्नपत्रिका (PYQ)",
        "material_type": MaterialType.PYQ,
        "file_path": "https://mpsc.gov.in/uploads/MPSC_Rajyaseva_5Years_PYQ.pdf",
        "year": 2023,
    },

    # --------------------------------------------------------------------------
    # 2. महाराष्ट्र पोलीस भरती (Police Bharti)
    # --------------------------------------------------------------------------
    {
        "title": "पोलीस भरती संपूर्ण अंकगणित सूत्रे, शॉर्टकट ट्रिक्स व १०० सराव प्रश्न",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "अंकगणित (Maths)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahapolice.gov.in/uploads/Police_Maths_Formula_Book.pdf",
        "year": 2024,
    },
    {
        "title": "पोलीस भरती बुद्धिमत्ता चाचणी - दिशा, नातेसंबंध, बैठक व्यवस्था व आकृत्या सराव",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "बुद्धिमत्ता (Reasoning)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahapolice.gov.in/uploads/Police_Reasoning_Master_Book.pdf",
        "year": 2024,
    },
    {
        "title": "पोलीस भरती मराठी व्याकरण - संधी, समास, अलंकार, म्हणी व समानार्थी शब्दसंग्रह",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "मराठी व्याकरण (Marathi)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahapolice.gov.in/uploads/Police_Marathi_Grammar_Vocab.pdf",
        "year": 2024,
    },
    {
        "title": "महाराष्ट्र पोलीस प्रशासन, कायदे, मानवी हक्क व संगणक ज्ञान विशेष प्रश्नसंच",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "पोलीस प्रशासन व कायदे",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahapolice.gov.in/uploads/Police_Acts_and_Rules.pdf",
        "year": 2024,
    },
    {
        "title": "मुंबई पोलीस शिपाई भरती २०२३ मूळ प्रश्नपत्रिका व सविस्तर स्पष्टीकरणासह उत्तरे",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "सराव पेपर (Practice Papers)",
        "material_type": MaterialType.PYQ,
        "file_path": "https://mahapolice.gov.in/uploads/Mumbai_Police_Constable_2023.pdf",
        "year": 2023,
    },
    {
        "title": "महाराष्ट्र पोलीस भरती १०० गुणांचे १० आदर्श सराव प्रश्नसंच (OMR Answer Sheet सह)",
        "exam_category": ExamCategory.POLICE_BHARTI,
        "subject": "सराव पेपर (Practice Papers)",
        "material_type": MaterialType.TEST_PAPER,
        "file_path": "https://mahapolice.gov.in/uploads/Police_Bharti_10_Model_Papers.pdf",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 3. सरळ सेवा (Saral Seva / Talathi / ZP / Nagar Parishad)
    # --------------------------------------------------------------------------
    {
        "title": "तलाठी भरती TCS / IBPS पॅटर्न संभाव्य ५ सराव प्रश्नसंच (स्पष्टीकरणासह)",
        "exam_category": ExamCategory.SARAL_SEVA,
        "subject": "तलाठी सराव संच (Talathi PYQ)",
        "material_type": MaterialType.TEST_PAPER,
        "file_path": "https://mahabhumi.gov.in/uploads/Talathi_TCS_IBPS_Mock_Papers.pdf",
        "year": 2024,
    },
    {
        "title": "सरळ सेवा भरती - महाराष्ट्र सामान्य ज्ञान व चालू घडामोडी ५०० वन लाइनर नोट्स",
        "exam_category": ExamCategory.SARAL_SEVA,
        "subject": "सामान्य ज्ञान (GK)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahabhumi.gov.in/uploads/Maharashtra_GK_500_OneLiners.pdf",
        "year": 2024,
    },
    {
        "title": "English Grammar & Vocabulary Guide for Talathi, ZP and Saral Seva Exams",
        "exam_category": ExamCategory.SARAL_SEVA,
        "subject": "इंग्रजी व्याकरण (English)",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahabhumi.gov.in/uploads/English_Grammar_SaralSeva.pdf",
        "year": 2024,
    },
    {
        "title": "जिल्हा परिषद व आरोग्य सेवक भरती विशेष तांत्रिक प्रश्नोत्तरे व सराव संच",
        "exam_category": ExamCategory.SARAL_SEVA,
        "subject": "आरोग्य सेवक / ZP तांत्रिक",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://mahabhumi.gov.in/uploads/ZP_Health_Worker_Technical_Notes.pdf",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 4. बँकिंग व SSC (Banking / SSC / Railway)
    # --------------------------------------------------------------------------
    {
        "title": "Banking Quantitative Aptitude: Arithmetic, Data Interpretation & Speed Maths",
        "exam_category": ExamCategory.BANKING,
        "subject": "Quantitative Aptitude",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ibps.in/uploads/Speed_Maths_and_DI_Mastery.pdf",
        "year": 2024,
    },
    {
        "title": "Reasoning Ability Puzzles, Syllogism & Seating Arrangement Capsule",
        "exam_category": ExamCategory.BANKING,
        "subject": "Reasoning Ability",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ibps.in/uploads/Reasoning_Puzzles_Bank_PO.pdf",
        "year": 2024,
    },
    {
        "title": "Banking Awareness, Financial Terms & RBI Monetary Policy Guidelines 2024",
        "exam_category": ExamCategory.BANKING,
        "subject": "Banking Awareness",
        "material_type": MaterialType.SHORT_NOTES,
        "file_path": "https://ibps.in/uploads/Banking_Awareness_2024.pdf",
        "year": 2024,
    },

    # --------------------------------------------------------------------------
    # 5. शासन निर्णय व अधिकृत परिपत्रके (Government Resolutions - GR)
    # --------------------------------------------------------------------------
    {
        "title": "शासन निर्णय: महाराष्ट्र शासकीय नोकरभरती परीक्षा पद्धती व नवीन मार्गदर्शक सूचना २०२४",
        "exam_category": ExamCategory.GENERAL,
        "subject": "शासन निर्णय (GR)",
        "material_type": MaterialType.GR,
        "file_path": "https://maharashtra.gov.in/GR_Recruitment_Rules_2024.pdf",
        "year": 2024,
    },
    {
        "title": "शासन निर्णय: स्पर्धा परीक्षांसाठी वयोमर्यादा शिथिलीकरण व समांतर आरक्षण नियमावली",
        "exam_category": ExamCategory.GENERAL,
        "subject": "शासन निर्णय (GR)",
        "material_type": MaterialType.GR,
        "file_path": "https://maharashtra.gov.in/GR_Age_Relaxation_Policy.pdf",
        "year": 2024,
    },
    {
        "title": "शासन निर्णय: खेळाडू, दिव्यांग व अनाथ आरक्षण प्रमाणपत्र पडताळणी सुधारित कार्यपद्धती",
        "exam_category": ExamCategory.GENERAL,
        "subject": "शासन निर्णय (GR)",
        "material_type": MaterialType.GR,
        "file_path": "https://maharashtra.gov.in/GR_Special_Reservation_Rules.pdf",
        "year": 2024,
    },
]


async def seed_bulk_materials():
    """Seed all categorized materials into the database."""
    print("Initializing database...")
    await init_db()
    
    count_added = 0
    count_skipped = 0

    async with get_session() as session:
        for item in BULK_MATERIALS:
            is_known = await crud.is_url_already_known(session, item["file_path"], item["file_path"])
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

    print(f"\n✅ Bulk Ingestion Complete!")
    print(f"   • Added: {count_added} new materials")
    print(f"   • Skipped (Already existed): {count_skipped}")


if __name__ == "__main__":
    asyncio.run(seed_bulk_materials())
