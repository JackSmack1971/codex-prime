<#
.SYNOPSIS
  Read-only P0-S01 environment probe for CODEX PRIME (BLUEPRINT v1.1 §0.2, §0.5).
.DESCRIPTION
  Prints a sanitized Markdown fact sheet to stdout. It never writes files, installs, upgrades,
  edits configuration, starts a model session, or reads credential files. User-home paths are
  rewritten to %USERPROFILE%; environment variables are reported as set/unset only; user
  config.toml is reported as section and key names only (never values).
  Run from the repository root:  pwsh -NoProfile -File tools/control_plane/collect_baseline.ps1
  -IncludeDoctor additionally runs `codex doctor --summary` (local checks plus unpaid connectivity probes).
#>
param([switch]$IncludeDoctor)
$ErrorActionPreference = 'Continue'
$home_ = $env:USERPROFILE
function San([string]$s) { if ($null -eq $s) { return '' }; $s = [regex]::Replace($s, [regex]::Escape($home_), '%USERPROFILE%', 'IgnoreCase'); $posix = '/' + $home_.Substring(0,1).ToLower() + ($home_.Substring(2) -replace '\\','/'); [regex]::Replace($s, [regex]::Escape($posix), '%USERPROFILE%', 'IgnoreCase') }
function Sec([string]$t) { "`n## $t`n" }
function Run([string]$label, [scriptblock]$b) {
  "**$label**"; '```text'
  try { & $b 2>&1 | ForEach-Object { San "$_" } } catch { "ERROR: $(San $_.Exception.Message)" }
  '```'
}

"# Baseline probe output (shell: PowerShell $($PSVersionTable.PSVersion) $($PSVersionTable.PSEdition))"
Sec 'Operating system'
$os = Get-CimInstance Win32_OperatingSystem
Run 'OS' { "$($os.Caption) | version $($os.Version) | build $($os.BuildNumber) | $($os.OSArchitecture)" }

Sec 'Codex binary'
$cmd = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1
Run 'Resolution' {
  if ($cmd) { "$($cmd.CommandType) | $($cmd.Source)"; $i = Get-Item $cmd.Source; "size=$($i.Length) modified=$($i.LastWriteTime.ToString('s'))" } else { 'codex not found on PATH' }
}
Run 'codex --version' { codex --version }
Run 'codex login status (availability only)' { codex login status }
Run 'Selected feature flags (codex features list)' {
  codex features list | Where-Object { $_ -match '^(hooks|multi_agent|multi_agent_v2|goals|network_proxy|worktrees|skill_search|shell_tool|guardian_approval|plugins|codex_hooks|memories)\s' }
}
Run 'Subcommands present' {
  $h = (codex --help) -join "`n"
  foreach ($c in 'exec', 'review', 'sandbox', 'debug', 'features', 'doctor', 'execpolicy', 'mcp', 'resume', 'fork') {
    "{0,-11} listed in top-level help: {1}" -f $c, [bool]($h -match "(?m)^\s+$c\s")
  }
  codex execpolicy check --help *> $null
  "execpolicy check --help works (exit code): $LASTEXITCODE"
}
if ($IncludeDoctor) { Run 'codex doctor --summary' { codex doctor --summary --no-color --ascii } }

Sec 'Environment (presence only)'
Run 'Variables' { foreach ($n in 'CODEX_HOME', 'OPENAI_API_KEY', 'CODEX_API_KEY') { "$n set: $([bool][Environment]::GetEnvironmentVariable($n))" } }

Sec 'Repository'
Run 'Git' {
  "git: $(git --version)"; "root: $(git rev-parse --show-toplevel)"; "branch: $(git branch --show-current)"
  "HEAD: $(git rev-parse --verify -q HEAD; if ($LASTEXITCODE) { 'none (no commits)' })"
  "remotes:"; git remote -v | ForEach-Object { ($_ -replace '//[^@/]*@', '//') }
  "worktrees:"; git worktree list
  "status:"; git status --short --branch
  "diff --stat:"; git diff --stat; "cached --stat:"; git diff --cached --stat
  "stash entries: $((git stash list | Measure-Object).Count)"
  "core.autocrlf: $(git config --get core.autocrlf)"
}
Run 'Untracked file inventory (size, sha256 prefix)' {
  git ls-files --others --exclude-standard | ForEach-Object { $f = Get-Item $_; "{0} {1} bytes sha256={2}" -f $_, $f.Length, (Get-FileHash $_).Hash.Substring(0, 16) }
}

Sec 'Existing control-plane artifacts'
Run 'Repository' {
  foreach ($p in 'AGENTS.md', '.codex', '.agents', '.codex-runtime', '.gitignore', '.gitattributes', 'tools', 'tests') { "{0,-16} exists: {1}" -f $p, (Test-Path $p) }
}
Run 'Instruction files on the path above the repo (existence, size, sha256 prefix; content not read)' {
  $d = Split-Path (Get-Location).Path -Parent
  while ($d) {
    foreach ($n in 'AGENTS.md', 'AGENTS.override.md') { $f = Join-Path $d $n; if (Test-Path $f) { "$f $((Get-Item $f).Length) bytes sha256=$((Get-FileHash $f).Hash.Substring(0,16))" } }
    $d = Split-Path $d -Parent
  }
}
Run 'User-level Codex layer (names only)' {
  $c = "$home_\.codex"
  foreach ($n in 'config.toml', 'hooks.json', 'AGENTS.md', 'AGENTS.override.md', 'rules\default.rules') { "{0,-22} exists: {1}" -f $n, (Test-Path "$c\$n") }
  "user config.toml sections/keys (values omitted):"
  Get-Content "$c\config.toml" | ForEach-Object {
    if ($_ -match '^\s*\[projects\.') { "  [projects.<redacted>]" } elseif ($_ -match '^\s*\[(.+)\]') { "  [$($Matches[1])]" } elseif ($_ -match '^\s*([A-Za-z0-9_.\-"]+)\s*=') { if ($Matches[1] -match '^"') { "    key: <quoted key redacted>" } else { "    key: $($Matches[1])" } } }
  "default.rules: $((Get-Content "$c\rules\default.rules").Count) lines; decisions: " + ((Select-String -Path "$c\rules\default.rules" -Pattern 'decision="(\w+)"' -AllMatches).Matches | Group-Object { $_.Groups[1].Value } | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join ', '
  "system skills: $((Get-ChildItem "$c\skills\.system" -Directory -Name) -join ', ')"
}
Run 'User-level skills in ~/.agents/skills (counts, SKILL.md presence, names)' {
  "directories: $((Get-ChildItem "$home_\.agents\skills" -Directory | Measure-Object).Count)"
  $d = Get-ChildItem "$home_\.agents\skills" -Directory; "with SKILL.md: $((($d | Where-Object { Test-Path "$($_.FullName)\SKILL.md" }) | Measure-Object).Count); without: $((($d | Where-Object { -not (Test-Path "$($_.FullName)\SKILL.md") }).Name) -join ', ')"
  "user skill names: $($d.Name -join ', ')"
  "files at top level: $((Get-ChildItem "$home_\.agents\skills" -File -Name) -join ', ')"
}
Run 'Managed/admin config locations' { foreach ($p in 'C:\ProgramData\OpenAI\Codex', 'C:\ProgramData\codex') { "$p exists: $(Test-Path $p)" } }

Sec 'Toolchains'
Run 'Versions' {
  foreach ($t in 'node', 'npm', 'python', 'py', 'pip', 'uv', 'pytest', 'git', 'gh', 'cargo', 'rustc', 'go', 'dotnet', 'java', 'pwsh', 'jq', 'wsl') {
    $c = Get-Command $t -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { $v = try { (& $c.Source --version 2>&1 | Select-Object -First 1) -replace "`0", '' } catch { '?' }; "$t | $(San $c.Source) | $v" } else { "$t | not found" }
  }
}
Run 'WSL distributions' { (wsl.exe -l -v 2>&1) -join "`n" -replace "`0", '' }

Run 'Git probes from Git Bash (second shell; uses only the bash that ships with the resolved git, never the WSL launcher)' {
  $g = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1
  $bash = if ($g) { Join-Path (Split-Path (Split-Path $g.Source -Parent) -Parent) 'bin\bash.exe' }
  if ($bash -and (Test-Path $bash)) {
    & $bash -c 'uname -s; command -v git; git --version; git branch --show-current; git status --short --branch; command -v codex; codex --version' 2>&1 | ForEach-Object { San "$_" }
  } else { 'Git for Windows bash.exe not found next to git; second-shell probe skipped (bash on PATH may be the WSL launcher and is deliberately not used)' }
}