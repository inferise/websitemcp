# WebSiteMCP, Specification 1.0

WebSiteMCP, a specification for re-describing websites designed for human operation as structured, agent-callable tools in the shape of the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). A contract tool maps directly onto an MCP [`Tool`](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

This document is the normative definition of the three artifacts and the rules that bind them. The accompanying JSON Schemas under `schema/1.0/` are the machine-readable form of these rules; where prose and schema disagree, the schema governs for structural validation and this document governs for intent. See `README.md` for the conceptual overview and motivation. Executing a binding, the runtime that drives a site, is out of scope; this spec defines only the description.

> **⚠️ Hard constraint, tool names.** An emitted MCP tool name **MUST** match `^[a-zA-Z0-9_-]{1,64}$`, **no dots, at most 64 characters.** The MCP specification itself is looser, but this is the tightest common denominator across clients (Claude Desktop enforces exactly this). The fully-qualified name is built from three parts, reverse-DNS host, contract id, and tool id, and *the whole thing* shares that 64-character budget, so every part must stay terse. Dotted forms are logical only and are rendered wire-safe per §7.

## 1. Scope and version

WebSiteMCP maps a website's human-facing interface onto a set of agent-callable tools: it re-describes an interface originally built for human use so an agent can address it as MCP tools. The central property: human-facing interfaces change continually, and WebSiteMCP confines that volatility to the binding layer, beneath a stable, versioned tool surface.

This is spec version **1.0**. The version line is shared across all schemas in `schema/1.0/` and this document (`SPEC_1.0.md`). A future revision is a new `schema/1.1/` set plus `SPEC_1.1.md`; existing instances keep pointing at the `1.0` schemas they were authored against.

## 2. Artifacts

WebSiteMCP defines three artifacts, all instance artifacts that describe real systems.

| Artifact     | Scope                  | Defines                                                           | Schema                     |
| ------------ | ---------------------- | ---------------------------------------------------------------- | -------------------------- |
| **Contract** | Shared, per category   | The abstract tool interface: tools, each with description + inputSchema/outputSchema + errors | `schema/1.0/contract.json` |
| **Manifest** | Per site               | Which contracts and binding versions are live                  | `schema/1.0/manifest.json` |
| **Binding**  | Per (site × contract)  | How each tool maps onto the site (a recording)                 | `schema/1.0/binding.json`  |

The defining property: **the contract is abstract and shared; the manifest and binding are concrete and per-site.** A site redesign is a binding-only republish, no contract change, nothing in the tool surface changes.

A site is identified by its hostname, laid out as a **reverse-DNS path** under `domain/`: `www.svb.com` lives at `domain/com/svb/www/`. That path is the site's identity, there is no separate identity field in the JSON. A distinct hostname (say `app.svb.com` → `domain/com/svb/app/`) is simply a distinct site.

## 3. Repository layout

```
SPEC_1.0.md
schema/
  1.0/
    contract.json        # meta-schema: contract artifacts
    manifest.json        # meta-schema: manifest artifacts
    binding.json         # meta-schema: binding (recording) artifacts
contract/
  bank@1.2.json       # shared, abstract; versioned filename so versions coexist
domain/
  com/svb/www/                         # the site's hostname as a reverse-DNS path (www.svb.com)
    manifest.json                      # the per-site manifest
    <contract>@<bindingVersion>.json   # the binding/recording
```

Worked example in this repo:

```
contract/bank@1.0.json
domain/com/svb/www/manifest.json
domain/com/svb/www/bank@1.0.json
```

Naming rules:

- **Contract:** `contract/<id>@<version>.json`. The filename stem before `@` equals `id`; the `@<version>` equals `version`. Versioned filenames let multiple contract versions sit on disk at once, required because manifests pin exact versions and migration is deliberate (§8).
- **Site & manifest:** `domain/<reverse-DNS path>/manifest.json`, where the path is the site's hostname reversed into folders (`www.svb.com` → `domain/com/svb/www/`). One manifest per site; the path is the identity.
- **Binding:** `domain/<reverse-DNS path>/<contract>@<bindingVersion>.json`, beside the manifest. The `@<version>` is the *binding* version, not the contract version; the contract version it targets is recorded inside as `satisfiesContract`.

## 4. Contract, the shared interface

A contract is the abstract vocabulary for a category (e.g. `bank`). It defines the full menu of tools; each tool declares a `description`, an `inputSchema`, an `outputSchema`, and a closed set of `errors`. It is authored once and reused across every site that implements the category. `inputSchema` and `outputSchema` use a constrained JSON-Schema subset (a `type`, plus `properties`/`required` for objects).

A tool is intentionally shaped like an MCP `Tool`: its key is the tool `name`, and `description`, `inputSchema`, and `outputSchema` carry the same names and meaning as in MCP, so an intermediary compiles a tool into an MCP `Tool` by copying those through (and deriving the fully-qualified name, §7). `errors` is the one addition — MCP has no error catalog on a tool — and is kept for the agent's benefit.

Two derived guarantees the rest of the spec leans on:

- The **inputSchema** property names are the only valid `{{tokens}}` a binding may inject.
- The **outputSchema** property names are the only valid output fields a binding may extract, and the **error** codes are the only codes a binding may raise.

**Every contract MUST define a `reachable` tool**, a no-argument reachability probe returning `{ reachable }` (plus an optional `detail`). It gives each contract a baseline (so a contract is never empty) and every site a uniform health check. The schema enforces its presence.

A contract may declare an optional `required` array, a conformance core of tools every implementing manifest must include (§5).

## 5. Manifest, the per-site declaration

A manifest lists the contracts live on a site; the site it belongs to is given by its path (§3), not by a field. For each contract it pins just two versions:

- `version`, the exact contract version (e.g. `1.2`).
- `binding`, the exact binding version (e.g. `1.5`).

The manifest does **not** list tools. The **binding's implemented tools are the single source of truth for what is callable**, a tool is live iff the binding has a recording for it. This avoids duplicating the tool list (and the drift it would invite); the intermediary derives the live set from the binding's keys, resolved against the contract for each tool's schema. To take a tool out of a site's surface, remove it from the binding.

```jsonc
// domain/com/example/www/manifest.json
{
  "kind": "manifest",
  "version": "1.0",
  "contracts": [
    { "id": "bank", "version": "1.2", "binding": "1.5" }
  ]
}
```

## 6. Binding, the recording

A binding implements a contract's tools for one site. It is **one-and-done**: authored by recording the in-page input, output, and actions for each tool. It is the private, site-specific implementation of the contract; its internals are never part of the tool surface.

Each tool is a `steps` array plus an optional `errors` map. The step vocabulary is semantic, not raw DOM events: `navigate`, `click`, `input`, `select`, `submit`, `waitFor`, `assert`, `read`.

**Locators are multi-strategy and ordered.** Every targeted step carries a `locators` array tried in priority order until one resolves uniquely, from most resilient (`role`, `testid`, `label`) to most brittle (`css`, `xpath`). This ordered redundancy is what lets a binding survive small redesigns and, when it can't, what a re-recording replaces.

**The bind map is explicit and two-sided.**

- *Inputs:* `input`/`select` steps inject a tool input via a `{{_name_}}` in `value`, where `_name_` is a property name from the tool's contract `inputSchema` (e.g. `{{amount}}`). No other names are valid.
- *Outputs:* `read` steps carry an `extract` that maps a captured value to a named `field` of the tool's contract `outputSchema`, with optional `as` coercion.

**Synchronization is explicit.** A `waitFor` step (or a `wait` pre-condition on any step) holds on a `selector`, `selectorGone`, `url`, `networkIdle`, or `timeout` condition before proceeding. A condition that exceeds its `timeoutMs` is a failure.

**Errors map to the contract.** The `errors` array maps a recognized failure condition (`selectorVisible`, `textContains`, `stepTimeout`, `urlMatches`) to a contract error `code`. A binding may only raise codes the contract declares for that tool.

```jsonc
// domain/com/example/www/bank@1.5.json (excerpt)
{
  "kind": "binding",
  "contract": "bank", "satisfiesContract": "1.2", "version": "1.5",
  "tools": {
    "transfer": {
      "steps": [
        { "action": "navigate", "url": "https://www.example.com/transfer",
          "wait": { "type": "networkIdle", "timeoutMs": 15000 } },
        { "action": "input", "value": "{{amount}}",
          "target": { "locators": [
            { "strategy": "label", "value": "Amount" },
            { "strategy": "testid", "value": "transfer-amount" } ] } },
        { "action": "read", "extract": { "field": "confirmationId", "from": "text", "as": "string" },
          "target": { "locators": [ { "strategy": "testid", "value": "confirmation-number" } ] } }
      ],
      "errors": [
        { "when": { "selectorVisible": { "locators": [ { "strategy": "testid", "value": "error-insufficient-funds" } ] } },
          "raise": "INSUFFICIENT_FUNDS" }
      ]
    }
  }
}
```

## 7. Tool naming

Each tool is identified by a keypath:

```
<reverse-DNS host>.<contract>.<tool>      e.g.  com.example.www.bank.transfer
```

The reverse-DNS host is the site's path (§3) rejoined with dots, `domain/com/svb/www/` yields `com.svb.www`. It namespaces every tool by the exact site it acts on. `www.svb.com` and `app.svb.com` are distinct sites (`com.svb.www`, `com.svb.app`) and therefore distinct tools with distinct bindings.

**Logical name vs wire name.** The dotted keypath above is the *logical* name, readable, and consistent with the domain path. It is not what a model sees. MCP clients constrain the tool name (`^[a-zA-Z0-9_-]{1,64}$`; no dots, ≤64 chars, see the constraint at the top of this document). The **wire name** an agent actually calls is the logical name with every `.` replaced by `_`:

```
logical:  com.svb.www.bank.transfer
wire:     com_svb_www_bank_transfer
```

The 64-character budget is shared across host, contract, and tool, so keep each part short. **A tool whose wire name would exceed 64 characters, or a tool id containing a character outside `[a-z0-9_-]`, is invalid.** (Because dots collapse to `_`, tool ids MUST NOT themselves contain `_` where it would be ambiguous with the separator, prefer camelCase within a segment, e.g. `checkBalance`.)

## 8. Versioning

All artifacts version independently because each drifts for a different reason. Every artifact uses a single `version` field; the binding additionally records `satisfiesContract`.

| Artifact     | Version line                    | Bumps when                                                       |
| ------------ | ------------------------------- | ---------------------------------------------------------------- |
| **Contract** | `bank@1.2` (in filename)     | A tool or its inputSchema/outputSchema/errors is added, changed, renamed |
| **Manifest** | `version: 1.0` (in-file only)   | Declared support changes, or a contract/binding pin moves        |
| **Binding**  | `com.example.www/bank@1.5` (in filename) | The recording changes (redesign, relocator, flow fix)            |

Rules:

- **The contract version is the agreement between manifest and binding.** A manifest pins an exact contract version; a binding records the version it satisfies. The two must match.
- **The binding version is free to move under a fixed contract version.** A relocator ships binding `1.5 → 1.6` while still satisfying `bank@1.2`. This is the whole payoff: a redesign is a binding-only republish.
- **Pins are exact, not ranges.** A manifest resolves to exactly one contract version and one binding version, so the mapping is deterministic.
- **Nothing auto-upgrades.** When a contract bumps `1.2 → 1.3`, a manifest stays on `1.2` until a `1.3` binding is authored, verified, and the manifest is explicitly re-pinned. Migration is deliberate and atomic per site. Versioned contract filenames let both versions coexist during the migration window.
- **The manifest is not versioned in its filename.** Contracts and bindings carry their version in the filename (`bank@1.2.json`) so multiple versions coexist. A site has exactly one manifest — `com.example.www/manifest.json` — and its `version` field tracks changes in place; there is no `manifest@1.0.json`.

## 9. Validation invariants

Checked at publish time, so the artifacts stay in sync by validation rather than convention. For each manifest contract entry `m` referencing contract `c@m.version` and binding `b`:

1. **Tool subset:** `keys(b.tools) ⊆ c.tools`, a binding can't implement a tool the contract doesn't define.
2. **Conformance floor (if present):** `c.required ⊆ keys(b.tools)`, a site's binding must implement the contract's required core.
3. **Contract pin match:** `b.satisfiesContract == m.version`, catches "contract moved, binding didn't."
4. **Resolvable contract:** `c@m.version` resolves to a real published contract file.
5. **Bind-map integrity:** every `{{token}}` in `b` names a property of the tool's contract `inputSchema`; every `extract.field` names a property of the tool's contract `outputSchema`; every `errors[].raise` is one of the tool's contract error `codes`.
6. **Path/identity agreement:** the site path is a valid reverse-DNS domain (two or more labels), and a binding's `contract`/`version` agree with its filename.

## 10. Authoring summary

Per site, the minimum authoring set is **two documents**:

- **1 manifest**, declares contracts + tool subsets + version pins.
- **N bindings**, one recording per supported contract.

Contracts are shared: authored once and reused across all sites. The contract is the published interface; the binding is its private, site-specific implementation; the manifest is where per-site partiality lives. Validation checks all three together (§9).
