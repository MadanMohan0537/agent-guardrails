# Threat model

The enforce module (from [ScopeLock](https://github.com/MadanMohan0537/scopelock)) assumes an agent may hallucinate, receive prompt injection, retry calls, or have its proposed arguments changed between approval and execution. The gateway, not the prompt, is the enforcement boundary.

| Asset | Threat | Implemented control | Residual risk |
|---|---|---|---|
| Tool authority | Unknown or over-scoped tool | deny-by-default registry and per-agent scopes | host process could bypass the gateway |
| Money | Excessive or redirected transfer | limits, recipient allowlist, distinct dual approval | policy configuration can be wrong |
| Approval intent | Payload changed after review | canonical payload hash, tool version, expiry | canonicalization does not encode external state |
| Audit evidence | History edited after execution | append-only API and SHA-256 hash chain | SQLite administrator can rewrite and rehash history |
| Operations | Approval queue stalls work | automatic low-risk reads and small transfers | no SLA service in this MVP |
| External systems | Dry run causes side effects | local deterministic simulator | adapters must implement true preview semantics |

Out of scope: authentication, key custody, network isolation, distributed consensus, cryptographic signer identities, production policy administration, and security certification.
