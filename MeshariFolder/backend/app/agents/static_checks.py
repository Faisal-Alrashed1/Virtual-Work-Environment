"""
Deterministic, rule-based checks the Security Reviewer and Data Reviewer
run over submitted content before (and independently of) the LLM — the
same "compute the fact in code, let the LLM narrate it" pattern as
hr.py's _active_days. A rule match here always ends up in the stored
findings, even when the small-tier model misses it: in live testing, the
model caught an SQL injection but missed two hardcoded secrets right next
to it, and misdescribed a data leak.

Pure functions over (filename, text) pairs — no DB, no LLM, no network —
so each rule is easy to test and a new one is a few lines. Rules are
deliberately conservative: a missed issue is still left to the LLM, but
a false alarm here would be stated as verified fact.
"""
import re
from dataclasses import dataclass

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass
class StaticFinding:
    category: str
    severity: str
    filename: str
    line: int
    description: str
    recommendation: str

    @property
    def location(self) -> str:
        if self.filename.endswith(".ipynb"):
            return f"{self.filename} (code cells) line {self.line}"
        return f"{self.filename} line {self.line}"

    def as_finding(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "description": f"{self.location}: {self.description}",
            "recommendation": self.recommendation,
            "source": "static_check",
        }


# ---------------------------------------------------------------------------
# Hardcoded secrets (Security Reviewer)
# ---------------------------------------------------------------------------

# A secret-looking name assigned a string literal: PASSWORD = "...",
# api_key: '...', "db_password": "..." (dict/JSON/YAML keys too).
_SECRET_ASSIGNMENT = re.compile(
    r"""(?i)\b(\w*(?:password|passwd|pwd|secret|api_?key|access_?key|"""
    r"""private_?key|auth_?token|token)\w*)["']?\s*[:=]\s*(["'])([^"'\n]{4,})\2"""
)

# Well-known key formats, recognizable regardless of the variable name.
_KEY_FORMATS = [
    ("an AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("an API key (sk-...)", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("a Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("a private key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
]

# Values that are obviously placeholders, not real secrets.
_PLACEHOLDER_HINTS = (
    "...", "xxx", "your", "change", "example", "placeholder", "dummy",
    "<", "${", "todo", "replace", "redacted", "****",
)

# Template files are meant to hold placeholders (.env.example etc).
_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in _PLACEHOLDER_HINTS)


def _mask(value: str) -> str:
    """Never store/echo the secret itself — enough to recognize it, no more."""
    return f"{value[:3]}… ({len(value)} chars)"


def find_hardcoded_secrets(files: list[tuple[str, str]]) -> list[StaticFinding]:
    findings: list[StaticFinding] = []
    for filename, text in files:
        if filename.lower().endswith(_TEMPLATE_SUFFIXES):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            match = _SECRET_ASSIGNMENT.search(line)
            if match and not _is_placeholder(match.group(3)):
                findings.append(
                    StaticFinding(
                        category="hardcoded_secret",
                        severity="high",
                        filename=filename,
                        line=line_no,
                        description=(
                            f"'{match.group(1)}' is set to a hardcoded value "
                            f"({_mask(match.group(3))}) in source code."
                        ),
                        recommendation=(
                            "Load it from an environment variable (e.g. os.environ) "
                            "or a secrets manager, keep the real value in a gitignored "
                            ".env, and rotate it if this code was ever shared or pushed."
                        ),
                    )
                )
                continue
            for label, pattern in _KEY_FORMATS:
                key = pattern.search(line)
                if key and not _is_placeholder(line):
                    findings.append(
                        StaticFinding(
                            category="hardcoded_secret",
                            severity="high",
                            filename=filename,
                            line=line_no,
                            description=f"Contains what looks like {label} ({_mask(key.group(0))}).",
                            recommendation=(
                                "Remove it from the code, load it from the environment "
                                "instead, and revoke/rotate the key."
                            ),
                        )
                    )
                    break
    return findings


# ---------------------------------------------------------------------------
# Data leakage / evaluation methodology (Data Reviewer)
# ---------------------------------------------------------------------------

_CODE_SUFFIXES = (".py", ".ipynb")
_SPLIT = re.compile(
    r"\b(?:train_test_split|KFold|StratifiedKFold|GroupKFold|TimeSeriesSplit|"
    r"cross_val_score|cross_validate|cross_val_predict)\s*\("
)
# Fitting a preprocessing step (scaler, encoder, imputer, vectorizer...)
# rather than a model. fit_transform on its own line counts too.
_PREPROCESS_FIT = re.compile(
    r"\.fit_transform\s*\(|"
    r"\b\w*(?:Scaler|Encoder|Imputer|Normalizer|PCA|SelectKBest|Vectorizer)\s*\([^)]*\)\s*\.fit\s*\("
)
_TRAIN_EVAL = re.compile(r"\.score\s*\(\s*X_train\b|\b\w+_score\s*\(\s*y_train\b")
_TEST_EVAL = re.compile(r"\.score\s*\(\s*X_test\b|\b\w+_score\s*\(\s*y_test\b")
_MODEL_FIT = re.compile(r"\.fit\s*\(")


def _first_line(pattern: re.Pattern, lines: list[str]) -> int | None:
    for line_no, line in enumerate(lines, start=1):
        if pattern.search(line):
            return line_no
    return None


def find_data_leakage(files: list[tuple[str, str]]) -> list[StaticFinding]:
    findings: list[StaticFinding] = []
    for filename, text in files:
        if not filename.lower().endswith(_CODE_SUFFIXES) or "sklearn" not in text:
            continue
        lines = text.splitlines()
        split_line = _first_line(_SPLIT, lines)

        # 1. Preprocessing fit on the whole dataset, before the split.
        if split_line is not None:
            for line_no, line in enumerate(lines[: split_line - 1], start=1):
                if _PREPROCESS_FIT.search(line) and "train" not in line.lower():
                    findings.append(
                        StaticFinding(
                            category="data_leakage",
                            severity="high",
                            filename=filename,
                            line=line_no,
                            description=(
                                "A preprocessing step is fit on the full dataset before "
                                f"the train/test split (split happens at line {split_line}), "
                                "so information from the test set leaks into training."
                            ),
                            recommendation=(
                                "Split first, then fit the preprocessing on the training "
                                "set only (or put it in a sklearn Pipeline) and just "
                                "transform the test set."
                            ),
                        )
                    )
                    break

        # 2. Evaluated only on the training data.
        train_eval = _first_line(_TRAIN_EVAL, lines)
        if train_eval is not None and _first_line(_TEST_EVAL, lines) is None:
            findings.append(
                StaticFinding(
                    category="evaluation_methodology",
                    severity="high",
                    filename=filename,
                    line=train_eval,
                    description=(
                        "The model is scored on its own training data and never on "
                        "held-out data, so the reported performance is overly optimistic."
                    ),
                    recommendation="Report the metric on the test set (or via cross-validation).",
                )
            )

        # 3. A model is trained with no held-out split at all.
        fit_line = _first_line(_MODEL_FIT, lines)
        if fit_line is not None and split_line is None and "X_test" not in text:
            findings.append(
                StaticFinding(
                    category="evaluation_methodology",
                    severity="medium",
                    filename=filename,
                    line=fit_line,
                    description="A model is trained, but there's no train/test split or cross-validation anywhere.",
                    recommendation="Hold out a test set (train_test_split) or use cross-validation before trusting any metric.",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Merging into the LLM's review
# ---------------------------------------------------------------------------

def facts_for_prompt(static: list[StaticFinding]) -> str:
    lines = [f"- {f.location}: {f.description}" for f in static]
    return (
        "ALREADY RECORDED (verified by code — these are added to your findings "
        "automatically, so don't repeat them; you may mention them briefly in "
        "your summary, but never repeat a secret's value):\n" + "\n".join(lines)
    )


def _duplicates_static(
    finding: dict, static: list[StaticFinding], known_files: list[str]
) -> bool:
    """An LLM finding repeats a static one when it has the same category
    and isn't about some *other* file. The model often doesn't name the
    file at all, so requiring the filename to match would miss those."""
    description = finding.get("description", "")
    for s in static:
        if finding.get("category") != s.category:
            continue
        other_files = [name for name in known_files if name != s.filename]
        if not any(name in description for name in other_files):
            return True
    return False


def merge_findings(
    static: list[StaticFinding], llm_findings: list[dict], known_files: list[str]
) -> list[dict]:
    """Static findings first (they're verified), then the LLM's — minus any
    that duplicate a static one. known_files: every file that was read."""
    kept = [f for f in llm_findings if not _duplicates_static(f, static, known_files)]
    return [f.as_finding() for f in static] + kept


def merge_risk_level(llm_risk: str, static: list[StaticFinding]) -> str:
    levels = [llm_risk] + [f.severity for f in static]
    return max(levels, key=lambda level: _SEVERITY_ORDER.get(level, 0))


def summary_prefix(static: list[StaticFinding]) -> str:
    """One deterministic line at the start of the thread message, so a
    verified issue is visible even if the LLM's summary skips it."""
    if not static:
        return ""
    return "Verified in code: " + "; ".join(
        f"{f.location} ({f.category.replace('_', ' ')})" for f in static
    ) + ". "
