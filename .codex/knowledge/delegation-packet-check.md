# P2-S02 Delegation Packet Check — CODEX PRIME

Scope: `tools/control_plane/check_delegation_packets.py`, a static grader for contracts.md §3 expectations **DELEG-1** (every delegation
packet has the six fields, each non-empty) and **DELEG-3** (no two writable packets claim overlapping paths), from BLUEPRINT.md v1.2
§2.4 and §2.5. Checked 2026-10-31 on `codex-cli 0.166.0`, Windows 11 build 22631, Git Bash, `python -I`. Base: `origin/main`
`7a53e0dab1df2dfa1700633250b8c640c2fc5016`. No model session, `codex exec` or operator check was run.

Started while **Phase 1 is PARTIAL** on the project owner's decision; none of its open evidence is resolved (O-A, O-B, O-I and O-J are
`BLOCKED: operator`; S05 and PR #8 are open; C1 persists). This slice is independent of PR #11 (architect agent): it adds new files only
and touches neither `contracts.md`, `validate_contracts.py` nor `native-capabilities.md`.

## 1. What it is, and what enforces what

| Claim | Enforcement point | State |
| --- | --- | --- |
| A packet lacking one of OBJECTIVE, SCOPE, BOUNDARIES, EVIDENCE, OUTPUT, COMPLETION (or leaving it empty, or repeating a field) fails | **Control-plane-enforced**, only when someone runs the script on packet text | statically tested (12 fixture cases) |
| Two packets that are not read-only and name the same path, or a path and its parent directory, fail | Same | statically tested |
| Codex spawns subagents only with such packets | **Advisory**: the six-field packet is a convention in the spawn prompt (contracts §3). Nothing in Codex reads or rejects it | unverified, unenforced |
| The grader sees what Codex actually sent to a subagent | none | **unverified**: how spawn prompts appear in `codex exec --json` (`collab` items) was not observed, so extracting packets from a session is out of scope. The script takes packet text as input |

Heuristics, stated so they are not mistaken for guarantees: read-only is inferred from the BOUNDARIES text (`read-only`, `do not edit`,
`no edits`); paths in SCOPE are tokens that contain `/` or `\` or end in a file extension; a writable packet with no recognizable path
fails because DELEG-3 cannot be checked for it. A packet that wrongly claims "read-only" while editing is not caught (that needs the diff,
DELEG-3's second half).

## 2. Failure behavior

| Input | Result |
| --- | --- |
| All packets pass | exit 0 |
| Any violation | exit 1, one line per violation |
| File missing, undecodable, or no packets | exit 2 (never 0) |
| Wrong arguments | exit 2 |

Observed on 0.166.0's host with the scratch fixtures: the BLUEPRINT §2.4 example (with CRLF line endings) → 0; two packets, one missing
COMPLETION and overlapping writable scopes → 1 with both violations; empty file → 2; non-UTF-8 bytes → 2; missing file → 2.

## 3. Static results

| Command | Result |
| --- | --- |
| `python -I tools/control_plane/check_delegation_packets.py --self-test` | `self-test: 12/12 cases behaved as intended`, `PASS` (includes the BLUEPRINT example as a passing case) |
| `python -I tools/control_plane/validate_config.py --codex --self-test` | regression: 15/15, PASS |
| `python -I tools/control_plane/validate_contracts.py --codex --self-test` | regression: 29/29, PASS |

The self-test is a set of fixture cases, not a mutation suite over the checker's own code; it shows the intended inputs produce the intended
verdicts, not that the parser is exhaustive.

## 4. Acceptance (P2-S02)

Static: **PASS**. Runtime use against real subagent prompts: **unverified** (needs a trusted project and a paid model session that spawns
subagents, which the project owner has not approved). Slice status: **PARTIAL**. Phase 2 remains **PARTIAL** (§2.9 runtime criteria unmet).

## 5. Reproduce

```bash
python -I tools/control_plane/check_delegation_packets.py --self-test
python -I tools/control_plane/check_delegation_packets.py path/to/packets.txt   # packets separated by a line containing only ---
```
