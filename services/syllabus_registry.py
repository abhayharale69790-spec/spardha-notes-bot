"""Syllabus Registry & Official Examination Hierarchy.

Hierarchical taxonomy: ExamCategory -> Subject -> Topic -> Subtopic -> Required Material Types.
Based on official, current exam syllabi across all 10 exam tiers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from database.models import ExamCategory, MaterialType


class ContentMaterialType(str, Enum):
    NOTES = "NOTES"
    TEXTBOOK = "TEXTBOOK"
    PYQ = "PYQ"
    MCQ = "MCQ"
    PRACTICE_TEST = "PRACTICE_TEST"
    CURRENT_AFFAIRS = "CURRENT_AFFAIRS"
    REFERENCE = "REFERENCE"


@dataclass
class SubtopicNode:
    name: str
    keywords: List[str] = field(default_factory=list)
    required_types: List[ContentMaterialType] = field(
        default_factory=lambda: [
            ContentMaterialType.NOTES,
            ContentMaterialType.PYQ,
            ContentMaterialType.PRACTICE_TEST,
        ]
    )


@dataclass
class TopicNode:
    name: str
    subtopics: List[SubtopicNode] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    required_types: List[ContentMaterialType] = field(
        default_factory=lambda: [
            ContentMaterialType.NOTES,
            ContentMaterialType.PYQ,
            ContentMaterialType.PRACTICE_TEST,
        ]
    )
    is_core: bool = True


@dataclass
class SubjectNode:
    name: str
    topics: List[TopicNode] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class ExamSyllabus:
    exam_category: ExamCategory
    display_name: str
    authority: str
    subjects: List[SubjectNode] = field(default_factory=list)
    min_readiness_threshold: float = 80.0  # Required overall coverage % for READY status
    min_subject_threshold: float = 70.0    # Required subject coverage %


# =========================================================================
# OFFICIAL EXAMINATION SYLLABI DEFINITIONS
# =========================================================================

MPSC_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.MPSC,
    display_name="MPSC (Rajyaseva & Combine Group B & C)",
    authority="Maharashtra Public Service Commission",
    subjects=[
        SubjectNode(
            name="राज्यशास्त्र (Polity)",
            keywords=["polity", "constitution", "राज्यघटना", "राज्यशास्त्र", "पंचायतराज", "कलम", "governance"],
            topics=[
                TopicNode(
                    name="भारतीय राज्यघटना व निर्मिती",
                    keywords=["घटना निर्मिती", "सरनामा", "preamble", "constituent assembly", "कलमे"],
                    subtopics=[
                        SubtopicNode("घटना समिती व मसुदा समिती", ["मसुदा समिती", "dr ambedkar", "drafting committee"]),
                        SubtopicNode("राज्यघटनेची वैशिष्ट्ये व सरनामा", ["सरनामा", "preamble", "salient features"]),
                    ],
                ),
                TopicNode(
                    name="मूलभूत हक्क, कर्तव्ये व मार्गदर्शक तत्त्वे",
                    keywords=["मूलभूत हक्क", "fundamental rights", "dpsp", "मार्गदर्शक तत्त्वे", "कर्तव्ये", "कलम १२-३५"],
                    subtopics=[
                        SubtopicNode("मूलभूत हक्क (कलम १२ ते ३५)", ["कलम १२", "कलम ३२", "हक्क", "right to equality", "freedom"]),
                        SubtopicNode("मार्गदर्शक तत्त्वे व मूलभूत कर्तव्ये (कलम ३६ ते ५१A)", ["dpsp", "मार्गदर्शक तत्त्वे", "५१a"]),
                    ],
                ),
                TopicNode(
                    name="संसद, राष्ट्रपती व न्यायव्यवस्था",
                    keywords=["parliament", "संसद", "लोकसभा", "राज्यसभा", "राष्ट्रपती", "सर्वोच्च न्यायालय", "न्यायव्यवस्था"],
                    subtopics=[
                        SubtopicNode("राष्ट्रपती, पंतप्रधान व मंत्रिमंडळ", ["president", "prime minister", "मंत्रिमंडळ"]),
                        SubtopicNode("संसद व विधिमंडळ", ["lok sabha", "rajya sabha", "विधानसभा"]),
                        SubtopicNode("सर्वोच्च व उच्च न्यायालय", ["supreme court", "high court", "न्यायालय"]),
                    ],
                ),
                TopicNode(
                    name="स्थानिक स्वराज्य संस्था (पंचायतराज)",
                    keywords=["पंचायतराज", "panchayat", "ग्रामपंचायत", "पंचायत समिती", "जिल्हा परिषद", "७३वी घटनादुरुस्ती"],
                    subtopics=[
                        SubtopicNode("ग्रामीण स्थानिक स्वराज्य (७३ वी घटनादुरुस्ती)", ["७३वी", "ग्रामपंचायत", "zp", "सरपंच"]),
                        SubtopicNode("नागरी स्थानिक स्वराज्य (७४ वी घटनादुरुस्ती)", ["७४वी", "महानगरपालिका", "नगरपरिषद"]),
                    ],
                ),
            ],
        ),
        SubjectNode(
            name="भूगोल (Geography)",
            keywords=["geography", "भूगोल", "महाराष्ट्र भूगोल", "नद्या", "पर्वत", "हवामान", "जमीन"],
            topics=[
                TopicNode(
                    name="महाराष्ट्राची प्राकृतिक रचना व सह्याद्री",
                    keywords=["सह्याद्री", "प्राकृतिक", "कोकण", "पठार", "डोंगररांगा", "शिखरे"],
                    subtopics=[
                        SubtopicNode("कोकण किनारपट्टी व पश्चिम घाट", ["कोकण", "घाटमाथा", "कळसूबाई"]),
                        SubtopicNode("महाराष्ट्र पठार व प्राकृतिक विभाग", ["दख्खन पठार", "पठार रचना"]),
                    ],
                ),
                TopicNode(
                    name="महाराष्ट्राची नदीप्रणाली व जलसंपत्ती",
                    keywords=["गोदावरी", "भीमा", "कृष्णा", "तापी", "नदीप्रणाली", "धरणे", "जलसंपदा"],
                    subtopics=[
                        SubtopicNode("गोदावरी, भीमा व कृष्णा खोरे", ["गोदावरी खोरे", "भीमा खोरे", "कृष्णा खोरे"]),
                        SubtopicNode("पश्चिम वाहिनी नद्या व धरणे", ["तापी", "नर्मदा", "कोकणातील नद्या", "जायकवाडी", "कोयना"]),
                    ],
                ),
                TopicNode(
                    name="हवामान, वने व खनिज संपत्ती",
                    keywords=["हवामान", "पाऊस", "मान्सून", "जंगल", "खनिजे", "मृदा", "काळी जमीन"],
                    subtopics=[
                        SubtopicNode("हवामान व पर्जन्य वितरण", ["मान्सून", "हवामान विभाग"]),
                        SubtopicNode("मृदा प्रकार व वने", ["काळी कापसाची मृदा", "जांभी मृदा", "सदाहरित वने"]),
                    ],
                ),
            ],
        ),
        SubjectNode(
            name="इतिहास (History)",
            keywords=["history", "इतिहास", "समाजसुधारक", "स्वातंत्र्य लढा", "१८५७", "काँग्रेस", "महाराष्ट्र"],
            topics=[
                TopicNode(
                    name="महाराष्ट्रातील समाजसुधारक व चळवळी",
                    keywords=["समाजसुधारक", "फुले", "शाहू", "आंबेडकर", "कर्वे", "आगरकर", "लोकहितवादी"],
                    subtopics=[
                        SubtopicNode("महात्मा जोतीराव फुले व सत्यशोधक समाज", ["फुले", "सत्यशोधक समाज"]),
                        SubtopicNode("राजर्षी छत्रपती शाहू महाराज", ["शाहू महाराज", "कोल्हापूर"]),
                        SubtopicNode("डॉ. बाबासाहेब आंबेडकर व दलित चळवळ", ["आंबेडकर", "बहिष्कृत हितकारिणी", "महाड सत्याग्रह"]),
                    ],
                ),
                TopicNode(
                    name="भारतीय राष्ट्रीय चळवळ व १८५७ चा उठाव",
                    keywords=["१८५७", "राष्ट्रीय सभा", "गांधीयुग", "असहकार", "सविनय कायदेभंग", "भारत छोडो"],
                    subtopics=[
                        SubtopicNode("१८५७ चा उठाव व परिणाम", ["१८५७", "उठाव"]),
                        SubtopicNode("गांधी युग व स्वातंत्र्य प्राप्ती (१९२०-१९४७)", ["गांधी", "असहकार", "चले जाव"]),
                    ],
                ),
            ],
        ),
        SubjectNode(
            name="चालू घडामोडी (Current Affairs)",
            keywords=["current affairs", "चालू घडामोडी", "वार्षिकी", "पुरस्कार", "क्रीडा", "योजना"],
            topics=[
                TopicNode(
                    name="राष्ट्रीय व आंतरराष्ट्रीय पुरस्कार व परिषदा",
                    keywords=["पुरस्कार", "नोबेल", "भारतरत्न", "g20", "परिषद", "नियुक्त्या"],
                ),
                TopicNode(
                    name="शासकीय योजना व आर्थिक घडामोडी",
                    keywords=["योजना", "अर्थसंकल्प", "लाडकी बहीण", "बजेट", "rbi धोरण"],
                ),
            ],
        ),
    ],
)

POLICE_BHARTI_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.POLICE_BHARTI,
    display_name="महाराष्ट्र पोलीस भरती (Police Bharti)",
    authority="Maharashtra Police Recruitment Board",
    subjects=[
        SubjectNode(
            name="मराठी व्याकरण (Marathi Grammar)",
            keywords=["मराठी व्याकरण", "marathi grammar", "संधी", "समास", "अलंकार", "प्रयोग", "शब्दसंग्रह"],
            topics=[
                TopicNode(
                    name="वर्णविचार व संधी",
                    keywords=["वर्णविचार", "स्वर", "व्यंजन", "संधी", "स्वरसंधी", "व्यंजनसंधी"],
                ),
                TopicNode(
                    name="शब्दांच्या जाती व काळ",
                    keywords=["नाम", "सर्वनाम", "विशेषण", "क्रियापद", "काळ", "वर्तमानकाळ", "भूतकाळ"],
                ),
                TopicNode(
                    name="प्रयोग, समास व अलंकार",
                    keywords=["कर्तरी", "कर्मणी", "भावे", "समास", "द्वंद्व", "अलंकार"],
                ),
                TopicNode(
                    name="शब्दसंग्रह, म्हणी व वाक्प्रचार",
                    keywords=["समानार्थी", "विरुद्धार्थी", "म्हणी", "वाक्प्रचार", "शब्दसमूह"],
                ),
            ],
        ),
        SubjectNode(
            name="अंकगणित व बुद्धिमत्ता (Maths & Reasoning)",
            keywords=["maths", "reasoning", "अंकगणित", "बुद्धिमत्ता", "शेकडेवारी", "नफा तोटा", "काळ काम वेग"],
            topics=[
                TopicNode(
                    name="अंकगणित मूलभूत संकल्पना",
                    keywords=["लसावि", "मसावि", "शेकडेवारी", "नफा-तोटा", "सरळव्याज", "चक्रवाढव्याज"],
                ),
                TopicNode(
                    name="काळ, काम, वेग व अंतर",
                    keywords=["काळ काम", "वेग", "रेल्वे", "बोट व प्रवाह", "पाण्याची टाकी"],
                ),
                TopicNode(
                    name="तर्क व बुद्धिमत्ता चाचणी",
                    keywords=["संख्या मालिका", "अक्षर मालिका", "नातेसंबंध", "दिशा ज्ञान", "घड्याळ", "कॅलेंडर"],
                ),
            ],
        ),
        SubjectNode(
            name="पोलीस कायदे व सामान्य ज्ञान (Police Laws & GK)",
            keywords=["police law", "कायदे", "motar vahan", "ipc", "crpc", "महाराष्ट्र पोलीस कायदा"],
            topics=[
                TopicNode(
                    name="महाराष्ट्र पोलीस अधिनियम व कायदे",
                    keywords=["पोलीस कायदा", "मोटार वाहन कायदा", "ipc", "crpc", "वाहतूक नियम"],
                ),
                TopicNode(
                    name="महाराष्ट्र जिल्हा विशेष व सामान्य ज्ञान",
                    keywords=["जिल्हा माहिती", "पोलीस पदश्रेणी", "मुख्यालय", "महाराष्ट्र GK"],
                ),
            ],
        ),
    ],
)

SARAL_SEVA_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.SARAL_SEVA,
    display_name="सरळ सेवा भरती (Talathi, ZP, Nagar Parishad TCS/IBPS)",
    authority="Maharashtra District Selection & Recruitment Committees",
    subjects=[
        SubjectNode(
            name="तलाठी व सरळ सेवा TCS पॅटर्न सराव (Talathi PYQ)",
            keywords=["तलाठी", "talathi", "tcs pattern", "ibps pattern", "zp bharti", "आरोग्य सेवक"],
            topics=[
                TopicNode(
                    name="तलाठी भरती TCS सर्व शिफ्ट्स PYQs",
                    keywords=["तलाठी शिफ्ट्स", "tcs pyq", "tcs question paper", "तलाठी प्रश्नसंच"],
                ),
                TopicNode(
                    name="जिल्हा परिषद व आरोग्य सेवक तांत्रिक विषय",
                    keywords=["आरोग्य तांत्रिक", "लस", "रोग", "मानवी शरीर", "zp technical"],
                ),
            ],
        ),
        SubjectNode(
            name="इंग्रजी व्याकरण (English Grammar TCS/IBPS)",
            keywords=["english grammar", "vocab", "synonyms", "antonyms", "idioms", "tcs english"],
            topics=[
                TopicNode(
                    name="TCS Grammar Rules & Spotting Errors",
                    keywords=["tenses", "subject verb agreement", "prepositions", "voice", "narration"],
                ),
                TopicNode(
                    name="High-Yield Vocabulary, Idioms & Phrases",
                    keywords=["idioms", "phrases", "one word substitution", "synonyms", "antonyms"],
                ),
            ],
        ),
    ],
)

NCERT_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.NCERT,
    display_name="NCERT Textbooks & Concept Foundation (Class 6 - 12)",
    authority="National Council of Educational Research and Training",
    subjects=[
        SubjectNode(
            name="General Science (सामान्य विज्ञान Class 6 - 10)",
            keywords=["ncert science", "class 6 science", "class 7 science", "class 8 science", "class 9 science", "class 10 science"],
            topics=[
                TopicNode(
                    name="Class 6 & 7 Living World & Motion",
                    keywords=["living world", "plants", "motion", "light", "acids and bases"],
                ),
                TopicNode(
                    name="Class 8 & 9 Matter, Atoms & Cells",
                    keywords=["cell structure", "atoms", "molecules", "force and laws of motion", "gravitation"],
                ),
                TopicNode(
                    name="Class 10 Chemical Reactions, Electricity & Genetics",
                    keywords=["chemical reactions", "electricity", "magnetic effects", "heredity and evolution", "carbon compounds"],
                ),
            ],
        ),
        SubjectNode(
            name="Mathematics (गणित Class 6 - 10)",
            keywords=["ncert maths", "algebra", "geometry", "trigonometry", "polynomials"],
            topics=[
                TopicNode(
                    name="Class 9 & 10 Algebra & Quadratic Equations",
                    keywords=["linear equations", "quadratic equations", "arithmetic progression", "polynomials"],
                ),
                TopicNode(
                    name="Geometry, Triangles & Trigonometry",
                    keywords=["triangles", "circles", "coordinate geometry", "trigonometry", "surface areas"],
                ),
            ],
        ),
    ],
)

BOARD_10_12_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.BOARD_10_12,
    display_name="Maharashtra State Board (10th SSC & 12th HSC)",
    authority="Maharashtra State Board of Secondary and Higher Secondary Education",
    subjects=[
        SubjectNode(
            name="10th SSC Board Examination",
            keywords=["10th ssc", "ssc board", "दहावी बोर्ड", "algebra", "geometry", "science 1", "science 2"],
            topics=[
                TopicNode(
                    name="Mathematics Part 1 (Algebra)",
                    keywords=["linear equations in two variables", "quadratic equations", "arithmetic progression", "probability", "statistics"],
                ),
                TopicNode(
                    name="Mathematics Part 2 (Geometry)",
                    keywords=["similarity", "pythagoras theorem", "circle", "geometric constructions", "trigonometry"],
                ),
                TopicNode(
                    name="Science & Technology Parts 1 & 2",
                    keywords=["gravitation", "periodic classification", "chemical reactions", "life processes", "environmental management"],
                ),
            ],
        ),
        SubjectNode(
            name="12th HSC Board Science Examination",
            keywords=["12th hsc", "hsc board", "बारावी", "physics", "chemistry", "biology", "mathematics"],
            topics=[
                TopicNode(
                    name="12th HSC Physics",
                    keywords=["rotational dynamics", "mechanical properties of fluids", "wave optics", "electrostatics", "semiconductors"],
                ),
                TopicNode(
                    name="12th HSC Chemistry",
                    keywords=["solid state", "solutions", "chemical thermodynamics", "coordination compounds", "organic chemistry"],
                ),
                TopicNode(
                    name="12th HSC Biology",
                    keywords=["reproduction in plants", "respiration and circulation", "control and coordination", "biotechnology"],
                ),
            ],
        ),
    ],
)

JEE_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.JEE,
    display_name="NTA JEE (Main & Advanced)",
    authority="National Testing Agency & IIT Joint Admission Board",
    subjects=[
        SubjectNode(
            name="Physics",
            keywords=["jee physics", "mechanics", "electrodynamics", "optics", "thermodynamics", "modern physics"],
            topics=[
                TopicNode(
                    name="Classical Mechanics & Rotational Motion",
                    keywords=["kinematics", "laws of motion", "work power energy", "rotational motion", "gravitation"],
                ),
                TopicNode(
                    name="Electromagnetism & Wave Optics",
                    keywords=["electrostatics", "current electricity", "magnetic effects", "electromagnetic induction", "wave optics"],
                ),
            ],
        ),
        SubjectNode(
            name="Chemistry",
            keywords=["jee chemistry", "physical chemistry", "organic chemistry", "inorganic chemistry"],
            topics=[
                TopicNode(
                    name="Physical Chemistry & Thermodynamics",
                    keywords=["atomic structure", "chemical kinetics", "thermodynamics", "equilibrium", "electrochemistry"],
                ),
                TopicNode(
                    name="Organic Chemistry Mechanisms",
                    keywords=["goc", "hydrocarbons", "aldehydes ketones", "amines", "polymers", "reaction mechanisms"],
                ),
            ],
        ),
        SubjectNode(
            name="Mathematics",
            keywords=["jee maths", "calculus", "algebra", "vectors", "coordinate geometry"],
            topics=[
                TopicNode(
                    name="Differential & Integral Calculus",
                    keywords=["limits continuity", "differentiation", "integration", "differential equations", "area under curve"],
                ),
                TopicNode(
                    name="Algebra, Vectors & 3D Geometry",
                    keywords=["matrices determinants", "complex numbers", "vectors", "3d geometry", "probability"],
                ),
            ],
        ),
    ],
)

NEET_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.NEET,
    display_name="NTA NEET (UG)",
    authority="National Testing Agency & National Medical Commission",
    subjects=[
        SubjectNode(
            name="Biology (Botany & Zoology)",
            keywords=["neet biology", "botany", "zoology", "human physiology", "genetics", "ecology"],
            topics=[
                TopicNode(
                    name="Human Physiology & Anatomy",
                    keywords=["digestion", "respiration", "circulation", "excretory products", "neural control", "chemical coordination"],
                ),
                TopicNode(
                    name="Genetics, Evolution & Biotechnology",
                    keywords=["principles of inheritance", "molecular basis of inheritance", "evolution", "biotechnology applications"],
                ),
                TopicNode(
                    name="Plant Physiology & Cell Biology",
                    keywords=["cell cycle", "photosynthesis", "respiration in plants", "plant growth"],
                ),
            ],
        ),
        SubjectNode(
            name="Chemistry",
            keywords=["neet chemistry", "physical chemistry", "organic chemistry"],
            topics=[
                TopicNode(
                    name="Physical & Inorganic Chemistry",
                    keywords=["chemical bonding", "periodic table", "equilibrium", "p block elements", "solutions"],
                ),
                TopicNode(
                    name="Organic Chemistry & Biomolecules",
                    keywords=["named reactions", "biomolecules", "aldehydes ketones", "haloalkanes"],
                ),
            ],
        ),
        SubjectNode(
            name="Physics",
            keywords=["neet physics", "mechanics", "current electricity", "optics", "thermodynamics"],
            topics=[
                TopicNode(
                    name="Mechanics, Fluids & Thermodynamics",
                    keywords=["laws of motion", "gravitation", "thermodynamics", "kinetic theory of gases"],
                ),
                TopicNode(
                    name="Electrodynamics & Ray Optics",
                    keywords=["electrostatics", "ray optics", "semiconductors", "current electricity"],
                ),
            ],
        ),
    ],
)

UPSC_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.UPSC,
    display_name="UPSC Civil Services Examination (CSE)",
    authority="Union Public Service Commission",
    subjects=[
        SubjectNode(
            name="Prelims GS Paper 1",
            keywords=["upsc gs 1", "prelims gs", "indian polity", "modern history", "geography", "environment"],
            topics=[
                TopicNode(
                    name="Indian Polity, Constitution & Governance",
                    keywords=["constitution", "preamble", "fundamental rights", "dpsp", "parliament", "judiciary", "panchayati raj"],
                ),
                TopicNode(
                    name="Indian & World Geography, Environment & Ecology",
                    keywords=["physical geography", "climate change", "biodiversity", "national parks", "ecology"],
                ),
                TopicNode(
                    name="Modern Indian History & Freedom Struggle",
                    keywords=["revolt of 1857", "socio religious reforms", "indian national congress", "gandhian era"],
                ),
            ],
        ),
        SubjectNode(
            name="CSAT Paper 2",
            keywords=["csat", "reading comprehension", "logical reasoning", "data interpretation", "quantitative aptitude"],
            topics=[
                TopicNode(
                    name="Reading Comprehension & Critical Reasoning",
                    keywords=["reading comprehension", "passages", "critical reasoning", "logical deduction"],
                ),
                TopicNode(
                    name="Analytical Reasoning & Quantitative Aptitude",
                    keywords=["number system", "data sufficiency", "syllogisms", "arrangements", "permutations"],
                ),
            ],
        ),
    ],
)

BANKING_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.BANKING,
    display_name="Banking Examinations (IBPS PO/Clerk, SBI PO, RBI Grade B)",
    authority="Institute of Banking Personnel Selection & RBI",
    subjects=[
        SubjectNode(
            name="Quantitative Aptitude (संख्यात्मक अभियोग्यता)",
            keywords=["banking quant", "speed maths", "data interpretation", "simplification", "arithmetic", "quadratic equations"],
            topics=[
                TopicNode(
                    name="Speed Maths, Simplification & Series",
                    keywords=["vedic maths", "simplification", "approximation", "number series", "missing series"],
                ),
                TopicNode(
                    name="Data Interpretation (DI) & Caselets",
                    keywords=["bar chart", "line graph", "pie chart", "caselet di", "radar di", "table di"],
                ),
                TopicNode(
                    name="Core Commercial Arithmetic",
                    keywords=["percentages", "profit and loss", "simple compound interest", "ratio and proportion", "time work"],
                ),
            ],
        ),
        SubjectNode(
            name="Reasoning Ability (तर्कशक्ती व बुद्धिमत्ता)",
            keywords=["banking reasoning", "puzzles", "seating arrangement", "syllogism", "inequalities", "coding decoding"],
            topics=[
                TopicNode(
                    name="High-Level Puzzles & Seating Arrangements",
                    keywords=["circular seating", "linear seating", "box puzzle", "floor puzzle", "month day puzzle"],
                ),
                TopicNode(
                    name="Syllogism, Inequalities & Machine Input",
                    keywords=["syllogism", "inequality", "machine input output", "direction sense", "blood relations"],
                ),
            ],
        ),
        SubjectNode(
            name="Banking & Financial Awareness (बँकिंग व वित्तीय जागरूकता)",
            keywords=["banking awareness", "rbi policy", "monetary policy", "npa", "inflation", "financial terms", "repo rate"],
            topics=[
                TopicNode(
                    name="RBI Structure, Monetary Policy & Terms",
                    keywords=["rbi acts", "repo rate", "reverse repo", "crr", "slr", "monetary policy committee", "npa"],
                ),
                TopicNode(
                    name="Banking Products, Financial Markets & Digital Banking",
                    keywords=["upi", "neft", "rtgs", "types of accounts", "capital market", "money market"],
                ),
            ],
        ),
    ],
)

SSC_SYLLABUS = ExamSyllabus(
    exam_category=ExamCategory.SSC,
    display_name="Staff Selection Commission (SSC CGL, CHSL, MTS, GD)",
    authority="Staff Selection Commission of India",
    subjects=[
        SubjectNode(
            name="Quantitative Aptitude & Advanced Maths",
            keywords=["ssc quant", "advanced maths", "algebra", "geometry", "trigonometry", "mensuration"],
            topics=[
                TopicNode(
                    name="Advanced Mathematics (Algebra & Trigonometry)",
                    keywords=["algebraic identities", "heights and distances", "trigonometric ratios", "polynomials"],
                ),
                TopicNode(
                    name="Geometry & Mensuration 2D/3D",
                    keywords=["triangles", "circles", "tangents", "quadrilaterals", "cylinder", "cone", "sphere volume"],
                ),
            ],
        ),
        SubjectNode(
            name="English Language & Comprehension",
            keywords=["ssc english", "idioms", "one word substitution", "synonyms", "antonyms", "cloze test", "error spotting"],
            topics=[
                TopicNode(
                    name="Repeated Vocabulary, Idioms & OWS",
                    keywords=["1000 repeated idioms", "one word substitutions", "synonyms", "antonyms", "spelling errors"],
                ),
                TopicNode(
                    name="Grammar Rules & Cloze Test",
                    keywords=["active passive voice", "direct indirect speech", "cloze test", "sentence improvement", "spotting errors"],
                ),
            ],
        ),
        SubjectNode(
            name="General Studies & Static GK",
            keywords=["ssc gs", "static gk", "indian history", "polity", "science", "folk dances", "monuments"],
            topics=[
                TopicNode(
                    name="Static GK, Culture, Festivals & Dances",
                    keywords=["classical dances", "folk dances", "festivals", "temples", "national parks", "first in india"],
                ),
                TopicNode(
                    name="General Science & Indian Constitution",
                    keywords=["physics chemistry biology questions", "fundamental rights articles", "amendments"],
                ),
            ],
        ),
    ],
)


# Master registry map indexed by ExamCategory
SYLLABUS_REGISTRY: Dict[ExamCategory, ExamSyllabus] = {
    ExamCategory.MPSC: MPSC_SYLLABUS,
    ExamCategory.POLICE_BHARTI: POLICE_BHARTI_SYLLABUS,
    ExamCategory.SARAL_SEVA: SARAL_SEVA_SYLLABUS,
    ExamCategory.NCERT: NCERT_SYLLABUS,
    ExamCategory.BOARD_10_12: BOARD_10_12_SYLLABUS,
    ExamCategory.JEE: JEE_SYLLABUS,
    ExamCategory.NEET: NEET_SYLLABUS,
    ExamCategory.UPSC: UPSC_SYLLABUS,
    ExamCategory.BANKING: BANKING_SYLLABUS,
    ExamCategory.SSC: SSC_SYLLABUS,
}


def get_exam_syllabus(exam_category: ExamCategory) -> Optional[ExamSyllabus]:
    """Retrieve official syllabus definition for an exam category."""
    return SYLLABUS_REGISTRY.get(exam_category)


def get_all_syllabi() -> List[ExamSyllabus]:
    """Return all registered exam syllabi."""
    return list(SYLLABUS_REGISTRY.values())
