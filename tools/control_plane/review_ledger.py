"""Deterministic review ledger: risk floors, verification evidence, findings, dedup, round cap, gate (P2-S04).

Usage (all state lives in .codex-runtime/review/<id>.json; nothing here calls a model):
  python -I tools/control_plane/review_ledger.py check-policy
  python -I tools/control_plane/review_ledger.py init ID [--base REF] [--suggest-tier T]
  python -I tools/control_plane/review_ledger.py evidence ID NAME [--record --command C --exit-code N | --not-run REASON] [--by WHO]
  python -I tools/control_plane/review_ledger.py round ID
  python -I tools/control_plane/review_ledger.py finding ID --role ROLE --json FILE
  python -I tools/control_plane/review_ledger.py dispose ID FINDING STATUS --role ROLE --by WHO --rationale TEXT [--check NAME]
  python -I tools/control_plane/review_ledger.py gate ID           # exit 0 only when the gate state is CHECKS_PASS
Exit: 0 ok / CHECKS_PASS; 1 gate not CHECKS_PASS; 2 refused, invalid input, or corrupt state (fail closed).

What this is. A LOCAL CONSISTENCY TOOL, not a security boundary. It keeps review facts in order around a review that something else
performs (a human, native /review, a reviewer session): evidence bound to a code state, findings, dedup, a round cap, risk floors.
It does not review code, call a model, run in CI, or authenticate anyone.
Human authorization is EXTERNAL and DEFERRED: there is no approval path here. `--role` and `--by` are strings the caller types, so
nothing in this file can tell a human from a model with shell access. CHECKS_PASS means the recorded automated conditions hold; it is
never an authorization to merge, push or deploy. A gate state of AWAITING_EXTERNAL_HUMAN means a person must decide elsewhere.
Other limits (see .codex/knowledge/review-ledger.md):
  * The ledger file is plain JSON under a writable directory. The per-finding hash detects accidental or partial edits, not a
    deliberate rewrite of the whole file.
  * The policy file lives under .codex/, a documented protected path in workspace-write; the code and ledger do not.
"""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".codex" / "review-policy.json"
TIERS = ("low", "medium", "high")
RANK = {t: i for i, t in enumerate(TIERS)}
ROLES = ("human", "model", "tool")
SEVERITIES = ("critical", "high", "medium", "low")
CLASSES = ("correctness", "regression", "security", "authorization", "data-loss", "reliability", "policy", "test-gap")
HARD_MAX_ROUNDS = 3
CLOSED = ("fixed", "false_positive", "accepted_risk")
POLICY_KEYS = {"schema_version", "max_auto_rounds", "default_tier", "path_rules", "file_count_floor", "required_evidence",
               "evidence_commands", "human_review", "material_severities"}


class PolicyError(Exception):
    """A rule was violated or input is unusable. Always fail closed."""


class RoundCapReached(PolicyError):
    pass


class LedgerCorrupt(PolicyError):
    pass


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# --- policy -----------------------------------------------------------------------------------------------------------
def validate_policy(p):
    errs = []
    if not isinstance(p, dict):
        return ["policy must be a JSON object"]
    for k in sorted(set(p) ^ POLICY_KEYS):
        errs.append(f"unknown or missing policy key {k!r}")
    if errs:
        return errs
    if p["schema_version"] != 1:
        errs.append("schema_version must be 1")
    m = p["max_auto_rounds"]
    if not (isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= HARD_MAX_ROUNDS):
        errs.append(f"max_auto_rounds must be an integer 1..{HARD_MAX_ROUNDS}")
    if p["default_tier"] not in TIERS:
        errs.append("default_tier must be low, medium or high")
    for i, r in enumerate(p["path_rules"] if isinstance(p["path_rules"], list) else []):
        if not (isinstance(r, dict) and set(r) == {"glob", "tier", "why"} and isinstance(r["glob"], str) and r["glob"]
                and r["tier"] in TIERS and isinstance(r["why"], str) and r["why"]):
            errs.append(f"path_rules[{i}] must be {{glob, tier, why}} with a valid tier")
    if not isinstance(p["path_rules"], list):
        errs.append("path_rules must be a list")
    f = p["file_count_floor"]
    if not (isinstance(f, dict) and set(f) == {"files", "tier"} and isinstance(f["files"], int) and f["files"] > 0 and f["tier"] in TIERS):
        errs.append("file_count_floor must be {files: positive int, tier}")
    ec = p["evidence_commands"]
    if not isinstance(ec, dict):
        errs.append("evidence_commands must be an object")
        ec = {}
    for name, cmds in ec.items():
        if cmds is not None and not (isinstance(cmds, list) and cmds and all(
                isinstance(c, list) and c and all(isinstance(a, str) and a for a in c) for c in cmds)):
            errs.append(f"evidence_commands[{name!r}] must be null (human-recorded) or a non-empty list of argv lists")
    re_ = p["required_evidence"]
    if not (isinstance(re_, dict) and set(re_) == set(TIERS)):
        errs.append("required_evidence must have exactly the keys low, medium, high")
    else:
        for t, names in re_.items():
            if not (isinstance(names, list) and names and all(isinstance(n, str) and n in ec for n in names)):
                errs.append(f"required_evidence[{t!r}] must be a non-empty list of names defined in evidence_commands")
        for lo, hi in (("low", "medium"), ("medium", "high")):
            if isinstance(re_.get(lo), list) and isinstance(re_.get(hi), list) and not set(re_[lo]) <= set(re_[hi]):
                errs.append(f"required_evidence[{hi!r}] must include everything required for {lo!r}")
    hr = p["human_review"]
    if not (isinstance(hr, dict) and set(hr) == set(TIERS) and all(v in ("required", "not_required") for v in hr.values())):
        errs.append("human_review must map each tier to required or not_required")
    elif hr["high"] != "required":
        errs.append("human_review for the high tier must be required (hard floor)")
    ms = p["material_severities"]
    if not (isinstance(ms, list) and {"critical", "high"} <= set(ms) <= set(SEVERITIES)):
        errs.append("material_severities must include critical and high and only known severities")
    return errs


def load_policy(path=POLICY_PATH):
    try:
        p = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise PolicyError(f"cannot load policy {path}: {e}")
    errs = validate_policy(p)
    if errs:
        raise PolicyError("invalid policy: " + "; ".join(errs))
    return p


# --- risk classification ----------------------------------------------------------------------------------------------
def glob_re(g):
    out, i = [], 0
    while i < len(g):
        if g.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif g.startswith("**", i):
            out.append(".*")
            i += 2
        elif g[i] == "*":
            out.append("[^/]*")
            i += 1
        elif g[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(g[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.I)


def norm_path(f):
    if not isinstance(f, str) or not f.strip():
        raise PolicyError("empty file path")
    s = f.replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    if s.startswith("/") or re.match(r"^[A-Za-z]:", s) or ".." in s.split("/"):
        raise PolicyError(f"path must be relative to the repository and stay inside it: {f!r}")
    return s


def classify(files, policy, suggested=None):
    """Tier = max over files of the highest matching path rule (default tier if none), raised by the file-count floor.
    A suggested tier can only raise the result; a lower suggestion is ignored and reported."""
    if not files:
        raise PolicyError("no changed files: nothing to classify (fail closed)")
    if suggested is not None and suggested not in TIERS:
        raise PolicyError(f"suggested tier must be one of {TIERS}")
    rules = [(glob_re(r["glob"]), r) for r in policy["path_rules"]]
    names = sorted({norm_path(x) for x in files})
    per_file = []
    for f in names:
        hits = [r for rx, r in rules if rx.match(f)]
        if hits:
            r = max(hits, key=lambda r: RANK[r["tier"]])
            per_file.append({"file": f, "tier": r["tier"], "rule": f"{r['glob']}: {r['why']}"})
        else:
            per_file.append({"file": f, "tier": policy["default_tier"], "rule": "default tier (no rule matched)"})
    floor = max((p["tier"] for p in per_file), key=RANK.get)
    cf = policy["file_count_floor"]
    if len(names) >= cf["files"] and RANK[cf["tier"]] > RANK[floor]:
        floor = cf["tier"]
    effective = suggested if suggested is not None and RANK[suggested] > RANK[floor] else floor
    return {"tier": effective, "floor": floor, "suggested": suggested,
            "downgrade_ignored": suggested is not None and RANK[suggested] < RANK[floor], "files": per_file}


# --- git (read-only) --------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def private_index(repo):
    """Environment that points git at a throwaway copy of the index.

    Commands that look read-only (`git diff`, `git status`) can refresh and rewrite .git/index even with --no-optional-locks
    (observed with git 2.53 for `git diff`). The copy absorbs that write so the user's index stays byte-identical."""
    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-path", "index"], capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise PolicyError(f"cannot locate the git index: {e}")
    if r.returncode != 0:
        raise PolicyError("not a git repository")
    real = Path(repo, r.stdout.decode().strip())
    fd, tmp = tempfile.mkstemp(suffix=".index")
    os.close(fd)
    try:
        if real.exists():
            shutil.copyfile(real, tmp)
        else:
            os.unlink(tmp)
        yield {**os.environ, "GIT_INDEX_FILE": tmp}
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def git(repo, *args):
    try:
        with private_index(repo) as env:
            r = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args], capture_output=True, env=env,
                               stdin=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise PolicyError(f"git {args[0]} failed to run: {e}")
    if r.returncode != 0:
        raise PolicyError(f"git {' '.join(args[:2])} exited {r.returncode}: {r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return r.stdout


def head_commit(repo):
    return git(repo, "rev-parse", "HEAD").decode().strip()


MAX_UNTRACKED_FILES = 2000
MAX_UNTRACKED_BYTES = 64 * 1024 * 1024


def untracked_digest(repo):
    """Digest of the path and CONTENT of every untracked, non-ignored file.
    Fails closed instead of guessing: too many or too large files, a symlink, a directory or nested repository, an unreadable file.
    Commit, ignore or remove such files before reviewing."""
    names = sorted(p for p in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p)
    if len(names) > MAX_UNTRACKED_FILES:
        raise PolicyError(f"{len(names)} untracked files (limit {MAX_UNTRACKED_FILES}): commit, ignore or remove them first")
    h, total = hashlib.sha256(), 0
    for raw in names:
        rel = raw.decode("utf-8", "replace")
        path = Path(repo, rel)
        try:
            if path.is_symlink():
                raise PolicyError(f"untracked symlink {rel!r}: its target can change or point outside the repository; commit, ignore or remove it")
            elif path.is_dir():
                raise PolicyError(f"untracked directory or nested repository {rel!r}: its contents cannot be bound to the state")
            else:
                total += path.stat().st_size
                if total > MAX_UNTRACKED_BYTES:
                    raise PolicyError(f"untracked files exceed {MAX_UNTRACKED_BYTES} bytes: commit, ignore or remove them first")
                d = hashlib.sha256()
                with open(path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        d.update(chunk)
                kind, digest = b"F", d.digest()
        except OSError as e:
            raise PolicyError(f"cannot read untracked file {rel!r}: {e}")
        h.update(kind + raw + b"\0" + digest)
    return h.digest()


def state_id(repo):
    """Identifies the exact code state: HEAD, `git status`, the tracked diff, and the path and content of untracked files.
    Ignored files are outside the state by definition. An edit to any covered file changes the id."""
    h = hashlib.sha256()
    for part in (git(repo, "rev-parse", "HEAD"), git(repo, "status", "--porcelain=v1", "-z"), git(repo, "diff", "HEAD", "--binary"),
                 untracked_digest(repo)):
        h.update(part)
        h.update(b"\0")
    return h.hexdigest()[:16]


def require_ignored_runtime(repo, rt):
    """The ledger directory must not change the state it describes: inside the repo it must be git-ignored."""
    try:
        rel = Path(rt).resolve().relative_to(Path(repo).resolve())
    except ValueError:
        return
    probe = (rel / "x.json").as_posix()
    try:
        r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", "--", probe], capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise PolicyError(f"cannot check whether the runtime directory is ignored: {e}")
    if r.returncode != 0:
        raise PolicyError(f"runtime directory {rel.as_posix()} is inside the repository but not git-ignored: "
                          "the ledger itself would change the code state and make every record stale")


def changed_files(repo, base):
    tracked = git(repo, "diff", "--name-only", "--no-renames", "-z", base).split(b"\0")
    other = git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    return sorted({p.decode("utf-8", "replace") for p in tracked + other if p})


def files_between(repo, a, b):
    return sorted(p.decode("utf-8", "replace") for p in git(repo, "diff", "--name-only", "--no-renames", "-z", a, b).split(b"\0") if p)


# --- ledger -----------------------------------------------------------------------------------------------------------
def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def finding_core(f):
    return {k: f[k] for k in ("id", "file", "line", "class", "severity", "summary", "evidence", "anchor_sha256", "provenance")}


def finding_id(file, cls, anchor):
    norm = re.sub(r"\s+", " ", anchor).strip()
    return hashlib.sha256(f"{norm_path(file)}\0{cls}\0{norm}".encode()).hexdigest()[:16]


def new_ledger(review_id, policy, files, head, state, now=None, suggested=None):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", review_id or ""):
        raise PolicyError("review id must match [A-Za-z0-9._-]{1,64}")
    return {"schema_version": 1, "review_id": review_id, "created_at": now or utcnow(), "head": head, "state_id": state,
            "risk": classify(files, policy, suggested), "rounds": [], "evidence": [], "findings": {}}


def verify(ledger):
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1:
        raise LedgerCorrupt("unsupported or malformed ledger")
    for fid, f in ledger["findings"].items():
        if f.get("core_sha256") != _sha(finding_core(f)) or fid != f["id"]:
            raise LedgerCorrupt(f"finding {fid} was modified after it was recorded")
    return ledger


def current_status(f):
    s = "open"
    for h in f["history"]:
        if h["status"] in ("open", "fixed", "false_positive", "accepted_risk", "proposed_false_positive", "escalated"):
            s = h["status"]
    return s


def is_material(f, policy):
    return f["severity"] in policy["material_severities"]


def unresolved_material(ledger, policy):
    return [f for f in ledger["findings"].values()
            if is_material(f, policy) and current_status(f) in ("open", "proposed_false_positive", "escalated")]


def _escalate(ledger, policy, now):
    for f in unresolved_material(ledger, policy):
        if current_status(f) != "escalated":
            f["history"].append({"status": "escalated", "role": "tool", "by": "round-cap", "at": now or utcnow(),
                                 "rationale": f"automatic round cap ({policy['max_auto_rounds']}) reached with the finding unresolved"})


def begin_round(ledger, policy, head, state, now=None):
    verify(ledger)
    if len(ledger["rounds"]) >= policy["max_auto_rounds"]:
        _escalate(ledger, policy, now)
        raise RoundCapReached(f"round cap reached ({policy['max_auto_rounds']}); unresolved material findings escalated to a human")
    ledger["rounds"].append({"n": len(ledger["rounds"]) + 1, "head": head, "state_id": state, "at": now or utcnow()})
    return ledger["rounds"][-1]["n"]


def add_evidence(ledger, name, source, results, state, now=None, not_run_reason=None):
    """results: list of {command, exit_code, output_sha256?, output_tail?}. source is 'tool' (the script ran it) or 'human'."""
    verify(ledger)
    if source not in ("tool", "human"):
        raise PolicyError("evidence must come from the tool or a human; model-reported results are not evidence")
    if not isinstance(name, str) or not name:
        raise PolicyError("evidence needs a name")
    if not_run_reason:
        entry = {"name": name, "source": source, "status": "not_run", "reason": not_run_reason, "results": [], "exit_code": None}
    else:
        if not results or not all(isinstance(r.get("exit_code"), int) and not isinstance(r.get("exit_code"), bool) and r.get("command")
                                  for r in results):
            raise PolicyError("evidence needs commands with integer exit codes, or an explicit not-run reason")
        bad = [r["exit_code"] for r in results if r["exit_code"] != 0]
        entry = {"name": name, "source": source, "status": "fail" if bad else "pass", "results": results,
                 "exit_code": bad[0] if bad else 0}
    entry.update({"state_id": state, "at": now or utcnow()})
    ledger["evidence"].append(entry)
    return entry["status"]


def evidence_status(ledger, name, state):
    """(ok, reason) for the latest entry with this name at the current state."""
    mine = [e for e in ledger["evidence"] if e["name"] == name]
    if not mine:
        return False, "not run (no evidence recorded)"
    e = mine[-1]
    if e["status"] == "not_run":
        return False, f"not run: {e.get('reason')}"
    if e["state_id"] != state:
        return False, "stale (recorded for a different code state)"
    if e["status"] != "pass":
        return False, f"failed (exit {e['exit_code']})"
    return True, "pass"


def add_finding(ledger, policy, raw, role, now=None):
    """Return ('added'|'duplicate'|'reopened', id). Raises PolicyError for unsupported or out-of-round findings."""
    verify(ledger)
    if role not in ROLES:
        raise PolicyError(f"role must be one of {ROLES}")
    if not ledger["rounds"]:
        raise PolicyError("no active round: begin a round before recording findings")
    rnd = ledger["rounds"][-1]["n"]
    try:
        file, line, cls, sev = norm_path(raw["file"]), raw["line"], raw["class"], raw["severity"]
        summary, evidence, anchor, reviewer = raw["summary"], raw["evidence"], raw["anchor"], raw["reviewer"]
    except KeyError as e:
        raise PolicyError(f"finding is missing field {e}")
    if not (isinstance(line, int) and not isinstance(line, bool) and line >= 1):
        raise PolicyError("line must be a positive integer (findings need file and line evidence)")
    if cls not in CLASSES or sev not in SEVERITIES:
        raise PolicyError(f"class must be one of {CLASSES} and severity one of {SEVERITIES}")
    for k, v, lo, hi in (("summary", summary, 1, 300), ("evidence", evidence, 10, 2000), ("anchor", anchor, 1, 500),
                         ("reviewer", reviewer, 1, 100)):
        if not (isinstance(v, str) and lo <= len(v.strip()) and len(v) <= hi):
            raise PolicyError(f"{k} must be a string of {lo}..{hi} characters (unsupported findings are rejected)")
    fid = finding_id(file, cls, anchor)
    existing = ledger["findings"].get(fid)
    if existing:
        if rnd not in existing["seen_rounds"]:
            existing["seen_rounds"].append(rnd)
        if current_status(existing) == "fixed":
            existing["history"].append({"status": "open", "role": role, "by": reviewer, "at": now or utcnow(),
                                        "rationale": "re-reported after being marked fixed: " + evidence[:200]})
            return "reopened", fid
        return "duplicate", fid
    f = {"id": fid, "file": file, "line": line, "class": cls, "severity": sev, "summary": summary.strip(), "evidence": evidence.strip(),
         "anchor_sha256": hashlib.sha256(re.sub(r"\s+", " ", anchor).strip().encode()).hexdigest(),
         "provenance": {"source": role, "reviewer": reviewer.strip(), "round": rnd, "recorded_at": now or utcnow()}}
    f["core_sha256"] = _sha(finding_core(f))
    f["seen_rounds"] = [rnd]
    f["history"] = []
    ledger["findings"][fid] = f
    return "added", fid


def disposition(ledger, policy, fid, status, role, by, rationale, state, check=None, now=None):
    verify(ledger)
    f = ledger["findings"].get(fid)
    if not f:
        raise PolicyError(f"unknown finding {fid}")
    if role not in ROLES or not (isinstance(by, str) and by.strip()):
        raise PolicyError("a disposition needs a role and an author")
    if not (isinstance(rationale, str) and len(rationale.strip()) >= 10):
        raise PolicyError("a disposition needs a rationale of at least 10 characters")
    if status not in CLOSED + ("proposed_false_positive", "open"):
        raise PolicyError(f"status {status!r} cannot be set by a caller")
    cur, material = current_status(f), is_material(f, policy)
    if cur == "escalated" and role != "human":
        raise PolicyError("finding is escalated: only a human can disposition it")
    if cur in CLOSED and status != "open":
        raise PolicyError(f"finding is {cur}; reopen it first (the record is never overwritten)")
    if status == "open" and cur not in CLOSED + ("proposed_false_positive",):
        raise PolicyError("only a closed or proposed-false-positive finding can be reopened")
    if status in ("false_positive", "accepted_risk") and material and role != "human":
        raise PolicyError(f"only a human can mark a material finding {status}; a model may use proposed_false_positive")
    if status == "fixed" and material:
        if role == "model":
            raise PolicyError("a model cannot close a material finding; a tool or human must cite passing evidence")
        ok, why = evidence_status(ledger, check, state) if check else (False, "no check named")
        if not ok:
            raise PolicyError(f"fixed needs a passing check at the current state: {check!r} is {why}")
    f["history"].append({"status": status, "role": role, "by": by.strip(), "at": now or utcnow(), "rationale": rationale.strip(),
                         **({"check": check} if check else {})})
    return current_status(f)


def unauthenticated_closures(ledger, policy):
    """Material findings recorded as false_positive or accepted_risk. Only a declared 'human' can set these, but the ledger cannot
    authenticate that declaration, so they are listed for an external human to confirm and never clear the gate by themselves."""
    out = []
    for f in ledger["findings"].values():
        st = current_status(f)
        if is_material(f, policy) and st in ("false_positive", "accepted_risk"):
            h = [x for x in f["history"] if x["status"] == st][-1]
            out.append({"id": f["id"], "status": st, "declared_by": h["by"], "declared_role": h["role"], "at": h["at"]})
    return out


def gate(ledger, policy, state):
    verify(ledger)
    tier = ledger["risk"]["tier"]
    blockers = []
    for name in policy["required_evidence"][tier]:
        ok, why = evidence_status(ledger, name, state)
        if not ok:
            blockers.append({"check": name, "reason": why})
    unresolved = unresolved_material(ledger, policy)
    capped = len(ledger["rounds"]) >= policy["max_auto_rounds"]
    needs_human = policy["human_review"][tier] == "required"
    claims = unauthenticated_closures(ledger, policy)
    latest = {}
    for e in ledger["evidence"]:
        latest[e["name"]] = e
    attested = sorted(n for n, e in latest.items() if e["source"] == "human")
    if unresolved and capped:
        verdict = "ESCALATED"
    elif blockers:
        verdict = "BLOCKED_EVIDENCE"
    elif unresolved:
        verdict = "BLOCKED_FINDINGS"
    elif needs_human or claims:
        verdict = "AWAITING_EXTERNAL_HUMAN"
    else:
        verdict = "CHECKS_PASS"
    return {"state": verdict, "tier": tier, "rounds": len(ledger["rounds"]), "max_rounds": policy["max_auto_rounds"],
            "missing_or_failed_evidence": blockers,
            "unresolved_material": [{"id": f["id"], "file": f["file"], "line": f["line"], "severity": f["severity"],
                                     "status": current_status(f)} for f in unresolved],
            "human_authorization": "external_deferred",
            "human_review_required_by_policy": needs_human,
            "unauthenticated_human_dispositions": claims,
            "unauthenticated_evidence": attested,
            "note": "local consistency check, not a security boundary: findings are reports; roles and attested evidence are typed by the "
                    "caller; CHECKS_PASS is not an authorization"}


def rereview_scope(repo, ledger):
    """Files for a diff-only re-review: changed since the previous round's head, plus files with unresolved findings."""
    if not ledger["rounds"]:
        raise PolicyError("no previous round")
    prev, cur = ledger["rounds"][-1]["head"], head_commit(repo)
    files = set(files_between(repo, prev, cur)) if prev != cur else set()
    files |= {f["file"] for f in ledger["findings"].values() if current_status(f) in ("open", "proposed_false_positive", "escalated")}
    return sorted(files)


# --- persistence ------------------------------------------------------------------------------------------------------
def ledger_path(runtime_dir, review_id):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", review_id):
        raise PolicyError("invalid review id")
    return Path(runtime_dir) / f"{review_id}.json"


def save(ledger, runtime_dir):
    p = ledger_path(runtime_dir, ledger["review_id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(ledger, fh, indent=2, sort_keys=True)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(runtime_dir, review_id):
    p = ledger_path(runtime_dir, review_id)
    try:
        return verify(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise LedgerCorrupt(f"cannot read ledger {p}: {e}")


# --- evidence execution (policy-defined commands only) ----------------------------------------------------------------
def run_policy_evidence(repo, policy, name, timeout=900):
    cmds = policy["evidence_commands"].get(name)
    if cmds is None:
        raise PolicyError(f"{name!r} has no policy command: record it as human evidence with --record")
    results = []
    with private_index(repo) as env:
        for argv in cmds:
            try:
                r = subprocess.run(argv, cwd=str(repo), capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout, env=env)
                out, code = r.stdout + r.stderr, r.returncode
            except subprocess.TimeoutExpired:
                out, code = b"timeout", 124
            except OSError as e:
                out, code = str(e).encode(), 127
            results.append({"command": " ".join(argv), "exit_code": code, "output_sha256": hashlib.sha256(out).hexdigest(),
                            "output_tail": out.decode("utf-8", "replace")[-400:]})
    return results


# --- CLI --------------------------------------------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser(prog="review_ledger", add_help=True)
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--policy", default=str(POLICY_PATH))
    ap.add_argument("--runtime-dir", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-policy")
    p = sub.add_parser("init"); p.add_argument("id"); p.add_argument("--base", default="origin/main"); p.add_argument("--suggest-tier")
    p = sub.add_parser("evidence"); p.add_argument("id"); p.add_argument("name"); p.add_argument("--record", action="store_true")
    p.add_argument("--command"); p.add_argument("--exit-code", type=int); p.add_argument("--not-run"); p.add_argument("--by", default="operator")
    p = sub.add_parser("round"); p.add_argument("id")
    p = sub.add_parser("finding"); p.add_argument("id"); p.add_argument("--role", required=True); p.add_argument("--json", required=True)
    p = sub.add_parser("dispose"); p.add_argument("id"); p.add_argument("finding"); p.add_argument("status")
    p.add_argument("--role", required=True); p.add_argument("--by", required=True); p.add_argument("--rationale", required=True); p.add_argument("--check")
    p = sub.add_parser("gate"); p.add_argument("id")
    a = ap.parse_args(argv)
    repo = Path(a.repo)
    rt = Path(a.runtime_dir) if a.runtime_dir else repo / ".codex-runtime" / "review"
    try:
        policy = load_policy(a.policy)
        if a.cmd == "check-policy":
            print("PASS: policy valid")
            return 0
        require_ignored_runtime(repo, rt)
        if a.cmd == "init":
            if ledger_path(rt, a.id).exists():
                raise PolicyError("a ledger with this id already exists; it is never overwritten")
            led = new_ledger(a.id, policy, changed_files(repo, a.base), head_commit(repo), state_id(repo), suggested=a.suggest_tier)
            save(led, rt)
            print(json.dumps({"risk": led["risk"]["tier"], "floor": led["risk"]["floor"],
                              "downgrade_ignored": led["risk"]["downgrade_ignored"], "files": len(led["risk"]["files"])}))
            return 0
        led = load(rt, a.id)
        state = state_id(repo)
        out = None
        if a.cmd == "evidence":
            if a.record:
                if a.not_run:
                    add_evidence(led, a.name, "human", [], state, not_run_reason=a.not_run)
                else:
                    add_evidence(led, a.name, "human", [{"command": a.command, "exit_code": a.exit_code}], state)
            else:
                add_evidence(led, a.name, "tool", run_policy_evidence(repo, policy, a.name), state)
            out = evidence_status(led, a.name, state)[1]
        elif a.cmd == "round":
            try:
                out = f"round {begin_round(led, policy, head_commit(repo), state)}"
            except RoundCapReached as e:
                save(led, rt)  # persist the escalation records
                print(f"REFUSED: {e}")
                return 2
        elif a.cmd == "finding":
            raw = json.loads(Path(a.json).read_text(encoding="utf-8"))
            out = add_finding(led, policy, raw, a.role)
        elif a.cmd == "dispose":
            out = disposition(led, policy, a.finding, a.status, a.role, a.by, a.rationale, state, a.check)
        elif a.cmd == "gate":
            g = gate(led, policy, state)
            print(json.dumps(g, indent=2))
            return 0 if g["state"] == "CHECKS_PASS" else 1
        save(led, rt)
        print(out)
        return 0
    except (PolicyError, json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print(f"REFUSED: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
