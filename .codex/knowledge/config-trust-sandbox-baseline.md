# P0-S03 Configuration, Trust, and Sandbox Baseline — CODEX PRIME

Scope: BLUEPRINT.md v1.1 §0.4 (configuration precedence), §0.5 (baseline snapshots, carried from S01), §0.6 (acceptance).
Captured 2026-10-13 against `codex-cli 0.162.1`, native Windows 11 build 22631, PowerShell 7.6.2 and Git Bash 5.2.37 (the Bash
tool was used only to drive PowerShell; all Codex helper probes ran in PowerShell). Sanitized: no credential file was opened, user
config was not read or written, and user-home paths are omitted.

Reproduce: `pwsh -NoProfile -File tools/control_plane/probe_config_baseline.ps1` (throwaway repo under `%TEMP%`, deleted afterwards;
starts no model session; one `curl.exe` request to example.com as a network control). Operator checks:
`tools/control_plane/operator_checks_p0s03.ps1` (`-Mode Prepare|Verify|Cleanup`; never edits user config or grants trust).

State words follow `native-capabilities.md` §1. **Every probe below ran in an UNTRUSTED project.** The user config has no
`[projects]` entry for this repository or for the scratch repos (S01), and nothing in this slice changed that.

## 1. Authority used

| ID | Source | Used for |
| --- | --- | --- |
| D3 | `learn.chatgpt.com/docs/config-file/config-basic` (docs MCP, full) | precedence order, trust gating of project layers |
| D2/D4/D6/D8/D11/D12 | as listed in `native-capabilities.md` §3 | protected paths, network, discovery, profiles, Windows sandbox |
| B* | installed binary probes (`native-capabilities.md` §4) plus P1–P5 below | all behavior claims |

D3 states: precedence, highest first — (1) CLI flags and `--config`; (2) project `.codex/config.toml` files, root to cwd, closest wins,
**trusted projects only**; (3) `--profile` files; (4) user `~/.codex/config.toml`; (5) cloud-managed defaults; (6) system config
(`/etc/codex/config.toml` on Unix); (7) built-ins. Untrusted projects skip project `.codex/` layers (config, hooks, rules); user and
system layers still load. Admin `requirements.toml` can constrain values (for example forbid `approval_policy = "never"`).

## 2. Probe results

| ID | Probe | Observed | State |
| --- | --- | --- | --- |
| P1 | Scratch repo, untrusted, project `.codex/config.toml` with `model = <sentinel>` and `[features] goals = false`; read effective values with `codex features list` and `codex doctor --json` | `goals` stayed `stable true`; effective model was not the sentinel. The whole project layer was skipped. | RUNTIME-TESTED (untrusted only) |
| P1b | Same project config, **trusted** | not run | `BLOCKED: operator` (O-A) |
| P2 | `codex debug prompt-input` launched from scratch root vs `sub/dir` | Root launch: root `AGENTS.md` and root skill present; `sub/AGENTS.md` and `sub/.agents` skill absent. Nested launch: all four present. | RUNTIME-TESTED (untrusted) |
| P2b | Ancestor `AGENTS.md` one directory **above** the Git root | not injected from either launch directory (`ancestorAGENTS=False` in both) | RUNTIME-TESTED (untrusted) |
| P2c | This repository, nested launch (`tools/control_plane`) | no instruction block from `C:\TEST-repos\AGENTS.md` or `C:\AGENTS.md` (contents never read); there is no project `AGENTS.md` yet. The rendered prompt's workspace root becomes `...\tools\control_plane` (a nested launch also changes the workspace root; the probe prints this). The no-ancestor-block check itself was a **manual**, path-based observation, not scripted. | RUNTIME-TESTED (manual, weaker evidence) |
| P2d | Project `.codex/agents/demo.toml` name in rendered prompt | absent from both launches. The prompt lists no agent roster, so this is **not** evidence either way. | UNVERIFIED |
| P2e | Built-in agents (`default`, `worker`, `explorer`) | not named in the rendered prompt; `spawn_agent` appears in the multi-agent section and `multi_agent` is enabled (B3). Names are documented (D5), not observed. | DOCUMENTED + INSTALLED only |
| P2f | Scratch root: `AGENTS.override.md` next to `AGENTS.md`; fallback filename via `-c project_doc_fallback_filenames`; `-c project_doc_max_bytes=64` with a 200+ byte file | Override file loaded and `AGENTS.md` **not** loaded; fallback file loaded when no `AGENTS.md`; with the cap, the head was loaded and the tail was not (truncation, silent) | RUNTIME-TESTED (untrusted) |
| P2g | `codex execpolicy check` on the scratch `.codex/rules/p.rules` | `forbidden` for `git push origin main`. Offline checker only: does not show a trusted project layer loaded the file. | RUNTIME-TESTED (offline) |
| P3 | Rendered prompt for this repository, no flags | `sandbox_mode` is `read-only`; "Network access is restricted" | RUNTIME-TESTED |
| P4 | `codex sandbox -P :workspace` (permission profile) in scratch repo | New file and new `.codex-runtime\a.txt`: succeed. Overwrite or append of **existing** `.codex\config.toml`, `.codex\agents\*.toml`, `.agents\...\SKILL.md`, `.git\config`: denied, and a content check of all four finds no change. New `.git\hooks\pre-commit`, new `.aws\probe.txt`, rename of `.codex`: denied. `:read-only` writes: denied. | RUNTIME-TESTED (helper path) |
| P4b | Same rows with **`-c sandbox_mode="workspace-write"`** (no profile) | Same outcomes as P4 for every row except `:read-only` (a profile, so skipped); the probe removes the earlier test files first so `created` is meaningful, and the four content checks pass. No profile and no `-c`: write denied (default is read-only). `del` of the protected `.codex\config.toml` exits 0 but the file remains, so exit codes are unreliable; the probe prints file state. | RUNTIME-TESTED |
| P5 | `curl.exe https://example.com` | unsandboxed: HTTP 200. Under `:workspace` and under the default: curl exit 7 (could not connect). Enabling network and `network_proxy` domain rules were deliberately **not** exercised (would loosen a native safeguard). | RUNTIME-TESTED (off by default) |

Notes that affect later phases:

- `del` under the sandbox returned exit 0 although the target stayed and "Access is denied" was printed. Grade protected-path tests on file
  state (and stderr text), never on exit code alone.
- Instruction files outside the Git root are not loaded, but instruction files **below** it load only when the launch directory is at or
  below them. A root launch never sees nested `AGENTS.md`; do not rely on nested files for contracts that must always apply.
- Skills show the same cwd-up-to-root rule; a nested skill is invisible from the root launch.
- `debug prompt-input` is a rendered prompt, not a stable interface, and shows no agent roster, hook table, rule table, or config-layer list.
  `codex doctor` reports `config.toml` parse status and a "cloud-managed policy" scope but does not list layers.

## 3. Platform limits (recorded separately)

| Platform | Observation | State |
| --- | --- | --- |
| Native Windows (this host) | Restricted-token sandbox helper works (P4/P5). `codex sandbox` takes the command directly; no `linux`/`windows`/`macos` subcommands (S01, conflict C1). Probes must run from PowerShell: Git Bash rewrites `cmd.exe /d /c` arguments (S02). | observed |
| Native Windows, MXC | `native MXC is unavailable on this executor` on build 22631 (needs 26100.9278+ per D12) | ENV-LIMITED (S02 B9) |
| WSL (Ubuntu, WSL2) | Distros present and Stopped (S01). WSL was **not** started in this slice. Codex presence, Linux sandbox (bubblewrap), and whether `/mnt/c` paths work are unobserved. | `BLOCKED: operator` (O-E) |
| Nested sandbox | These probes ran from an agent shell that is not itself in a Codex or bubblewrap sandbox, and Codex's own sandbox worked. No nested-sandbox failure was observed, so the blueprint's "record as environment-specific" rule was not triggered. A Linux-in-container nested case was not tested. | not observed |
| Admin/managed layers | No `C:\ProgramData\OpenAI\Codex` or `C:\ProgramData\codex` (S01). A cloud-managed policy or `requirements.toml` is invisible to local probes. | UNVERIFIED |

## 4. Operator-only checks (exact commands)

Run in PowerShell 7. Nothing here is executed by the builder. Record `PASS`/`FAIL` with the observed output.

| ID | Check | Command / step | Expected | Status |
| --- | --- | --- | --- | --- |
| O-A | Trusted project layer loads | `pwsh -NoProfile -File C:\TEST-repos\codex-prime\tools\control_plane\operator_checks_p0s03.ps1 -Mode Prepare`, then follow its printed steps 1-3 (trust the scratch path in the TUI, then `-Mode Verify`; the script prints absolute paths) | before trust `goals true`; after trust `goals false` from root and from `sub` | `BLOCKED: operator` |
| O-B | Effective layers, sandbox, roots for this repo | `cd C:\TEST-repos\codex-prime; codex`, trust prompt, then `/status` | records active config layers, sandbox, approval, workspace roots | `BLOCKED: operator` (S01 U1/U4) |
| O-C | Hook trust state | `/hooks` in the trusted TUI session (no hooks exist until Phase 4) | empty list now | `BLOCKED: operator` (S01 U2) |
| O-D | Custom/built-in agent visibility | After O-A: `cd <scratch root printed by Prepare>; codex exec --sandbox read-only -c 'approval_policy="never"' --json 'Spawn the agent named demo_agent and report its reply.'` (must run from the trusted scratch root); also `/subagents` in the TUI | JSON events show a spawn naming `demo_agent`; built-ins listed | paid session, needs user approval of spend |
| O-E | WSL | In Ubuntu: `command -v codex && codex --version`, then a `codex sandbox` write probe in a repo under the Linux home | Codex present; bubblewrap works | `BLOCKED: operator` |
| O-F | `exec` approval policy effect | same command as O-D without the agent prompt: `codex exec --sandbox read-only -c 'approval_policy="never"' --json 'Run git status and report.'`; grade the policy from the event stream | events consistent with `never` | paid session, needs user approval of spend |
| O-G | Network enable + proxy domains | Step 1: `codex sandbox -c 'sandbox_mode="workspace-write"' -c 'sandbox_workspace_write.network_access=true' -- curl.exe -s -m 8 -o NUL -w '%{http_code}' https://example.com`. Step 2 (proxy domain policy): **not specified here**; the operator must take the exact `features.network_proxy` table keys from D2/D11 and confirm them with a parse test before use | step 1: 200 only with network on; step 2: allowlist enforced | operator-run only (loosens a safeguard); not run |
| O-H | Cleanup | `-Mode Cleanup`, then remove the scratch trust entry from `~/.codex/config.toml` | entry gone | operator |

## 5. Phase 0 acceptance register (BLUEPRINT §0.6)

| # | Criterion | Result | Evidence / gap |
| --- | --- | --- | --- |
| 1 | Installed Codex CLI version identified | PASS | `codex-cli 0.162.1` (S01, S02 B1) |
| 2 | Repository status and pre-existing changes recorded | PASS | S01 §1; untracked `BLUEPRINT.md`, `CLAUDE.md` left untouched |
| 3 | Applicable instruction hierarchy identified | PARTIAL | Behavior observed in an untrusted scratch repo: root vs nested, ancestor exclusion, `AGENTS.override.md`, fallback filenames, and the size cap (P2, P2b, P2f). This repo has no `AGENTS.md` yet, and trusted-session behavior and the global `~/.codex/AGENTS.md` path were not observed. |
| 4 | Official/native capability matrix completed | PASS | `native-capabilities.md` (25 groups). Carried from S02; see §7 on branch lineage. |
| 5 | Active configuration and trust behavior verified | PARTIAL | Untrusted skip verified (P1). Trusted loading, `/status`, and layer precedence between project and user are `BLOCKED: operator` (O-A, O-B). |
| 6 | Native agent and skill discovery tested | PARTIAL | Skills PASS (root and nested, P2). Custom agents and built-in agents UNVERIFIED (P2d/P2e), `BLOCKED: operator` plus a paid session (O-D). |
| 7 | Hook and rules support identified | PARTIAL | Supported and documented, `hooks` feature enabled (S02 rows 13-14); `execpolicy check` parses a rule file (P2g, offline). Hook trust and runtime rule loading are `BLOCKED: operator` (O-B, O-C). |
| 8 | Protected-path behavior and default network state observed | PASS (scope-limited) | P3, P4, P4b, P5 on native Windows via `codex sandbox`, under both a permission profile and `-c sandbox_mode`. Not observed inside a model session or with `sandbox_mode` set in a trusted project file. |
| 9 | Host-platform limitations documented | PARTIAL | Native Windows and MXC documented (§3); WSL `BLOCKED: operator` (O-E); no nested-sandbox case seen. |
| 10 | No unintended repository or environment changes | PASS | See §6: repository diff is the three deliverables; user config and trust untouched; Codex's own `CODEX_HOME` state files change when it runs. |

**Phase 0 overall: PARTIAL.** None is a `FAIL`. Open items fall in two groups:

- `BLOCKED: operator`: trusted-layer loading and `/status` (O-A, O-B), hook trust (O-C), WSL (O-E).
- **Not operator-blocked**, so they are open work, not a pass: built-in and custom agent visibility needs a paid model session
  (user approval of the spend, O-D); `exec` approval-policy effect (O-F, paid); admin/cloud-managed policy is not observable locally.

`CLAUDE.md` allows starting Phase 1 static work only when the sole open items are `BLOCKED: operator`. That condition is **not met**
while the paid-session items remain open. This report does not authorize Phase 1; the user must either approve the paid runs
(O-D/O-F) or explicitly accept those items as deferred. Phase 1 acceptance cannot rely on trusted-project behavior until O-A and O-B pass.

## 6. Environment and repository effects

- Created and deleted only under `%TEMP%` (`cp-s03-*`); removed by the probe's `finally` block, which prints a warning if removal fails.
- **User config and trust were not written** (`~/.codex/config.toml` mtime unchanged per independent review; no trust entry, no hook
  review, no approval answered, no `--dangerously-*`, `--yolo`, `--ignore-rules`, or `--skip-git-repo-check` flag used).
  Codex itself writes its own state under `CODEX_HOME` when run (observed by the reviewer: `cap_sid`, `.sandbox/`, sqlite files); that
  is native Codex behavior and was not suppressed or edited. No `codex exec`/`review` model session was started.
- Network: `curl.exe` makes one control request to example.com; `codex doctor` and `debug prompt-input` may make their own
  connectivity requests (not captured).
- `codex features list`, `doctor`, `debug prompt-input`, `sandbox`, and `execpolicy check` were the only Codex commands run.
- Repository changes in this slice: this report, `probe_config_baseline.ps1`, `operator_checks_p0s03.ps1`.

## 7. Supported configuration recommendation

1. **Treat the project `.codex/` layer as inactive until the operator trusts the path** (D3, P1). Every delivered setting must either
   work without it or be passed as a launch flag. Keep a Phase 1 self-check in `AGENTS.md` instructing the agent to report when the
   project layer is not active (for example, a sentinel the config is expected to set).
2. **Launch from the repository root** and put always-on policy in the root `AGENTS.md` (and root `.agents/skills`). Nested
   `AGENTS.md`/skills only load for nested launches (P2). Never place contract text above the Git root; it is not loaded (P2b).
3. **Sandbox**: `workspace-write` with command network off for implementation runs; `read-only` otherwise. Set it with
   `sandbox_mode` (or `-c sandbox_mode=...`), not permission profiles, until O-A/O-B confirm profile precedence (S02 row 21 silent-override
   risk). Never `danger-full-access` without operator approval.
4. **Runtime output only under `.codex-runtime/`**; `.codex/`, `.agents/`, `.git/` deny writes including edits to existing files, under both a permission profile and `sandbox_mode` (P4, P4b; helper path only).
5. **Do not rely on the sandbox exit code** in tests (the `del` case); assert on resulting file state.
6. **Windows**: develop and test in PowerShell 7; do not run `cmd.exe` sandbox probes from Git Bash. Treat MXC and WSL as unavailable
   or unverified. Treat admin/cloud-managed policy as possible unseen constraints and report any unexplained denial instead of working around it.
7. Do not write retired settings (S02 row 25). Do not write keys into the project file that Codex ignores there (D4 list).

## 8. Limitations of this report

- All behavior is from an **untrusted** project and the `codex sandbox` helper; the model-session sandbox and trusted-layer merge
  behavior are not observed.
- The ancestor-file test (P2b) used a sentinel; the real-repo check (P2c) did not read the ancestor files and is weaker.
- `del` exit-code behavior and curl exit 7 are Windows-sandbox observations from one host.
- Branch lineage: this slice branches from the S02 head because PR #2 merged into `p0-s01-baseline`, **not** `main`
  (`origin/main` at `411554b` lacks the capability matrix). This PR therefore also carries the two S02 commits.
