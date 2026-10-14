<#
.SYNOPSIS
  P0-S03 probe: configuration loading, discovery, protected paths, command network (read-only for this repo).

.DESCRIPTION
  Builds a throwaway Git repo under $env:TEMP, runs Codex helper commands inside it, prints results,
  and deletes it. Does NOT touch user config, trust, hooks, or this repository. Starts no model session.
  The scratch repo is untrusted by construction (no [projects] entry), so results describe an
  UNTRUSTED project. Run from PowerShell 7 (Git Bash rewrites cmd.exe arguments).
  Network control uses curl.exe against https://example.com (one outbound HTTPS request).
#>
$ErrorActionPreference = 'Continue'
$repoRoot = (git rev-parse --show-toplevel) 2>$null
$c = Join-Path $env:TEMP ("cp-s03-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$s = Join-Path $c "repo"
function Has($text, $needle) { [bool]($text -match [regex]::Escape($needle)) }
function Sbx($profile, $cmd, $extra = @()) {
  $a = @() + $extra + @('sandbox'); if ($profile) { $a += @('-P', $profile) }
  $a += @('--', 'cmd.exe', '/d', '/c', $cmd)
  $null = & codex @a 2>&1; return $LASTEXITCODE
}

"codex: $(codex --version)   shell: PowerShell $($PSVersionTable.PSVersion)"
try {
  New-Item -ItemType Directory $c, $s, "$s\.codex\agents", "$s\.codex\rules", "$s\.agents\skills\demo-skill",
    "$s\sub\dir", "$s\sub\.agents\skills\nested-skill", "$s\.aws" | Out-Null
  Set-Location $s
  git init -q . 2>$null; git config user.email probe@example.invalid; git config user.name probe
  Set-Content "$c\AGENTS.md" 'ANCESTOR_SENTINEL_S03'   # one level ABOVE the Git root
  Set-Content "$s\AGENTS.md" 'ROOT_SENTINEL_S03'
  Set-Content "$s\sub\AGENTS.md" 'SUB_SENTINEL_S03'
  Set-Content "$s\.codex\config.toml" "model = `"project-model-sentinel`"`n[features]`ngoals = false`n"
  Set-Content "$s\.codex\agents\demo.toml" "name = `"demo_agent`"`ndescription = `"S03 demo`"`ndeveloper_instructions = `"x`"`n"
  Set-Content "$s\.codex\rules\p.rules" "prefix_rule(pattern=[`"git`",`"push`"], decision=`"forbidden`")`n"
  Set-Content "$s\.agents\skills\demo-skill\SKILL.md" "---`nname: demo-skill`ndescription: S03_ROOT_SKILL_SENTINEL`n---`nbody`n"
  Set-Content "$s\sub\.agents\skills\nested-skill\SKILL.md" "---`nname: nested-skill`ndescription: S03_NESTED_SKILL_SENTINEL`n---`nbody`n"
  git add -A 2>$null; git commit -qm init 2>$null

  "`n## P1 project config.toml in an UNTRUSTED project (project sets goals=false, model=sentinel)"
  $g = (codex features list | Select-String '^goals').Line -replace '\s+', ' '
  $m = (codex doctor --json | ConvertFrom-Json).checks.'config.load'.details.model
  "features.goals effective: '$g'  (project layer active would show false)"
  "effective model equals project sentinel: $($m -eq 'project-model-sentinel')"

  "`n## P2 instruction + skill discovery by launch directory (debug prompt-input)"
  foreach ($d in @($s, "$s\sub\dir")) {
    Set-Location $d
    $p = codex debug prompt-input | Out-String
    "launch=$($d.Replace($s,'<scratch>'))  rootAGENTS=$(Has $p 'ROOT_SENTINEL_S03')  subAGENTS=$(Has $p 'SUB_SENTINEL_S03')  rootSkill=$(Has $p 'S03_ROOT_SKILL_SENTINEL')  nestedSkill=$(Has $p 'S03_NESTED_SKILL_SENTINEL')  customAgentName=$(Has $p "demo_agent")  ancestorAGENTS=$(Has $p "ANCESTOR_SENTINEL_S03")"
  }

  "`n## P3 default sandbox mode and network text in the rendered prompt (this repository, untrusted)"
  Set-Location $repoRoot
  $p = codex debug prompt-input | Out-String
  "prompt says sandbox_mode read-only: $($p -match 'sandbox_mode. is .read-only')   network restricted: $(Has $p 'Network access is restricted')"

  "`n## P4 protected paths + network under codex sandbox (scratch repo, -P :workspace unless noted)"
  Set-Location $s
  $rows = @(
    @('write normal file', ':workspace', 'echo x> normal.txt', 'normal.txt', $true),
    @('create .codex-runtime', ':workspace', 'mkdir .codex-runtime & echo x> .codex-runtime\a.txt', '.codex-runtime\a.txt', $true),
    @('overwrite existing .codex\config.toml', ':workspace', 'echo hacked> .codex\config.toml', $null, $false),
    @('append existing .codex\agents file', ':workspace', 'echo hacked>> .codex\agents\demo.toml', $null, $false),
    @('rename .codex', ':workspace', 'ren .codex .codex_x', '.codex_x', $false),
    @('overwrite existing .agents skill', ':workspace', 'echo hacked> .agents\skills\demo-skill\SKILL.md', $null, $false),
    @('append .git\config', ':workspace', 'echo hacked>> .git\config', $null, $false),
    @('new file .git\hooks\pre-commit', ':workspace', 'echo x> .git\hooks\pre-commit', '.git\hooks\pre-commit', $false),
    @('new file .aws\probe.txt', ':workspace', 'echo x> .aws\probe.txt', '.aws\probe.txt', $false),
    @('profile :read-only writes', ':read-only', 'echo x> ro.txt', 'ro.txt', $false)
  )
  foreach ($r in $rows) {
    $rc = Sbx $r[1] $r[2]
    $created = if ($r[3]) { Test-Path $r[3] } else { 'n/a' }
    "{0,-40} exit={1} created={2}" -f $r[0], $rc, $created
  }
  "config.toml untouched: $(-not ((Get-Content .codex\config.toml -Raw) -match 'hacked'))   agents file untouched: $(-not ((Get-Content .codex\agents\demo.toml -Raw) -match 'hacked'))"
  $rc = Sbx $null 'echo x> dflt.txt';                                   "no profile, no -c: write exit=$rc created=$(Test-Path dflt.txt)"
  $rc = Sbx $null 'echo x> sm.txt' @('-c', 'sandbox_mode="workspace-write"'); "-c sandbox_mode=workspace-write: write exit=$rc created=$(Test-Path sm.txt)"
  $rc = Sbx $null 'echo x> .git\sm.txt' @('-c', 'sandbox_mode="workspace-write"'); "-c sandbox_mode=workspace-write: .git write exit=$rc created=$(Test-Path .git\sm.txt)"

  "`n## P5 command network (curl exit 7 = could not connect; control run is unsandboxed)"
  $ctl = curl.exe -s -m 8 -o NUL -w '%{http_code}' https://example.com
  $null = & codex sandbox -P ':workspace' -- curl.exe -s -m 8 -o NUL -w '%{http_code}' https://example.com 2>&1
  "unsandboxed HTTP status=$ctl   :workspace curl exit=$LASTEXITCODE"
  $null = & codex sandbox -- curl.exe -s -m 8 -o NUL -w '%{http_code}' https://example.com 2>&1
  "no-profile curl exit=$LASTEXITCODE"
}
finally {
  Set-Location $(if ($repoRoot) { $repoRoot } else { $env:TEMP })
  if ($c -and (Test-Path $c) -and $c.StartsWith($env:TEMP)) { Remove-Item -Recurse -Force $c -ErrorAction SilentlyContinue }
}
