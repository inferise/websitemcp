# Changelog

Notable changes to the WebSiteMCP specification. Newest first.

## Aligned contract tools with the MCP `Tool` shape

_2026-07-08_

Renamed the contract tool fields to match MCP's own `Tool` object so a tool compiles into an MCP `Tool` by copying fields through: `context` → `description`, `params` → `inputSchema`, `returns` → `outputSchema`. `errors` stays (MCP has no per-tool error catalog; we keep ours for the agent). `context` → `description` was applied **everywhere** — contracts, manifests, and bindings — since `description` is a non-optional MCP field we can treat as the old `context`; `inputSchema`/`outputSchema` apply to contracts only, as bindings are not MCP items. Object-valued data fields that happen to be named `description` (e.g. a transaction memo) were left untouched. Validator, `SPEC_1.0.md`, and `README.md` updated to match.

## Error messages are now actionable

_2026-07-08_

Rewrote every error `message` to say what happened **and** what the agent should do next — e.g. `NOT_SIGNED_IN` → "No active session; call auth.login first, then retry."; `NOT_FOUND` (stale preview) → "The preview expired or is unknown; re-run the preview for a fresh previewId, then retry." Recovery hints point at the concrete next tool (listAccounts, listOrders, reachable, mfaStatus, re-preview) rather than just stating the fact.

## Rewrote every `context` for fit-for-purpose

_2026-07-08_

Rewrote all `context` blurbs to one tight sentence stating what a thing is and what it's for. Two audiences, two voices: instance contexts (tool/param/return in `contract/*.json`) are jargon-free for an operating agent; schema contexts (`schema/1.0/*.json`) describe the format for authors. Dropped meta-language like "JSON-Schema-style object…" and "…a binding may extract," filled in bare return fields, and fixed a stale note that still said the required core is checked against the manifest (it's the binding). `broker` got a full field-by-field consistency pass so its account/ticker/market-data blurbs read in the same voice as `bank`/`auth`.

## Dropped contract `title`

_2026-07-08_

Removed the contract-level `title` field (schema + all contracts). It was a human-display label with no machine role now that `id` carries the identity and `context` the description; dropping it also makes contracts parallel with tools (which only have `context`). A contract is now `kind, id, version, context, tools`.

## `description`/`summary` → `context`

_2026-07-08_

Renamed every `description` and tool `summary` field to **`context`**, a purpose-built name for the concise, machine-facing text that tells an LLM what an item is. Applied to the instance artifacts, the meta-schemas (including their own annotations), and rewrote the long contract/tool text into terse one-liners. `context` is now **required** on every contract and every tool. (Data fields that happen to be named `description`, e.g. a transaction memo, are untouched, only the metadata field was renamed.)

_2026-07-08_

Removed the per-contract `tools` array from the manifest. It duplicated the binding's implemented tools (the old `binding.tools == manifest.tools` invariant literally forced them equal) and could drift. Now the **binding's implemented tools are the single source of truth for the live tool set**; the intermediary derives the callable list from the binding's keys, resolved against the contract. A manifest contract entry is just `{ id, version, binding }`.

Invariants updated accordingly: dropped `binding.tools == manifest.tools`; the subset/floor checks now run against the binding (`keys(binding.tools) ⊆ contract.tools`, `contract.required ⊆ keys(binding.tools)`). To remove a tool from a site's surface, remove it from the binding.

## Universal `reachable` tool

_2026-07-08_

Every contract now defines a `reachable` tool, a no-argument reachability probe returning `{ reachable, detail? }`. This gives every contract a baseline (so stub contracts are no longer empty) and every site a uniform health check. The schema restores `minProperties: 1` on `tools` and additionally requires a `reachable` key. `auth`'s former session-status tool was renamed to `session` (returns `active`, `mfaPending`) for clarity.

## `auth` contract: field renames

_2026-07-08_

Clarified the `auth` login/status fields: `username` → `accountId`, `organization` → `groupId`, `password` → `passcode` (method-agnostic typed secret), and `status.mfaRequired` → `mfaPending` (evokes the site awaiting the user's MFA input).

## Contracts: short ids, `tools` convention, and stubs

_2026-07-08_

- Renamed `banking` → `bank`, `authenticate` → `auth`, `brokerage` → `broker` (files, `id`, the `'auth'` cross-references in descriptions, and the example manifest + binding).
- Brought the three into the `tools` convention, they had been authored with the old `methods` key before the rename landed, which was failing validation.
- Added stub contracts with empty tool sets: `search`, `airline`, `hotel`, `insurer`, `news`, `social` (all `@1.0`; tools to be defined).
- Updated the `bank` example references throughout README and the spec.

## Schema + validator: empty tool sets and contract checks

_2026-07-08_

- `contract.tools` may now be empty (removed `minProperties: 1`) so stub/draft contracts validate.
- The validator now schema-checks every `contract/*.json` (kind + id/version vs filename), not only the contracts a manifest references, so standalone stubs are covered.

## Tool-name constraint: ≤64 chars, no dots

_2026-07-08_

Documented the hard limit on emitted MCP tool names as a callout at the top of the spec and a logical-vs-wire rule in §7 (Tool naming). An emitted tool name must match `^[a-zA-Z0-9_-]{1,64}$`. The dotted keypath (`com.svb.www.banking.transfer`) is *logical*; the **wire name** replaces every `.` with `_` (`com_svb_www_banking_transfer`) and must fit the shared 64-character budget across host + contract + tool.

Rationale: the MCP spec permits dots, but major clients don't, Claude Desktop enforces `^[a-zA-Z0-9_-]{1,64}$` exactly. This is easy to miss and silently breaks integration, so it's now front and center. Also surfaced as a **Constraints** section in the README.

## Spec surfaced to repo root as `SPEC_1.0.md`

_2026-07-08_

Moved `spec/1.0.md` → `SPEC_1.0.md` at the repository root and removed the `spec/` directory; updated references in `README.md` and `tools/validate.py`.

Rationale: the normative document was easy to miss buried under `spec/`. The version stays in the filename so versions can coexist; if/when multiple published versions are needed, a `versions/` directory (OpenAPI-style) is the migration path.

## `methods` → `tools`

_2026-07-08_

Renamed the `methods` field to `tools` across all artifacts, contracts, manifests, and bindings, and throughout the spec, README, schemas, and validator.

Rationale: under MCP the callable primitive is a *tool* (alongside resources and prompts), and every callable operation, including reads like `checkBalance`, is a tool. "methods" was OOP jargon that clashed with the tool vocabulary the spec is built on. A contract now defines `tools`; a manifest lists which `tools` a site offers; a binding implements each `tool`. Tool names themselves are unchanged.
