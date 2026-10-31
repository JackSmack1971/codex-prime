"""Validate .codex/agents/*.toml against the documented custom-agent format (P2-S01, BLUEPRINT.md v1.2 section 2.3).

Usage: python -I tools/control_plane/validate_agents.py [--self-test]
  (default)    static checks on every .codex/agents/*.toml; exit 0 = pass, 1 = fail
  --self-test  prove each static check fails on a mutated agent (negative controls)

Scope and limits. This is a static check of the file against the schema in the official subagents page
(learn.chatgpt.com/docs/agent-configuration/subagents, checked 2026-10-31). It does NOT show that Codex discovers
or spawns the agent: the installed CLI (0.166.0) has no command that parses an agent file, `debug prompt-input`
lists no agent roster, and discovery needs a trusted project plus a model session (BLOCKED: operator).
"""
import copy
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / ".codex" / "agents"

REQUIRED = ("name", "description", "developer_instructions")
OPTIONAL_TOP = {"model", "model_reasoning_effort", "model_reasoning_summary", "model_verbosity"}
# Documented capability reductions: set to false only.
FEATURE_KEYS = {"shell_tool", "apps", "plugins", "memories", "request_permissions_tool"}
SKILLS_KEYS = {"config", "bundled", "include_instructions"}
# Documented as ignored in an agent file (they belong to the parent session): writing them misleads.
IGNORED = {
    "sandbox_mode": "inherited from the parent session; ignored in an agent file",
    "approval_policy": "inherited from the parent session; ignored in an agent file",
    "model_provider": "inherited from the parent session; ignored in an agent file",
    "mcp_servers": "inherited from the parent session; ignored in an agent file",
    "service_tier": "follows the root session; ignored in an agent file",
}
BUILTIN = {"default", "worker", "explorer"}  # a custom agent with these names silently takes precedence
ANALYSIS_ONLY = {"architect"}  # BLUEPRINT 2.3: analysis-only specialists drop command execution
STATUSES = ("COMPLETE", "PARTIAL", "BLOCKED", "CONFLICTED", "UNVERIFIED")
MAX_DESC = 600


def _words(s):
    return set(re.findall(r"[a-z]{4,}", s.lower()))


def check_agent(stem, cfg):
    errs = []
    for k in REQUIRED:
        v = cfg.get(k)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{stem}: required field '{k}' missing, empty or not a string")
    for k, why in IGNORED.items():
        if k in cfg:
            errs.append(f"{stem}: '{k}' is {why}")
    allowed = set(REQUIRED) | OPTIONAL_TOP | {"features", "skills"} | set(IGNORED)
    for k in cfg:
        if k not in allowed:
            errs.append(f"{stem}: unknown key '{k}' (not in the documented agent schema)")
    for k in OPTIONAL_TOP:
        if k in cfg and not (isinstance(cfg[k], str) and cfg[k].strip()):
            errs.append(f"{stem}: '{k}' must be a non-empty string")
    feats = cfg.get("features", {})
    if not isinstance(feats, dict):
        errs.append(f"{stem}: 'features' must be a table")
    else:
        for k, v in feats.items():
            if k not in FEATURE_KEYS:
                errs.append(f"{stem}: features.{k} is not a documented agent capability reduction "
                            f"(a '[features]' header before developer_instructions captures later keys)")
            elif v is not False:
                errs.append(f"{stem}: features.{k} must be false (agent files only reduce capabilities)")
    skills = cfg.get("skills", {})
    if not isinstance(skills, dict):
        errs.append(f"{stem}: 'skills' must be a table")
    else:
        for k in skills:
            if k not in SKILLS_KEYS:
                errs.append(f"{stem}: skills.{k} is not a documented key")
    name = cfg.get("name")
    if isinstance(name, str):
        if name.replace("-", "_") != stem.replace("-", "_"):
            errs.append(f"{stem}: name {name!r} does not match the filename (project convention)")
        if name in BUILTIN:
            errs.append(f"{stem}: name {name!r} shadows a built-in agent (must be deliberate; none is approved)")
    desc = cfg.get("description")
    if isinstance(desc, str) and len(desc) > MAX_DESC:
        errs.append(f"{stem}: description is {len(desc)} chars (> {MAX_DESC}); keep it short so routing stays clear")
    di = cfg.get("developer_instructions")
    if isinstance(di, str):
        if not re.search(r"(?i)do not edit repository files", di) and stem in ANALYSIS_ONLY:
            errs.append(f"{stem}: analysis-only agent must tell the model not to edit repository files")
        if not all(s in di for s in STATUSES):
            errs.append(f"{stem}: instructions must name the five completion statuses (BLUEPRINT 2.7)")
        if not re.search(r"(?i)do not invent", di):
            errs.append(f"{stem}: instructions must forbid invented APIs or runtime behavior")
        if not re.search(r"(?i)evidence|inspected", di):
            errs.append(f"{stem}: instructions must require inspected evidence (BLUEPRINT 2.9)")
    if stem in ANALYSIS_ONLY and feats.get("shell_tool") is not False:
        errs.append(f"{stem}: analysis-only agent must set features.shell_tool = false (BLUEPRINT 2.3)")
    return errs


def check_all(agents):
    """agents: {stem: cfg}. Cross-agent checks run here."""
    errs = []
    names = {}
    for stem, cfg in agents.items():
        errs += check_agent(stem, cfg)
        n = cfg.get("name")
        if isinstance(n, str):
            if n in names:
                errs.append(f"duplicate agent name {n!r} in {stem} and {names[n]}")
            names[n] = stem
    stems = sorted(agents)
    for i, a in enumerate(stems):
        for b in stems[i + 1:]:
            da, db = agents[a].get("description"), agents[b].get("description")
            if isinstance(da, str) and isinstance(db, str):
                wa, wb = _words(da), _words(db)
                if wa and wb and len(wa & wb) / len(wa | wb) > 0.5:
                    errs.append(f"descriptions of {a} and {b} overlap heavily (BLUEPRINT 2.9: minimal overlap)")
    return errs


def load():
    agents, errs = {}, []
    if not AGENTS.is_dir():
        return agents, [f"{AGENTS} not found"]
    for p in sorted(AGENTS.glob("*.toml")):
        try:
            agents[p.stem] = tomllib.loads(p.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
            errs.append(f"{p.name}: does not parse as TOML: {e}")
    if not agents and not errs:
        errs.append("no agent files found")
    for extra in sorted(AGENTS.iterdir()):
        if extra.is_file() and extra.suffix != ".toml":
            errs.append(f"{extra.name}: unexpected non-TOML file in .codex/agents/")
    return agents, errs


def _drop(d, *path):
    d = copy.deepcopy(d)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    cur.pop(path[-1], None)
    return d


def mutations(base):
    """(label, mutated {stem: cfg}, substring the intended check must emit)."""
    a = base["architect"]

    def one(cfg):
        return {"architect": cfg}

    def setk(path, value):
        d = copy.deepcopy(a)
        cur = d
        for k in path[:-1]:
            cur = cur.setdefault(k, {})
        cur[path[-1]] = value
        return one(d)

    twin = copy.deepcopy(a)  # same name as the original, different file stem
    return [
        ("missing name", one(_drop(a, "name")), "required field 'name'"),
        ("empty description", setk(("description",), "  "), "required field 'description'"),
        ("missing developer_instructions", one(_drop(a, "developer_instructions")), "required field 'developer_instructions'"),
        ("sandbox_mode in agent", setk(("sandbox_mode",), "read-only"), "'sandbox_mode' is inherited"),
        ("approval_policy in agent", setk(("approval_policy",), "never"), "'approval_policy' is inherited"),
        ("mcp_servers in agent", setk(("mcp_servers",), {"x": {"url": "http://localhost"}}), "'mcp_servers' is inherited"),
        ("unknown key", setk(("tools",), ["shell"]), "unknown key 'tools'"),
        ("undocumented feature key", setk(("features", "web_search"), False), "features.web_search is not a documented"),
        ("feature set true", setk(("features", "apps"), True), "features.apps must be false"),
        ("shell_tool not disabled", setk(("features", "shell_tool"), True), "features.shell_tool must be false"),
        ("shell_tool absent", one(_drop(a, "features", "shell_tool")), "must set features.shell_tool = false"),
        ("name shadows built-in", setk(("name",), "explorer"), "shadows a built-in"),
        ("name differs from file", setk(("name",), "other"), "does not match the filename"),
        ("unknown skills key", setk(("skills", "paths"), []), "skills.paths is not a documented key"),
        ("description too long", setk(("description",), "word " * 200), "chars (>"),
        ("no edit prohibition", setk(("developer_instructions",),
            a["developer_instructions"].replace("Do not edit repository files", "Feel free to change files")), "not to edit repository files"),
        ("statuses removed", setk(("developer_instructions",),
            a["developer_instructions"].replace("CONFLICTED", "X")), "five completion statuses"),
        ("invention ban removed", setk(("developer_instructions",),
            a["developer_instructions"].replace("Do not invent", "Feel free to invent")), "forbid invented"),
        ("evidence requirement removed", setk(("developer_instructions",),
            re.sub(r"(?i)evidence|inspected", "stuff", a["developer_instructions"])), "inspected evidence"),
        ("non-string effort", setk(("model_reasoning_effort",), 5), "'model_reasoning_effort' must be"),
        ("duplicate name", {"architect": a, "architect_two": twin}, "duplicate agent name"),
        ("overlapping descriptions", {"architect": a, "architect_two": {**copy.deepcopy(a), "name": "architect_two"}}, "overlap heavily"),
    ]


def self_test(base):
    bad = 0
    ok_base = check_all(base)
    if ok_base:
        print("self-test: baseline does not pass:", *ok_base, sep="\n  ")
        return 1
    # A table header before developer_instructions must be caught by the real file parser path.
    captured = tomllib.loads('name="a"\ndescription="d"\n[features]\nshell_tool=false\ndeveloper_instructions="x"\n')
    if "developer_instructions" not in captured.get("features", {}):
        print("self-test: TOML capture assumption is wrong")
        return 1
    if not any("features.developer_instructions" in e for e in check_agent("a", captured)):
        print("self-test FAIL: '[features]' capture of developer_instructions not detected")
        bad += 1
    muts = mutations(base)
    for label, cfgs, needle in muts:
        errs = check_all(cfgs)
        if not any(needle in e for e in errs):
            print(f"self-test FAIL: mutation '{label}' not detected by the intended check ({needle!r}); got {errs}")
            bad += 1
    total = len(muts) + 1
    print(f"self-test: {total - bad}/{total} mutations detected by the intended check")
    return 1 if bad else 0


def main(argv):
    agents, errs = load()
    if not errs:
        errs = check_all(agents)
    if errs:
        print("FAIL")
        for e in errs:
            print(" -", e)
        return 1
    rc = 0
    if "--self-test" in argv:
        rc = self_test(agents)
    print("PASS" if rc == 0 else "FAIL")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
