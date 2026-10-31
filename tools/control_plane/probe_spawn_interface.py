"""Report the `spawn_agent` tool interface that the installed Codex renders into its model-visible prompt (P2-S03).

Usage: python -I tools/control_plane/probe_spawn_interface.py            # probe the installed codex
       python -I tools/control_plane/probe_spawn_interface.py --self-test  # test the extractor on synthetic documents
Exit: 0 = a spawn_agent definition was found and summarized; 2 = codex missing, output not JSON, or no unique definition
(an unknown interface is never reported as a pass). Starts no model session: it runs `codex debug prompt-input` only.

What this is. Local evidence about the interface the installed binary offers the model, taken from a rendered prompt. The rendered
prompt is not a documented or stable interface, so the summary describes one binary and one launch directory; it does not show how
a session behaves. The output lists parameter names and flags, never the prompt text. It does not show whether custom agents
would add parameters when a trusted project defines them: that is unobserved.
"""
import json
import re
import shutil
import subprocess
import sys

MODEL_ID = re.compile(r"`(gpt-[\w.\-]+)`")
SELECTOR_HINT = re.compile(r"agent|role|type|persona|profile", re.I)


def find_tools(doc, name="spawn_agent"):
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("name") == name and isinstance(o.get("parameters"), dict):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(doc)
    return found


def summarize(tool):
    params = tool["parameters"]
    props = params.get("properties", {})
    return {
        "parameters": sorted(props),
        "required": sorted(params.get("required", [])),
        "additionalProperties": params.get("additionalProperties"),
        "encrypted_parameters": sorted(k for k, v in props.items() if isinstance(v, dict) and v.get("encrypted")),
        "selector_like_parameters": sorted(k for k in props if k != "task_name" and SELECTOR_HINT.search(k)),
        "model_override_ids": MODEL_ID.findall(tool.get("description", "")),
    }


def probe(text):
    doc = json.loads(text.lstrip("﻿"))
    tools = find_tools(doc)
    if len(tools) != 1:
        raise ValueError(f"expected exactly one spawn_agent definition, found {len(tools)}")
    return summarize(tools[0])


def self_test():
    def tool(props, required=(), extra=False, desc=""):
        return {"type": "function", "name": "spawn_agent", "description": desc,
                "parameters": {"type": "object", "properties": props, "required": list(required), "additionalProperties": extra}}

    base = tool({"task_name": {"type": "string"}, "message": {"type": "string", "encrypted": True}}, ["task_name", "message"],
                desc="Available: `gpt-a` and `gpt-b.1`.")
    cases = []
    s = summarize(base)
    cases.append(("parameters and required", s["parameters"] == ["message", "task_name"] and s["required"] == ["message", "task_name"]))
    cases.append(("encrypted flag", s["encrypted_parameters"] == ["message"]))
    cases.append(("model ids", s["model_override_ids"] == ["gpt-a", "gpt-b.1"]))
    cases.append(("no selector", s["selector_like_parameters"] == []))
    sel = summarize(tool({"task_name": {"type": "string"}, "agent_type": {"type": "string"}}))
    cases.append(("selector detected", sel["selector_like_parameters"] == ["agent_type"]))
    nested = [{"type": "namespace", "tools": [base]}]
    cases.append(("nested lookup", probe(json.dumps(nested))["parameters"] == ["message", "task_name"]))
    for label, bad in (("absent tool", "[]"), ("two definitions", json.dumps([base, base])), ("not json", "hello")):
        try:
            probe(bad)
            cases.append((label + " rejected", False))
        except (ValueError, json.JSONDecodeError):
            cases.append((label + " rejected", True))
    ok = sum(1 for _, v in cases if v)
    for label, v in cases:
        if not v:
            print("self-test FAIL:", label)
    print(f"self-test: {ok}/{len(cases)} cases behaved as intended")
    return 0 if ok == len(cases) else 2


def main(argv):
    if argv == ["--self-test"]:
        rc = self_test()
        print("PASS" if rc == 0 else "FAIL")
        return rc
    if argv:
        print(__doc__.split("\n\n")[0])
        return 2
    codex = shutil.which("codex")
    if not codex:
        print("FAIL: codex not found on PATH")
        return 2
    try:
        out = subprocess.run([codex, "debug", "prompt-input", "probe"], capture_output=True, text=True, encoding="utf-8",
                             stdin=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"FAIL: could not run codex debug prompt-input: {e}")
        return 2
    if out.returncode != 0:
        print(f"FAIL: codex debug prompt-input exited {out.returncode}")
        return 2
    try:
        summary = probe(out.stdout)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"FAIL: {e}")
        return 2
    ver = subprocess.run([codex, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
    print(json.dumps({"codex": ver, "spawn_agent": summary}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
