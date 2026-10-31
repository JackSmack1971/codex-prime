# P2-S03 Built-in Agents and Spawn Interface on Codex 0.166.0 — CODEX PRIME

Scope: BLUEPRINT.md v1.2 §2.1 and §2.9 criterion 1 ("native built-in agents identified"): what the documentation says about built-in and
custom agents, and what the installed binary exposes to the model for spawning them. Checked **2026-10-31**, `codex-cli 0.166.0`, Windows 11
build 22631, Git Bash, `python -I`. Base: `origin/main` `7a53e0dab1df2dfa1700633250b8c640c2fc5016`. No model session, `codex exec` or
operator check was run.

Started while **Phase 1 is PARTIAL** on the project owner's decision; its open evidence is unresolved (O-A, O-B, O-I, O-J `BLOCKED: operator`;
S05 open; C1 persists). This slice adds new files only and does not touch any file changed by an open PR.

State words: **documented** (official page), **observed locally** (0.166.0 binary, no model turn), **unverified**.

## 1. Documented

Source: `https://learn.chatgpt.com/docs/agent-configuration/subagents`, opened 2026-10-31 through the docs MCP, full page.

- Built-in agents: `default` (general-purpose fallback), `worker` (execution-focused), `explorer` (read-heavy exploration).
- Custom agents are TOML files under `.codex/agents/` or `~/.codex/agents/`; Codex "identifies the custom agent by its `name` field"; a custom
  agent whose name matches a built-in takes precedence.
- Subagents spawn when the user asks directly or when applicable `AGENTS.md` or skill instructions request it; they inherit the parent's
  sandbox and approvals.
- The page does not describe the tool-call parameters the model uses to pick an agent.

## 2. Observed locally (tool: `tools/control_plane/probe_spawn_interface.py`)

`codex debug prompt-input` renders the prompt and tool definitions the model sees. Launched from this repository's root (no `.codex/agents/`
on `main`; project trust not read, so it is unknown whether the project layer was active). The probe output on 0.166.0:

| Item | Observed |
| --- | --- |
| `spawn_agent` definitions found | exactly one |
| Parameters | `fork_turns`, `message`, `model`, `reasoning_effort`, `task_name` |
| Required | `message`, `task_name` |
| `additionalProperties` | `false` |
| Encrypted parameters | `message` (flagged `encrypted: true` in the schema) |
| Selector-like parameter (name matching agent, role, type, persona or profile, other than `task_name`) | **none** |
| Model override ids listed in the tool description | `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6.1-terra`, `gpt-6-sol`, `gpt-6-luna` (account/build specific; do not pin) |
| Names `default`, `worker`, `explorer` anywhere in the rendered prompt | 0 matches |
| Features | `multi_agent` stable `true`; `multi_agent_v2` stable `false`; `multi_agent_mode` `removed`; `multi_agent_v2_dynamic_tools` under development `false` |

The same probe on 0.162.1 was not run, so no version difference is claimed.

## 3. What this does not establish

| Question | State |
| --- | --- |
| Which built-in agents exist at runtime | **documented only**; no runtime evidence. §2.9 criterion 1 stays unmet beyond documentation |
| How the model selects `explorer`, `worker` or a custom agent by name | **unverified.** The rendered `spawn_agent` schema has no selector. Possible explanations, none tested: a selector appears only when a trusted project defines agents; selection happens through `message` or `task_name` text; built-in roles are internal |
| Whether a custom agent file adds anything to this schema | **unverified**; needs a trusted project with an agent file and a rendered prompt from that session, or a model session |
| Whether spawn prompts are readable in session output | **unverified.** `message` is marked encrypted in the schema; how `codex exec --json` presents it was not observed |
| Whether `fork_turns` or model overrides interact with agent files | unverified |

## 4. Conflict recorded (not resolved)

**C2.** Documentation says agents are identified and spawned by name (built-in and custom), but the 0.166.0 `spawn_agent` interface shown to the
model has no agent-name or role parameter. Per the project rule, work that depends on spawn-by-name is `BLOCKED: evidence` until it is observed
in a trusted session. That includes relying on a custom agent being selectable from its `description`, and any tooling that assumes spawn
prompts are plain text in event streams. C2 is independent of C1 (`codex sandbox` subcommands).

## 5. Static results (my runs; not independently reproduced)

| Command | Result |
| --- | --- |
| `python -I tools/control_plane/probe_spawn_interface.py --self-test` | `self-test: 9/9 cases behaved as intended`, `PASS` (synthetic documents: found, nested, selector detected, absent tool, two definitions, non-JSON) |
| `python -I tools/control_plane/probe_spawn_interface.py` | exit 0; the table in §2 |
| `python -I tools/control_plane/validate_config.py --codex --self-test` | regression: 15/15, PASS |
| `python -I tools/control_plane/validate_contracts.py --codex --self-test` | regression: 29/29, PASS |

Failure behavior of the probe: codex missing, non-zero exit, timeout, non-JSON output, or zero/multiple `spawn_agent` definitions all exit 2
(never 0). The rendered prompt is not a documented or stable interface, so a future version may change the format and the probe will then
fail closed rather than report an old shape.

## 6. Acceptance (P2-S03)

Documentation: complete. Local observation: complete for this binary and launch directory. Runtime identification of built-in agents and
spawn-by-name: **unverified**, `BLOCKED: operator` plus a paid session that the project owner has not approved. Slice status: **PARTIAL**.
Phase 2 remains **PARTIAL**.

## 7. Reproduce

```bash
python -I tools/control_plane/probe_spawn_interface.py --self-test
python -I tools/control_plane/probe_spawn_interface.py
```
