#!/usr/bin/env python3
"""WebSiteMCP conformance checker.

Validates every site manifest and its bindings against the spec:
  * structural checks (kind, required fields, version/id patterns, path agreement)
  * the cross-artifact invariants from SPEC_1.0.md section 9
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


def validate_contract(cpath):
    rel = os.path.relpath(cpath, ROOT)
    print(f"\n== {rel} ==")
    c = load(cpath)
    schema_validate("contract", c, rel)
    check(c.get("kind") == "contract", "contract.kind == 'contract'")
    stem = os.path.basename(cpath)[:-5]  # strip '.json'
    fid, _, fver = stem.partition("@")
    check(c.get("id") == fid, f"contract.id matches filename ({fid})")
    check(str(c.get("version")) == fver, f"contract.version matches filename ({fver})")


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
        print(f"  -- contract '{cid}'@{cver} via binding {bver} --")

        # contract resolves
        cpath = os.path.join(ROOT, "contract", f"{cid}@{cver}.json")
        if not check(os.path.exists(cpath), f"contract file resolves: contract/{cid}@{cver}.json"):
            continue
        c = load(cpath)
        cmethods = c.get("tools", {})

        # binding resolves, the binding's tools ARE the live tool set
        bpath = os.path.join(site_dir, f"{cid}@{bver}.json")
        if not check(os.path.exists(bpath), f"binding file resolves: {cid}@{bver}.json"):
            continue
        b = load(bpath)
        schema_validate("binding", b, os.path.relpath(bpath, ROOT))
        check(b.get("kind") == "binding", "binding.kind == 'binding'")
        check(b.get("contract") == cid, "binding.contract matches filename")
        check(str(b.get("version")) == str(bver), "binding.version matches filename @version")
        check(b.get("satisfiesContract") == cver, "INV3 binding.satisfiesContract == manifest pin")

        btools = set(b.get("tools", {}))
        check(btools <= set(cmethods), "INV1 binding.tools ⊆ contract.tools")
        check(set(c.get("required", [])) <= btools, "INV2 contract.required ⊆ binding.tools")

        # INV4 bind-map integrity, per tool
        bad = []
        for mn, rec in b.get("tools", {}).items():
            if mn not in cmethods:
                continue
            params = set(cmethods[mn].get("inputSchema", {}).get("properties", {}))
            rets = set(cmethods[mn].get("outputSchema", {}).get("properties", {}))
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
        check(not bad, "INV4 bind-map integrity (tokens/fields/error codes)")
        for x in bad:
            print("        -", x)


def main():
    manifests = []
    domain_root = os.path.join(ROOT, "domain")
    for dirpath, _, files in os.walk(domain_root):
        if "manifest.json" in files:
            manifests.append(os.path.join(dirpath, "manifest.json"))
    manifests.sort()

    contract_dir = os.path.join(ROOT, "contract")
    contracts = sorted(
        os.path.join(contract_dir, f)
        for f in os.listdir(contract_dir)
        if f.endswith(".json")
    ) if os.path.isdir(contract_dir) else []

    if VALIDATORS is None:
        print("note: 'jsonschema' not importable, running structural + invariant checks only")
    if not manifests and not contracts:
        print("no contracts under contract/ or manifests under domain/")
        return 1

    for cp in contracts:
        validate_contract(cp)
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
