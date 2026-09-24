"""
Unit test for app/agents/static_checks.py — the rule-based checks the
Security Reviewer and Data Reviewer run before the LLM. Pure functions,
so no server, DB, or LLM mocking needed. Covers both directions: what
each rule must catch, and what it must NOT flag (a false alarm here is
stated to the graduate as verified fact).

Run: python smoke_test_static_checks.py
"""
from app.agents.static_checks import (
    StaticFinding,
    find_data_leakage,
    find_hardcoded_secrets,
    merge_findings,
    merge_risk_level,
    summary_prefix,
)


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# ---------------- hardcoded secrets ----------------

app_py = '''import os
DB_PASSWORD = "SuperSecret123!"
API_KEY = "sk-live-4f9a8b7c6d5e4f3a2b1c"
config = {"db_password": "hunter2hunter2"}
TOKEN = os.environ["TOKEN"]
password = os.getenv("PASSWORD")
'''
found = find_hardcoded_secrets([("app.py", app_py)])
lines = sorted(f.line for f in found)
check("secrets: catches PASSWORD = \"...\" (line 2)", 2 in lines)
check("secrets: catches API_KEY = \"sk-...\" (line 3)", 3 in lines)
check("secrets: catches a dict key \"db_password\": \"...\" (line 4)", 4 in lines)
check("secrets: env-var lookups are NOT flagged (lines 5, 6)", 5 not in lines and 6 not in lines)
check("secrets: one finding per line, no duplicates", len(lines) == len(set(lines)))
check("secrets: all high severity", all(f.severity == "high" for f in found))
check(
    "secrets: the secret value itself is never stored",
    not any("SuperSecret123!" in str(f.as_finding()) for f in found),
)

placeholders = '''API_KEY = "your-api-key-here"
SECRET = "change-me"
PASSWORD = "<password>"
TOKEN = "xxxxxxxx"
KEY = "sk-..."
'''
check("secrets: obvious placeholders are NOT flagged", find_hardcoded_secrets([("settings.py", placeholders)]) == [])
check(
    "secrets: template files (.env.example) are skipped",
    find_hardcoded_secrets([(".env.example", 'DB_PASSWORD="realvalue123"')]) == [],
)
check(
    "secrets: a known key format is caught regardless of variable name",
    len(find_hardcoded_secrets([("client.js", 'const x = "AKIAZ7Q3N4P2R8T6V1W5";')])) == 1,
)
check(
    "secrets: a private key block is caught",
    len(find_hardcoded_secrets([("deploy.sh", "-----BEGIN RSA PRIVATE KEY-----")])) == 1,
)


# ---------------- data leakage ----------------

leaky = '''from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
X_scaled = StandardScaler().fit_transform(X)
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y)
model.fit(X_train, y_train)
print(model.score(X_train, y_train))
'''
found = find_data_leakage([("analysis.ipynb", leaky)])
categories = {f.category: f for f in found}
check("leakage: scaler fit before the split is caught", "data_leakage" in categories)
check("leakage: it points at the fit line (3), not the split line", categories["data_leakage"].line == 3)
check("leakage: scoring only on training data is caught", "evaluation_methodology" in categories)
check("leakage: notebook location says 'code cells'", "code cells" in categories["data_leakage"].location)

correct = '''from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y)
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)
model.fit(X_train, y_train)
print(model.score(X_train, y_train), model.score(X_test, y_test))
'''
check("leakage: correct split-then-fit code is NOT flagged", find_data_leakage([("train.py", correct)]) == [])

no_split = '''from sklearn.linear_model import LogisticRegression
model = LogisticRegression().fit(X, y)
'''
found = find_data_leakage([("model.py", no_split)])
check("leakage: training with no split at all is caught (medium)", len(found) == 1 and found[0].severity == "medium")
check("leakage: non-ML code is ignored", find_data_leakage([("app.py", "x.fit_transform(y)")]) == [])
check("leakage: non-code files are ignored", find_data_leakage([("notes.txt", leaky)]) == [])


# ---------------- merging with the LLM's review ----------------

static = [
    StaticFinding("hardcoded_secret", "high", "app.py", 2, "'DB_PASSWORD' is hardcoded.", "Use env vars."),
]
llm = [
    {"category": "hardcoded_secret", "severity": "high", "description": "app.py has a hardcoded password.", "recommendation": "x"},
    {"category": "hardcoded_secret", "severity": "high", "description": "A password is hardcoded.", "recommendation": "x"},
    {"category": "hardcoded_secret", "severity": "high", "description": "config.py hardcodes a token.", "recommendation": "x"},
    {"category": "injection_risk", "severity": "high", "description": "app.py builds SQL with f-strings.", "recommendation": "y"},
]
merged = merge_findings(static, llm, ["app.py", "config.py"])
secrets = [f for f in merged if f["category"] == "hardcoded_secret"]
check("merge: verified finding comes first", merged[0].get("source") == "static_check")
check("merge: duplicate naming the same file is dropped", not any(f["description"] == "app.py has a hardcoded password." for f in merged))
check("merge: duplicate naming no file at all is dropped (the live-test case)", not any(f["description"] == "A password is hardcoded." for f in merged))
check("merge: same category but a DIFFERENT file is kept", any("config.py" in f["description"] for f in secrets))
check("merge: the LLM's other categories are kept", any(f["category"] == "injection_risk" for f in merged))
check("merge: risk level is raised to the verified finding's severity", merge_risk_level("low", static) == "high")
check("merge: risk level never lowered", merge_risk_level("high", []) == "high")
check("merge: summary prefix names the location", summary_prefix(static).startswith("Verified in code: app.py line 2"))
check("merge: no prefix when nothing was verified", summary_prefix([]) == "")

print("\nAll static-check smoke checks passed.")
