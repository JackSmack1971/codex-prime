"""Check delegation packets against contracts.md section 3 (P2-S02; BLUEPRINT.md v1.2 sections 2.4 and 2.5).

Usage: python -I tools/control_plane/check_delegation_packets.py PACKETS_FILE
       python -I tools/control_plane/check_delegation_packets.py --self-test
Exit: 0 = every packet passes; 1 = a violation; 2 = unusable input (missing, empty, undecodable file) or self-test failure.

PACKETS_FILE is UTF-8 text. Packets are separated by a line containing only `---`. A packet has an optional `AGENT:` line and
the six fields, each as `NAME:` at the start of a line followed by its content (BLUEPRINT 2.4 example):
OBJECTIVE, SCOPE, BOUNDARIES, EVIDENCE, OUTPUT, COMPLETION.

What this is. A post-hoc grader for expectations DELEG-1 (six non-empty fields) and DELEG-3 (no two writable packets claim
overlapping paths). It is `control-plane-enforced` only in the sense that a script you run on text you give it can fail; it
does not stop Codex from spawning anything, it does not read Codex events, and the six-field packet itself is a convention
(contracts section 3). How spawn prompts appear in `codex exec --json` output is unverified, so extracting packets from
a session is out of scope; feed the prompt text in. Failure behavior: unreadable or empty input exits 2, never 0.
Read-only is inferred from the BOUNDARIES text (`read-only`, `do not edit`, `no edits`); that inference is a heuristic.
"""
import re
import sys
from pathlib import Path

FIELDS = ("OBJECTIVE", "SCOPE", "BOUNDARIES", "EVIDENCE", "OUTPUT", "COMPLETION")
HEAD = re.compile(r"^(AGENT|" + "|".join(FIELDS) + r"):[ \t]*(.*)$")
READ_ONLY = re.compile(r"read-only|do not edit|no edits", re.I)
PATH_TOKEN = re.compile(r"[^\s,;`'\"]+")


def split_packets(text):
    packets, cur = [], []
    for line in text.splitlines():
        if line.strip() == "---":
            packets.append(cur)
            cur = []
        else:
            cur.append(line)
    packets.append(cur)
    return [p for p in packets if any(l.strip() for l in p)]


def parse_packet(lines):
    """Return ({FIELD: text}, [duplicate/unknown notes]). Text before the first heading is ignored."""
    fields, notes, cur = {}, [], None
    for line in lines:
        m = HEAD.match(line)
        if m:
            cur = m.group(1)
            if cur in fields:
                notes.append(f"field {cur} appears more than once")
            fields[cur] = m.group(2)
        elif cur is not None:
            fields[cur] += "\n" + line
    return {k: v.strip() for k, v in fields.items()}, notes


def scope_paths(scope):
    out = []
    for tok in PATH_TOKEN.findall(scope):
        tok = tok.lstrip("-*").strip()
        if "/" in tok or "\\" in tok or re.search(r"\.\w+$", tok):
            out.append(tok.replace("\\", "/").rstrip("/"))
    return out


def overlaps(a, b):
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def check_packets(text):
    errs = []
    packets = split_packets(text)
    if not packets:
        return None, ["no packets found"]
    parsed = []
    for i, lines in enumerate(packets, 1):
        fields, notes = parse_packet(lines)
        label = f"packet {i}" + (f" ({fields['AGENT']})" if fields.get("AGENT") else "")
        errs += [f"{label}: {n}" for n in notes]
        for f in FIELDS:
            if not fields.get(f, "").strip():
                errs.append(f"{label}: field {f} missing or empty (DELEG-1)")
        parsed.append((label, fields))
    writable = []
    for label, fields in parsed:
        if fields.get("BOUNDARIES") and not READ_ONLY.search(fields["BOUNDARIES"]):
            paths = scope_paths(fields.get("SCOPE", ""))
            if not paths:
                errs.append(f"{label}: writable packet names no recognizable path in SCOPE (DELEG-3 cannot be checked)")
            writable.append((label, paths))
    for i, (la, pa) in enumerate(writable):
        for lb, pb in writable[i + 1:]:
            for x in pa:
                for y in pb:
                    if overlaps(x, y):
                        errs.append(f"{la} and {lb}: writable scopes overlap ({x} / {y}) (DELEG-3)")
    return parsed, errs


# --- self-test fixtures -------------------------------------------------------------------------------------------------
BLUEPRINT_EXAMPLE = """AGENT: security_auditor

OBJECTIVE:
Assess the authentication-token storage flow
for confidentiality and authorization defects.

SCOPE:
src/auth/
src/storage/
tests/auth/

BOUNDARIES:
Read-only investigation.
Do not edit files.
Do not reveal credentials.

EVIDENCE:
Inspect implementation, relevant tests,
configuration, and actual trust boundaries.

OUTPUT:
- Concrete vulnerabilities
- File and symbol references

COMPLETION:
Every finding must be tied to inspected
behavior or explicitly labeled hypothetical.
"""


def _packet(agent="impl_a", scope="src/a/", boundaries="Edit only the scoped files.", **drop):
    f = {"OBJECTIVE": "Fix X.", "SCOPE": scope, "BOUNDARIES": boundaries, "EVIDENCE": "Read the tests.",
         "OUTPUT": "Changed files.", "COMPLETION": "Focused test passes."}
    for k in drop:
        f.pop(k, None)
    head = f"AGENT: {agent}\n" if agent else ""
    return head + "".join(f"{k}:\n{v}\n\n" for k, v in f.items())


def self_test():
    cases = [
        # label, text, expected exit-like verdict (True = no errors), substring the error must contain
        ("blueprint example passes", BLUEPRINT_EXAMPLE, True, None),
        ("two writable disjoint scopes pass", _packet("a", "src/a/") + "---\n" + _packet("b", "src/b/"), True, None),
        ("two read-only overlapping scopes pass",
         _packet("a", "src/", "Read-only.") + "---\n" + _packet("b", "src/x/", "Do not edit files."), True, None),
        ("missing OBJECTIVE", _packet(OBJECTIVE=1), False, "field OBJECTIVE missing"),
        ("missing COMPLETION", _packet(COMPLETION=1), False, "field COMPLETION missing"),
        ("empty EVIDENCE", _packet().replace("Read the tests.", ""), False, "field EVIDENCE missing"),
        ("duplicate field", _packet() + "OBJECTIVE:\nagain\n", False, "appears more than once"),
        ("identical writable scope", _packet("a", "src/a/") + "---\n" + _packet("b", "src/a/"), False, "writable scopes overlap"),
        ("parent and child writable scope", _packet("a", "src/") + "---\n" + _packet("b", "src/a/f.py"), False, "writable scopes overlap"),
        ("backslash paths overlap", _packet("a", "src\\a\\") + "---\n" + _packet("b", "src/a/x.py"), False, "writable scopes overlap"),
        ("writable packet without a path", _packet("a", "the auth code"), False, "no recognizable path"),
        ("no packets", "   \n---\n", False, "no packets found"),
    ]
    bad = 0
    for label, text, want_ok, needle in cases:
        _, errs = check_packets(text)
        ok = not errs
        hit = needle is None or any(needle in e for e in errs)
        if ok != want_ok or not hit:
            print(f"self-test FAIL: {label}: errors={errs}")
            bad += 1
    print(f"self-test: {len(cases) - bad}/{len(cases)} cases behaved as intended")
    return 2 if bad else 0


def main(argv):
    if argv == ["--self-test"]:
        rc = self_test()
        print("PASS" if rc == 0 else "FAIL")
        return rc
    if len(argv) != 1 or argv[0].startswith("-"):
        print(__doc__.split("\n\n")[0])
        return 2
    try:
        text = Path(argv[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"FAIL: cannot read input: {e}")
        return 2
    parsed, errs = check_packets(text)
    if parsed is None:
        print("FAIL:", *errs)
        return 2
    if errs:
        print("FAIL")
        for e in errs:
            print(" -", e)
        return 1
    print(f"PASS: {len(parsed)} packet(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
