# WebSiteMCP

**Much of the world's information and services live behind websites built for people, not agents. WebSiteMCP is a specification to make them accessible to agents.**

The actions people actually need, moving money, booking travel, filing a claim, checking an order, mostly live behind websites with no usable API. Meanwhile the Model Context Protocol (MCP) has become the common way to give agents tools, but it reaches APIs, not the human web. WebSiteMCP closes that gap by _describing_ a site's actions as MCP tools, instead of requiring the site to publish an API of its own.

It is a specification, a set of JSON Schemas, for describing a human-facing site as a stable, versioned set of agent-callable MCP tools. The volatile part, how a given site actually works, is confined to a single replaceable layer, so a redesign is a behind-the-scenes republish and nothing an agent sees changes. That isolation is what makes an agent's use of a site reliable rather than brittle.

## Core Concepts

A **contract** defines the common actions for a category of site, for banking, _check balance, transfer funds, pay a bill_, as an abstract, versioned tool interface. It is authored once and shared by every provider in the category: the actions are the same whichever bank you use.

_How_ each action maps onto a specific site differs from site to site, and that lives in a **binding**, a per-site description of how to fulfill the contract on one provider's site, which the provider can publish itself. The actions are common; the binding is specific.

A **manifest** joins the two for a given site, identified by its hostname as a reverse-DNS folder path (`www.svb.com` lives at `domain/com/svb/www/`): it declares which contracts, and which of their actions, that site actually offers, and pins the exact contract and binding versions in use.

Together these are the **what/how split** the spec formalizes: the contract fixes _what_ the tools are and holds still, while the binding holds _how_ they map onto the site and absorbs the churn of the real web. Confining the volatile _how_ to the binding is what lets a site change without changing the tools an agent sees.

Concretely, the spec is a set of **JSON Schemas**, contract, manifest, and binding. Every contract, manifest, and binding is a JSON document validated against them, so the pieces are guaranteed to fit before anything ships.

## Artifacts

| Artifact     | Scope                          | Defines                                                           |
| ------------ | ------------------------------ | ----------------------------------------------------------------- |
| **Contract** | Shared, per category  | The abstract tool interface: methods + param/return/error schemas |
| **Manifest** | Per site              | Which contracts, which methods, and which binding are live        |
| **Binding**  | Per (site × contract) | How each method maps onto the site                                |

The contract is the shared, public interface; the binding is its private, site-specific implementation; the manifest declares which of the contract's tools a site actually offers.

## Repository layout

```
spec/1.0.md                              # the normative specification
schema/1.0/                              # JSON Schemas (the machine-readable spec)
  contract.json  manifest.json  binding.json
contract/
  banking@1.0.json                       # shared, abstract; versioned in the filename
domain/
  com/svb/www/                           # hostname as a reverse-DNS path (www.svb.com)
    manifest.json                        # the per-site declaration
    <contract>@<bindingVersion>.json     # the binding
tools/validate.py                        # conformance checker
Makefile
```

Schemas are versioned as a set (`schema/1.0/`); instances pin the spec they conform to via their `$schema` pointer and carry their own version in the filename.

## Example

A worked slice looks like `contract/banking@1.0.json` plus a per-site `domain/<reverse-DNS path>/` pair (`manifest.json` + `banking@1.0.json`), for example `domain/com/svb/www/` (the reverse-DNS path for `www.svb.com`). It would expose the `banking` category, declaring only `checkBalance`, `transfer`, and `payBill` of the contract's full method set.

## Validate

```
make validate
```

Walks every manifest, resolves the contracts and bindings it pins, and checks structure plus the spec invariants (method subset, conformance floor, binding coverage, contract-pin match, bind-map integrity). Pure `python3`, no dependencies; if `jsonschema` is importable it additionally validates each instance against `schema/1.0/`.

## Specification

`spec/1.0.md` is the full normative reference: the three artifacts, the tool-naming scheme, versioning rules, and the validation invariants.
