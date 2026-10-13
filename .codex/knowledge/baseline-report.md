# P0-S01 Baseline Report — CODEX PRIME

Scope: BLUEPRINT.md v1.1 §0.2 (environment inventory) and §0.5 (baseline snapshots).
Captured: 2026-10-13, before any control-plane file existed. Sanitized: user-home paths appear as
`%USERPROFILE%`; no credential files were opened, no environment values were printed, and user
`config.toml` is reported as section and key names only.

Reproduce the machine-readable part with
`pwsh -NoProfile -File tools/control_plane/collect_baseline.ps1` (read-only; stdout only).
Status words: **Observed** = seen in this session by the named command. **Unresolved** = not
checked, or checkable only by the operator.

## 1. Observed facts

| Area | Observation | Source (shell) |
| --- | --- | --- |
| OS | Windows 11 Pro, version 10.0.22631, build 22631, 64-bit | `Get-CimInstance Win32_OperatingSystem` (PowerShell 7.6.2) |
| Host shells | PowerShell 7.6.2 Core (operator-style shell); Git Bash 5.2.37 on MSYS (`MINGW64_NT-10.0-22631`) | `$PSVersionTable`, `uname -a` (both) |
| Codex binary | `%USERPROFILE%\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`, native Windows `.exe`, not a script wrapper; one `codex` on PATH; `codex-cli 0.162.1` in both shells; `version.json` reports latest = 0.162.1 | `Get-Command -All codex`, `codex --version` (both) |
| Runtime layout | "standalone" package under `%USERPROFILE%\.codex\packages\standalone\releases\0.162.1-x86_64-pc-windows-msvc`, install "consistent" | `codex doctor --summary` (PowerShell) |
| Authentication | `codex login status` → "Logged in using ChatGPT"; `doctor` → "auth is configured". `CODEX_HOME`, `OPENAI_API_KEY`, `CODEX_API_KEY` are unset. Credential files were not read. | PowerShell |
| Git | git 2.53.0.windows.2; root `C:/TEST-repos/codex-prime`; branch `main` with **no commits**; single worktree; no stash; `core.autocrlf=true` | PowerShell |
| Remote | `origin` → `https://github.com/JackSmack1971/codex-prime.git`; the GitHub repo is **public and empty** (no branches); local upstream shows `[gone]`; `gh` is authenticated with ADMIN permission | `git remote -v`, `gh repo view` |
| Pre-existing changes | Two untracked files only, no tracked diffs: `BLUEPRINT.md` (154151 bytes, sha256 `7489C316…`), `CLAUDE.md` (6555 bytes, sha256 `D29C516B…`). Left untouched and uncommitted. | `git status`, `Get-FileHash` |
| Project control-plane files | None: no `AGENTS.md`, `.codex/`, `.agents/`, `.codex-runtime/`, `.gitignore`, `.gitattributes`, `tests/` | `Test-Path` |
| Instructions (project) | No project `AGENTS.md`. | |
| Instructions (above repo) | `C:\TEST-repos\AGENTS.md` (27216 bytes) and `C:\AGENTS.md` (5080 bytes) exist. Neither was loaded into the model-visible prompt when launched from the repo root (`codex debug prompt-input`: no path or content from either appears; cwd `C:\TEST-repos\codex-prime`). Contents were not read. | `Test-Path`, `codex debug prompt-input` |
| Instructions (user) | No `~/.codex/AGENTS.md` or `AGENTS.override.md`. | |
| Existing agents | No `.codex/agents/` in the project or `~/.codex/`. | `Test-Path` |
| Skills | None in the project. User scope `~/.agents/skills`: 46 skill directories plus 4 loose files (`AGENTS.md`, `CATEGORY_INDEX.md`, `CATEGORY_MAP.csv`, `inventory-report.tmp`). System skills in `~/.codex/skills/.system`: imagegen, openai-docs, review-agent, skill-creator, skill-installer. The model-visible prompt lists 48 skills (user + system) at the repo root. Names overlapping future blueprint skills (§3.3 names such as `security-review`, `implementation`, `repository-recon`): none of those exact names is installed; closest user-level names are `implementation-slice`, `recon-gate`, `review-change`, `verification-gate`. | directory listing, `codex debug prompt-input` |
| Hooks | No project hooks; no `~/.codex/hooks.json`. Feature `hooks` = stable, enabled. | `Test-Path`, `codex features list` |
| Execution rules | User `~/.codex/rules/default.rules`: 59 lines, all `decision="allow"` prefix rules, accumulated from other projects' approvals. Includes broad allows for `gh` and `git push` and `git switch`. No `forbidden`/`prompt` rules. Rule text not reproduced here (contains other projects' paths). | file inspection (PowerShell) |
| Config layers | User `config.toml` has keys `model`, `model_reasoning_effort`, `[tui]`, `[windows] sandbox`, and two `[projects.*]` trust entries for **other** paths. No `[projects]` entry for `codex-prime`. No managed config at `C:\ProgramData\OpenAI\Codex` or `C:\ProgramData\codex`. No retired settings (`approval_policy`, `features.codex_hooks`, `agents.max_threads`) among the key names. | key-name listing |
| Sandbox / approval | `doctor`: "restricted fs + restricted network · approval OnRequest"; `[windows] sandbox` is set at user level (value not recorded). | `codex doctor` |
| Feature flags (selected) | `hooks` stable/true; `multi_agent` stable/true; `multi_agent_v2` stable/false; `goals` stable/true; `skill_search` stable/true; `worktrees` stable/true; `network_proxy` experimental/false; `guardian_approval` stable/true; `plugins` stable/true; `codex_hooks` is not a known feature in this version | `codex features list` |
| CLI surface (0.162.1) | Top-level: `exec`, `review`, `sandbox`, `debug`, `features`, `doctor`, `mcp`, `resume`, `fork`, `login`, `plugin`, `cloud`, `apply`, and others. `codex execpolicy check --rules <PATH> [--pretty] <COMMAND>...` works although `execpolicy` is **absent from top-level help**. `codex sandbox` takes the command directly on Windows (no `sandbox linux/macos/windows` subcommands, unlike BLUEPRINT §0.2). `exec` has `--sandbox` (read-only, workspace-write, danger-full-access), `--json`, `--ephemeral`, `--output-schema`, `-o/--output-last-message`, `--ignore-rules`, `--skip-git-repo-check`, and `--approve-for-me`; it has **no `--ask-for-approval` flag** in its help (the interactive `codex` command has `-a`: `on-request` or `never`). | `--help` output (PowerShell) |
| MCP | `codex doctor`: no MCP servers configured in Codex. | PowerShell |
| Toolchains | node v22.20.0, npm 10.9.3, Python 3.14.3 (`python` and `py`), pip 26.1.2, uv 0.12.7, pytest 9.0.3, cargo/rustc 1.96.0, gh 2.97.0, git 2.53.0, pwsh 7.6.2. Not found: go, dotnet, java, jq. | `Get-Command`, `--version` |
| Host health notes | `doctor`: Defender may interfere with Codex (exclusions not verified); worktree is not on a Dev Drive; background app-server socket stale/unreachable; free disk 8.7 GiB; network/websocket/endpoint reachability OK. | `codex doctor` |
| WSL | WSL 2.6.1.0; distributions `Ubuntu` and `docker-desktop`, both WSL2, both Stopped. Not started (starting is a state change). | `wsl.exe -l -v` |

## 2. Windows vs WSL differences

Observed: native Windows `codex.exe` 0.162.1 is installed and works from both PowerShell and Git
Bash; the Codex Windows sandbox is configured at user level; `codex sandbox` exposes a single
Windows restricted-token form. Git Bash is MSYS, not WSL: its `uname` reports `MINGW64_NT`.
Unresolved: whether Codex is installed inside the Ubuntu WSL distro, and how Linux sandbox
(bubblewrap) behavior differs. See §3.

## 3. Unresolved checks

| ID | Item | Why unresolved | Status |
| --- | --- | --- | --- |
| U1 | Project trust for `codex-prime` | Not in user config. Trust is an operator decision; the project `.codex/` layer will be skipped until trusted. | `BLOCKED: operator` |
| U2 | Hook trust and `/hooks` state | Interactive TUI only; no hooks exist yet. | `BLOCKED: operator` |
| U3 | Ancestor `AGENTS.md` (`C:\TEST-repos`, `C:\`) exclusion from the instruction chain | Observed absent from the prompt at the repo root; not yet checked from a nested launch directory, or once a project `AGENTS.md` exists. Contents unread, so their conflict potential with the contract is unknown. | Open (Phase 1) |
| U4 | Effective layer precedence, sandbox mode, and approval policy for a trusted project | Needs a trusted project and `/status`. | `BLOCKED: operator` |
| U5 | Protected-path behavior (`.git`, `.codex`, `.agents`) and default network state under `workspace-write` | Needs a `codex exec`/sandbox runtime run (paid session or sandbox probe) that was not made in this slice. | Open |
| U6 | Windows sandbox actual behavior (`codex sandbox`) | Not executed to keep the slice non-intrusive. | Open |
| U7 | WSL/Linux: Codex presence and `bubblewrap` behavior | WSL distros stopped; not started. | Open |
| U8 | Native agent/skill discovery from `.codex/agents` and `.agents/skills` | Nothing exists to discover yet. | Open (Phase 2/3) |
| U9 | How to set approval policy for `codex exec` runs, and the `--json` event schema | No `--ask-for-approval` in `exec --help`; event schema not observed (no paid run made). | Open |
| U10 | Defender exclusions; stale app-server daemon | Reported by `doctor`; may affect runtime tests. Operator/host action, not altered. | Open |
| U11 | Existing required tests / known working verification commands | Repository has no code, tests, or CI. | N/A: none exist |
| U12 | Public-repo exposure | `JackSmack1971/codex-prime` is public. Files committed here become public. | Noted |

## 4. Blueprint vs installed-binary conflicts found

1. BLUEPRINT §0.2 lists `codex sandbox linux|windows|macos`; the installed 0.162.1 `codex sandbox`
   takes `[COMMAND]...` directly (Windows restricted token) and has only an `uninstall` subcommand.
2. `execpolicy` works but is not listed in top-level `codex --help`; do not use help listing as
   proof of absence.
3. `CLAUDE.md` tells the builder to run `codex exec` with an explicit `--ask-for-approval`; the
   installed `codex exec --help` lists no such flag. The top-level `codex -a` accepts only
   `on-request` and `never`. Approval for `exec` runs must be set another way (for example
   `-c approval_policy=...`), to be confirmed in the docs and by a parse test before any paid run.

These belong in `.codex/knowledge/native-capabilities.md` (S02, not created in this slice).

## 5. Probe output snapshot

Output of `tools/control_plane/collect_baseline.ps1` from PowerShell 7.6.2 follows, verbatim except
for the line wrapping of Markdown. Items marked Observed above that came from other commands
(`doctor`, `prompt-input`, `--help`) are not repeated here.

Note: this snapshot was taken after this report and the probe script were written, so they also appear as untracked files and `.codex`/`tools` exist; the pre-existing state is the two files in §1.

### Probe run (shell: PowerShell 7.6.2 Core)

#### Operating system

**OS**
```text
Microsoft Windows 11 Pro | version 10.0.22631 | build 22631 | 64-bit
```

#### Codex binary

**Resolution**
```text
Application | %USERPROFILE%\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe
size=333479728 modified=2026-10-09T14:26:10
```
**codex --version**
```text
codex-cli 0.162.1
```
**codex login status (availability only)**
```text
Logged in using ChatGPT
```
**Selected feature flags (codex features list)**
```text
goals                                    stable             true
guardian_approval                        stable             true
hooks                                    stable             true
memories                                 stable             false
multi_agent                              stable             true
multi_agent_v2                           stable             false
network_proxy                            experimental       false
plugins                                  stable             true
shell_tool                               stable             true
skill_search                             stable             true
worktrees                                stable             true
```
**Subcommands present**
```text
exec        listed in top-level help: True
review      listed in top-level help: True
sandbox     listed in top-level help: True
debug       listed in top-level help: True
features    listed in top-level help: True
doctor      listed in top-level help: True
execpolicy  listed in top-level help: False
mcp         listed in top-level help: True
resume      listed in top-level help: True
fork        listed in top-level help: True
execpolicy check --help works (exit code): 0
```

#### Environment (presence only)

**Variables**
```text
CODEX_HOME set: False
OPENAI_API_KEY set: False
CODEX_API_KEY set: False
```

#### Repository

**Git**
```text
git: git version 2.53.0.windows.2
root: C:/TEST-repos/codex-prime
branch: main
HEAD: none (no commits)
remotes:
origin	https://github.com/JackSmack1971/codex-prime.git (fetch)
origin	https://github.com/JackSmack1971/codex-prime.git (push)
worktrees:
C:/TEST-repos/codex-prime 0000000 [main]
status:
#### No commits yet on main...origin/main [gone]
?? .codex/
?? BLUEPRINT.md
?? CLAUDE.md
?? tools/
diff --stat:
cached --stat:
stash entries: 0
core.autocrlf: true
```
**Untracked file inventory (size, sha256 prefix)**
```text
.codex/knowledge/baseline-report.md 10257 bytes sha256=C81E7E8307281116
BLUEPRINT.md 154151 bytes sha256=7489C3168D9B4340
CLAUDE.md 6555 bytes sha256=D29C516B692F43E3
tools/control_plane/collect_baseline.ps1 5864 bytes sha256=C7AAF5D07605CA5F
```

#### Existing control-plane artifacts

**Repository**
```text
AGENTS.md        exists: False
.codex           exists: True
.agents          exists: False
.codex-runtime   exists: False
.gitignore       exists: False
.gitattributes   exists: False
tools            exists: True
tests            exists: False
```
**Instruction files on the path above the repo (existence, size, sha256 prefix; content not read)**
```text
C:\TEST-repos\AGENTS.md 27216 bytes sha256=7132DCD93ED7AB36
C:\AGENTS.md 5080 bytes sha256=B53EC530BA3FC6BE
```
**User-level Codex layer (names only)**
```text
config.toml            exists: True
hooks.json             exists: False
AGENTS.md              exists: False
AGENTS.override.md     exists: False
rules\default.rules    exists: True
user config.toml sections/keys (values omitted):
    key: model
    key: model_reasoning_effort
  [tui]
    key: screen_reader_detection_done
  [tui.model_availability_nux]
    key: "gpt-6.1-sol"
  [projects.'c:\workspaces\deployed\substack-publisher-mcp']
    key: trust_level
  [projects.'c:\test-repos\experimental-01']
    key: trust_level
  [windows]
    key: sandbox
default.rules: 59 lines; decisions: allow=59
system skills: imagegen, openai-docs, review-agent, skill-creator, skill-installer
```
**User-level skills in ~/.agents/skills (directory count only; names are in the report)**
```text
directories: 46
files at top level: AGENTS.md, CATEGORY_INDEX.md, CATEGORY_MAP.csv, inventory-report.tmp
```
**Managed/admin config locations**
```text
C:\ProgramData\OpenAI\Codex exists: False
C:\ProgramData\codex exists: False
```

#### Toolchains

**Versions**
```text
node | C:\Program Files\nodejs\node.exe | v22.20.0
npm | C:\Program Files\nodejs\npm.ps1 | 10.9.3
python | %USERPROFILE%\.local\bin\python.exe | Python 3.14.3
py | %USERPROFILE%\AppData\Local\Microsoft\WindowsApps\py.exe | Python 3.14.3
pip | %USERPROFILE%\AppData\Local\Python\bin\pip.exe | pip 26.1.2 from %USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\pip (python 3.14)
uv | %USERPROFILE%\.local\bin\uv.exe | uv 0.12.7 (61291a8ca 2026-08-27 x86_64-pc-windows-msvc)
pytest | %USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\Scripts\pytest.exe | pytest 9.0.3
git | C:\Program Files\Git\cmd\git.exe | git version 2.53.0.windows.2
gh | C:\Program Files\GitHub CLI\gh.exe | gh version 2.97.0 (2026-07-31)
cargo | %USERPROFILE%\.cargo\bin\cargo.exe | cargo 1.96.0 (30a34c682 2026-05-25)
rustc | %USERPROFILE%\.cargo\bin\rustc.exe | rustc 1.96.0 (ac68faa20 2026-05-25)
go | not found
dotnet | not found
java | not found
pwsh | C:\Program Files\PowerShell\7\pwsh.exe | PowerShell 7.6.2
jq | not found
wsl | C:\WINDOWS\system32\wsl.exe | WSL version: 2.6.1.0
```
**WSL distributions**
```text
  NAME              STATE           VERSION

* Ubuntu            Stopped         2

  docker-desktop    Stopped         2


```
