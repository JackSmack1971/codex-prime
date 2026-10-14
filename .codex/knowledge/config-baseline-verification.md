# P1-S03 Project Config Baseline Verification — CODEX PRIME

Scope: `.codex/config.toml` per BLUEPRINT.md v1.1 §1.2. Installed binary `codex-cli 0.162.1`, native Windows 11 (build 22631).
Probes ran in PowerShell 7 (sandbox) or Git Bash (doctor/parse); no model session was started; user config, trust and
credentials were not read or written. Scratch repos and homes lived under the session scratchpad or `%TEMP%`.

## 1. Delivered file

Keys (all cited in `native-capabilities.md` rows 21, 25-26 and §4 B4 plus the docs MCP page `config-file/config-basic`):

| Key | Value | Why |
| --- | --- | --- |
| `approval_policy` | `"on-request"` | supported value; `untrusted` is rejected at load, `on-failure` deprecated |
| `sandbox_mode` | `"workspace-write"` | documented sandbox model; permission profiles not validated, so none are written |
| `sandbox_workspace_write.network_access` | `false` | documented default, stated explicitly |
| `shell_environment_policy.ignore_default_excludes` | `false` | docs: default is `true` (passes `*KEY*`/`*SECRET*`/`*TOKEN*`); `false` applies the exclusions |
| `agents.max_concurrent_threads_per_session` | `4` | current key (legacy alias `max_threads` not used) |

Deliberately absent: `default_permissions`/`[permissions.*]` (silently ignored when `sandbox_mode` is present, C3), `writable_roots`,
`approvals_reviewer` (Phase 4), MCP servers, hooks, `projects` trust, model/provider/paths. `validate_config.py` enforces this list.

## 2. Evidence

| ID | Check | Result | State |
| --- | --- | --- | --- |
| V1 | `python -I tools/control_plane/validate_config.py --codex --self-test` | exact-content and policy checks pass; 14/14 mutations (untrusted/on-failure/never, danger-full-access, network true or removed, excludes ignored, `writable_roots`, profile alongside `sandbox_mode`, MCP server, legacy alias, unknown key, changed concurrency) are detected | PASS (static) |
| V2 | File loaded as the user layer of a throwaway `CODEX_HOME`; `codex doctor --json` | `config.load ok`, `config.toml parse: ok`. Negative control: `max_concurrent_threads_per_session = "x"` → `failed to load bootstrap configuration`, exit 1, so the loader does read the file | PASS (parse under installed binary) |
| V3 | `codex -c approval_policy=... doctor --json` | `approval policy` reads `Never` / `OnRequest`, so doctor reflects the policy value; the file's value equals the default, so doctor on the file alone cannot discriminate | PASS (key accepted); effect from file UNVERIFIED |
| V4 | `codex sandbox -c approval_policy="on-request" -c sandbox_mode="workspace-write" -c sandbox_workspace_write.network_access=false …` in a scratch repo | new workspace file created; overwrite of existing `.codex\config.toml` denied (content unchanged); new `.git\hooks\pre-commit` not created; `curl.exe https://example.com` exit 7. Control with `network_access=true`: exit 35 (traffic leaves the sandbox; TLS then fails), so the flag changes behavior | PASS (values via `-c`, helper path) |
| V5 | Same, with `CP_FAKE_SECRET_TOKEN` and `CP_PLAIN_VAR` set, `set CP_` | `ignore_default_excludes=false`: only `CP_PLAIN_VAR`; `=true`: both. The file's value filters secret-named variables | PASS |

## 3. Findings and limits

- **Untrusted project skips this file** (P0-S03 P1). Every probe above passes the same values via `-c` or a user-layer copy; none shows the
  *project* layer loading. That is `BLOCKED: operator` (§4).
- **Use the default `CODEX_HOME` for sandbox probes.** With a fresh throwaway `CODEX_HOME`, `codex sandbox` denied even workspace writes
  (no sandbox setup state there), a false negative unrelated to the config. Parse/doctor checks are fine in a throwaway home.
- `codex debug prompt-input` always rendered `sandbox_mode` as `read-only` here, even with `-c sandbox_mode="workspace-write"`; it is not
  evidence for the sandbox mode. Do not use it for this.
- `codex doctor` shows approval policy, network ("restricted") and filesystem ("restricted") but not the sandbox mode name, and
  `workspace-write` and `read-only` both report `restricted`.
- `agents.max_concurrent_threads_per_session = 4`: key and type accepted (B4); runtime enforcement of the cap is UNVERIFIED (needs a paid
  multi-agent session).
- Protected-path and network results come from the `codex sandbox` helper, not from a model session (same limit as P0-S03 P4b).
- **Repository lineage:** `origin/main` (18c4359) does not contain P1-S01 (`.gitignore`, `.gitattributes`); PR #4 merged into
  `p0-s03-config-baseline`, not `main`. This branch is based on `origin/main` and does not add them. Until they land, `.codex-runtime/`
  is not ignored. Needs a decision outside this slice.

## 4. Operator-only checks (BLOCKED: operator)

Run in PowerShell 7; the builder does not trust projects or answer prompts.

| ID | Step | Expected |
| --- | --- | --- |
| O-I | Trust `C:\TEST-repos\codex-prime` in the Codex TUI trust prompt, then run `codex` from the repo root and enter `/status` | approval `on-request`, sandbox `workspace-write`, network restricted, project config layer listed |
| O-J | Same trusted session: ask Codex to create a file under `.codex-runtime/` and to edit `.codex/config.toml` | the first works (after creating the directory); the second is refused |
| O-K | `/subagents` or a paid `codex exec` run that spawns more than 4 agents (needs user approval of spend) | at most 4 concurrent threads |
| O-L | Remove nothing: this slice added no scratch trust entry | — |

## 5. Acceptance (P1-S03)

Static: PASS. Parse under installed binary: PASS. Security defaults independently checked via binary-level probes: PASS (helper path).
Intended settings loading in a **trusted** project: `BLOCKED: operator` (O-I, O-J). Concurrency cap enforcement: UNVERIFIED (O-K).
Overall: **PARTIAL** until O-I/O-J pass.
