# P1-S06 Re-baseline for Codex 0.166.0 and BLUEPRINT v1.2 — CODEX PRIME

Scope: the Codex capabilities Phase 1 relies on (project config keys, `AGENTS.md` discovery, trust/loading, sandbox and
protected paths), and the shipped knowledge docs versus the `BLUEPRINT.md` in this workspace. Checked **2026-10-31**.
Installed binary `codex-cli 0.162.1` → `codex-cli 0.166.0`. Probes ran on native Windows 11 (build 22631) in PowerShell 7.6.2;
validators ran in Git Bash with `python -I`. Base: `origin/main` `060f7f39921542d9779c7972b3676bd71b35049f`.

This file **adds** 0.166.0 findings. The 0.162.1 evidence in `native-capabilities.md`, `config-trust-sandbox-baseline.md` and
`config-baseline-verification.md` is unchanged and still describes 0.162.1 only. No model session was started (`codex exec`,
`codex review` not run); no user config, trust, hook review or credential was read or changed.

State words: **documented** (official page says so), **locally accepted** (the 0.166.0 config loader accepted or rejected the value),
**runtime-verified** (behavior observed on 0.166.0), **unverified**.

## 1. Official sources (opened 2026-10-31)

Base `https://learn.chatgpt.com/docs/` (the Codex docs host; see `native-capabilities.md` §3). Retrieval: **MCP** = `openaiDeveloperDocs`
`fetch_openai_doc`, full page; **HTTP** = `.md` twin fetched with `curl`, searched with `grep` (not read in full).

| ID | Page | Retrieval | Used for |
| --- | --- | --- | --- |
| D6 | `agent-configuration/agents-md` | MCP | instruction chain, override, fallback, size cap |
| D3 | `config-file/config-basic` | MCP | precedence, trust gating, `shell_environment_policy` default |
| D2 | `agent-approvals-security` | MCP | sandbox/approvals, protected paths, network, retired `untrusted` |
| D4 | `config-file/config-reference` | HTTP | key presence, keys ignored in a project file |

Source 3 (version-matched repository tag) was not used. Source 4 (general search) was not used.

## 2. Findings

| # | Claim (Phase 1 reliance) | Documented | Locally accepted (0.166.0) | Runtime-verified (0.166.0) | Unverified / limits |
| --- | --- | --- | --- | --- | --- |
| 1 | The five baseline keys exist with the types used: `approval_policy`, `sandbox_mode`, `sandbox_workspace_write.network_access`, `shell_environment_policy.ignore_default_excludes`, `agents.max_concurrent_threads_per_session` | D4 lists each; D3 gives the `ignore_default_excludes` default (`true`) | Baseline values accepted. Wrong-typed values rejected by name (`expected a boolean`, `expected usize`). An unknown key is accepted silently, so a rejection, not an acceptance, is the evidence a key exists | no | Effect of the values from the project file in a trusted project: unverified |
| 2 | `approval_policy = "untrusted"` is retired | D2, D4 | Rejected: `approval_policy = "untrusted" is no longer supported`. Domain error still lists `untrusted` as a variant name | n/a | none |
| 3 | `approvals_reviewer` domain | D2: `user`, `auto_review` | Binary lists `user`, `auto_review`, `guardian_subagent`. The third value is not in the pages read; not used | no | Same as 0.162.1 |
| 4 | Legacy `profile = ...` is gone; profile files are `<name>.config.toml` | D3, D4 | Rejected: use `--profile x` with `x.config.toml` | n/a | none |
| 5 | Untrusted project skips project `.codex/` layers | D3, D4 | n/a | Untrusted scratch repo: project `goals = false` and `model` sentinel ignored (probe P1) | **Trusted** project loading: unverified, `BLOCKED: operator` (O-A, O-B, O-I) |
| 6 | Project/user precedence and `-c` highest | D3 | `-c` values accepted | not exercised against a trusted project | Merge of a trusted project layer: `BLOCKED: operator` |
| 7 | `AGENTS.md` discovery: root to launch directory, `AGENTS.override.md` first, fallback names, `project_doc_max_bytes` cap | D6 | `project_doc_max_bytes`, `project_doc_fallback_filenames`, `project_root_markers` accepted; wrong types rejected | Untrusted scratch repo via `debug prompt-input`: root launch loads root `AGENTS.md` only; nested launch also loads `sub/AGENTS.md` and nested skill; a file one level above the Git root is not loaded; override loaded and `AGENTS.md` not; fallback file loaded when no `AGENTS.md`; cap 64 bytes kept the head and dropped the tail silently | Global `~/.codex/AGENTS.md` path not observed. Trusted-session chain not observed |
| 8 | This repository's `AGENTS.md` reaches the model-visible prompt | D6 | n/a | `validate_contracts.py --codex` (renders `codex debug prompt-input`) passed | Trust state of this path was not read, so it is unknown whether that render was trusted. `debug prompt-input` is a rendered prompt, not a stable interface |
| 9 | `workspace-write` keeps `.git`, `.agents`, `.codex`, `.aws` read-only, recursively | D2 | `sandbox_mode` domain: `read-only`, `workspace-write`, `danger-full-access` | `codex sandbox` helper, scratch repo, both `-P :workspace` and `-c sandbox_mode="workspace-write"`: new file and `.codex-runtime\a.txt` created; overwrite or append of existing `.codex\config.toml`, `.codex\agents\*.toml`, `.agents\...\SKILL.md`, `.git\config` denied and contents unchanged; new `.git\hooks\pre-commit`, new `.aws\probe.txt` and rename of `.codex` denied; `:read-only` writes denied; no profile and no `-c`: write denied. `del` of the protected file exited 0 and the file remained (grade on file state, not exit code) | **Whether a model-session write to a protected path prompts for approval or is simply denied was not observed.** The helper has no approval layer. `BLOCKED: operator` (O-J) |
| 10 | Command network is off in `workspace-write` | D2 | `network_access` boolean accepted | Under the sandbox `curl.exe https://example.com` exit 7; unsandboxed control HTTP 200 | Network on and `network_proxy` domain rules not exercised (would loosen a safeguard) |
| 11 | Feature flags Phase 1 may touch exist | D3 table: `hooks`, `goals`, `multi_agent`, `shell_tool` stable | `features list` 0.166.0: `hooks`, `goals`, `multi_agent`, `shell_tool`, `plugins`, `apps`, `guardian_approval` stable `true`; `memories` stable `false`; `network_proxy` experimental `false` | n/a | `prefer_mxc` is `under development` / `false` although D3 shows `[features] prefer_mxc = true` as a setting; not used by Phase 1 |

**Differences between 0.162.1 and 0.166.0 in the rows re-probed: none observed** (rows 1–5, 7, 9, 10). Probe P2 `customAgentName=False`
(custom agent names do not appear in the rendered prompt) is also unchanged and is not evidence either way.

### Documentation / CLI conflict (recorded, not resolved)

| ID | Documentation | Installed 0.166.0 | Impact |
| --- | --- | --- | --- |
| C1 (persists from 0.162.1) | D2 shows `codex sandbox macos\|linux\|windows [--permissions-profile <name>] [COMMAND]...` | `codex sandbox --help`: `codex sandbox [OPTIONS] [COMMAND]...` plus one subcommand, `uninstall`. Arguments are described as run "under Windows restricted token sandbox". `-P` works (probe rows) | No platform subcommand is used or required by any Phase 1 deliverable. Anything that scripts the documented subcommand form must stay blocked until reconciled; probes keep using the direct form |

## 3. BLUEPRINT.md reconciliation

| Fact | Value |
| --- | --- |
| File in this workspace | untracked at S06 start; `BLUEPRINT.md`, 157,855 bytes, sha256 `543d3fb0cb852dce155007d07af9ae63259e2831f6aaa97faf443721e2690235`, LF endings, 2010 lines |
| Self-declared revision | header "Architecture Specification v1.2 · October 31, 2026"; "Revision 1.2 (October 31, 2026)" block |
| File recorded by P0-S01 (`baseline-report.md`) | 154,151 bytes, sha256 prefix `7489C316…`. **A different file.** The shipped docs were written against that file (cited as v1.1), which is not in this repository or its history, so a content diff v1.1 → v1.2 was not possible |
| Why it is treated as the intended v1.2 | The operator directed S06 to reconcile with "BLUEPRINT.md v1.2 … available in this workspace"; the header and revision block match; the hash differs from the v1.1 record. No stronger provenance exists locally. The untracked original was copied, not moved |

Checked against v1.2 (anchors cited by shipped docs):

| Shipped reference | Result in v1.2 |
| --- | --- |
| `config.toml` baseline (S03) vs §1.2 | Same five keys and values, same comments' intent. `approvals_reviewer` and `[permissions.*]` remain optional/absent as shipped |
| `contracts.md` seven contracts vs §7 | Seven contracts named as shipped; §7.3 lists conflicts as "identify" only (matches the stricter-by-project note); §7.4 titled "Verification contract" and §7.5 five outcomes without tie-break (C12, C13 hold); §6.2 and §12 still call a safety pause "its own outcome" |
| `AGENTS.md` vs §1.1 recommended contract | The shipped file keeps the six responsibilities; it differs on purpose (protected-path line, pointers to `contracts.md` and `native-capabilities.md`, no subtree line, `.codex-runtime/` state). Not a v1.2 change |
| `.gitignore`/`.gitattributes` vs §3, §9 | §9 row 3 names both; matches |
| Section anchors §0.1, §0.2, §0.3, §0.4, §0.5, §0.6, §3.3, §3.6, §4.6, §7.5 | All present with the cited subject |
| v1.2 revision items affecting shipped Phase 1 files | `.codex-runtime/` for runtime output and protected `.codex/.agents/.git/.aws` (already shipped); nested `AGENTS.md` only along root-to-launch path (matches row 7). Others (hook failure wording, `SessionStart` compaction, rules scope, `PermissionRequest`, `SubagentStart/Stop`, `allow_implicit_invocation`) concern Phase 2–4 files that do not exist |

Edits made for consistency: `contracts.md` line 4 no longer says the blueprint is outside the repository; `native-capabilities.md` gains a
pointer to this file. Existing "v1.1" citations elsewhere are **historical** and left as written (their anchors were checked above).

Not reconciled: the unmerged S05 branch (`task-classification.md`, `AGENTS.md` L0–L3 rules) cites v1.1 §1.3–§1.5; headings §1.3–§1.5 exist in
v1.2 but their content was not compared here. That belongs to whoever lands S05.

## 4. Static results (0.166.0 installed)

| Command | Result |
| --- | --- |
| `python -I tools/control_plane/validate_config.py --codex --self-test` | `self-test: 15/15 mutations detected by the intended check`, `PASS`, exit 0 |
| `python -I tools/control_plane/validate_contracts.py --codex --self-test` | `self-test: 29/29 mutations detected by the intended check`, `PASS`, exit 0 (run again after the doc edits; see the S06 report) |
| `pwsh -NoProfile -File tools/control_plane/probe_config_baseline.ps1` | completed; rows summarised in §2; scratch repo removed by its `finally` block |
| `codex -c <key>=<value> features list` key probes | as §2 rows 1–4, 7 |

Not run: `validate_classification.py` and the S05 scenarios (S05 is not on this branch; its scenarios are paid and need explicit approval).

## 5. Open blockers

| ID | Item | State |
| --- | --- | --- |
| O-A, O-B, O-I | Trust the path in the TUI, then `/status`: confirm the project config layer, approval `on-request`, sandbox `workspace-write` | `BLOCKED: operator` |
| O-J | In the trusted session, ask Codex to write under `.codex-runtime/` and to edit `.codex/config.toml`; record whether the second is refused or prompts | `BLOCKED: operator` |
| E-1 | Protected-path write inside a model session (prompt versus denial) | `BLOCKED: operator` + paid session needing approval |
| E-2 | C1 documentation/CLI mismatch for `codex sandbox` | `BLOCKED: evidence` for any work that depends on the documented subcommands |
| E-3 | Windows MXC (`B9`), WSL, and `agents.max_concurrent_threads_per_session` enforcement not re-run on 0.166.0 | unverified (not part of the S06 probe set) |

## 6. Reproduce

```powershell
codex --version
pwsh -NoProfile -File tools/control_plane/probe_config_baseline.ps1
python -I tools/control_plane/validate_config.py --codex --self-test
python -I tools/control_plane/validate_contracts.py --codex --self-test
```
