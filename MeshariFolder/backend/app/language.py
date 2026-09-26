"""
Per-request language for agent output.

The UI can be English or Arabic (frontend/src/lib/i18n), but until now every
agent — the Manager's plans, the Mentor's reviews, HR, the meeting room, the
roundtable, the onboarding questions — answered in English regardless. This
module lets them answer in the language the graduate is actually using.

How it works: the frontend sends `X-Venv-Language: ar|en` with every API call
(see lib/api.ts). LanguageMiddleware stores it in a ContextVar for the life of
that request, and llm_client appends a short instruction to the system prompt of
every model call it makes (with_language) — so no agent needed to change, and a
new agent gets it for free. English is the default and adds nothing, so
English behaviour is byte-for-byte what it was.

Why a header rather than a stored preference: it is what the UI shows *right
now* (no sync problem between devices or after a toggle), needs no migration,
and every agent call is already triggered by an HTTP request.
See docs/AGENT_LANGUAGE.md.
"""
from contextvars import ContextVar

SUPPORTED_LANGUAGES = ("en", "ar")
DEFAULT_LANGUAGE = "en"

current_language: ContextVar[str] = ContextVar("venv_language", default=DEFAULT_LANGUAGE)

# Appended to the system prompt. Keeps everything a program reads (JSON keys,
# enum values, ids, code) in English — only the words a person reads change.
_ARABIC_DIRECTIVE = (
    "\n\n---\n"
    "LANGUAGE INSTRUCTION: this graduate uses Venv in Arabic. Write every "
    "human-readable piece of text you produce (task titles and descriptions, "
    "questions, review summaries and comments, reasoning, chat replies) in clear "
    "Modern Standard Arabic. Do NOT translate: JSON keys, tool or function names, "
    "enum values (for example 'approved', 'needs_changes', track names and agent "
    "ids), code, identifiers, file names, URLs, commands, or widely used technical "
    "terms (API, JWT, Docker, Git, GitHub, SQL, React and similar stay in Latin "
    "script). Everything else above still applies exactly as written."
)

_DIRECTIVES = {"ar": _ARABIC_DIRECTIVE}


def normalize_language(raw: str | None) -> str:
    """Anything we don't support (or a missing/garbled header) is English."""
    code = (raw or "").strip().lower()[:2]
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def language_directive() -> str:
    return _DIRECTIVES.get(current_language.get(), "")


def with_language(system: str) -> str:
    """`system` plus the language instruction for the current request (a no-op
    for English)."""
    return system + language_directive()


class LanguageMiddleware:
    """Pure ASGI middleware (not BaseHTTPMiddleware) so the ContextVar is visible
    to endpoints, including sync ones that FastAPI runs in a threadpool — the
    threadpool copies the context as it is when the endpoint is called."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"x-venv-language"), None)
        token = current_language.set(normalize_language(raw))
        try:
            await self.app(scope, receive, send)
        finally:
            current_language.reset(token)
