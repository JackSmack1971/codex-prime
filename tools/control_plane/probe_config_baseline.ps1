<#
.SYNOPSIS
  P0-S03 probe: configuration loading, discovery, protected paths, command network (read-only for this repo).

.DESCRIPTION
  Builds a throwaway Git repo under $env:TEMP, runs Codex helper commands inside it, prints results,
  and deletes it. Does NOT touch user config, trust, hooks, or this repository. Starts no model session.
  The scratch repo is untrusted by construction (no [projects] entry), so results describe an
  UNTRUSTED project. Run from PowerShell 7 (Git Bash rewrites cmd.exe arguments).
  Network control uses curl.exe against https://example.com (one outbound HTTPS request from curl.exe; codex doctor/prompt-input may make their own).
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

  "`n## P2f AGENTS.override.md, fallback filename, and size cap (scratch root, untrusted)"
  Set-Location $s
  Set-Content "$s\AGENTS.override.md" 'OVERRIDE_SENTINEL_S03'
  $p = codex debug prompt-input | Out-String
  "override present: root AGENTS.md=$(Has $p 'ROOT_SENTINEL_S03') override=$(Has $p 'OVERRIDE_SENTINEL_S03')"
  Remove-Item "$s\AGENTS.override.md"; Remove-Item "$s\AGENTS.md"
  Set-Content "$s\FALLBACK_DOC.md" 'FALLBACK_SENTINEL_S03'
  $p = codex -c 'project_doc_fallback_filenames=["FALLBACK_DOC.md"]' debug prompt-input | Out-String
  "fallback filename (no AGENTS.md): loaded=$(Has $p 'FALLBACK_SENTINEL_S03')"
  Set-Content "$s\AGENTS.md" ('CAP_HEAD_S03 ' + ('x' * 200) + ' CAP_TAIL_S03')
  $p = codex -c 'project_doc_max_bytes=64' debug prompt-input | Out-String
  "project_doc_max_bytes=64: head loaded=$(Has $p 'CAP_HEAD_S03') tail loaded=$(Has $p 'CAP_TAIL_S03')"
  Remove-Item "$s\FALLBACK_DOC.md"; Set-Content "$s\AGENTS.md" 'ROOT_SENTINEL_S03'

  "`n## P2g rule file parse (offline checker; does NOT show the project layer loaded it)"
  codex execpolicy check --rules "$s\.codex\rules\p.rules" -- git push origin main | ConvertFrom-Json | ForEach-Object { "decision=$($_.decision)" }

  "`n## P3 default sandbox mode and network text in the rendered prompt (this repository, untrusted)"
  Set-Location $(if ($repoRoot) { $repoRoot } else { $s })
  $p = codex debug prompt-input | Out-String
  "prompt says sandbox_mode read-only: $($p -match 'sandbox_mode. is .read-only')   network restricted: $(Has $p 'Network access is restricted')"
  $nested = Join-Path $repoRoot 'tools\control_plane'
  if (Test-Path $nested) {
    Set-Location $nested
    $pn = codex debug prompt-input | Out-String
    $wr = [regex]::Matches($pn, '<root>(.*?)</root>') | ForEach-Object { $_.Groups[1].Value }
    "nested launch in this repo: workspace root(s) in prompt = $(($wr | ForEach-Object { $_ -replace [regex]::Escape($env:USERPROFILE), '%USERPROFILE%' }) -join '; ')"
  }
  if (-not $repoRoot) { "WARNING: not run inside a Git repo; P3 skipped" }

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
  function Run-Rows($label, $useProfile, $extra) {
    foreach ($r in $rows) {
      if (-not $useProfile -and $r[1] -eq ':read-only') { continue }
      $rc = Sbx $(if ($useProfile) { $r[1] } else { $null }) $r[2] $extra
      $created = if ($r[3]) { Test-Path $r[3] } else { 'n/a' }
      "{0,-14} {1,-40} exit={2} created={3}" -f $label, $r[0], $rc, $created
    }
  }
  function Guarded-State {
    $bad = @('.codex\config.toml', '.codex\agents\demo.toml', '.agents\skills\demo-skill\SKILL.md', '.git\config') |
      Where-Object { (Get-Content $_ -Raw) -match 'hacked' }
    "protected files modified (content check, expect none): $(if ($bad) { $bad -join ', ' } else { 'none' })"
  }
  Run-Rows 'profile' $true @();                                         Guarded-State
  Remove-Item -Force normal.txt -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force .codex-runtime -ErrorAction SilentlyContinue
  Run-Rows 'sandbox_mode' $false @('-c', 'sandbox_mode="workspace-write"'); Guarded-State
  $null = Sbx ':workspace' 'del .codex\config.toml'
  "del of protected .codex\config.toml: exit=$LASTEXITCODE file still present=$(Test-Path .codex\config.toml)  (grade on file state, not exit code)"
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
  if ($c -and (Test-Path $c) -and $c.StartsWith($env:TEMP)) { Remove-Item -Recurse -Force $c -ErrorAction SilentlyContinue; if (Test-Path $c) { "WARNING: scratch dir not removed: $c" } }
}
