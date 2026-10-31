# P2-S01 Architect Agent — Verification — CODEX PRIME

Scope: one custom agent, `.codex/agents/architect.toml` (BLUEPRINT.md v1.2 §2.3, §2.7, §2.8, build order §9 row 8), and the static
validator `tools/control_plane/validate_agents.py`. Checked **2026-10-31**, `codex-cli 0.166.0`, native Windows 11 (build 22631),
PowerShell 7.6.2 / Git Bash. Base: `origin/main` `7a53e0dab1df2dfa1700633250b8c640c2fc5016`. No model session, `codex exec`, or
operator check was run; no user config or credential was read.

## 1. Authorization and standing blockers

Phase 2 work began on the project owner's explicit decision, made while **Phase 1 is PARTIAL**: Phase 1 is *not* complete and none of
its open evidence is resolved. Residual Phase 1 / S06 blockers stay open and are not changed by this slice:

- `BLOCKED: operator`: trusted-project config loading and `/status` (O-A, O-B, O-I); protected-path write outcome in a model session (O-J).
- S05 (PR #8, open, untouched): L3 reporting held in 1 of 3 clean passes; reworded L3 and scoped L1 wording unevaluated; not evaluated on 0.166.0; paid R4 unrun.
- C1: docs describe `codex sandbox macos|linux|windows`; the 0.166.0 CLI does not have them.
- Not re-run on 0.166.0: Windows MXC, WSL, agent concurrency cap enforcement.

## 2. Source (opened 2026-10-31)

`https://learn.chatgpt.com/docs/agent-configuration/subagents`, fetched in full through the `openaiDeveloperDocs` MCP server.

## 3. What the file does and why

| Item | Value |
| --- | --- |
| File | `.codex/agents/architect.toml` (one agent per file, project scope) |
| Required fields | `name = "architect"`, `description`, `developer_instructions` |
| Model behavior | `model_reasoning_effort = "high"`; no `model` set, so it resolves from the spawn value, then `[agents]` defaults, then the parent |
| Capability reduction | `features.shell_tool = false` (dotted key, not a `[features]` table) |
| Not set (ignored per docs) | `sandbox_mode`, `approval_policy`, `model_provider`, `mcp_servers`, service tier |
| Built-in name clash | none (`default`, `worker`, `explorer` are not used) |

Differences from the BLUEPRINT §2.3 example (all project additions, listed so nothing is silent):

1. `description` adds "not for routine edits".
2. Return item 8: a status, exactly one of the five §2.7 values (`COMPLETE`, `PARTIAL`, `BLOCKED`, `CONFLICTED`, `UNVERIFIED`).
3. "Label anything you did not inspect as a hypothesis."
4. "If you cannot inspect the repository with the tools you have, say so and return BLOCKED" (see risk R-1 below).
5. Header comments cite the source and the limits of the read-only claim.

## 4. Claims and enforcement

| # | Claim | Enforcement point | State | Evidence / limit |
| --- | --- | --- | --- | --- |
| 1 | The file uses the documented schema: three required fields, only documented optional keys | n/a (format) | **documented**; **statically checked** | Subagents page; `validate_agents.py` (23/23 mutations detected). No CLI command was found that parses an agent file, so the file is **not locally accepted by Codex** |
| 2 | Codex discovers the agent from `.codex/agents/` and can spawn it by name | Codex | **unverified** | Needs a trusted project and a model session. The 0.166.0 rendered prompt lists no agent roster (S06 probe `customAgentName=False`, untrusted scratch), so it is not evidence either way. `BLOCKED: operator` + paid session |
| 3 | `features.shell_tool = false` removes command execution for this agent | Codex (documented capability reduction) | **documented**; partially probed | `codex -c features.shell_tool=false debug prompt-input` dropped the `write_stdin` tool from the rendered prompt but `exec_command` still appears in prompt text in both runs, so the probe is inconclusive and the rendered prompt is not a stable interface. The `-c` flag sets the whole session, not an agent file, so it does not exercise the agent path |
| 4 | The agent will not edit files | **Advisory** (instruction) | **unenforced** | Docs: custom agent instructions "don't create a separate read-only sandbox"; `shell_tool = false` does not remove `apply_patch`. A real read-only boundary needs the parent session in `--sandbox read-only` |
| 5 | The agent inherits the parent's sandbox and approvals | Codex | **documented** | Same page; not observed |
| 6 | The agent returns a status and evidence | **Advisory** | unenforced | Phase 4 `SubagentStop` could reinforce it; not built |
| 7 | Edits to this directory by Codex at runtime are refused or need the operator | Codex sandbox (protected path) | documented; helper-observed denial; model-session outcome unverified | S06 row 9. The operator workflow for control-plane changes applies (BLUEPRINT file-ownership table) |

### Residual risks

- **R-1 (usefulness unverified).** The architect must inspect the repository. Whether an agent with `features.shell_tool = false` can still
  read files (file reads may go through the shell tool) is not documented in the pages read and was not observed. If it cannot, the agent
  will return `BLOCKED` by its own instruction and the blueprint's `shell_tool = false` choice will need to be revisited. Do not rely on this
  agent for real work until a trusted model session shows it can read files.
- **R-2 (routing unverified).** Delegation to this agent depends on the parent following `AGENTS.md` delegation guidance and the agent
  description; Codex does not spawn agents automatically (BLUEPRINT §2.1). Unmeasured.
- **R-3 (single agent).** §2.3's roster has ten specialists. Only this one exists; §2.9's "minimal overlap" is vacuously true until a second is added.

## 5. Failure behavior

A malformed agent file: how Codex reacts (ignore, warn, or fail to start) is **unverified**; no hook or policy depends on it. The validator
fails closed on unparseable TOML, missing required fields, unknown or ignored keys, built-in name clashes, name/filename mismatch, a
`[features]` table that captures later keys, and a missing `shell_tool = false` for analysis-only agents.

## 6. Static results

| Command | Result |
| --- | --- |
| `python -I tools/control_plane/validate_agents.py --self-test` | `self-test: 23/23 mutations detected by the intended check`, `PASS` |
| `python -I tools/control_plane/validate_config.py --codex --self-test` | regression: `self-test: 15/15 mutations detected by the intended check`, `PASS` |
| `python -I tools/control_plane/validate_contracts.py --codex --self-test` | regression: first run **FAILED** (it guards the claim "no custom agents" while `.codex/agents` exists); after updating `contracts.md` (Delivered controls) and removing the custom-agents entry from the validator's `NOT_DELIVERED` list, `self-test: 29/29 mutations detected by the intended check`, `PASS`. The guard was retired for that one item because the claim it protected was removed; no assertion about rules or hooks was weakened. Nothing now checks that `contracts.md` names each delivered agent (limitation) |

`validate_classification.py` is not on `main` (PR #8) and was not run.

## 7. Acceptance (P2-S01)

Static: **PASS**. Discovery, spawn, and shell-tool behavior: **unverified**, `BLOCKED: operator` plus a paid model session that needs the
project owner's approval. Slice status: **PARTIAL**. Phase 2 status: **PARTIAL** (one of ten specialists; §2.9 runtime criteria unmet).

## 8. Reproduce

```bash
python -I tools/control_plane/validate_agents.py --self-test
# Operator, later (paid, interactive): trust the path, then ask Codex to spawn `architect` for a read-only mapping task and
# record the spawn event, whether it could read files, and its returned status.
```
