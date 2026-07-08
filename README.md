# WebSiteMCP

**Much of the world's information and services live behind websites built for people, not agents. WebSiteMCP is a specification to make them accessible to agents.**

The actions people actually need, moving money, booking travel, filing a claim, checking an order, mostly live behind websites with no usable API. Meanwhile the Model Context Protocol (MCP) has become the common way to give agents tools, but it reaches APIs, not the human web. WebSiteMCP closes that gap by _describing_ a site's actions as MCP tools, instead of requiring the site to publish an API of its own.

It is a specification, a set of JSON Schemas, for describing a human-facing site as a stable, versioned set of agent-callable MCP tools. The volatile part, how a given site actually works, is confined to a single replaceable layer, so a redesign is a behind-the-scenes republish and nothing an agent sees changes. That isolation is what makes an agent's use of a site reliable rather than brittle.

## Core Concepts

A **contract** defines the common actions for a category of site, for banking, _check balance, transfer funds, pay a bill_, as an abstract, versioned tool interface. It is authored once and shared by every provider in the category: the actions are the same whichever bank you use.

_How_ each action maps onto a specific site differs from site to site, and that lives in a **binding**, a per-site description of how to fulfill the contract on one provider's site, which the provider can publish itself. The actions are common; the binding is specific.

A **manifest** joins the two for a given site, identified by its hostname as a reverse-DNS folder path (`www.svb.com` lives at `domain/com/svb/www/`): it names which contracts the site offers and pins the exact contract and binding versions in use. It does not list tools, the binding's implemented tools are the live set, so there's nothing to duplicate or let drift. To use a site, a client resolves its host (`www.svb.com` → `domain/com/svb/www/`), pulls that manifest for the pinned contracts and bindings, then reads each binding to see which tools are live and each contract for their definitions.

Together these are the **what/how split** the spec formalizes: the contract fixes _what_ the tools are and holds still, while the binding holds _how_ they map onto the site and absorbs the churn of the real web. Confining the volatile _how_ to the binding is what lets a site change without changing the tools an agent sees.

Concretely, the spec is a set of **JSON Schemas**, contract, manifest, and binding. Every contract, manifest, and binding is a JSON document validated against them, so the pieces are guaranteed to fit before anything ships.

## Artifacts

| Artifact     | Scope                          | Defines                                                           |
| ------------ | ------------------------------ | ----------------------------------------------------------------- |
| **Contract** | Shared, per category  | The abstract tool interface: tools, each with description + inputSchema/outputSchema + errors |
| **Manifest** | Per site              | Which contracts and binding versions are live                   |
| **Binding**  | Per (site × contract) | How each tool maps onto the site (and thus which tools are live) |

The contract is the shared, public interface; the binding is its private, site-specific implementation and the source of truth for which tools are live; the manifest just pins the contracts and bindings a site offers.

## Constraints

MCP tool names are limited: a name must match `^[a-zA-Z0-9_-]{1,64}$`, **at most 64 characters, and no dots.** (The MCP spec itself is looser, but clients like Claude Desktop enforce exactly this, so it's the safe common denominator.)

WebSiteMCP uses **dots** as its separator, the reverse-DNS host, contract, and tool joined into one keypath, because it reads clearly and mirrors the domain path. That dotted form is *logical*. To get the name an agent actually calls (the *wire* name), each dot is transcoded to an underscore:

```
logical:  org.wikipedia.fr.search
wire:     org_wikipedia_fr_search
```

The 64-character budget is shared across the whole name (host + contract + tool), so keep each part short and abbreviate where you can. A name whose wire form would exceed 64 characters is invalid.

## Repository layout

```
SPEC_1.0.md                              # the normative specification
schema/1.0/                              # JSON Schemas (the machine-readable spec)
  contract.json  manifest.json  binding.json
contract/
  bank@1.0.json                       # shared, abstract; versioned in the filename
domain/
  com/svb/www/                           # hostname as a reverse-DNS path (www.svb.com)
    manifest.json                        # the per-site declaration
    <contract>@<bindingVersion>.json     # the binding
tools/validate.py                        # conformance checker
Makefile
```

Schemas are versioned as a set (`schema/1.0/`); instances pin the spec they conform to via their `$schema` pointer and carry their own version in the filename.

## Example

A worked slice looks like `contract/bank@1.0.json` plus a per-site `domain/<reverse-DNS path>/` pair (`manifest.json` + `bank@1.0.json`), for example `domain/com/svb/www/` (the reverse-DNS path for `www.svb.com`). It would expose the `bank` category, declaring only `checkBalance`, `transfer`, and `payBill` of the contract's full tool set.

## Validate

```
make validate
```

Walks every manifest, resolves the contracts and bindings it pins, and checks structure plus the spec invariants (tool subset, conformance floor, binding coverage, contract-pin match, bind-map integrity). Pure `python3`, no dependencies; if `jsonschema` is importable it additionally validates each instance against `schema/1.0/`.

## Specification

`SPEC_1.0.md` is the full normative reference: the three artifacts, the tool-naming scheme, versioning rules, and the validation invariants.
