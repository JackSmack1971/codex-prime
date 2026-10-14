"""Validate .codex/knowledge/contracts.md and its scenario verification (P1-S04, BLUEPRINT.md Part III).

Usage: python -I tools/control_plane/validate_contracts.py [--codex] [--self-test]
  (default)    static checks; exit 0 = pass, 1 = fail
  --codex      also render the model-visible prompt with `codex debug prompt-input` (no model session) and
               require the AGENTS.md contract pointers to be present
  --self-test  prove each check fails on a mutated input (negative controls)

What this proves: structure, enforcement labels, citations, scenario coverage, and that "not delivered"
claims match the repository. What it cannot prove: that a model obeys the contracts.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / ".codex" / "knowledge" / "contracts.md"
VERIFY = ROOT / ".codex" / "knowledge" / "contracts-verification.md"
MATRIX = ROOT / ".codex" / "knowledge" / "native-capabilities.md"
CFGVERIFY = ROOT / ".codex" / "knowledge" / "config-baseline-verification.md"
CONFIG = ROOT / ".codex" / "config.toml"
AGENTS = ROOT / "AGENTS.md"

SECTIONS = [  # (heading name, expectation prefix)
    ("Authority", "AUTH"), ("Task", "TASK"), ("Delegation", "DELEG"), ("Change", "CHG"),
    ("Execution", "EXEC"), ("Evidence", "EVID"), ("Completion", "COMP"),
]
CHANNELS = {"transcript", "diff", "events", "native"}
LABELS = {"GUIDANCE", "NATIVE", "NATIVE-PARTIAL"}
TASK_STATUSES = ["COMPLETE", "PARTIAL", "BLOCKED", "FAILED", "CANCELLED"]
AGENT_STATUSES = ["COMPLETE", "PARTIAL", "BLOCKED", "CONFLICTED", "UNVERIFIED"]
CLASSES = {"safe", "destructive", "ambiguous", "incomplete"}
# Wording that claims a guarantee Codex does not give.
OVERCLAIM = re.compile(
    r"\bguarantee[sd]?\b|\bensures?\b|cannot be bypassed|\bimpossible\b|always blocks|"
    r"\bfully enforced\b|\bcompletely prevents?\b|\bnever fails\b", re.I)
# "Not delivered" claims in contracts.md must match the repository: (path relative to ROOT, description).
NOT_DELIVERED = [(".codex/rules", "execution rules"), (".codex/hooks.json", "hooks"),
                 (".codex/agents", "custom agents")]
EXP_ROW = re.compile(r"^\| ([A-Z]+-\d+) \| ([^|]+?) \| (.+?) \|$", re.M)
SCEN_ROW = re.compile(r"^\| (S\d+) \| (\w+) \| (.+?) \| (.+?) \| (.+?) \| `?([A-Z]+)`? \|$", re.M)


def sections(text):
    """Map contract name -> body of its '## N. <Name> contract' section."""
    parts = re.split(r"^## (\d)\. (\w+) contract\s*$", text, flags=re.M)
    out, order = {}, []
    for i in range(1, len(parts), 3):
        out[parts[i + 1]] = parts[i + 2]
        order.append((int(parts[i]), parts[i + 1]))
    return out, order


def bullets(body):
    """Join wrapped bullet lines into single strings."""
    out, cur = [], None
    for line in body.splitlines():
        if line.startswith("- "):
            cur = [line]
            out.append(cur)
        elif cur is not None and line.startswith("  ") and line.strip():
            cur.append(line.strip())
        else:
            cur = None
    return [" ".join(b) for b in out]


def check_contracts(text, matrix, cfgverify, config, root_exists):
    errs = []
    secs, order = sections(text)
    want = [(i + 1, n) for i, (n, _) in enumerate(SECTIONS)]
    if order != want:
        errs.append(f"sections must be exactly {[n for _, n in want]} in order, found {[n for _, n in order]}")
    matrix_ids = {int(m) for m in re.findall(r"^### (\d+)\. ", matrix, re.M)}
    seen = set()
    for name, prefix in SECTIONS:
        body = secs.get(name)
        if body is None:
            continue
        for marker in ("**Rules**", "**Enforcement**", "**Expectations**"):
            if marker not in body:
                errs.append(f"{name}: missing {marker}")
        enf = body.split("**Enforcement**")[1].split("**Expectations**")[0] if "**Enforcement**" in body and "**Expectations**" in body else ""
        if not any(f"`{lab}`" in enf for lab in LABELS):
            errs.append(f"{name}: Enforcement states no label from {sorted(LABELS)}")
        for tok in re.findall(r"`(NATIVE[A-Z-]*|GUIDANCE)`", body):
            if tok not in LABELS:
                errs.append(f"{name}: unknown enforcement label `{tok}`")
        for b in bullets(enf):
            if re.search(r"`NATIVE(-PARTIAL)?`", b) and not re.search(r"\bNC\d+\b|\bV\d+\b", b):
                errs.append(f"{name}: NATIVE claim without NC<n>/V<n> citation: {b[:70]}...")
            for v in re.findall(r"\bV(\d+)\b", b):
                if f"| V{v} |" not in cfgverify:
                    errs.append(f"{name}: V{v} cited but config-baseline-verification.md has no row V{v}")
        exp_ids = []
        for m in EXP_ROW.finditer(body.split("**Expectations**")[-1]):
            eid, chans = m.group(1), {c.strip() for c in m.group(2).split(",")}
            if not eid.startswith(prefix + "-"):
                errs.append(f"{name}: expectation {eid} has wrong prefix (want {prefix}-)")
            if not chans or not chans <= CHANNELS:
                errs.append(f"{eid}: 'Seen in' must be a subset of {sorted(CHANNELS)}, got {sorted(chans)}")
            if len(m.group(3).strip()) < 25:
                errs.append(f"{eid}: expectation text too thin to observe")
            exp_ids.append(eid)
        if len(exp_ids) < 4:
            errs.append(f"{name}: needs at least 4 observable expectations, found {len(exp_ids)}")
        if exp_ids != [f"{prefix}-{i}" for i in range(1, len(exp_ids) + 1)]:
            errs.append(f"{name}: expectation ids must be {prefix}-1.. in order, got {exp_ids}")
        if seen & set(exp_ids):
            errs.append(f"{name}: duplicate expectation ids {sorted(seen & set(exp_ids))}")
        seen |= set(exp_ids)
    for n in {int(x) for x in re.findall(r"\bNC(\d+)\b", text)}:
        if n not in matrix_ids:
            errs.append(f"NC{n} cited but native-capabilities.md has no entry {n}")
    comp = secs.get("Completion", "")
    for s in TASK_STATUSES:
        if not re.search(rf"^\s*\| `{s}` \|", comp, re.M):
            errs.append(f"Completion: status `{s}` not defined in the outcomes table")
    deleg = secs.get("Delegation", "")
    for s in AGENT_STATUSES:
        if f"`{s}`" not in deleg:
            errs.append(f"Delegation: subagent status `{s}` missing")
    for field in ("Objective", "Scope", "Boundaries", "Evidence", "Output", "Completion"):
        if f"**{field}**" not in deleg:
            errs.append(f"Delegation: packet field **{field}** missing")
    if "clean final diff is not a clean working tree" not in secs.get("Change", ""):
        errs.append("Change: must state that a clean diff is not a clean working tree")
    for w in ("**Observation and assumption.**", "**Enforcement labels.**"):
        if w not in text:
            errs.append(f"missing preamble item {w}")
    for m in OVERCLAIM.finditer(text):
        errs.append(f"over-claim wording {m.group(0)!r}: state the condition and the gap instead")
    if re.search(r"claude", text, re.I):
        errs.append("contracts.md must not reference Claude (no builder dependency in the delivered system)")
    if re.search(r"^\[hooks", config, re.M) or re.search(r"^hooks\s*=", config, re.M):
        errs.append("config.toml defines hooks but contracts.md says hooks are not delivered: update the contracts and labels")
    if "any active layer" not in text:
        errs.append("contracts.md must state that rules from any active layer (including user rules) also apply")
    for rel, what in NOT_DELIVERED:
        if root_exists(rel):
            errs.append(f"{rel} exists but contracts.md says {what} are not delivered: update the contracts and labels")
    return errs


def check_agents(text):
    errs = []
    if "contracts.md" not in text:
        errs.append("AGENTS.md must point to .codex/knowledge/contracts.md")
    if "if the file exists" in text:
        errs.append("AGENTS.md still hedges the contracts pointer with 'if the file exists'")
    for name, _ in SECTIONS:
        if name.lower() not in text.lower():
            errs.append(f"AGENTS.md pointer does not name the {name.lower()} contract")
    if len(set(re.findall(r"§(\d)", text))) < 5:
        errs.append("AGENTS.md should carry contextual section pointers (§n) in the relevant sections")
    if len(text.encode()) > 8 * 1024:
        errs.append("AGENTS.md grew beyond 8 KiB: keep the root contract concise")
    if re.search(r"claude", text, re.I):
        errs.append("AGENTS.md must not reference Claude")
    return errs


def check_scenarios(vtext, contracts):
    errs, rows = [], SCEN_ROW.findall(vtext)
    secs, _ = sections(contracts)
    exp = {m.group(1) for b in secs.values() for m in EXP_ROW.finditer(b)}
    if len(rows) < 10:
        errs.append(f"need at least 10 scenarios, found {len(rows)}")
    classes = {r[1] for r in rows}
    for c in CLASSES - classes:
        errs.append(f"no scenario of class {c!r}")
    for c in classes - CLASSES:
        errs.append(f"unknown scenario class {c!r}")
    covered, statuses = set(), set()
    for sid, cls, req, ids, native, status in rows:
        refs = set(re.findall(r"[A-Z]+-\d+", ids))
        if not refs:
            errs.append(f"{sid}: no expectation ids")
        for r in refs - exp:
            errs.append(f"{sid}: unknown expectation {r}")
        covered |= refs
        if status not in TASK_STATUSES:
            errs.append(f"{sid}: status {status!r} is not one of {TASK_STATUSES}")
        statuses.add(status)
    for e in sorted(exp - covered):
        errs.append(f"expectation {e} is exercised by no scenario")
    for s in TASK_STATUSES:
        if s not in statuses:
            errs.append(f"no scenario ends in {s}")
    return errs


def run_all(t, root_exists):
    return (check_contracts(t["contracts"], t["matrix"], t["cfgverify"], t["config"], root_exists)
            + check_agents(t["agents"]) + check_scenarios(t["verify"], t["contracts"]))


def mutations(t):
    def sub(key, old, new, count=1):
        def f(d):
            assert old in d[key], (key, old)
            d = dict(d)
            d[key] = d[key].replace(old, new, count)
            return d
        return f
    drop_row = lambda eid: sub("contracts", re.search(rf"^\| {eid} \|.*\n", t["contracts"], re.M).group(0), "")
    scen_first = SCEN_ROW.search(t["verify"]).group(0)
    return {
        "section removed": sub("contracts", "## 5. Execution contract", "## 5. Something else"),
        "sections reordered": sub("contracts", "## 3. Delegation contract", "## 9. Delegation contract"),
        "rules marker removed": sub("contracts", "**Rules**", "**Steps**"),
        "enforcement labels removed": lambda d: {**d, "contracts": re.sub(r"`GUIDANCE`", "`advice`", d["contracts"])},
        "unknown label": sub("contracts", "`NATIVE-PARTIAL`. Under `workspace-write`", "`NATIVE-FULL`. Under `workspace-write`"),
        "native claim uncited": sub("contracts", "proxy (NC24), so injected", "proxy, so injected"),
        "citation to missing matrix entry": sub("contracts", "(NC23, interactive only", "(NC99, interactive only"),
        "expectation row dropped (below 4)": lambda d: drop_row("COMP-5")(drop_row("COMP-4")(drop_row("COMP-3")(d))),
        "wrong channel": sub("contracts", "| AUTH-1 | transcript |", "| AUTH-1 | vibes |"),
        "wrong id prefix": sub("contracts", "| TASK-1 |", "| TSK-1 |"),
        "id gap": sub("contracts", "| CHG-2 |", "| CHG-9 |"),
        "over-claim wording": sub("contracts", "Smallest coherent change", "The sandbox guarantees the smallest coherent change"),
        "completion status missing": sub("contracts", "| `CANCELLED` | The user stopped the work. |\n", ""),
        "subagent status missing": sub("contracts", "`CONFLICTED`", "`DISPUTED`", -1),
        "packet field missing": sub("contracts", "**Objective**,", "Objective,"),
        "clean-diff distinction removed": sub("contracts", "A clean final diff is not a clean working tree", "A clean diff is fine"),
        "claude reference": sub("contracts", "# Engineering Contracts", "# Claude Engineering Contracts"),
        "agents pointer removed": lambda d: {**d, "agents": d["agents"].replace("contracts.md", "x.md")},
        "agents hedge restored": sub("agents", "Pointers (read when relevant):", "Pointers (read when relevant, if the file exists):"),
        "agents section pointers removed": lambda d: {**d, "agents": re.sub(r"contracts §\d(, §\d)?", "", d["agents"])},
        "scenario unknown expectation": sub("verify", scen_first, scen_first.replace("TASK-2", "TASK-77", 1)),
        "scenario bad status": sub("verify", scen_first, re.sub(r"`?[A-Z]+`? \|$", "`DONE` |", scen_first)),
        "all scenarios of one class removed": lambda d: {**d, "verify": re.sub(r"^\| S\d+ \| destructive \|.*\n", "", d["verify"], flags=re.M)},
        "all CANCELLED scenarios removed": lambda d: {**d, "verify": re.sub(r"^\| S\d+ \|.*`CANCELLED` \|\n", "", d["verify"], flags=re.M)},
        "coverage gap": lambda d: {**d, "verify": re.sub(r"EXEC-4,?\s*", "", d["verify"])},
        "unknown V citation": sub("contracts", "`config-baseline-verification.md` V5", "`config-baseline-verification.md` V99"),
        "inline hooks table": lambda d: {**d, "config": d["config"] + "\n[hooks]\n"},
        "active-layer caveat removed": sub("contracts", "any active layer", "the project layer"),
    }


# Substring the intended check's message must contain (a mutation caught only by another check is a miss).
EXPECTED_ERR = {
    "section removed": "sections must be exactly", "sections reordered": "sections must be exactly",
    "rules marker removed": "missing **Rules**", "enforcement labels removed": "states no label",
    "unknown label": "unknown enforcement label", "native claim uncited": "without NC",
    "citation to missing matrix entry": "NC99", "expectation row dropped (below 4)": "at least 4",
    "wrong channel": "Seen in", "wrong id prefix": "wrong prefix", "id gap": "must be CHG-1",
    "over-claim wording": "over-claim", "completion status missing": "`CANCELLED` not defined",
    "subagent status missing": "`CONFLICTED` missing", "packet field missing": "**Objective** missing",
    "clean-diff distinction removed": "clean diff is not a clean", "claude reference": "must not reference Claude",
    "agents pointer removed": "must point to", "agents hedge restored": "if the file exists",
    "agents section pointers removed": "contextual section pointers",
    "scenario unknown expectation": "unknown expectation", "scenario bad status": "is not one of",
    "all scenarios of one class removed": "no scenario of class",
    "all CANCELLED scenarios removed": "no scenario ends in CANCELLED",
    "coverage gap": "exercised by no scenario",
    "unknown V citation": "V99 cited", "inline hooks table": "defines hooks",
    "active-layer caveat removed": "any active layer",
}


def codex_prompt_check():
    codex = shutil.which("codex")
    if not codex:
        return ["codex not found on PATH"]
    out = subprocess.run([codex, "debug", "prompt-input", "hi"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", cwd=ROOT)
    if out.returncode != 0:
        return [f"codex debug prompt-input exit {out.returncode}: {out.stderr.strip()[:200]}"]
    errs = []
    for needle in (".codex/knowledge/contracts.md", "the seven contracts", "contracts §7"):
        if needle not in out.stdout:
            errs.append(f"model-visible prompt lacks {needle!r}")
    return errs


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    t = {"contracts": CONTRACTS.read_text(encoding="utf-8"), "verify": VERIFY.read_text(encoding="utf-8"),
         "matrix": MATRIX.read_text(encoding="utf-8"), "agents": AGENTS.read_text(encoding="utf-8"),
         "cfgverify": CFGVERIFY.read_text(encoding="utf-8"), "config": CONFIG.read_text(encoding="utf-8")}
    exists = lambda rel: (ROOT / rel).exists()
    errs = run_all(t, exists)
    if "--codex" in argv:
        errs += codex_prompt_check()
    for e in errs:
        print("FAIL:", e)
    if "--self-test" in argv:
        muts, missed = mutations(t), []
        for name, fn in muts.items():
            found = run_all(fn(t), exists)
            want = EXPECTED_ERR.get(name)
            if not found or (want and not any(want in e for e in found)):
                missed.append(name)
        # Negative control for the repo-reality check: pretend a rules directory now exists.
        found = run_all(t, lambda rel: rel == ".codex/rules" or exists(rel))
        if not any("not delivered" in e for e in found):
            missed.append("rules dir appears")
        for n in missed:
            print("SELF-TEST FAIL: mutation not detected:", n)
        total = len(muts) + 1
        print(f"self-test: {total - len(missed)}/{total} mutations detected by the intended check")
        errs += missed
    print("PASS" if not errs else "FAILED")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
