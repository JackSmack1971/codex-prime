"""Fixture tests for review_ledger.py (P2-S04). Run: python -I tools/control_plane/test_review_ledger.py

These test a local consistency tool (not a security boundary) with synthetic findings. They do not run Codex, a reviewer, or a model, and so say nothing
about live reviewer behavior.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_ledger as rl  # noqa: E402

POLICY = rl.load_policy()
S1, S2 = "state-aaaa", "state-bbbb"
T = "2026-10-31T00:00:00+00:00"


def finding(file="src/app.py", line=10, anchor="x = eval(user)", cls="security", sev="high", **kw):
    f = {"file": file, "line": line, "class": cls, "severity": sev, "summary": "eval on user input",
         "evidence": "src/app.py:10 passes request data to eval()", "anchor": anchor, "reviewer": "reviewer-1"}
    f.update(kw)
    return f


def ledger(files=("docs/a.md",), suggested=None):
    return rl.new_ledger("r1", POLICY, list(files), "head1", S1, now=T, suggested=suggested)


def passing(led, names, state=S1):
    for n in names:
        rl.add_evidence(led, POLICY, n, "tool", [{"command": n, "exit_code": 0}], state, now=T)


class Classification(unittest.TestCase):
    def test_floor_cannot_be_downgraded_by_suggestion(self):
        r = rl.classify([".codex/config.toml"], POLICY, suggested="low")
        self.assertEqual((r["tier"], r["floor"], r["downgrade_ignored"]), ("high", "high", True))

    def test_suggestion_can_raise(self):
        r = rl.classify(["docs/a.md"], POLICY, suggested="high")
        self.assertEqual((r["floor"], r["tier"], r["downgrade_ignored"]), ("low", "high", False))

    def test_mixed_change_takes_highest_file_tier(self):
        self.assertEqual(rl.classify(["docs/a.md", "tools/control_plane/x.py"], POLICY)["tier"], "high")

    def test_docs_only_is_low_and_unmatched_is_default(self):
        self.assertEqual(rl.classify(["docs/a.md"], POLICY)["tier"], "low")
        self.assertEqual(rl.classify(["src/app.py"], POLICY)["tier"], "medium")

    def test_case_insensitive_and_backslash_paths(self):
        self.assertEqual(rl.classify([".CODEX\\Rules\\x.md"], POLICY)["tier"], "high")
        self.assertEqual(rl.classify(["SRC/Auth/login.py"], POLICY)["tier"], "high")

    def test_many_files_raise_floor(self):
        self.assertEqual(rl.classify([f"docs/{i}.md" for i in range(15)], POLICY)["tier"], "medium")

    def test_bad_paths_and_empty_fail_closed(self):
        for bad in (["../x"], ["/etc/passwd"], ["C:/x"], [""]):
            with self.assertRaises(rl.PolicyError):
                rl.classify(bad, POLICY)
        with self.assertRaises(rl.PolicyError):
            rl.classify([], POLICY)
        with self.assertRaises(rl.PolicyError):
            rl.classify(["a.md"], POLICY, suggested="critical")

    def test_policy_rejects_weakening(self):
        for mutate in (lambda p: p.update(max_auto_rounds=4), lambda p: p.update(max_auto_rounds=0),
                       lambda p: p["human_review"].update(high="not_required"),
                       lambda p: p.update(material_severities=["medium"]), lambda p: p.update(extra=1),
                       lambda p: p["required_evidence"].update(high=["diff_check"]),
                       lambda p: p["required_evidence"].update(low=["nonexistent"])):
            p = copy.deepcopy(POLICY)
            mutate(p)
            self.assertTrue(rl.validate_policy(p), "weakened policy was accepted")
        self.assertEqual(rl.validate_policy(POLICY), [])


class Evidence(unittest.TestCase):
    def test_clean_review_with_valid_evidence_passes(self):
        led = ledger()
        rl.begin_round(led, POLICY, "head1", S1, now=T)
        passing(led, ["diff_check"])
        g = rl.gate(led, POLICY, S1)
        self.assertEqual((g["state"], g["tier"]), ("CHECKS_PASS", "low"))

    def test_medium_tier_with_all_checks_still_awaits_an_external_human(self):
        led = ledger(["src/app.py"])
        passing(led, ["diff_check", "focused_check"])
        g = rl.gate(led, POLICY, S1)
        self.assertEqual(g["state"], "AWAITING_EXTERNAL_HUMAN")
        self.assertEqual((g["human_authorization"], g["human_review_required_by_policy"]), ("external_deferred", True))
        self.assertEqual(rl.gate(led, POLICY, S2)["state"], "BLOCKED_EVIDENCE")  # new code needs new evidence

    def test_no_approval_path_exists_and_only_low_tier_can_pass(self):
        # roles and flags are typed by the caller, so nothing here can authenticate a human: there is no approval to record
        self.assertFalse(hasattr(rl, "approve"))
        self.assertNotIn("approvals", ledger())
        for files in (["src/app.py"], [".codex/config.toml"], ["tools/control_plane/x.py"]):
            led = ledger(files)
            passing(led, ["diff_check", "focused_check", "static_validators"])
            self.assertEqual(rl.gate(led, POLICY, S1)["state"], "AWAITING_EXTERNAL_HUMAN", files)

    def test_human_attested_evidence_is_flagged_not_trusted_silently(self):
        led = ledger(["src/app.py"])
        passing(led, ["diff_check"])
        rl.add_evidence(led, POLICY, "focused_check", "human", [{"command": "ran the module by hand", "exit_code": 0}], S1, now=T, by="jack")
        g = rl.gate(led, POLICY, S1)
        self.assertEqual(g["unauthenticated_evidence"],
                         [{"check": "focused_check", "recorded_by": "jack", "recorded_by_authenticated": False, "status": "pass"}])
        self.assertEqual(g["missing_or_failed_evidence"], [])
        self.assertEqual(led["evidence"][-1]["by"], "jack")
        self.assertIs(led["evidence"][-1]["by_authenticated"], False)

    def test_human_evidence_needs_a_name(self):
        led = ledger(["src/app.py"])
        for by in (None, "", "  "):
            with self.assertRaises(rl.PolicyError):
                rl.add_evidence(led, POLICY, "focused_check", "human", [{"command": "x", "exit_code": 0}], S1, by=by)

    def test_human_cannot_satisfy_a_check_that_has_policy_commands(self):
        # recording a passing diff_check without running it must not reach CHECKS_PASS on a low-tier change
        led = ledger()
        with self.assertRaises(rl.PolicyError):
            rl.add_evidence(led, POLICY, "diff_check", "human", [{"command": "git diff --check", "exit_code": 0}], S1, now=T, by="jack")
        self.assertEqual(led["evidence"], [])
        g = rl.gate(led, POLICY, S1)
        self.assertEqual((g["state"], g["tier"]), ("BLOCKED_EVIDENCE", "low"))
        # a hand-edited ledger that carries such an entry is also rejected by the gate
        led["evidence"].append({"name": "diff_check", "source": "human", "status": "pass", "results": [], "exit_code": 0,
                                "state_id": S1, "at": T, "by": "jack", "by_authenticated": False})
        g = rl.gate(led, POLICY, S1)
        self.assertEqual(g["state"], "BLOCKED_EVIDENCE")
        self.assertIn("policy-defined commands", g["missing_or_failed_evidence"][0]["reason"])
        # ... and it cannot back a 'fixed' disposition either
        led2 = ledger(["src/app.py"])
        rl.begin_round(led2, POLICY, "head1", S1, now=T)
        rl.add_finding(led2, POLICY, finding(), "model", now=T)
        fid = next(iter(led2["findings"]))
        led2["evidence"].append(dict(led["evidence"][-1]))
        with self.assertRaises(rl.PolicyError):
            rl.disposition(led2, POLICY, fid, "fixed", "human", "jack", "fixed it, honest", S1, check="diff_check", now=T)

    def test_human_not_run_is_allowed_and_blocks(self):
        led = ledger()
        rl.add_evidence(led, POLICY, "diff_check", "human", [], S1, now=T, not_run_reason="no git here", by="jack")
        self.assertEqual(rl.gate(led, POLICY, S1)["state"], "BLOCKED_EVIDENCE")

    def test_unknown_evidence_name_refused(self):
        with self.assertRaises(rl.PolicyError):
            rl.add_evidence(ledger(), POLICY, "made_up", "tool", [{"command": "x", "exit_code": 0}], S1)

    def test_missing_evidence_fails_closed(self):
        led = ledger(["tools/control_plane/x.py"])  # high: needs three checks
        g = rl.gate(led, POLICY, S1)
        self.assertEqual(g["state"], "BLOCKED_EVIDENCE")
        self.assertEqual({b["check"] for b in g["missing_or_failed_evidence"]}, {"diff_check", "focused_check", "static_validators"})
        passing(led, ["diff_check", "focused_check"])
        self.assertEqual(rl.gate(led, POLICY, S1)["missing_or_failed_evidence"][0]["check"], "static_validators")

    def test_not_run_stale_and_failed_evidence_block(self):
        led = ledger()
        rl.add_evidence(led, POLICY, "diff_check", "human", [], S1, now=T, not_run_reason="no git here", by="jack")
        self.assertIn("not run", rl.gate(led, POLICY, S1)["missing_or_failed_evidence"][0]["reason"])
        passing(led, ["diff_check"], S2)
        self.assertIn("stale", rl.gate(led, POLICY, S1)["missing_or_failed_evidence"][0]["reason"])
        rl.add_evidence(led, POLICY, "diff_check", "tool", [{"command": "git diff --check", "exit_code": 2}], S1, now=T)
        g = rl.gate(led, POLICY, S1)
        self.assertEqual(g["state"], "BLOCKED_EVIDENCE")
        self.assertIn("failed (exit 2)", g["missing_or_failed_evidence"][0]["reason"])

    def test_model_reported_evidence_refused(self):
        led = ledger()
        with self.assertRaises(rl.PolicyError):
            rl.add_evidence(led, POLICY, "diff_check", "model", [{"command": "x", "exit_code": 0}], S1)
        with self.assertRaises(rl.PolicyError):
            rl.add_evidence(led, POLICY, "diff_check", "tool", [{"command": "x", "exit_code": True}], S1)  # bool is not an exit code
        with self.assertRaises(rl.PolicyError):
            rl.add_evidence(led, POLICY, "diff_check", "tool", [], S1)


class Findings(unittest.TestCase):
    def setUp(self):
        self.led = ledger(["src/app.py"])
        passing(self.led, ["diff_check", "focused_check"])
        rl.begin_round(self.led, POLICY, "head1", S1, now=T)

    def test_confirmed_regression_blocks_progression(self):
        outcome, fid = rl.add_finding(self.led, POLICY, finding(), "model", now=T)
        self.assertEqual(outcome, "added")
        g = rl.gate(self.led, POLICY, S1)
        self.assertEqual(g["state"], "BLOCKED_FINDINGS")
        self.assertEqual(g["unresolved_material"][0]["id"], fid)
        # fixing it requires a passing check at the current state, from a tool or a human
        with self.assertRaises(rl.PolicyError):
            rl.disposition(self.led, POLICY, fid, "fixed", "tool", "ci", "patched the eval call", S1, check=None)
        with self.assertRaises(rl.PolicyError):
            rl.disposition(self.led, POLICY, fid, "fixed", "model", "agent", "patched the eval call", S1, check="diff_check")
        rl.disposition(self.led, POLICY, fid, "fixed", "tool", "ci", "patched the eval call", S1, check="diff_check")
        self.assertEqual(rl.gate(self.led, POLICY, S1)["state"], "AWAITING_EXTERNAL_HUMAN")  # medium tier: a person decides elsewhere
        # the same bug found again after the fix reopens it and blocks again
        rl.begin_round(self.led, POLICY, "head2", S1, now=T)
        outcome, _ = rl.add_finding(self.led, POLICY, finding(line=44), "model", now=T)
        self.assertEqual(outcome, "reopened")
        self.assertEqual(rl.gate(self.led, POLICY, S1)["state"], "BLOCKED_FINDINGS")

    def test_false_positive_preserves_the_record(self):
        _, fid = rl.add_finding(self.led, POLICY, finding(), "model", now=T)
        before = copy.deepcopy(rl.finding_core(self.led["findings"][fid]))
        with self.assertRaises(rl.PolicyError):  # a model cannot close a material finding
            rl.disposition(self.led, POLICY, fid, "false_positive", "model", "agent-1", "looks like test code", S1)
        rl.disposition(self.led, POLICY, fid, "proposed_false_positive", "model", "agent-1", "looks like test code only", S1, now=T)
        self.assertEqual(rl.gate(self.led, POLICY, S1)["state"], "BLOCKED_FINDINGS")  # still blocking
        rl.disposition(self.led, POLICY, fid, "false_positive", "human", "jack", "input is a hardcoded constant here", S1, now=T)
        f = self.led["findings"][fid]
        self.assertEqual(rl.finding_core(f), before)
        rl.verify(self.led)
        self.assertEqual(rl.current_status(f), "false_positive")
        self.assertEqual([(h["status"], h["role"], h["by"]) for h in f["history"]],
                         [("proposed_false_positive", "model", "agent-1"), ("false_positive", "human", "jack")])
        self.assertTrue(all(h["at"] and h["rationale"] for h in f["history"]))
        self.assertEqual(f["provenance"]["reviewer"], "reviewer-1")
        g = rl.gate(self.led, POLICY, S1)
        self.assertEqual(g["state"], "AWAITING_EXTERNAL_HUMAN")
        self.assertEqual([(c["id"], c["declared_by"], c["declared_role"]) for c in g["unauthenticated_human_dispositions"]],
                         [(fid, "jack", "human")])

    def test_a_declared_human_cannot_clear_a_material_finding_even_on_a_low_tier_change(self):
        led = ledger(["docs/a.md"])  # low tier: no human review required by policy
        passing(led, ["diff_check"])
        rl.begin_round(led, POLICY, "head1", S1, now=T)
        _, fid = rl.add_finding(led, POLICY, finding(file="docs/a.md", anchor="run this"), "model", now=T)
        rl.disposition(led, POLICY, fid, "false_positive", "human", "anyone", "typed by whoever calls the tool", S1, now=T)
        g = rl.gate(led, POLICY, S1)
        self.assertEqual(g["state"], "AWAITING_EXTERNAL_HUMAN")
        self.assertNotEqual(g["state"], "CHECKS_PASS")
        self.assertEqual(g["unauthenticated_human_dispositions"][0]["id"], fid)

    def test_tampering_with_a_recorded_finding_is_detected(self):
        _, fid = rl.add_finding(self.led, POLICY, finding(), "model", now=T)
        self.led["findings"][fid]["severity"] = "low"
        with self.assertRaises(rl.LedgerCorrupt):
            rl.gate(self.led, POLICY, S1)

    def test_duplicate_is_not_reissued_and_keeps_its_disposition(self):
        _, fid = rl.add_finding(self.led, POLICY, finding(), "model", now=T)
        rl.disposition(self.led, POLICY, fid, "false_positive", "human", "jack", "input is a hardcoded constant here", S1, now=T)
        rl.begin_round(self.led, POLICY, "head2", S1, now=T)
        again = finding(line=99, anchor="  x  =   eval(user)  ", summary="eval of user input (reworded)")
        outcome, fid2 = rl.add_finding(self.led, POLICY, again, "model", now=T)
        self.assertEqual((outcome, fid2), ("duplicate", fid))
        self.assertEqual(len(self.led["findings"]), 1)
        f = self.led["findings"][fid]
        self.assertEqual(f["seen_rounds"], [1, 2])
        self.assertEqual(rl.current_status(f), "false_positive")
        self.assertEqual(f["line"], 10)  # the original record is unchanged
        # a different anchor in the same file is a different finding
        self.assertEqual(rl.add_finding(self.led, POLICY, finding(anchor="os.system(cmd)"), "model", now=T)[0], "added")

    def test_unsupported_findings_are_rejected(self):
        for bad in (finding(line=0), finding(evidence="guess"), finding(cls="style"), finding(sev="blocker"),
                    finding(file="../x"), {k: v for k, v in finding().items() if k != "anchor"}):
            with self.assertRaises(rl.PolicyError):
                rl.add_finding(self.led, POLICY, bad, "model", now=T)
        with self.assertRaises(rl.PolicyError):
            rl.add_finding(ledger(), POLICY, finding(), "model")  # no round begun

    def test_low_severity_is_recorded_but_does_not_block(self):
        rl.add_finding(self.led, POLICY, finding(sev="low", anchor="# todo"), "model", now=T)
        g = rl.gate(self.led, POLICY, S1)
        self.assertEqual(g["unresolved_material"], [])
        self.assertEqual(g["state"], "AWAITING_EXTERNAL_HUMAN")  # not blocked by the nit; the medium tier still needs a person


class RoundCap(unittest.TestCase):
    def test_three_rounds_then_escalate(self):
        led = ledger(["src/app.py"])
        passing(led, ["diff_check", "focused_check"])
        for i in range(3):
            self.assertEqual(rl.begin_round(led, POLICY, f"head{i}", S1, now=T), i + 1)
        _, fid = rl.add_finding(led, POLICY, finding(), "model", now=T)
        _, low = rl.add_finding(led, POLICY, finding(sev="low", anchor="# nit"), "model", now=T)
        self.assertEqual(rl.gate(led, POLICY, S1)["state"], "ESCALATED")  # cap + unresolved: no fourth round
        with self.assertRaises(rl.RoundCapReached):
            rl.begin_round(led, POLICY, "head4", S1, now=T)
        self.assertEqual(len(led["rounds"]), 3)
        f = led["findings"][fid]
        self.assertEqual(rl.current_status(f), "escalated")
        self.assertEqual(f["history"][-1]["by"], "round-cap")
        self.assertEqual(rl.current_status(led["findings"][low]), "open")  # non-material findings are not escalated
        for role in ("model", "tool"):
            with self.assertRaises(rl.PolicyError):
                rl.disposition(led, POLICY, fid, "proposed_false_positive", role, "x", "automatic attempt to clear it", S1)
        with self.assertRaises(rl.RoundCapReached):  # escalation is idempotent
            rl.begin_round(led, POLICY, "head5", S1, now=T)
        self.assertEqual(sum(h["status"] == "escalated" for h in f["history"]), 1)
        rl.disposition(led, POLICY, fid, "accepted_risk", "human", "jack", "accepted: constant input, tracked in the backlog", S1, now=T)
        g = rl.gate(led, POLICY, S1)
        self.assertEqual(g["state"], "AWAITING_EXTERNAL_HUMAN")  # recorded, but unauthenticated: an external human must confirm
        self.assertEqual(g["unauthenticated_human_dispositions"][0]["status"], "accepted_risk")

    def test_cap_reached_without_findings_is_not_an_escalation(self):
        led = ledger()
        passing(led, ["diff_check"])
        for i in range(3):
            rl.begin_round(led, POLICY, f"h{i}", S1, now=T)
        self.assertEqual(rl.gate(led, POLICY, S1)["state"], "CHECKS_PASS")


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL, check=True).stdout


def make_repo(root):
    sh(root, "git", "init", "-q", ".")
    sh(root, "git", "config", "user.email", "t@example.invalid")
    sh(root, "git", "config", "user.name", "t")
    Path(root, ".gitignore").write_text(".codex-runtime/\n")
    Path(root, "tracked.txt").write_text("one\n")
    Path(root, "docs").mkdir()
    Path(root, "docs", "a.md").write_text("doc\n")
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-q", "-m", "init")


def snapshot(root):
    """Snapshot that cannot disturb what it measures: the real index is read as bytes, and git runs on a private copy of it
    (independent of the code under test) because `git diff` rewrites .git/index when its stat data is stale."""
    index = Path(root, ".git", "index").read_bytes()
    with tempfile.TemporaryDirectory() as td:
        copy_ = Path(td, "index")
        copy_.write_bytes(index)
        env = {**os.environ, "GIT_INDEX_FILE": str(copy_)}

        def g(*a):
            return subprocess.run(["git", "-C", str(root), *a], capture_output=True, stdin=subprocess.DEVNULL, check=True, env=env).stdout

        snap = {"status": g("status", "--porcelain=v1", "-z"), "diff": g("diff", "HEAD", "--binary"),
                "staged": g("diff", "--cached", "--binary")}
    snap["files"] = {str(p.relative_to(root)): p.read_bytes() for p in Path(root).rglob("*")
                     if p.is_file() and ".git" not in p.relative_to(root).parts and ".codex-runtime" not in p.relative_to(root).parts}
    snap["index"] = index
    snap["index_still"] = Path(root, ".git", "index").read_bytes()
    return snap


class Repository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        make_repo(self.root)
        # pre-existing user changes: modified tracked, staged new, untracked
        Path(self.root, "tracked.txt").write_text("one\nlocal edit\n")
        Path(self.root, "staged.txt").write_text("staged\n")
        sh(self.root, "git", "add", "staged.txt")
        Path(self.root, "untracked.txt").write_text("mine\n")
        pol = copy.deepcopy(POLICY)
        pol["evidence_commands"]["static_validators"] = [[sys.executable, "-c", "pass"]]
        self.policy_path = Path(self.tmp.name).parent / (Path(self.tmp.name).name + "-policy.json")
        self.policy_path.write_text(json.dumps(pol))

    def tearDown(self):
        self.policy_path.unlink(missing_ok=True)
        self.tmp.cleanup()

    def cli(self, *args):
        r = subprocess.run([sys.executable, "-I", str(Path(rl.__file__)), "--repo", self.root, "--policy", str(self.policy_path), *args],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout.strip()

    def test_review_flow_leaves_unrelated_changes_intact(self):
        # make the index stale (mtime moves, content does not): a plain `git status` would rewrite .git/index to refresh it
        st = Path(self.root, "docs", "a.md").stat()
        os.utime(Path(self.root, "docs", "a.md"), (st.st_atime + 120, st.st_mtime + 120))
        before = snapshot(self.root)
        files = rl.changed_files(self.root, "HEAD")
        self.assertEqual(files, ["staged.txt", "tracked.txt", "untracked.txt"])
        self.assertEqual(self.cli("init", "run1", "--base", "HEAD")[0], 0)
        rc, out = self.cli("evidence", "run1", "diff_check")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.cli("round", "run1")[0], 0)
        self.assertEqual(self.cli("gate", "run1")[0], 1)  # medium tier: focused_check missing, human approval missing
        Path(self.root, "f.json").write_text(json.dumps(finding(file="tracked.txt", anchor="local edit")))
        rc, out = self.cli("finding", "run1", "--role", "model", "--json", str(Path(self.root, "f.json")))
        self.assertEqual(rc, 0, out)
        os.unlink(Path(self.root, "f.json"))
        self.assertEqual(self.cli("gate", "run1")[0], 1)
        after = snapshot(self.root)
        self.assertEqual(before, after)  # status, diffs, staged state, file bytes and index are all unchanged
        self.assertTrue(Path(self.root, ".codex-runtime", "review", "run1.json").exists())

    def test_cli_end_to_end_checks_pass_for_a_docs_change(self):
        sh(self.root, "git", "checkout", "-q", "--", "tracked.txt")
        sh(self.root, "git", "rm", "-q", "--cached", "staged.txt")
        os.unlink(Path(self.root, "staged.txt"))
        os.unlink(Path(self.root, "untracked.txt"))
        Path(self.root, "docs", "a.md").write_text("doc changed\n")
        self.assertEqual(self.cli("init", "docs1", "--base", "HEAD", "--suggest-tier", "low")[0], 0)
        self.assertEqual(self.cli("evidence", "docs1", "diff_check")[0], 0)
        rc, out = self.cli("gate", "docs1")
        self.assertEqual((rc, json.loads(out)["state"]), (0, "CHECKS_PASS"))
        Path(self.root, "docs", "a.md").write_text("doc changed again\n")  # code state moved: evidence is stale
        rc, out = self.cli("gate", "docs1")
        self.assertEqual((rc, json.loads(out)["state"]), (1, "BLOCKED_EVIDENCE"))

    def test_cli_refuses_recorded_diff_check_and_requires_by(self):
        sh(self.root, "git", "checkout", "-q", "--", "tracked.txt")
        sh(self.root, "git", "rm", "-q", "--cached", "staged.txt")
        os.unlink(Path(self.root, "staged.txt"))
        os.unlink(Path(self.root, "untracked.txt"))
        Path(self.root, "docs", "a.md").write_text("doc changed\n")
        self.assertEqual(self.cli("init", "docs2", "--base", "HEAD", "--suggest-tier", "low")[0], 0)
        rec = ("evidence", "docs2", "diff_check", "--record", "--command", "git diff --check", "--exit-code", "0")
        self.assertEqual(self.cli(*rec, "--by", "jack")[0], 2)  # policy command exists: a recorded pass is refused
        self.assertEqual(self.cli("evidence", "docs2", "focused_check", "--record", "--command", "x", "--exit-code", "0")[0], 2)  # no --by
        rc, out = self.cli("gate", "docs2")
        self.assertEqual((rc, json.loads(out)["state"]), (1, "BLOCKED_EVIDENCE"))
        self.assertEqual(self.cli("evidence", "docs2", "focused_check", "--record", "--command", "x", "--exit-code", "0", "--by", "jack")[0], 0)
        led = json.loads(Path(self.root, ".codex-runtime", "review", "docs2.json").read_text())
        self.assertEqual((led["evidence"][-1]["by"], led["evidence"][-1]["by_authenticated"]), ("jack", False))

    def test_cli_refuses_overwrite_unknown_review_and_bad_policy(self):
        self.assertEqual(self.cli("init", "x1", "--base", "HEAD")[0], 0)
        self.assertEqual(self.cli("init", "x1", "--base", "HEAD")[0], 2)
        self.assertEqual(self.cli("gate", "nope")[0], 2)
        self.assertEqual(self.cli("approve", "x1", "--by", "jack")[0], 2)  # there is no approval command
        self.assertNotIn("approvals", json.loads(Path(self.root, ".codex-runtime", "review", "x1.json").read_text()))
        bad = copy.deepcopy(POLICY)
        bad["max_auto_rounds"] = 9
        self.policy_path.write_text(json.dumps(bad))
        self.assertEqual(self.cli("gate", "x1")[0], 2)

    def test_untracked_content_change_makes_collected_evidence_stale(self):
        self.assertEqual(self.cli("init", "u1", "--base", "HEAD")[0], 0)
        rc, out = self.cli("evidence", "u1", "diff_check")
        self.assertEqual(rc, 0, out)
        rc, out = self.cli("gate", "u1")
        missing = {m["check"]: m["reason"] for m in json.loads(out)["missing_or_failed_evidence"]}
        self.assertNotIn("diff_check", missing)  # fresh and passing; only the human-recorded focused_check is missing
        Path(self.root, "untracked.txt").write_text("mine, edited after the evidence was collected\n")
        rc, out = self.cli("gate", "u1")
        missing = {m["check"]: m["reason"] for m in json.loads(out)["missing_or_failed_evidence"]}
        self.assertIn("stale", missing["diff_check"])
        self.assertEqual(json.loads(out)["state"], "BLOCKED_EVIDENCE")

    def test_state_id_covers_untracked_contents_but_not_ignored_files(self):
        a = rl.state_id(self.root)
        self.assertEqual(a, rl.state_id(self.root))  # deterministic
        Path(self.root, "untracked.txt").write_text("changed\n")
        b = rl.state_id(self.root)
        self.assertNotEqual(a, b)
        Path(self.root, "second_untracked.txt").write_text("x\n")
        c = rl.state_id(self.root)
        self.assertNotEqual(b, c)
        os.unlink(Path(self.root, "second_untracked.txt"))
        self.assertEqual(b, rl.state_id(self.root))
        Path(self.root, ".codex-runtime").mkdir(exist_ok=True)
        Path(self.root, ".codex-runtime", "scratch.txt").write_text("ignored\n")
        self.assertEqual(b, rl.state_id(self.root))  # git-ignored files are outside the state

    def test_untracked_files_that_cannot_be_bound_fail_closed(self):
        Path(self.root, "second_untracked.txt").write_text("x\n")
        with mock.patch.object(rl, "MAX_UNTRACKED_FILES", 1), self.assertRaises(rl.PolicyError):
            rl.state_id(self.root)
        with mock.patch.object(rl, "MAX_UNTRACKED_BYTES", 1), self.assertRaises(rl.PolicyError):
            rl.state_id(self.root)
        with mock.patch.object(Path, "is_symlink", return_value=True), self.assertRaises(rl.PolicyError):  # symlinks cannot be created here
            rl.state_id(self.root)
        os.unlink(Path(self.root, "second_untracked.txt"))
        nested = Path(self.root, "nested")
        nested.mkdir()
        sh(nested, "git", "init", "-q", ".")
        with self.assertRaises(rl.PolicyError):  # a nested repository is listed as a directory
            rl.state_id(self.root)

    def test_runtime_directory_inside_the_repo_must_be_ignored(self):
        rc, out = self.cli("--runtime-dir", str(Path(self.root, "rt")), "init", "n1", "--base", "HEAD")
        self.assertEqual(rc, 2)
        self.assertIn("not git-ignored", out)
        self.assertFalse(Path(self.root, "rt").exists())

    def test_state_id_changes_with_tracked_edits(self):
        a = rl.state_id(self.root)
        Path(self.root, "tracked.txt").write_text("one\nlocal edit\nmore\n")
        self.assertNotEqual(a, rl.state_id(self.root))

    def test_rereview_scope_is_diff_only_plus_open_findings(self):
        led = rl.new_ledger("r2", POLICY, ["tracked.txt"], rl.head_commit(self.root), rl.state_id(self.root), now=T)
        rl.begin_round(led, POLICY, rl.head_commit(self.root), S1, now=T)
        rl.add_finding(led, POLICY, finding(file="tracked.txt", anchor="local edit"), "model", now=T)
        self.assertEqual(rl.rereview_scope(self.root, led), ["tracked.txt"])  # no new commit: only unresolved findings
        sh(self.root, "git", "add", "tracked.txt")
        sh(self.root, "git", "commit", "-q", "-m", "second")
        Path(self.root, "docs", "a.md").write_text("d2\n")
        sh(self.root, "git", "add", "docs/a.md")
        sh(self.root, "git", "commit", "-q", "-m", "third")
        # staged.txt was already staged by setUp, so the first commit includes it: everything changed since the round's head
        self.assertEqual(rl.rereview_scope(self.root, led), ["docs/a.md", "staged.txt", "tracked.txt"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
