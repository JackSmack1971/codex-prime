# Root AGENTS.md verification (P1-S02)

Installed: `codex-cli 0.162.1`. Shell: Git Bash on Windows 11. Source: BLUEPRINT.md §1.1, Part III §7.

## Scope
`AGENTS.md` at the repo root is the Codex runtime contract. `CLAUDE.md` is builder-only and is
not read by Codex; it is untracked and not part of this slice. The file is 3,362 bytes, far
below the 32 KiB `project_doc_max_bytes` default (D6).

## Instruction loading (`codex debug prompt-input hi`, no model session)
| Launch directory | Contract heading in model-visible prompt |
| --- | --- |
| repo root | present |
| `.codex/knowledge` | present |
| `tools/control_plane` | present |
| `C:\Users\<user>` (outside repo) | absent |

`CLAUDE.md` text ("Builder Operating Contract") was absent from the prompt in the root launch.
This checks what is injected, not whether the model obeys it.

## Trivial work stays lightweight (`codex exec`, 1 paid session)
Command: `codex exec --sandbox read-only --ephemeral --json "What is the first heading line of AGENTS.md? Answer in one line."`
Event stream: `thread.started`, `turn.started`, one `agent_message`, `turn.completed`. Zero
`command_execution`, plan, or subagent items. The answer matched the heading, so it came from the
loaded instructions. One run on one prompt is a smoke check, not a behavioral guarantee.

## Not verified
- BLOCKED: operator: interactive checks (trust prompts, `/plan` behavior on a complex request,
  approval behavior) need the TUI. L2/L3 planning and delegation behavior depends on later slices
  (contracts, `task-triage`, agents) and is not claimed here.
- Not tested: `AGENTS.override.md`, `project_doc_fallback_filenames`, the 32 KiB cap, a global file.
- `.codex/knowledge/contracts.md` and the `.agents/skills/` directory do not exist yet; the
  contract references them conditionally ("if the file exists").
