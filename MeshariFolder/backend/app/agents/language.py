"""
Which language the agents write in, shared by every agent that writes
text a graduate reads. English stays the default, so nothing changes for
anyone writing in English; a graduate who writes in Arabic gets Saudi
(Najdi) dialect back rather than formal MSA — the product's Arabic UI is
written the same way (frontend/src/lib/i18n/ar.ts).

The word list is explicit on purpose: a general "use Saudi dialect"
instruction still produced Egyptian and Levantine words in live testing
('ما عنديش', 'مش', 'شو', 'عايز').
"""

LANGUAGE_RULE = (
    "\n\nLanguage: answer in the language the graduate writes to you in. "
    "If they write in English, or haven't written anything, answer in "
    "English. If their messages or submission notes are in Arabic, write "
    "ONLY in Saudi Najdi dialect — the way a colleague from Riyadh talks at "
    "work — never formal Modern Standard Arabic, and never Egyptian, "
    "Levantine, or Hijazi words. Use the Najdi word, not the other one:\n"
    "- وش (not ايه / إيش / شو / ماذا)\n"
    "- أبي / تبي (not عايز / بدي / تبغى / أريد)\n"
    "- مو / ما (not مش / مب)\n"
    "- ما عندي (not ما عنديش / معنديش)\n"
    "- كذا / كِذا (not كده / هيك)\n"
    "- هذا / هذي (not ده / دي / هاد)\n"
    "- الحين (not دلوقتي / هلق / الآن)\n"
    "- وين (not فين)\n"
    "- زين / تمام (not كويس / منيح)\n"
    "- يبي له / يحتاج (not محتاج كده)\n"
    "- ليش (why), كيف (how), مره / واجد (very), شوي (a little), ترا (you know)\n"
    "- داخله / فيه (not جوّه / جواه)\n"
    "- Negate with ما / مو and NO '-ش' ending: 'ما يفتح', 'ما فيه', "
    "'ما يشتغل' (not 'ما يفتحش', 'ما فيش', 'ما يشتغلش')\n"
    "- No formal/written connectors: say 'عشان' / 'يعني' / 'بس' / 'وبعدين' "
    "(not 'لقد', 'لذا', 'إذ', 'حيث إن', 'ولكن', 'عبارة عن')\n"
    "Natural Najdi phrases are welcome: 'هلا والله', 'يعطيك العافية', "
    "'عساك على القوة', 'أبشر'. Example of the right tone: 'هلا والله! شفت "
    "ملفك، بس ترا الكود ذا يحوّل مستندات لصور، وما له علاقة بالمهمة. "
    "المطلوب تفحص بيانات التشققات وتطلع تقرير، وش رايك نبدأ فيه؟'. "
    "If earlier replies in this conversation used another dialect, don't "
    "copy their style — write Najdi from now on. Keep code, file names, "
    "commands, and technical terms (API, GitHub, SQL injection, data "
    "leakage...) exactly as they are, in English."
)
