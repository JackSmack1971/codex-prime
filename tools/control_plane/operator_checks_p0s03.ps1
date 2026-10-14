<#
.SYNOPSIS
  P0-S03 operator checks for observations that need project trust (operator-only).

.DESCRIPTION
  Modes (run each from PowerShell 7):
    -Mode Prepare  Create a throwaway repo under $env:TEMP with a project .codex layer, print the manual steps.
    -Mode Verify   Run the non-interactive checks against that repo (read-only; starts no model session).
    -Mode Cleanup  Delete the throwaway repo and print the reminder to remove the trust entry.
  This script NEVER writes ~/.codex/config.toml and never grants trust. Trust is granted by the operator
  answering the Codex trust prompt (step 2) and removed by the operator (Cleanup reminder).
#>
param([Parameter(Mandatory)][ValidateSet('Prepare', 'Verify', 'Cleanup')][string]$Mode)
$root = Join-Path $env:TEMP 'cp-s03-operator'
function Has($t, $n) { [bool]($t -match [regex]::Escape($n)) }

switch ($Mode) {
  'Prepare' {
    if (Test-Path $root) { throw "$root exists; run -Mode Cleanup first." }
    New-Item -ItemType Directory $root, "$root\.codex\agents", "$root\.codex\rules", "$root\.agents\skills\demo-skill" | Out-Null
    Set-Location $root; git init -q . ; git config user.email op@example.invalid; git config user.name op
    Set-Content "$root\AGENTS.md" 'ROOT_SENTINEL_S03'
    Set-Content "$root\.codex\config.toml" "[features]`ngoals = false`n"
    Set-Content "$root\.codex\agents\demo.toml" "name = `"demo_agent`"`ndescription = `"S03 demo agent`"`ndeveloper_instructions = `"Reply only with DEMO_AGENT_OK.`"`n"
    Set-Content "$root\.codex\rules\p.rules" "prefix_rule(pattern=[`"git`",`"push`"], decision=`"forbidden`", justification=`"S03 probe`")`n"
    Set-Content "$root\.agents\skills\demo-skill\SKILL.md" "---`nname: demo-skill`ndescription: S03_ROOT_SKILL_SENTINEL`n---`nbody`n"
    git add -A; git commit -qm init
    @"
Prepared: $root

Manual steps (operator only):
 1. BEFORE trust:   cd '$root'; codex features list | Select-String '^goals'     # expect: true  (project layer skipped)
 2. Grant trust:    cd '$root'; codex       # answer the trust prompt with "trust", then /status (record sandbox, approval,
                                            # roots, loaded config layers), /hooks (record state; no hooks exist), /agent or
                                            # /subagents if available, /skills, then /quit
 3. AFTER trust:    pwsh -NoProfile -File '$PSCommandPath' -Mode Verify
                    # expect: goals false; execpolicy shows project rule; project agent/skill visible per the checks
 4. Cleanup:        pwsh -NoProfile -File '$PSCommandPath' -Mode Cleanup
                    then remove the [projects.'<temp path>'] trust entry for the scratch path from ~/.codex/config.toml.
Record each result as: PASS / FAIL / BLOCKED: operator, with the command and the observed output.
"@
  }
  'Verify' {
    if (-not (Test-Path $root)) { throw 'Run -Mode Prepare first.' }
    Set-Location $root
    "codex: $(codex --version)"
    $g = (codex features list | Select-String '^goals').Line -replace '\s+', ' '
    "V1 project config active (trusted => 'goals stable false'): $g"
    $p = codex debug prompt-input | Out-String
    "V2 root AGENTS.md in prompt: $(Has $p 'ROOT_SENTINEL_S03')   repo skill in prompt: $(Has $p 'S03_ROOT_SKILL_SENTINEL')"
    "V3 project rule file is only honored when trusted; offline rule parse (does not prove it is loaded):"
    codex execpolicy check --rules "$root\.codex\rules\p.rules" --pretty -- git push origin main
    "V4 nested launch from a subdirectory still resolves the project layer:"
    New-Item -ItemType Directory -Force "$root\sub" | Out-Null; Set-Location "$root\sub"
    "   $((codex features list | Select-String '^goals').Line -replace '\s+', ' ')"
    "V5 custom agent visibility needs a model session (paid): NOT run here. Planned, operator-approved run only:"
    "   cd '$root'; codex exec --sandbox read-only -c 'approval_policy=`"never`"' --json 'Spawn the agent named demo_agent and report its reply.'"
    "   (codex exec has no --ask-for-approval flag in 0.162.1; approval is set with -c.) Must run from the trusted scratch root."
    "   expect: a spawn event naming demo_agent. Record PASS/FAIL from the JSON event stream."
  }
  'Cleanup' {
    Set-Location $env:TEMP
    if (Test-Path $root) { Remove-Item -Recurse -Force $root; "Removed $root" }
    'Reminder: remove the trust entry for that scratch path from ~/.codex/config.toml yourself (this script never edits it).'
  }
}
