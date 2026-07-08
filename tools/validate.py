#!/usr/bin/env python3
"""WebSiteMCP conformance checker.

Validates every site manifest and its bindings against the spec:
  * structural checks (kind, required fields, version/id patterns, path agreement)
  * the cross-artifact invariants from spec/1.0.md section 9
Resolves the shared contracts the manifest pins as needed.

Zero required dependencies. If `jsonschema` is importable, each instance is
ADDITIONALLY validated against schema/1.0/*.json for full draft-2020-12
structural conformance; otherwise that layer is skipped with a note.

Usage:  python3 tools/validate.py [REPO_ROOT]
Exit code 0 = all green, 1 = at least one failure.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
SPEC = "1.0"
SCHEMA_DIR = os.path.join(ROOT, "schema", SPEC)

SEMVER = re.compile(r"^[0-9]+\.[0-9]+$")
TOKEN = re.compile(r"\{\{(\w+)\}\}")

fails = []
checks = 0


def load(path):
    with open(path) as f:
        return json.load(f)


def check(cond, label):
    global checks
    checks += 1
    if not cond:
        fails.append(label)
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {label}")
    return cond


def find_tokens(node):
    """All {{token}} names appearing in any string within node."""
    out = set()
    if isinstance(node, str):
        out |= set(TOKEN.findall(node))
    elif isinstance(node, dict):
        for v in node.values():
            out |= find_tokens(v)
    elif isinstance(node, list):
        for v in node:
            out |= find_tokens(v)
    return out


# ---- optional JSON Schema layer -------------------------------------------
def build_schema_validators():
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except Exception:
        return None
    reg = Registry()
    schemas = {}
    for name in ("contract", "manifest", "binding"):
        s = load(os.path.join(SCHEMA_DIR, f"{name}.json"))
        schemas[name] = s
        r = Resource.from_contents(s)
        reg = reg.with_resource(s["$id"], r).with_resource(f"{name}.json", r)
    return {n: Draft202012Validator(s, registry=reg) for n, s in schemas.items()}


VALIDATORS = build_schema_validators()


def schema_validate(kind, inst, label):
    if VALIDATORS is None:
        return
    errs = sorted(VALIDATORS[kind].iter_errors(inst), key=lambda e: list(e.path))
    check(not errs, f"schema/{kind}: {label}"
          + ("" if not errs else f" -> {list(errs[0].path)} {errs[0].message}"))


def validate_manifest(mpath):
    rel = os.path.relpath(mpath, ROOT)
    print(f"\n== {rel} ==")
    parts = rel.split(os.sep)  # domain/<labels...>/manifest.json
    labels = parts[1:-1]
    host = ".".join(labels)  # reverse-DNS identity, derived from the path
    site_dir = os.path.dirname(mpath)

    m = load(mpath)
    schema_validate("manifest", m, rel)
    check(m.get("kind") == "manifest", "manifest.kind == 'manifest'")
    check(len(labels) >= 2 and all(re.match(r"^[a-z0-9-]+$", p) for p in labels),
          f"path is a reverse-DNS domain ({host})")
    check(bool(SEMVER.match(str(m.get("version", "")))), "manifest.version is MAJOR.MINOR")
    check(isinstance(m.get("contracts"), list) and m["contracts"], "manifest.contracts non-empty")

    for entry in m.get("contracts", []):
        cid = entry.get("id")
        cver = entry.get("version")
        bver = entry.get("binding")
        mmethods = set(entry.get("methods", []))
        print(f"  -- contract '{cid}'@{cver} via binding {bver} --")

        # contract resolves
        cpath = os.path.join(ROOT, "contract", f"{cid}@{cver}.json")
        if not check(os.path.exists(cpath), f"contract file resolves: contract/{cid}@{cver}.json"):
            continue
        c = load(cpath)
        cmethods = c.get("methods", {})
        check(set(mmethods) <= set(cmethods), "INV1 manifest.methods ⊆ contract.methods")
        check(set(c.get("required", [])) <= mmethods, "INV2 contract.required ⊆ manifest.methods")

        # binding resolves
        bpath = os.path.join(site_dir, f"{cid}@{bver}.json")
        if not check(os.path.exists(bpath), f"binding file resolves: {cid}@{bver}.json"):
            continue
        b = load(bpath)
        schema_validate("binding", b, os.path.relpath(bpath, ROOT))
        check(b.get("kind") == "binding", "binding.kind == 'binding'")
        check(b.get("contract") == cid, "binding.contract matches filename")
        check(str(b.get("version")) == str(bver), "binding.version matches filename @version")
        check(b.get("satisfiesContract") == cver, "INV4 binding.satisfiesContract == manifest pin")
        check(set(b.get("methods", {})) == mmethods, "INV3 binding.methods keys == manifest.methods")

        # INV6 bind-map integrity, per method
        bad = []
        for mn, rec in b.get("methods", {}).items():
            if mn not in cmethods:
                continue
            params = set(cmethods[mn].get("params", {}).get("properties", {}))
            rets = set(cmethods[mn].get("returns", {}).get("properties", {}))
            codes = {e["code"] for e in cmethods[mn].get("errors", [])}
            for t in find_tokens(rec):
                if t not in params:
                    bad.append(f"{mn}: {{{{{t}}}}} not a contract param")
            for st in rec.get("steps", []):
                ex = st.get("extract")
                if ex and ex.get("field") not in rets:
                    bad.append(f"{mn}: extract.field '{ex.get('field')}' not a contract return")
            for er in rec.get("errors", []):
                if er.get("raise") not in codes:
                    bad.append(f"{mn}: raises '{er.get('raise')}' not a contract error")
        check(not bad, "INV6 bind-map integrity (tokens/fields/error codes)")
        for x in bad:
            print("        -", x)


def main():
    manifests = []
    domain_root = os.path.join(ROOT, "domain")
    for dirpath, _, files in os.walk(domain_root):
        if "manifest.json" in files:
            manifests.append(os.path.join(dirpath, "manifest.json"))
    manifests.sort()

    if VALIDATORS is None:
        print("note: 'jsonschema' not importable — running structural + invariant checks only")
    if not manifests:
        print("no manifests found under domain/")
        return 1

    for mp in manifests:
        validate_manifest(mp)

    print(f"\n{'='*48}")
    print(f"{checks} checks, {len(fails)} failures")
    if fails:
        for f in fails:
            print("  FAIL:", f)
        print("RESULT: FAILURES")
        return 1
    print("RESULT: ALL GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
