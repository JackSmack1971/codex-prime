# Native Capabilities Matrix — CODEX PRIME (P0-S02)

Scope: BLUEPRINT.md v1.1 §0.3 (25 capability groups). Authority order per `CLAUDE.md`: (1) installed
`codex` binary, (2) official Codex documentation, (3) `openai/codex` at the installed tag, (4) discovery only.
Captured 2026-10-13 on Windows 11 Pro build 22631, native `codex.exe`. Sanitized: user-home paths are
omitted, no credential file was opened, and user `config.toml` was touched only for retired-token **counts**.

**installed_version: `codex-cli 0.162.1`** (probe B1). Every row below applies to that version only; re-run the
probes in §9 after any upgrade.

## 1. Reading this file

State vocabulary (BLUEPRINT §0.1). A state is claimed only where the named evidence exists.

| State | Meaning here |
| --- | --- |
| DOCUMENTED | Stated in the official docs pages listed in §3 |
| INSTALLED | Present in the installed binary (help text, feature list, or the config loader recognizes the key) |
| INITIALIZED | The binary accepted the value, or the feature is enabled, without error |
| RUNTIME-TESTED | Real behavior observed (a sandboxed command, `debug prompt-input`, `execpolicy check`) |
| UNSUPPORTED | Binary rejects it or the docs say it is removed |
| UNVERIFIED | Not checked, or checkable only through a paid model session |
| BLOCKED: operator | Needs the interactive TUI, project trust, hook trust, or user-level configuration |
| ENV-LIMITED | Failed for a reason specific to this host or build, not a statement about Codex |

`syntax_verified` means a key/value was **accepted by the binary's config loader**. It does not mean a
project `.codex/config.toml`, `hooks.json`, agent file, or skill was loaded by a trusted session.

Evidence IDs: **B*n*** = binary probe (§4), **D*n*** = doc page (§3), **S01** = `baseline-report.md`.
No paid `codex exec`/`codex review` session was run in this slice, so nothing that needs a model turn is
RUNTIME-TESTED.

## 2. Summary

| # | Capability | Documented | Installed / initialized | Runtime-tested | Blocker / note |
| --- | --- | --- | --- | --- | --- |
| 1 | Project-level configuration | yes | keys recognized | no | project trust: BLOCKED: operator |
| 2 | Instruction hierarchy | yes | yes | **partial** (prompt-input) | override files, size cap untested |
| 3 | Built-in agents | yes | `multi_agent` enabled | no | model session needed |
| 4 | Custom agent definitions | yes | keys recognized | no | trusted project + model session |
| 5 | Subagent spawning/coordination | yes | `agents.*` recognized | no | model session needed |
| 6 | Repository skill discovery | yes | yes | **yes** (prompt-input) | |
| 7 | Explicit skill invocation | yes | n/a | no | interactive TUI |
| 8 | Skill metadata and references | yes | yes | **partial** | only `name`/`description` safe |
| 9 | Planning | yes | built in | no | interactive TUI |
| 10 | Native code review | yes | `review` subcommand | no | paid session |
| 11 | Sandbox modes | yes | enums verified | **yes** (`codex sandbox`) | MXC ENV-LIMITED |
| 12 | Approval policies | yes | enums verified | no | `exec` has no approval flag |
| 13 | Execution rules | yes | `execpolicy check` works | **yes** (offline) | offline check does not split wrappers |
| 14 | Hooks and event payloads | yes | feature enabled, `hooks` table recognized | no | hook trust: BLOCKED: operator |
| 15 | Context compaction | yes | keys recognized | no | interactive TUI |
| 16 | Noninteractive execution | yes | `exec` help verified | no | paid session |
| 17 | Session resume/continuation | yes | subcommands present | no | needs saved session |
| 18 | Windows and WSL behavior | yes | native sandbox works | **partial** | WSL Codex unconfirmed; MXC ENV-LIMITED |
| 19 | Protected paths | yes | n/a | **yes** (`codex sandbox`) | via permission profile, native Windows only |
| 20 | Command network access / `network_proxy` | yes | `network_proxy` experimental, off | **partial** (network off observed) | proxy domain policy untested |
| 21 | Permission profiles (beta) | yes | flags and keys recognized | **partial** | silent precedence vs `sandbox_mode` |
| 22 | Automatic approval review | yes | enum + `guardian_approval` enabled | no | paid session |
| 23 | Goals and plan mode | yes | `goals` enabled | no | interactive TUI |
| 24 | Hosted tools outside the sandbox | yes | `web_search` enum verified | no | |
| 25 | Retired/deprecated settings | yes | **rejections observed** | no (loader/syntax evidence only) | none present in loaded layers |

## 3. Official documentation used (source 2)

Base: `https://learn.chatgpt.com/docs/`. The Codex docs now live under this host; searches did not return
Codex pages on `developers.openai.com`. Retrieval path is recorded because the docs MCP is the preferred
route: **MCP** = fetched through the `openaiDeveloperDocs` server; **HTTP** = the same host's `.md` twin
fetched with `curl` and searched with `grep` (not read in full).

| ID | Page (relative to base) | Retrieval | Used for |
| --- | --- | --- | --- |
| D1 | `hooks` | MCP, full | hooks (14), compaction hooks, hosted-tool coverage |
| D2 | `agent-approvals-security` | MCP, full | sandbox, approvals, protected paths, network, web search, retired policy |
| D3 | `config-file/config-basic` | MCP, full | precedence, trust, feature flags, `web_search` |
| D4 | `config-file/config-reference` | HTTP, grep | key names, enums, ignored project keys |
| D5 | `agent-configuration/subagents` | MCP, full | built-in/custom agents, `agents.*` |
| D6 | `agent-configuration/agents-md` | MCP, full | instruction chain |
| D7 | `agent-configuration/rules` | MCP, full | `prefix_rule`, wrapper splitting |
| D8 | `build-skills` | MCP, full | skill locations, metadata, invocation |
| D9 | `non-interactive-mode` | MCP, full | `codex exec` |
| D10 | `developer-commands` | HTTP, grep | CLI subcommands, slash commands |
| D11 | `permissions` | MCP, full | permission profiles |
| D12 | `windows/windows-sandbox` | HTTP, grep | Windows sandbox implementations, MXC |
| D13 | `windows/wsl` | MCP, full | WSL |
| D14 | `code-review` | HTTP, grep | local review |
| D15 | `sandboxing/auto-review` | HTTP, head + headings only | auto-review |

Source 3 (repository at the installed tag): **not used.** Context7 lists `openai/codex` versions up to
`rust-v0.155.1`; there is no entry for 0.162.1, and `CLAUDE.md` forbids `main` and mismatched tags.
Source 4 (Exa): not used.

## 4. Binary probes (source 1)

Run from `C:\TEST-repos\codex-prime` (or the scratch repo noted) in PowerShell 7.6.2 or Git Bash 5.2.37;
none of them starts a model turn.

| ID | Probe | Result recorded |
| --- | --- | --- |
| B1 | `codex --version` | `codex-cli 0.162.1` |
| B2 | `--help` for root, `exec`, `review`, `resume`, `fork`, `sandbox`, `debug`, `features`, `mcp`, `execpolicy check` | Flag inventories used in rows 10, 16, 17, 22 |
| B3 | `codex features list` | 167 flags; used for stage/enabled facts |
| B4 | `codex -c <key>=<poison> features list` (type-poisoning) | A **wrong-typed value is rejected only if the loader knows the key**; unknown keys are silently accepted (`-c bogus_key=1` exits 0). A rejection is therefore evidence for INSTALLED **for top-level and non-`features` keys only**; under `features.*` any non-boolean value is rejected whether or not the flag exists (`features.totally_bogus_flag="x"` → "expected a boolean"), so B4 cannot prove a feature flag exists. Feature flags are evidenced by B3 (`codex features list`); the `features.codex_hooks` alias is evidenced by behavior: `-c features.codex_hooks=false` turns `hooks` to `false` in `features list`, while `-c features.totally_bogus_flag=false` leaves it `true`. `--strict-config` is **not supported** by `features` ("`--strict-config` is not supported for `codex features`"). |
| B5 | `codex execpolicy check --rules <file>` against a scratch rules file | Rows 13, 25 |
| B6 | `codex debug prompt-input` in a scratch Git repo (root and nested launch dirs) containing `AGENTS.md`, `sub/AGENTS.md`, `.agents/skills/demo-skill`, `.codex/agents/demo.toml` | Rows 2, 6, 8 |
| B7 | `codex sandbox [-P <profile>] -- <cmd>` in the scratch repo | Rows 11, 19, 20, 21 |
| B8 | `codex mcp list` | "No MCP servers configured yet." |
| B9 | `codex -c windows.sandbox=mxc sandbox --permission-profile :workspace -- cmd.exe /d /c echo MXC_OK` | `Error: failed to prepare MXC sandbox: native MXC is unavailable on this executor` |

The scratch repo is a throwaway repository in session temp space. It is untrusted by definition, so B6/B7
results about `.codex/` content are about an **untrusted** project.

### B4 key-recognition results

"Recognized" = the loader rejected a wrong-typed value, so the key exists in 0.162.1. Value domains are the
error text the binary printed.

| Key | Recognized | Binary-reported domain |
| --- | --- | --- |
| `approval_policy` | yes | `untrusted`, `on-failure`, `on-request`, `granular`, `never` (`untrusted` then rejected, row 25) |
| `sandbox_mode` | yes | `read-only`, `workspace-write`, `danger-full-access` |
| `approvals_reviewer` | yes | `user`, `auto_review`, **`guardian_subagent`** (third value undocumented in D2/D4 excerpts read; do not use) |
| `web_search` | yes | `disabled`, `cached`, `indexed`, `live` |
| `default_permissions` | yes | `":workspace"` accepted with no table; an unknown name → "requires a `[permissions]` table" |
| `permissions`, `hooks`, `projects`, `mcp_servers`, `otel`, `notify` | yes | table/sequence types |
| `windows.sandbox` | yes | `elevated`, `unelevated`, `mxc` |
| `project_doc_max_bytes`, `project_doc_fallback_filenames`, `model_auto_compact_token_limit`, `review_model` | yes | usize / sequence / i64 / string |
| `features.hooks`, `.multi_agent`, `.goals`, `.shell_tool`, `.apps`, `.plugins`, `.memories`, `.request_permissions_tool`, `.guardian_approval`, `.prefer_mxc` | **B3, not B4** (listed in `codex features list`) | boolean; B4 type errors here prove nothing |
| `features.codex_hooks` | yes — live alias of `hooks` (alias behavior test above) | boolean |
| `agents.enabled`, `.interrupt_message` | yes | boolean |
| `agents.max_concurrent_threads_per_session`, `agents.max_threads` | yes | usize |
| `agents.default_subagent_model`, `.default_subagent_reasoning_effort` | yes | string |
| `sandbox_workspace_write.network_access`, `allow_login_shell` | yes | boolean |
| `shell_environment_policy.ignore_default_excludes` | yes (P1-S03) | boolean; `"x"` → `failed to load bootstrap configuration`, `false` accepted. D3/D4: default **true** (no automatic `*KEY*`/`*SECRET*`/`*TOKEN*` filtering); `false` applies it |
| `history.persistence`, `shell_environment_policy.inherit`, `tui.resume_cwd` | yes | `save-all`/`none`; `core`/`all`/`none`; `current`/`session` |
| `skills.max_context_tokens`, `.bundled.enabled`, `.include_instructions` | yes | nonzero usize / boolean |
| `log_dir`, `auto_review.policy`, `model_reasoning_effort` | yes | path string / string / string |
| `profile` | yes, **rejected** | "legacy `profile = ...` config is no longer supported; use `--profile`" |
| `features.network_proxy` | yes | boolean or table ("data did not match any variant of untagged enum FeatureToml" for `"x"`/`1`) |
| `project_root_markers` | yes | array of strings ("must be an array of strings") |
| `tools.web_search.allowed_domains` | yes | typed ("did not match any variant of untagged enum WebSearchToolConfigInput"); an unrelated `tools.web_search.bogus=1` is accepted |

## 5. Capability entries

Common to every entry: `installed_version` = `codex-cli 0.162.1`.

### 1. Project-level configuration

| Field | Value |
| --- | --- |
| official_reference | D3 (precedence, trust), D4 (ignored keys) |
| config_location | `<repo>/.codex/config.toml`, root-to-cwd layering; highest precedence is `-c`/flags. Loads **only for a trusted project**. Trust is `[projects."<path>"] trust_level` in user config (operator-only). |
| states | DOCUMENTED; INSTALLED (keys in B4); INITIALIZED: no project config exists; RUNTIME-TESTED: no |
| syntax_verified | Per-key via B4 only. No project `config.toml` was parsed. |
| runtime_verified | No. Trust for this project is not set (S01 U1). **BLOCKED: operator** |
| limitations | Untrusted projects skip the whole project `.codex/` layer (config, hooks, rules). Codex ignores `openai_base_url`, `chatgpt_base_url`, `apps_mcp_product_sku`, `model_provider`, `model_providers`, `notify`, `profile`, `profiles`, `experimental_realtime_ws_base_url`, `otel` in a project file (D4). Trust-gated `.codex/` also means nothing in this layer can be assumed active in CI/`exec` without the operator trusting the path. |
| fallback | Pass the critical settings explicitly as `-c key=value` flags in the documented launch command (flags outrank every file layer, D3), and have `AGENTS.md` instruct the agent to report if the project layer is not active. |

### 2. Instruction hierarchy

| Field | Value |
| --- | --- |
| official_reference | D6 |
| config_location | `~/.codex/AGENTS.override.md` or `AGENTS.md` (first non-empty), then per directory from project root to cwd: `AGENTS.override.md`, `AGENTS.md`, `project_doc_fallback_filenames`; one file per directory; concatenated root-first |
| states | DOCUMENTED; INSTALLED; INITIALIZED; RUNTIME-TESTED: **partial** |
| syntax_verified | `project_doc_max_bytes`, `project_doc_fallback_filenames` recognized (B4) |
| runtime_verified | **Partial (B6).** In an untrusted scratch repo: a root `AGENTS.md` sentinel appeared in the model-visible prompt when launched at the root; launching from `sub/dir` added `sub/AGENTS.md` as well. S01: from this repo's root, the `AGENTS.md` files in two ancestor directories above the repo were not injected. Not tested: `AGENTS.override.md`, fallback names, the 32 KiB cap, global file (none exists). |
| limitations | Loaded only from the project root down to the launch directory, so a nested launch sees more files than a root launch. Project root is typically the Git root (D6); `project_root_markers` can change it. Size cap `project_doc_max_bytes` (default 32 KiB per D6). Instruction loading did **not** require trust in the B6 scratch case; do not extend that to `.codex/` content. |
| fallback | Keep the root `AGENTS.md` under the cap and self-contained; do not depend on nested files being loaded when launched from the root. |

### 3. Native built-in agents

| Field | Value |
| --- | --- |
| official_reference | D5 |
| config_location | Built in: `default`, `worker`, `explorer`. A custom agent with the same name takes precedence. |
| states | DOCUMENTED; INSTALLED (`multi_agent` stable, enabled — B3); INITIALIZED (enabled); RUNTIME-TESTED: no |
| syntax_verified | `agents.enabled` recognized (B4); `multi_agent` is a listed flag (B3) |
| runtime_verified | No. Needs a model session. |
| limitations | Spawned only on a direct request or applicable `AGENTS.md`/skill instruction (D5). Subagents inherit the parent's sandbox and approvals. A `multi_agent_v2` flag exists (stable, off — B3); it is not described in the pages read, so it is not used. |
| fallback | Single-agent sequential execution; `AGENTS.md` must state delegation is optional. |

### 4. Custom agent definitions

| Field | Value |
| --- | --- |
| official_reference | D5 |
| config_location | `.codex/agents/*.toml` (project), `~/.codex/agents/` (user). Required: `name`, `description`, `developer_instructions`. Optional: `model`, `model_reasoning_effort`, `model_reasoning_summary`, `model_verbosity`, `features.shell_tool`/`apps`/`plugins`/`memories`/`request_permissions_tool = false`, `skills.config`, `skills.bundled.enabled`, `skills.include_instructions`. Name in the file is the identity. |
| states | DOCUMENTED; INSTALLED (feature flags listed in B3; `skills.*` keys recognized — B4); INITIALIZED: no agent file exists; RUNTIME-TESTED: no |
| syntax_verified | `skills.*` per B4; the `features.*` names are the B3 flag list. No agent TOML was loaded by Codex: `debug prompt-input` does not list agents and the scratch project was untrusted. |
| runtime_verified | No. **BLOCKED: operator** (trust) plus a model session. |
| limitations | A custom agent **cannot** override `sandbox_mode`, `approval_policy`, `model_provider`, or `mcp_servers`; those inherit the parent (D5). Instructions can ask an agent not to edit but do not create a read-only sandbox. Capability limiting is by feature flags only. Claude-style `.claude/agents/*.md` and `tools:` are not read. |
| fallback | Express roles as skills plus `AGENTS.md` conventions; enforce read-only roles through the parent's sandbox/profile, not through agent text. |

### 5. Subagent spawning and coordination

| Field | Value |
| --- | --- |
| official_reference | D5; hooks `SubagentStart`/`SubagentStop` in D1 |
| config_location | `[agents]` in config: `enabled`, `max_concurrent_threads_per_session`, `default_subagent_model`, `default_subagent_reasoning_effort`, `interrupt_message`. Interactive control: `/subagents`. |
| states | DOCUMENTED; INSTALLED; INITIALIZED (loader accepts); RUNTIME-TESTED: no |
| syntax_verified | All five `agents.*` keys recognized (B4) |
| runtime_verified | No. Needs a model session. |
| limitations | Non-interactive runs: an action needing new approval fails and the error returns to the parent (D5). Read-heavy parallelism is advised; parallel writers conflict. `agents.max_threads` is a legacy alias; the loader still accepts it with no warning observed (row 25). Subagent hooks do not run `SessionEnd`/`Interrupt` (D1). |
| fallback | Sequential single-agent work; set `agents.enabled = false` if delegation proves unsafe. |

### 6. Repository skill discovery

| Field | Value |
| --- | --- |
| official_reference | D8 |
| config_location | `.agents/skills/<name>/SKILL.md` in every directory from cwd up to the repo root; also `~/.agents/skills`, `/etc/codex/skills`, bundled system skills. Same-name skills are not merged. |
| states | DOCUMENTED; INSTALLED; INITIALIZED; RUNTIME-TESTED: **yes** |
| syntax_verified | `skills.*` keys recognized (B4) |
| runtime_verified | **Yes (B6).** `demo-skill` with a sentinel description appeared, with its description, in the model-visible prompt from the scratch repo root **and** from a nested launch directory; the scratch repo was untrusted, so repo-skill discovery did not need project trust there. S01: this host already lists 47 skills (43 user, 4 system) at the repo root, none with BLUEPRINT §3.3 names. |
| limitations | Skill names collide across scopes without merging, so a user-level and a project skill with the same name can both appear in selectors (D8). The initial list is budgeted (about 2% of context or 8,000 characters; `skills.max_context_tokens` up to 10,000, D8) and may drop skills with a warning. Changes are auto-detected; restart if not. |
| fallback | Keep skill `description`s short and front-loaded; reference skills by exact name in `AGENTS.md`; run the collision check from BLUEPRINT §3.6 before claiming a name is unique. |

### 7. Explicit skill invocation

| Field | Value |
| --- | --- |
| official_reference | D8, D10 |
| config_location | Prompt text `$skill-name`, or `/skills` in the interactive CLI |
| states | DOCUMENTED; binary support UNVERIFIED (`/skills` is only listed in D10); RUNTIME-TESTED: no |
| syntax_verified | n/a |
| runtime_verified | No. Interactive TUI. **BLOCKED: operator** |
| limitations | `agents/openai.yaml` with `policy.allow_implicit_invocation: false` removed the skill from the model-visible skill list in B6, so such a skill is reachable only if explicit `$name` invocation still works for it; D8 says it does, and that is **unverified here**. |
| fallback | Name the skill and its `SKILL.md` path in the task prompt or `AGENTS.md` so the agent reads it by path. |

### 8. Skill metadata and references

| Field | Value |
| --- | --- |
| official_reference | D8 |
| config_location | `SKILL.md` frontmatter `name` and `description` (required); optional `scripts/`, `references/`, `assets/`; optional `agents/openai.yaml` (`interface`, `policy.allow_implicit_invocation`, `dependencies.tools`) |
| states | DOCUMENTED; INSTALLED; RUNTIME-TESTED: **partial** |
| syntax_verified | Frontmatter parsed well enough that `name` and `description` rendered into the prompt (B6) |
| runtime_verified | Partial. Observed: description text reaches the prompt; `allow_implicit_invocation: false` hides the skill from the list. Not observed: reference loading, script execution. |
| limitations | Only `name`/`description` are documented frontmatter. Claude-style `allowed-tools` is not documented and must not be relied on. `dependencies.tools` can name an MCP server, which conflicts with the "no MCP in delivered config" rule — leave it out. |
| fallback | Put policy in prose in `SKILL.md` and in `agents/openai.yaml` only for `allow_implicit_invocation`. |

### 9. Planning

| Field | Value |
| --- | --- |
| official_reference | D10 (`/plan`), D1 (`update_plan` visible to hooks), D9 (plan updates in `--json` items) |
| config_location | Interactive `/plan [prompt]`; unavailable while Codex is already working |
| states | DOCUMENTED; binary support UNVERIFIED (docs only); RUNTIME-TESTED: no |
| syntax_verified | n/a |
| runtime_verified | No. **BLOCKED: operator** (TUI). Whether `codex exec` can enter plan mode is undocumented in the pages read. |
| limitations | The binary reports a `collaboration_modes` flag as "removed"; the docs still document `/plan`. Treat plan mode as UI behavior, not a configurable contract. |
| fallback | Have the agent write the plan as a message or a file under `.codex-runtime/` before editing. |

### 10. Native code review

| Field | Value |
| --- | --- |
| official_reference | D10, D14 |
| config_location | `codex review [--uncommitted \| --base <BRANCH> \| --commit <SHA> [--title]] [PROMPT]`; `codex exec review`; `/review`; `review_model` in config |
| states | DOCUMENTED; INSTALLED (B2); INITIALIZED; RUNTIME-TESTED: no |
| syntax_verified | `review_model` recognized (B4); flags per B2 help |
| runtime_verified | No. A review is a paid model session. |
| limitations | The three targets and a custom prompt are mutually exclusive; `--title` only with `--commit` (D10). `review` has no `--sandbox`/`--ask-for-approval` flags in B2 help. |
| fallback | Review with an explicit `codex exec --sandbox read-only` prompt, or a human/other-tool diff review. |

### 11. Sandbox modes

| Field | Value |
| --- | --- |
| official_reference | D2, D12 |
| config_location | `sandbox_mode` = `read-only` \| `workspace-write` \| `danger-full-access`; CLI `-s/--sandbox`; `[sandbox_workspace_write]`; Windows implementation `[windows] sandbox` = `elevated` \| `unelevated` \| `mxc` |
| states | DOCUMENTED; INSTALLED; INITIALIZED; RUNTIME-TESTED: **yes** (helper, not a model session) |
| syntax_verified | Enum values confirmed by the binary's error text (B4) |
| runtime_verified | **Yes (B7).** Native Windows `codex sandbox`: default and `:workspace` profile run commands; `:workspace` can write a workspace file; `:read-only` cannot write; writes to protected directories are denied (row 19); outbound HTTP is blocked (row 20). The `[windows] sandbox` value in user config was not read, so which implementation ran is not recorded. MXC: **ENV-LIMITED** — `native MXC is unavailable on this executor` (B9); D12 requires Windows 11 build 26100.9278 or later and this host is 22631. |
| limitations | `codex sandbox` here takes the command directly with an optional `-P/--permission-profile`; the `linux`/`macos`/`windows` subcommands in BLUEPRINT §0.2 and D2 do not exist on this Windows build (S01), and D12's `codex sandbox setup --elevated …` is absent: `codex sandbox --help` lists only `uninstall`. D2/D12 call `elevated` and `unelevated` legacy fallbacks. Sandbox probes exercised the permission-profile path, not `sandbox_mode = "workspace-write"` from a config file. |
| fallback | Run `codex exec --sandbox read-only` unless writes are required; never choose `danger-full-access` without operator approval. |

### 12. Approval policies

| Field | Value |
| --- | --- |
| official_reference | D2, D3, D4 |
| config_location | `approval_policy` = `on-request` \| `never` \| `granular` (table form); interactive `-a/--ask-for-approval` accepts only `on-request`, `never` (B2) |
| states | DOCUMENTED; INSTALLED; INITIALIZED; RUNTIME-TESTED: no |
| syntax_verified | Enum from binary: `untrusted` (rejected), `on-failure`, `on-request`, `granular`, `never` (B4) |
| runtime_verified | No. |
| limitations | **`codex exec` has no `-a/--ask-for-approval` flag** (B2; `codex exec -a never` → "unexpected argument"), contradicting the `CLAUDE.md` runtime-verification instruction. The documented routes are `-c approval_policy="..."` (accepted by the loader; effect unverified) and `--approve-for-me`, which routes approvals through automatic review **using the workspace-write sandbox** (it also selects a sandbox; not a read-only option). In non-interactive runs, an action needing approval fails (D5). A `granular` policy is documented (D2) but its table shape was not parse-tested. |
| fallback | Set the policy with `-c approval_policy=...` and confirm it from the `--json` event stream (thread/turn items) before trusting it; default to the most restrictive sandbox so approvals are rarely needed. |

### 13. Execution rules

| Field | Value |
| --- | --- |
| official_reference | D7 |
| config_location | `rules/*.rules` next to an active config layer: `~/.codex/rules/` and `<repo>/.codex/rules/` (project rules load only when trusted). Starlark `prefix_rule(pattern, decision, justification, match, not_match)`. |
| states | DOCUMENTED; INSTALLED (`codex execpolicy check`, "preview"); RUNTIME-TESTED: **yes** (offline) |
| syntax_verified | **Yes (B5).** Valid file parsed; `decision="ask"` rejected as a Starlark error; a `match` example that no rule matches fails the load ("unmatched examples"). |
| runtime_verified | Offline checker only. Exact-prefix commands match (`git push origin main` → `prompt`; `git status` → `allow`). Multiple files/rules: strictest wins (`allow` + `prompt` + `forbidden` → `forbidden`). **Not matched by the offline checker:** `git -C . push …`, `git --no-pager push …`, `bash -lc "git push …"`, `bash -lc "git status && rm -rf …"`, `pwsh -Command …`, `powershell.exe -Command …`, `cmd.exe /c …` — each returned `{"matchedRules":[]}`. D7 says Codex splits simple `bash -lc` chains at runtime and evaluates each command; the offline checker does **not** do that, so splitting is **UNVERIFIED** here. |
| limitations | D7 marks rules "experimental and may change". Rules are literal argv-prefix matches, so reordered global options (`git -C`) evade them; unmatched commands fall through to normal approval/sandbox. PowerShell and `cmd` wrappers are not documented as split. Rules apply only to commands Codex would run **outside** the sandbox. The user's `default.rules` is 59 allow-only entries (S01) and applies in addition to any project rules. `--ignore-rules` disables them (operator-only for this project). |
| fallback | Enumerate each dangerous argv form as its own rule (include `git -C`, `git -c`, `--no-pager` variants), add a `PreToolUse` hook as a second layer, and rely on the sandbox for containment. CLAUDE.md's "reordered and shell-wrapped" test requirement cannot be fully met with `execpolicy check` alone; wrapper behavior needs a runtime test (**BLOCKED: operator / paid session**). |

### 14. Hooks and event payloads

| Field | Value |
| --- | --- |
| official_reference | D1 |
| config_location | `hooks.json` or inline `[hooks]` next to an active layer (`~/.codex/`, `<repo>/.codex/`); pick one per layer. Project hooks load only for a trusted project; non-managed hooks must be reviewed in `/hooks` and are keyed to a hash. |
| states | DOCUMENTED; INSTALLED (`hooks` stable, enabled — B3; `hooks` table recognized — B4; `features.codex_hooks` alias behavior test); INITIALIZED: no hooks defined; RUNTIME-TESTED: no |
| syntax_verified | Only the table type (B4). No `hooks.json` was parsed by Codex. |
| runtime_verified | No. **BLOCKED: operator** (project trust, `/hooks` review). |
| limitations | Events: `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `SubagentStart`, `SubagentStop`, `Stop`, `Interrupt`. Handlers: `command` and `mcp_tool` run; `prompt`/`agent` are parsed and skipped. Matchers are regexes on tool name/source/trigger; `UserPromptSubmit`, `Stop`, `Interrupt` ignore `matcher`. **Blocking contract** for `PreToolUse`: `hookSpecificOutput.permissionDecision = "deny"` with a reason, the older `decision:"block"`, or exit code 2 with a stderr reason. `permissionDecision:"ask"`, legacy `decision:"approve"`, `continue`, `stopReason`, `suppressOutput` are unsupported there (`permissionDecision:"allow"` with `updatedInput` rewrites the call and is supported): the hook run fails **and the tool call proceeds**. `PermissionRequest` allow/deny shape differs and must not return `updatedInput`/`updatedPermissions`/`interrupt`. D1 states that an unsupported `PreToolUse` field marks the run failed and continues the tool call, and that MCP-hook errors do not block; that command-hook errors, timeouts and malformed output also fail open is an inference from CLAUDE.md, not a D1 quote. Hosted tools (for example `WebSearch`) are not covered; D1 calls tool hooks "a useful guardrail, not a complete enforcement boundary". Default timeout 600 s (`SessionEnd`/`Interrupt` 1 s, max 3 s). Windows override: `commandWindows` (`command_windows` in TOML). Plugin-bundled hooks also need trust. Large `additionalContext` spills to a temp-dir file. |
| fallback | Treat hooks as advisory; keep deny logic in `execpolicy` rules and the sandbox. Blocking hooks must return exit 2 on their own internal errors (CLAUDE.md). Use `command` handlers only. |

### 15. Context compaction

| Field | Value |
| --- | --- |
| official_reference | D10 (`/compact`), D4 (`model_auto_compact_token_limit`, `…_scope`), D1 (`PreCompact`, `PostCompact`, `SessionStart` source `compact`) |
| config_location | `/compact` (interactive); `model_auto_compact_token_limit` (number); scope `total` \| `body_after_prefix` |
| states | DOCUMENTED; INSTALLED (`model_auto_compact_token_limit` recognized — B4); RUNTIME-TESTED: no |
| syntax_verified | Limit key typed i64 (B4); scope key not probed |
| runtime_verified | No. `/compact` is interactive. **BLOCKED: operator** |
| limitations | `PreCompact` can stop compaction with `continue:false`; `PostCompact` runs after. Re-injection after compaction relies on a `SessionStart` hook matching `compact` (D1). |
| fallback | Keep durable state in files under `.codex-runtime/` and in `AGENTS.md`, not in chat context. |

### 16. Noninteractive execution

| Field | Value |
| --- | --- |
| official_reference | D9, D10 |
| config_location | `codex exec [OPTIONS] [PROMPT]`; stdin as prompt with `-`; `--json`, `-o/--output-last-message`, `--output-schema`, `--ephemeral`, `--sandbox`, `--approve-for-me` (implies the workspace-write sandbox), `--ignore-user-config`, `--ignore-rules`, `--skip-git-repo-check`, `-C`, `--add-dir`, `--color` |
| states | DOCUMENTED; INSTALLED (B2); INITIALIZED; RUNTIME-TESTED: no |
| syntax_verified | Flags from help; `--full-auto` → "unexpected argument" (UNSUPPORTED) |
| runtime_verified | No. Every `exec` run is a paid model session; none was run. The JSONL event schema (`thread.started`, `turn.started`, `turn.completed`, `turn.failed`, `item.*`, `error`) is DOCUMENTED, not observed. |
| limitations | Default sandbox is read-only (D9). A Git repo is required unless `--skip-git-repo-check` (operator-only here). `--ephemeral`, `--output-schema`, and `-o` require a prompt (D10). No approval flag (row 12). Progress goes to stderr; stdout carries only the final message unless `--json`. |
| fallback | Use `--json` and grade from events; if a run cannot be afforded, mark the dependent check `unverified` instead of simulating it. |

### 17. Session resume or continuation

| Field | Value |
| --- | --- |
| official_reference | D9, D10 |
| config_location | `codex resume [--last\|--all] [ID]`, `codex fork`, `codex exec resume [--last] [ID]`, `codex exec fork`, `/resume`, `/fork`; `tui.resume_cwd` |
| states | DOCUMENTED; INSTALLED (B2); RUNTIME-TESTED: no |
| syntax_verified | `tui.resume_cwd` recognized: `current` \| `session` (B4) |
| runtime_verified | No. Needs a saved session, which means a model session. |
| limitations | `--last` is scoped to the current working directory unless `--all`; D10 says resume does not accept `--worktree`, but `resume --help` lists the flag (conflict C9, runtime UNVERIFIED); `--ephemeral` runs persist nothing to resume. `resume`/`fork` interactive commands also accept `-a on-request\|never`, unlike `exec`. |
| fallback | Persist task state in `.codex-runtime/` files so a fresh session can continue without session resume. |

### 18. Windows and WSL behavior

| Field | Value |
| --- | --- |
| official_reference | D2, D12, D13 |
| config_location | `[windows] sandbox`, `features.prefer_mxc`, `/setup-default-sandbox`; WSL2 uses the Linux sandbox (bubblewrap) |
| states | DOCUMENTED; INSTALLED; RUNTIME-TESTED: **partial** |
| syntax_verified | `windows.sandbox` domain `elevated`/`unelevated`/`mxc`; `features.prefer_mxc` is a listed flag (B3: "under development") |
| runtime_verified | Native Windows sandbox helper: observed (rows 11, 19, 20). MXC: unavailable (B9, **ENV-LIMITED**, build 22631). WSL: distros `Ubuntu` and `docker-desktop` exist (S01); whether Codex is installed or the bubblewrap sandbox works inside WSL is **UNVERIFIED** (S01 U7); a bare `bash` on this host's PATH is the WSL launcher, not Git Bash (S01). |
| limitations | WSL1 is unsupported from Codex 0.115 (D2, D13). Docs advise keeping WSL repositories under the Linux home, not `/mnt/c`. In Git Bash, MSYS path conversion rewrites `cmd.exe /d /c …` arguments, so Windows-sandbox probes must run from PowerShell (observed: the command did not execute from Git Bash). Hook scripts need Windows-safe commands (`commandWindows`). `unelevated` has weaker network isolation and no denied-read support (D12). |
| fallback | Develop and test natively on Windows with PowerShell; treat WSL as an unverified alternative until the operator runs a WSL probe. |

### 19. Protected paths inside writable roots

| Field | Value |
| --- | --- |
| official_reference | D2, D11 |
| config_location | Built into `workspace-write` and the `:workspace` profile; profiles that `extends = ":workspace"` keep it |
| states | DOCUMENTED; RUNTIME-TESTED: **yes** (native Windows, permission-profile path) |
| syntax_verified | n/a |
| runtime_verified | **Yes (B7).** In a scratch Git repo with `:workspace`: a write to a normal file succeeded; creating `.codex\probe.txt`, `.git\probe.txt`, `.agents\probe.txt`, `.aws\probe.txt`, and a new `.codex\newdir` each failed with "Access is denied"; creating `.codex-runtime\a.txt` (new directory) **succeeded**. `:read-only` denied every write. |
| limitations | Observed through `codex sandbox`, not inside a model session and not through `sandbox_mode = "workspace-write"` from a config file. Only top-level creates were tested; a `.git` pointer file, symlinks, and deep recursion were not. The protection applies "when it exists as a directory" (D2) — verified for `.aws` only because it was pre-created in the scratch repo. |
| fallback | Never plan for Codex to write under `.codex/`, `.agents/`, or `.git/`; write runtime output to `.codex-runtime/` (confirmed writable above). |

### 20. Command network access and `network_proxy`

| Field | Value |
| --- | --- |
| official_reference | D2, D11 |
| config_location | `[sandbox_workspace_write] network_access`; `[features.network_proxy] enabled/domains/…` or `features.network_proxy = true`; profile `network.enabled` + `network.domains` |
| states | DOCUMENTED; INSTALLED (`network_proxy` experimental, **off** — B3; `sandbox_workspace_write.network_access` recognized — B4); RUNTIME-TESTED: **partial** |
| syntax_verified | `network_access` boolean verified; the `features.network_proxy` is typed boolean-or-table (B4) |
| runtime_verified | **Network off observed (B7):** `Invoke-WebRequest https://example.com` inside `codex sandbox` (default and `:workspace`) failed to connect, while the same call outside the sandbox returned HTTP 200. Enabling network, and the proxy's domain allow/deny, were **not** tested. |
| limitations | Domain rules do nothing unless command network is on **and** the proxy is on; proxy on with network off changes nothing (D2). Network-on + proxy-off means unrestricted direct egress. The proxy filters only sandboxed commands (row 24). |
| fallback | Keep network off. If a phase needs it, enable it explicitly with a narrow allowlist and proxy, and record the operator's approval. |

### 21. Permission profiles (beta)

| Field | Value |
| --- | --- |
| official_reference | D11 |
| config_location | `default_permissions = "<name>"` and `[permissions.<name>]` (`extends`, `filesystem`, `network`, `workspace_roots`); built-ins `:read-only`, `:workspace`, `:danger-full-access`; CLI `codex sandbox -P/--permission-profile` |
| states | DOCUMENTED; INSTALLED; INITIALIZED; RUNTIME-TESTED: **partial** |
| syntax_verified | `default_permissions` and `permissions` recognized; an unknown profile name → "default_permissions requires a `[permissions]` table" (B4) |
| runtime_verified | `:workspace` and `:read-only` behavior observed through `codex sandbox -P` (B7). A user-defined profile was not loaded. |
| limitations | Beta. D11: profiles do not compose with `sandbox_mode`; if `sandbox_mode` appears anywhere or `--sandbox` is passed, Codex uses the older settings and ignores `default_permissions`. **The loader accepted both together without error** (`-c default_permissions=":workspace" -c sandbox_mode="workspace-write"`, exit 0), so the BLUEPRINT's "must not combine" is a convention to enforce ourselves, not a loader guard — the failure mode is silent. `network.domains` need `features.network_proxy`. |
| fallback | Pick one system per layer; ship `sandbox_mode`/`approval_policy` unless the operator opts into profiles, and check the effective choice with `/status` (**BLOCKED: operator**). |

### 22. Automatic approval review

| Field | Value |
| --- | --- |
| official_reference | D2, D15, D4 |
| config_location | `approvals_reviewer = "user" \| "auto_review"`; `[auto_review] policy`; `--approve-for-me` on `exec`, `resume`, `fork`, root |
| states | DOCUMENTED; INSTALLED (`guardian_approval` stable, enabled — B3); INITIALIZED; RUNTIME-TESTED: no |
| syntax_verified | Enum `user`/`auto_review`/`guardian_subagent` (B4); `auto_review.policy` recognized |
| runtime_verified | No. Needs a model session. |
| limitations | Applies only when approvals are interactive (`on-request` or `granular`); with `never` there is nothing to review (D15). Evaluates only actions already needing approval; uses extra model calls; fails closed. The `guardian_subagent` value is not in the docs read — do not write it. |
| fallback | Leave `approvals_reviewer` at its default `user`. |

### 23. Goals and plan mode

| Field | Value |
| --- | --- |
| official_reference | D10, D3 (`goals` flag) |
| config_location | `/goal <objective>` (view, `edit`, `pause`, `resume`, `clear`; ≤ 4,000 chars), `/plan`; `features.goals` |
| states | DOCUMENTED; INSTALLED (`goals` stable, enabled — B3); INITIALIZED; RUNTIME-TESTED: no |
| syntax_verified | `goals` is a listed flag (B3) |
| runtime_verified | No. Interactive TUI. **BLOCKED: operator** |
| limitations | Whether goals or plan mode work under `codex exec` is not documented in the pages read. |
| fallback | Record the goal as the first line of the task prompt and in a `.codex-runtime/` file. |

### 24. Hosted tools outside the command sandbox

| Field | Value |
| --- | --- |
| official_reference | D2, D3, D1, D11 |
| config_location | `web_search = "cached" \| "indexed" \| "live" \| "disabled"`, `--search`; MCP via `[mcp_servers]`; apps/connectors, browser, Computer Use via feature flags |
| states | DOCUMENTED; INSTALLED (`web_search` enum — B4; `browser_use`, `computer_use`, `apps` stable and enabled — B3); RUNTIME-TESTED: no |
| syntax_verified | `web_search` domain confirmed; `mcp_servers` table recognized |
| runtime_verified | No. `codex mcp list` → no servers (B8). |
| limitations | **Hook visibility differs by surface (D1 "Tool coverage")**: hosted tools such as `WebSearch` are *not* seen by `PreToolUse`/`PostToolUse`; MCP tools *are* (matchable as `mcp__<server>__<tool>`). **Proxy**: none of web search, apps/connectors, MCP, or browser/Computer Use traffic is filtered by the sandbox network proxy (D2, D11). Default `web_search` is `cached`; it becomes `live` under full-access sandbox settings (D3). `tools.web_search.allowed_domains` filters results, not command egress (D11); the key is recognized (B4). |
| fallback | Set `web_search = "disabled"` in launch flags when a task must not reach external content; the delivered `.codex/` carries no MCP servers (CLAUDE.md). |

### 25. Retired or deprecated settings

| Field | Value |
| --- | --- |
| official_reference | D2 (retired `untrusted`), D9 (`--full-auto` removed), D1 (`codex_hooks` alias), D5 (`agents.max_threads` alias) |
| config_location | Any loaded layer |
| states | See table |
| syntax_verified | Rejections and acceptances below were produced by the binary (B4, B2) |
| runtime_verified | Loader behavior yes; model-session effects no |
| limitations | See table |
| fallback | Never write these; add a static check that fails the build if one appears in a delivered file. |

| Setting | Binary result (0.162.1) | Docs / blueprint | Status |
| --- | --- | --- | --- |
| `approval_policy = "untrusted"` | **Rejected at load**: `approval_policy = "untrusted" is no longer supported; remove this setting`, exit 1 | D2: retired, can prevent startup | UNSUPPORTED (verified) |
| `approval_policy = "on-failure"` | Accepted; no warning observed | D4 (`approval_policy` description): "`on-failure` is deprecated; use `on-request` … or `never`" | DOCUMENTED deprecated; loader still accepts it silently — do not write it |
| `--full-auto` | `error: unexpected argument '--full-auto' found` on `exec` and root | D9: no longer supported | UNSUPPORTED (verified) |
| `features.codex_hooks` | Recognized boolean; absent from `codex features list` | D1: deprecated alias of `features.hooks` | Accepted, no warning observed; write `features.hooks` |
| `agents.max_threads` | Recognized usize | D5/D4: legacy alias of `agents.max_concurrent_threads_per_session` | Accepted, no warning observed; write the new name |
| `profile = "<name>"` in config | **Rejected**: use `--profile <name>` with `<name>.config.toml` | D4: `profile` ignored in project config | UNSUPPORTED as a config key (verified); beyond blueprint list |
| `features.web_search`, `web_search_cached`, `web_search_request` | `web_search_cached`/`_request` listed "deprecated" (B3) | D3: all three deprecated; use top-level `web_search` | Do not use |
| `use_legacy_landlock`, `transcript_v2` features | Listed "deprecated" | D11: disable `use_legacy_landlock` | Do not use |

Loaded layers checked: the user `config.toml` (token counts only: `untrusted`, `on-failure`, `codex_hooks`,
`max_threads` all 0) and `*.config.toml` profile files (none present). No project config exists. System
or managed config: none (S01). Result: **no retired or deprecated setting is present in any loaded layer.**

## 6. Conflicts between blueprint, docs, and binary

Recorded per `CLAUDE.md`; none is resolved silently.

| # | Blueprint / instruction says | Docs / binary says | Effect |
| --- | --- | --- | --- |
| C1 | BLUEPRINT §0.2: `codex sandbox linux\|windows\|macos` | D2 documents those subcommands; installed Windows build takes `[COMMAND]...` and `-P` (B2, S01) | Platform-dependent; use the form shown by the host's `--help` |
| C2 | CLAUDE.md: run `codex exec` with `--ask-for-approval` | `exec --help` has no such flag; `-a` → "unexpected argument" (B2) | Use `-c approval_policy=...` and verify from events |
| C3 | BLUEPRINT §0.3 #21: profiles "must not be combined with `sandbox_mode`" | Loader accepts both; D11 says `sandbox_mode` silently wins | Enforce in our own validator |
| C4 | CLAUDE.md: test rules for "reordered and shell-wrapped forms" with `codex execpolicy check` | Offline check does not match `git -C …` or any shell wrapper (B5) | Wrapper behavior needs a runtime test |
| C5 | BLUEPRINT §0.3 #25: `approval_policy = "on-failure"` deprecated | D4 agrees; the binary still accepts it with no warning | No conflict on status; a deprecated value will not fail at load, so a static check is needed |
| C6 | Docs: `approvals_reviewer` = `user\|auto_review` | Binary also accepts `guardian_subagent` | Undocumented value; do not use |
| C7 | D12/D4 treat `features.prefer_mxc` as a config key | Binary lists it as "under development", default off | Documented but not a stable feature in 0.162.1 |
| C8 | BLUEPRINT §0.3 #24: MCP is "not visible to `PreToolUse`/`PostToolUse`" | D1 "Tool coverage": MCP tools are covered (Yes/Yes); only hosted tools such as `WebSearch` are not | Treat MCP as hook-visible but proxy-unfiltered |
| C9 | D10: `resume`/`review` cannot be combined with `--worktree` | `codex resume --help`, `exec resume`, `exec review` list `--worktree` (B2) | Help lists the flag, docs forbid it; runtime rejection UNVERIFIED (would start a session) |
| C10 | CLAUDE.md: run `codex exec` with an explicit `--ask-for-approval` | `codex exec -a never` is rejected (`unexpected argument`); the top-level `codex -a never exec --help` parses (P0-S03 review), but whether `exec` honors the top-level flag is UNVERIFIED | Use `-c 'approval_policy="never"'` and grade from `--json` events; refines C2 |
| C11 | BLUEPRINT lines 16, 157 and 211 (§3) say `contracts.md` holds five contracts (task, delegation, evidence, change, completion), and line 474 (§1.1) lists four of them; Part III §7 defines seven (adds authority, execution) | n/a (blueprint-internal) | `contracts.md` carries all seven; the root `AGENTS.md` pointer now names all seven (P1-S04) |
| C12 | BLUEPRINT §7 lists the sixth contract as "Evidence" but its body (§7.4) is titled "Verification contract"; Delegation and Execution have no §7 body | n/a (blueprint-internal) | Named "Evidence" in `contracts.md`; §7.4's table is its rule 2; Delegation takes §2.4–§2.8, Execution takes §4/§12/§2.8 and the native entries 11–14, 19, 20, 24 |
| C13 | BLUEPRINT §7.5 defines five outcomes without a tie-break; §12 says a safety-monitoring pause is "its own outcome" | Codex has no such states (§7.5 says so) | `contracts.md` §7 adds a precedence order (CANCELLED, COMPLETE, BLOCKED, FAILED, PARTIAL) and reports a safety pause as `BLOCKED` unless the user stopped it. Project convention, not a Codex behavior; revisit if the blueprint adds a sixth outcome |

Note: Codex docs live on `learn.chatgpt.com/docs/` (BLUEPRINT v1.1 already says so); cite that host.

## 7. Operator-only and blocked checks

| ID | Check | Command or step | Status |
| --- | --- | --- | --- |
| O1 | Trust this project | `cd C:\TEST-repos\codex-prime; codex`, answer the trust prompt | BLOCKED: operator (S01 U1) |
| O2 | Confirm layers, sandbox, approval, roots | In that session run `/status` | BLOCKED: operator (S01 U4) |
| O3 | Review/trust hooks | `/hooks` (after Phase 4 creates hooks) | BLOCKED: operator (S01 U2) |
| O4 | Skill invocation, plan mode, goals, compaction, `/review` | Interactive `$skill`, `/plan`, `/goal`, `/compact`, `/review` | BLOCKED: operator |
| O5 | WSL: Codex present and sandbox working | In the Ubuntu distro: `command -v codex && codex --version` then a `codex sandbox` probe | BLOCKED: operator (S01 U7) |
| O6 | Custom agent discovery and spawn | After O1, add an agent file and run a `codex exec --json` session that names it | Paid session; plan and approve first |
| O7 | Hook payload and deny behavior | Fixture tests offline, then one `exec --json` run | Paid session for the runtime half |
| O8 | Rule behavior for wrapped commands | `codex exec` with a `prompt`/`forbidden` rule and a wrapped command | Paid session |
| O9 | `exec` JSONL schema and the `-c approval_policy` effect | One `codex exec --json` run | Paid session |
| O10 | Network enable plus `network_proxy` domains | Sandbox/session probe with network on | Open (not run to stay non-intrusive) |

## 8. Other limitations of this matrix

- B4 proves a non-`features` key **exists and is typed** (feature flags: B3); it does not prove semantics. Behavior rows rely on D* until a runtime probe exists.
- B6/B7 ran in an **untrusted** scratch repo and through `codex sandbox`; trusted-project behavior and model-session behavior are not observed.
- D4, D10, D12, D14, D15 were searched, not read in full; claims from them are limited to the passages quoted above.
- `debug prompt-input` output is a rendered prompt and is not a stable interface.

## 9. Reproducing the probes

```powershell
codex --version
codex features list
codex -c 'agents.max_concurrent_threads_per_session="x"' features list   # expect: invalid type ... expected usize
codex -c 'approval_policy=untrusted' features list                         # expect: no longer supported, exit 1
codex exec --full-auto --help                                              # expect: unexpected argument
codex execpolicy check --rules <file> -- git push origin main              # then try: git -C . push ; bash -lc "git push"
codex sandbox -P ':workspace' -- cmd.exe /d /c "echo x> .git\probe.txt"    # expect: Access is denied (run from PowerShell)
codex -c windows.sandbox=mxc sandbox --permission-profile :workspace -- cmd.exe /d /c echo MXC_OK
codex debug prompt-input                                                   # run in a repo with AGENTS.md and .agents/skills
```

Run the sandbox and `prompt-input` probes in a throwaway Git repository, not in this one.
