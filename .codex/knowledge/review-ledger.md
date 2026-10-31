# P2-S04 Risk-adaptive Review Ledger — CODEX PRIME

Scope: deterministic review state and policy handling (`tools/control_plane/review_ledger.py`, `.codex/review-policy.json`, tests), designed
with input from "Solving code review at Anthropic" (`claude.dev/blog/solving-code-review-at-anthropic/`, read 2026-10-31). The article is design
input, not authority: this repository's architecture, BLUEPRINT.md v1.2 and `CLAUDE.md` govern. Checked 2026-10-31, `codex-cli 0.166.0`,
Windows 11 build 22631, Git Bash, `python -I`, git 2.53.0. Base: `origin/main` `7a53e0dab1df2dfa1700633250b8c640c2fc5016`.

Started while **Phase 1 is PARTIAL** on the project owner's decision; its open evidence is unresolved (O-A, O-B, O-I, O-J `BLOCKED: operator`;
S05 open; C1 and C2 recorded). No model session, `codex exec`, `/review`, or operator check was run.

## 1. What the ledger is, and is not

It records facts and applies fixed rules around a review that someone or something else performs. It does not review code, call a model,
run in CI, or loop. Nothing invokes it automatically: no hook, `AGENTS.md` line, or workflow was added, because Phase 4 hooks are not built
and `AGENTS.md` is changed by an open PR. BLUEPRINT §1 says the control plane must not reimplement Codex's reasoning in Python; this code holds
state and policy only.

## 2. Gap classification (what existed on `main` before this slice)

| Area (from the brief) | Status before | Evidence | After this slice |
| --- | --- | --- | --- |
| Verification evidence before review | **partial** | BLUEPRINT §5.11 designs `.codex-runtime/results/<task>.json` (no code); contracts §6 is guidance | **implemented**: policy-defined commands run by the tool, bound to an exact code state; human-recorded and explicit `not_run` entries; `focused_check` is human-recorded because no repo-wide command exists |
| Independent fresh-context review | **externally dependent** | native `/review` is documented (D14, NC10) but never exercised here; needs a model session | unchanged; the ledger records who reported (provenance) |
| Repository-specific review rules | **partial** | `AGENTS.md` and contracts are guidance; the docs allow a `## Code Review Rules` section in `AGENTS.md` for GitHub review | **deferred**: `AGENTS.md` is edited by PR #8 and the GitHub path is external |
| Risk classification with deterministic floors | **missing** (PR #8 adds qualitative L0–L3 guidance, not on `main`) | none on `main` | **implemented**: path rules and a file-count floor in a protected policy; a suggested tier can only raise |
| Specialized bug and security review | **intentionally deferred** | BLUEPRINT §2.3 lists a security auditor; none built | deferred (needs agents and paid sessions) |
| Structured findings | **missing** | none | **implemented**: file, line, class, severity, summary, evidence, provenance, append-only history |
| Stable identity, dedup, suppression | **missing** | none | **implemented**: id = hash(file, class, whitespace-normalized anchor line); a repeat is not reissued and keeps its disposition |
| Bounded convergence, max three rounds | **missing** (BLUEPRINT §5.3 retry policy is qualitative) | none | **implemented**: policy hard cap 1..3; a fourth round is refused; unresolved material findings are escalated |
| Diff-only re-review | **missing** | none | **partial**: `rereview_scope` computes changed-since-last-round files plus files with unresolved findings; no reviewer consumes it |
| Deterministic enforcement of critical rules | **partial** | sandbox and approvals are native (NC11, NC12); rules and hooks are Phase 4, not built | gate states are deterministic, but nothing forces a caller to consult the gate |
| CI / GitHub integration | **externally dependent** | no `.github/`; branch protection and required checks are GitHub configuration | not added |
| Human authorization boundaries | **partial** | contracts §1 authority rules (guidance) | `AWAITING_HUMAN` gate; only a human approval counts, bound to one code state |
| Reviewer regression evaluation, false-positive rate | **intentionally deferred** | BLUEPRINT Phase 6 | deferred (needs model runs); dispositions are preserved so a later measurement can use them |

## 3. Facts versus judgment

| Source | What it establishes |
| --- | --- |
| Tools and policy | tier and floor, evidence status (exit code, state id), round count, finding identity, gate state |
| Humans | approvals, `false_positive`, `accepted_risk`, and any disposition of an escalated finding |
| Models | findings and `proposed_false_positive` only. A model cannot approve, mark a material finding closed, supply evidence, lower a tier, or disposition an escalated finding |

## 4. Rules implemented

- **Risk:** per-file tier is the highest matching rule (default medium); the change tier is the highest file tier, raised by the file-count floor.
  A suggested tier can raise it and a lower suggestion is ignored and recorded. `.codex/**`, `.agents/**`, `AGENTS.md`, `CLAUDE.md`,
  `tools/control_plane/**`, workflows, `*.rules`, migrations, auth, secret and env files are high. Docs-only is low.
- **Evidence:** required names per tier; missing, `not_run`, failed (non-zero exit), or recorded for a different code state means `BLOCKED_EVIDENCE`.
  The code state id covers `HEAD`, `git status` and `git diff HEAD`; contents of untracked files are not hashed (limitation).
- **Findings:** rejected unless they carry a file, a positive line, a class and severity from closed lists, and at least 10 characters of inspected
  evidence. `low` severity is recorded and never blocks. Material = critical, high, medium.
- **Dispositions are append-only.** The recorded fields of a finding never change (a per-finding hash is verified on every load and gate);
  its status is derived from the history. `fixed` on a material finding needs a passing check at the current state from a tool or a human;
  `false_positive` and `accepted_risk` on a material finding are human-only; a model may only propose a false positive, which still blocks.
- **Rounds:** at most three (policy values above three are rejected). Unresolved material findings at the cap become `escalated`; only a human can
  then disposition them.
- **Gate order:** `ESCALATED`, `BLOCKED_EVIDENCE`, `BLOCKED_FINDINGS`, `AWAITING_HUMAN`, `CLEAR`. `CLEAR` means the automated conditions hold and any
  required human approval exists for the current state. It is not an authorization to merge, push or deploy; those stay with the project owner.

## 5. Enforcement labels and limits (read before relying on it)

| Claim | Label |
| --- | --- |
| Policy cannot be weakened by editing it from a `workspace-write` session | **Codex-enforced**, documented protected path, helper-observed denial (S06); model-session outcome unverified. The policy file lives in `.codex/`. The code and the ledger do **not**: `tools/control_plane/` and `.codex-runtime/` are writable |
| Role rules (`--role`, human-only dispositions, approvals) | **Advisory against a hostile caller.** The role is declared by whoever calls. A caller with shell access can declare `human`, or edit the ledger JSON. The per-finding hash detects accidental or partial edits, not a deliberate rewrite of the whole file. A real human gate must be run by a person outside the model's reach, or by CI |
| Three-round cap, dedup, risk floors, fail-closed evidence | **Control-plane-enforced** only for callers that use the ledger; nothing makes a repair loop call it |
| The gate result blocks anything | **Advisory** until a required CI check or branch-protection rule consumes it (external dependency, not configured) |
| Anchor-based identity | **Heuristic.** The reviewer supplies the anchor line and class; a reworded anchor or a different class creates a new finding |

Python cannot start inside the Codex sandbox on this host (S05 finding on 0.162.1, not rechecked on 0.166.0), so Codex itself may be unable to run
this tool in a session; it is intended for the builder, operator or CI side.

## 6. Verification (my runs; not independently reproduced)

| Command | Result |
| --- | --- |
| `python -I tools/control_plane/test_review_ledger.py` | `Ran 27 tests ... OK` |
| `python -I tools/control_plane/review_ledger.py check-policy` | `PASS: policy valid` |
| `python -I tools/control_plane/validate_config.py --codex --self-test` | regression: 15/15, PASS |
| `python -I tools/control_plane/validate_contracts.py --codex --self-test` | regression: 29/29, PASS |

The tests cover the brief's cases with synthetic findings: (1) a clean review with valid evidence passes; (2) failing evidence, an open material finding,
and a fixed finding that reappears all block; (3) a false-positive disposition keeps the original fields, provenance, author, time and rationale
and the hash still verifies; (4) a duplicate on a later round with a shifted line and reworded summary is not reissued and keeps its disposition;
(5) the fourth round is refused and unresolved findings escalate and cannot be cleared by a model or tool; (6) a suggested lower tier cannot lower the
floor; (7) missing, not-run, stale and failed evidence fail closed; (8) in a temporary git repo with a modified tracked file, a staged file and an
untracked file, the whole flow leaves the status, diffs, file bytes and `.git/index` byte-identical.

Negative controls: 12 deliberate breaks of the code were applied to copies and each made the tests fail (floor downgrade allowed, no round cap, model
approval counts, duplicate re-added, missing evidence ignored, stale evidence accepted, model marks a material finding false-positive, fixed without a
check, integrity check removed, escalated finding editable by a model, model evidence accepted, private git index disabled).

Finding during verification: `git diff` rewrites `.git/index` (stat refresh) even with `--no-optional-locks`, so an early version that merely avoided
`git status` still altered the user's index. All git calls and policy evidence commands now run against a throwaway copy of the index
(`GIT_INDEX_FILE`). The index holds only stat data for the staged and tracked state, but "read-only" is claimed only after the byte comparison passed.

## 7. Not verified / external dependencies

- No live reviewer, `/review`, subagent, or model was run; nothing here shows how a real reviewer behaves or how often it is wrong.
- The article's own numbers (round cap, results, tiers) are its authors' claims about their system; none was reproduced here. It does not say how
  finding identity is computed, how its vote threshold works, or whether its round cap is enforced mechanically; this design is independent of those.
- Required checks, branch protection, a CI workflow that runs the gate, and any GitHub review integration are not configured (operator/GitHub dependency).
- Human-only gates are unenforced against a caller who can run commands as the operator (section 5).
- Not implemented: pre-existing tagging, a nightly review, incident-derived evaluation sets, false-positive rate measurement, specialized reviewers.

## 8. Reproduce

```bash
python -I tools/control_plane/test_review_ledger.py
python -I tools/control_plane/review_ledger.py check-policy
# review flow (operator side), from the repository root:
python -I tools/control_plane/review_ledger.py init R1 --base origin/main
python -I tools/control_plane/review_ledger.py evidence R1 diff_check
python -I tools/control_plane/review_ledger.py round R1
python -I tools/control_plane/review_ledger.py gate R1      # exit 0 only when CLEAR
```
