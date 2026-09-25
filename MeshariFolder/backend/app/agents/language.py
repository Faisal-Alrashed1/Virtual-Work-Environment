"""
Which language the agents write in, shared by every agent that writes
text a graduate reads. English stays the default, so nothing changes for
anyone writing in English; a graduate who writes in Arabic gets Saudi
(Najdi) dialect back rather than formal MSA — the product's Arabic UI is
written the same way (frontend/src/lib/i18n/ar.ts).
"""

LANGUAGE_RULE = (
    "\n\nLanguage: answer in the language the graduate writes to you in. "
    "If their messages or submission notes are in Arabic, write in Saudi "
    "Najdi dialect — natural and friendly, the way a Saudi colleague from "
    "Riyadh talks at work (e.g. 'وش', 'الحين', 'زين', 'ترا', 'عساك', "
    "'يعطيك العافية'), not formal Modern Standard Arabic. Keep code, file "
    "names, commands, and technical terms (API, GitHub, SQL injection...) "
    "exactly as they are. If they write in English, or haven't written "
    "anything, answer in English."
)
