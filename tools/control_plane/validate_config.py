"""Validate .codex/config.toml against the P1-S03 baseline (BLUEPRINT.md section 1.2).

Usage: python -I tools/control_plane/validate_config.py [--codex] [--self-test]
  (default)    static policy checks on .codex/config.toml; exit 0 = pass, 1 = fail
  --codex      also load the file as the user layer of a throwaway CODEX_HOME and require
               `codex doctor` to report "config.toml parse: ok" (no model session, no trust change)
  --self-test  prove each static check fails on a mutated config (negative controls)
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".codex" / "config.toml"

# Exact expected content: any added key is a failure until the baseline is deliberately extended.
EXPECTED = {
    "approval_policy": "on-request",
    "sandbox_mode": "workspace-write",
    "sandbox_workspace_write": {"network_access": False},
    "shell_environment_policy": {"ignore_default_excludes": False},
    "agents": {"max_concurrent_threads_per_session": 4},
}
# Called out by name so the failure message says why, even though EXPECTED already excludes them.
FORBIDDEN_TOP = {
    "default_permissions": "permission profiles do not compose with sandbox_mode (silent override)",
    "permissions": "permission profiles do not compose with sandbox_mode (silent override)",
    "mcp_servers": "no MCP servers in the delivered configuration",
    "hooks": "hooks belong to a later phase",
    "projects": "machine-local trust is operator-only",
    "approvals_reviewer": "optional Phase 4 item",
    "model_provider": "machine/account specific",
}


def _same(a, b):
    """Strict equality: same types (4.0 != 4, 0 != False), recursing into tables."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def check(cfg):
    errs = []
    for key, why in FORBIDDEN_TOP.items():
        if key in cfg:
            errs.append(f"forbidden key '{key}': {why}")
    if cfg.get("approval_policy") in ("untrusted", "on-failure"):
        errs.append(f"retired/deprecated approval_policy {cfg['approval_policy']!r}")
    if cfg.get("sandbox_mode") == "danger-full-access":
        errs.append("sandbox_mode must not be danger-full-access")
    if cfg.get("sandbox_workspace_write", {}).get("network_access") is not False:
        errs.append("sandbox_workspace_write.network_access must be explicitly false")
    if cfg.get("shell_environment_policy", {}).get("ignore_default_excludes") is not False:
        errs.append("shell_environment_policy.ignore_default_excludes must be explicitly false")
    if "writable_roots" in cfg.get("sandbox_workspace_write", {}):
        errs.append("writable_roots must not be set (protected paths stay read-only)")
    if "max_threads" in cfg.get("agents", {}):
        errs.append("agents.max_threads is a legacy alias; use max_concurrent_threads_per_session")
    if not _same(cfg, EXPECTED):
        errs.append("content differs from the approved baseline (unexpected, missing or changed keys)")
    return errs


def mutations(cfg):
    def m(fn):
        c = copy.deepcopy(cfg)
        fn(c)
        return c
    return {
        "approval untrusted": m(lambda c: c.update(approval_policy="untrusted")),
        "approval on-failure": m(lambda c: c.update(approval_policy="on-failure")),
        "approval never": m(lambda c: c.update(approval_policy="never")),
        "sandbox danger-full-access": m(lambda c: c.update(sandbox_mode="danger-full-access")),
        "network true": m(lambda c: c["sandbox_workspace_write"].update(network_access=True)),
        "network key removed": m(lambda c: c["sandbox_workspace_write"].pop("network_access")),
        "env excludes ignored": m(lambda c: c["shell_environment_policy"].update(ignore_default_excludes=True)),
        "env key removed": m(lambda c: c.pop("shell_environment_policy")),
        "writable_roots added": m(lambda c: c["sandbox_workspace_write"].update(writable_roots=["C:/x"])),
        "profile alongside sandbox_mode": m(lambda c: c.update(default_permissions=":workspace")),
        "mcp server added": m(lambda c: c.update(mcp_servers={"x": {"command": "x"}})),
        "legacy max_threads": m(lambda c: c["agents"].update(max_threads=4)),
        "unknown key": m(lambda c: c.update(task_classifier={"enabled": True})),
        "concurrency changed": m(lambda c: c["agents"].update(max_concurrent_threads_per_session=8)),
        "concurrency float": m(lambda c: c["agents"].update(max_concurrent_threads_per_session=4.0)),
    }


# Each mutation must trip its own named check, not only the generic baseline-equality check.
EXPECTED_ERR = {
    "approval untrusted": "retired/deprecated",
    "approval on-failure": "retired/deprecated",
    "sandbox danger-full-access": "danger-full-access",
    "network true": "network_access",
    "network key removed": "network_access",
    "env excludes ignored": "ignore_default_excludes",
    "env key removed": "ignore_default_excludes",
    "writable_roots added": "writable_roots",
    "profile alongside sandbox_mode": "default_permissions",
    "mcp server added": "mcp_servers",
    "legacy max_threads": "max_threads",
}


def codex_parse_check():
    codex = shutil.which("codex")
    if not codex:
        return ["codex not found on PATH"]
    home = Path(tempfile.mkdtemp(prefix="cp-s03-home-"))
    try:
        shutil.copyfile(CONFIG, home / "config.toml")
        env = dict(os.environ, CODEX_HOME=str(home))
        out = subprocess.run([codex, "doctor", "--json"], capture_output=True, text=True, env=env, cwd=home)
        checks = json.loads(out.stdout)["checks"]
        det = checks["config.load"]["details"]
        errs = []
        if det.get("config.toml parse") != "ok":
            errs.append(f"codex doctor config.toml parse = {det.get('config.toml parse')!r}")
        if checks["config.load"]["status"] != "ok":
            errs.append(f"config.load status {checks['config.load']['status']}")
        return errs
    finally:
        shutil.rmtree(home, ignore_errors=True)


def main(argv):
    cfg = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    errs = check(cfg)
    if "--codex" in argv:
        errs += codex_parse_check()
    for e in errs:
        print("FAIL:", e)
    if "--self-test" in argv:
        missed = []
        for n, c in mutations(cfg).items():
            found = check(c)
            want = EXPECTED_ERR.get(n)
            if not found or (want and not any(want in e for e in found)):
                missed.append(n)
        for n in missed:
            print("SELF-TEST FAIL: mutation not detected:", n)
        print(f"self-test: {len(mutations(cfg)) - len(missed)}/{len(mutations(cfg))} mutations detected by the intended check")
        errs += missed
    print("PASS" if not errs else "FAILED")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
