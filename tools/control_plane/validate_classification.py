"""Validate .codex/knowledge/task-classification.md and its verification (P1-S05, BLUEPRINT.md v1.2 §1.3-§1.5).

Usage: python -I tools/control_plane/validate_classification.py [--codex] [--self-test]
  (default)    static checks; exit 0 = pass, 1 = fail
  --codex      also render the model-visible prompt with `codex debug prompt-input` (no model session) and
               require the AGENTS.md classification pointer to be present
  --self-test  prove each check fails on a mutated input (negative controls)

Proves: structure, that no numeric scoring formula or classifier service crept in, scenario coverage, and
that the runtime results table is complete. Cannot prove: that a model classifies correctly (that is the
`codex exec` evidence in task-classification-verification.md, graded by run_classification_scenarios.py).
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / ".codex" / "knowledge" / "task-classification.md"
VERIFY = ROOT / ".codex" / "knowledge" / "task-classification-verification.md"
CONTRACTS = ROOT / ".codex" / "knowledge" / "contracts.md"
AGENTS = ROOT / "AGENTS.md"

INTENTS = ["Feature", "Bug", "Refactor", "Migration", "Security", "Performance", "Reliability",
           "Infrastructure", "Research", "Documentation", "Mixed"]
LEVELS = ["L0", "L1", "L2", "L3"]
CHANNELS = {"transcript", "diff", "events"}
RESULTS = {"PASS", "FAIL", "PARTIAL"}
# A numeric scoring formula, weights, thresholds, or an external classification service.
FORMULA = re.compile(r"\bC\s*=|\b\d\s*[S R D U V]\b\s*\+|weighted (score|sum)|score\s*(>=|<=|>|<|=)\s*\d|"
                     r"threshold of \d|https?://|classif\w+ (service|api|endpoint|server)|\bMCP server\b", re.I)
EXP_ROW = re.compile(r"^\| (CLS-\d+) \| ([^|]+?) \| (.+?) \|$", re.M)
STATIC_ROW = re.compile(r"^\| (T\d+) \| ([A-Za-z+ ]+?) \| (L[0-3]) \| (yes|no) \| (.+?) \| (.+?) \| (.+?) \|$", re.M)
RUN_ROW = re.compile(r"^\| (R\d+) \| (L[0-3]) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", re.M)
RUNS_WANTED = ["R1", "R2", "R3", "R4", "R5", "R6"]


def section(text, heading):
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def check_doc(t, contracts):
    errs = []
    intents = section(t, "1. Intent: what kind of work")
    for name in INTENTS:
        if not re.search(rf"^\| {name} \|", intents, re.M):
            errs.append(f"intent table lacks {name}")
    lv = section(t, "2. Complexity: how much process")
    for lvl in LEVELS:
        if not re.search(rf"^\| {lvl} \|", lv, re.M):
            errs.append(f"complexity table lacks {lvl}")
    if "highest" not in lv or "Do not compute a score" not in lv:
        errs.append("section 2 must say to take the highest supported level and not compute a score")
    risk = section(t, "3. High-risk override")
    for word in ("security-sensitive", "destructive", "irreversible", "data-migrating", "production-facing"):
        if word not in risk:
            errs.append(f"high-risk override must name {word!r}")
    if "L3 controls" not in risk or "naming that action and target" not in risk:
        errs.append("high-risk override must require L3 controls and authorization naming action and target")
    if "Independent verification" not in risk:
        errs.append("high-risk override must require independent verification")
    for lvl_row, banned in (("L0", "plan"), ("L1", "plan")):
        row = re.search(rf"^\| {lvl_row} \|.*$", lv, re.M)
        if row and "No plan" not in row.group(0):
            errs.append(f"{lvl_row} row must say there is no plan")
    for m in FORMULA.finditer(t):
        errs.append(f"numeric scoring formula or external classifier wording {m.group(0)!r}")
    if re.search(r"claude", t, re.I):
        errs.append("task-classification.md must not reference Claude")
    if "GUIDANCE" not in section(t, "5. Enforcement"):
        errs.append("section 5 must label the rules GUIDANCE")
    ids = []
    for m in EXP_ROW.finditer(section(t, "6. Expectations")):
        chans = {c.strip() for c in m.group(2).split(",")}
        if not chans <= CHANNELS:
            errs.append(f"{m.group(1)}: 'Seen in' must be a subset of {sorted(CHANNELS)}")
        if len(m.group(3)) < 40:
            errs.append(f"{m.group(1)}: expectation text too thin to observe")
        ids.append(m.group(1))
    if ids != [f"CLS-{i}" for i in range(1, len(ids) + 1)] or len(ids) < 7:
        errs.append(f"expectations must be CLS-1..CLS-n in order, at least 7; got {ids}")
    for ref in set(re.findall(r"contracts §(\d)", t)):
        if not re.search(rf"^## {ref}\. \w+ contract", contracts, re.M):
            errs.append(f"cites contracts §{ref}, which does not exist")
    return errs


def check_agents(a):
    errs = []
    if "task-classification.md" not in a:
        errs.append("AGENTS.md must point to .codex/knowledge/task-classification.md")
    if len(a.encode()) > 8 * 1024:
        errs.append("AGENTS.md grew beyond 8 KiB")
    for m in FORMULA.finditer(a):
        errs.append(f"AGENTS.md: numeric scoring formula or classifier wording {m.group(0)!r}")
    return errs


def check_verify(v, doc):
    errs = []
    ids = {m.group(1) for m in EXP_ROW.finditer(section(doc, "6. Expectations"))}
    rows = STATIC_ROW.findall(v)
    seen_int, seen_lv, covered, override = set(), set(), set(), set()
    for tid, intent, lvl, ov, req, beh, exps in rows:
        parts = {p.strip() for p in intent.split("+")}
        if not parts <= set(INTENTS):
            errs.append(f"{tid}: unknown intent {intent!r}")
        if "+" in intent:
            seen_int.add("Mixed")
        seen_int |= parts
        seen_lv.add(lvl)
        if ov == "yes":
            override.add(lvl)
            if lvl != "L3":
                errs.append(f"{tid}: a high-risk override must classify as L3")
        refs = set(re.findall(r"CLS-\d+", exps))
        if not refs:
            errs.append(f"{tid}: no expectation ids")
        for r in refs - ids:
            errs.append(f"{tid}: unknown expectation {r}")
        covered |= refs
    for i in INTENTS:
        if i not in seen_int:
            errs.append(f"no static trace row for intent {i}")
    for lvl in LEVELS:
        if lvl not in seen_lv:
            errs.append(f"no static trace row at {lvl}")
    if not override:
        errs.append("no static trace row exercises the high-risk override")
    runs = {r[0]: r for r in RUN_ROW.findall(v)}
    for rid in RUNS_WANTED:
        if rid not in runs:
            errs.append(f"runtime results table lacks {rid}")
    for rid, r in runs.items():
        covered_refs = set(re.findall(r"CLS-\d+", r[3]))
        for x in covered_refs - ids:
            errs.append(f"{rid}: unknown expectation {x}")
        covered |= covered_refs
        words = re.findall(r"[A-Z]{4,}", r[5])  # the cell may hold one verdict per clean pass
        if not words or not set(words) <= RESULTS:
            errs.append(f"{rid}: result must be made of {sorted(RESULTS)}, got {r[5]!r}")
    for e in sorted(ids - covered):
        errs.append(f"expectation {e} is covered by no trace row or run")
    for needle in ("## Not verified", "BLOCKED: operator"):
        if needle not in v:
            errs.append(f"verification doc lacks {needle!r}")
    return errs


def run_all(t):
    return check_doc(t["doc"], t["contracts"]) + check_agents(t["agents"]) + check_verify(t["verify"], t["doc"])


def mutations(t):
    def sub(key, old, new, count=1):
        def f(d):
            assert old in d[key], (key, old)
            d = dict(d)
            d[key] = d[key].replace(old, new, count)
            return d
        return f
    first_static = STATIC_ROW.search(t["verify"]).group(0)
    return {
        "intent removed": lambda d: {**d, "doc": re.sub(r"^\| Reliability \|.*\n", "", d["doc"], flags=re.M)},
        "level removed": lambda d: {**d, "doc": re.sub(r"^\| L2 \|.*\n", "", d["doc"], flags=re.M)},
        "highest-level rule removed": sub("doc", "take the **highest**", "take the"),
        "score formula added": sub("doc", "Do not compute a score.", "Compute C = 2S + 2R + D + U + V."),
        "classifier service added": sub("doc", "no external service", "a call to https://classify.example/api"),
        "mcp server added": sub("doc", "no external service", "an MCP server"),
        "override word removed": sub("doc", "data-migrating, or\nproduction-facing", "data-migrating,"),
        "L3 controls removed": sub("doc", "L3 controls", "extra care"),
        "authorization rule removed": sub("doc", "naming that action and target", "from anyone"),
        "independent verification removed": sub("doc", "Independent verification", "Verification"),
        "L0 gains a plan": sub("doc", "No plan, no agents, no suite. ", ""),
        "claude reference": sub("doc", "# Task Classification", "# Claude Task Classification"),
        "enforcement label removed": lambda d: {**d, "doc": d["doc"].replace("GUIDANCE", "advice")},
        "expectation id gap": sub("doc", "| CLS-3 |", "| CLS-9 |"),
        "wrong channel": sub("doc", "| CLS-1 | events, diff |", "| CLS-1 | vibes |"),
        "dangling contracts citation": sub("doc", "contracts §7", "contracts §9", 1),
        "agents pointer removed": lambda d: {**d, "agents": d["agents"].replace("task-classification.md", "x.md")},
        "agents formula": lambda d: {**d, "agents": d["agents"] + "\nScore = weighted score >= 5.\n"},
        "static row for an intent removed": lambda d: {**d, "verify": re.sub(r"^\| T\d+ \| Research \|.*\n", "", d["verify"], flags=re.M)},
        "static rows at L3 removed": lambda d: {**d, "verify": re.sub(r"^\| T\d+ \| [A-Za-z+ ]+ \| L3 \|.*\n", "", d["verify"], flags=re.M)},
        "override row not L3": sub("verify", first_static, re.sub(r"\| L[0-3] \| (yes|no) \|", "| L1 | yes |", first_static)),
        "unknown expectation in trace": sub("verify", first_static, first_static + "\n| T99 | Bug | L1 | no | x | y | CLS-77 |"),
        "run row removed": lambda d: {**d, "verify": re.sub(r"^\| R3 \|.*\n", "", d["verify"], flags=re.M)},
        "coverage gap": lambda d: {**d, "verify": re.sub(r"CLS-6,?\s*", "", d["verify"])},
        "not-verified section removed": sub("verify", "## Not verified", "## Other"),
    }


EXPECTED_ERR = {
    "intent removed": "lacks Reliability", "level removed": "lacks L2",
    "highest-level rule removed": "highest", "score formula added": "numeric scoring formula",
    "classifier service added": "numeric scoring formula", "mcp server added": "numeric scoring formula",
    "override word removed": "production-facing", "L3 controls removed": "L3 controls",
    "authorization rule removed": "L3 controls", "independent verification removed": "independent verification",
    "L0 gains a plan": "L0 row must say", "claude reference": "must not reference Claude",
    "enforcement label removed": "GUIDANCE", "expectation id gap": "CLS-1..CLS-n",
    "wrong channel": "Seen in", "dangling contracts citation": "§9",
    "agents pointer removed": "must point to", "agents formula": "AGENTS.md: numeric",
    "static row for an intent removed": "intent Research", "static rows at L3 removed": "at L3",
    "override row not L3": "must classify as L3", "unknown expectation in trace": "unknown expectation",
    "run row removed": "lacks R3", "coverage gap": "covered by no", "not-verified section removed": "Not verified",
}


def codex_prompt_check():
    codex = shutil.which("codex")
    if not codex:
        return ["codex not found on PATH"]
    out = subprocess.run([codex, "debug", "prompt-input", "hi"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", cwd=ROOT)
    if out.returncode != 0:
        return [f"codex debug prompt-input exit {out.returncode}: {out.stderr.strip()[:200]}"]
    return [f"model-visible prompt lacks {n!r}" for n in (".codex/knowledge/task-classification.md", "there is no score")
            if n not in out.stdout]


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    t = {"doc": DOC.read_text(encoding="utf-8"), "verify": VERIFY.read_text(encoding="utf-8"),
         "contracts": CONTRACTS.read_text(encoding="utf-8"), "agents": AGENTS.read_text(encoding="utf-8")}
    errs = run_all(t)
    if "--codex" in argv:
        errs += codex_prompt_check()
    for e in errs:
        print("FAIL:", e)
    if "--self-test" in argv:
        muts, missed = mutations(t), []
        for name, fn in muts.items():
            found = run_all(fn(t))
            want = EXPECTED_ERR.get(name)
            if not found or (want and not any(want in e for e in found)):
                missed.append(name)
        for n in missed:
            print("SELF-TEST FAIL: mutation not detected:", n)
        print(f"self-test: {len(muts) - len(missed)}/{len(muts)} mutations detected by the intended check")
        errs += missed
    print("PASS" if not errs else "FAILED")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
