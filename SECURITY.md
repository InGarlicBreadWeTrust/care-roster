# Security posture of `care-roster`

`care-roster` is an **offline** care-giver roster / accountability tool. Of the
five sibling tools, it holds the **most sensitive PII**: care-recipient and
care-giver names, contact detail, and duty times. It is a pure-stdlib, no-
network tool. This page is the threat model and the standing protections; read it
alongside `PRIVACY.md`.

## Threat model

| Input / asset | Trusted? | Why it is safe |
| --- | --- | --- |
| Roster/events on disk | No, low risk of *code* risk | Parsed as data with stdlib `json`; content is never executed. |
| CLI arguments (names, times, paths) | No, low risk | Parsed and stored; never `eval`'d/`exec`'d or sent anywhere. |
| `--input` / `--output` paths | Yes | Resolved locally; never executed or exfiltrated (no network). |

## Design principles

1. **No code execution.** No `eval`, `exec`, `compile`, `subprocess`,
   `os.system`, `pickle`, `marshal`, or `ctypes`. A roster file can never run
   code — it is parsed as JSON and treated as data only.
2. **No network, no telemetry.** No sockets, no HTTP, no third-party runtime
   dependencies. Because the tool has no network capability, the PII it holds
   cannot be exfiltrated *by this tool*.
3. **No hardcoded secrets.** No credentials, API keys, or tokens in the source.
4. **Local writes only.** Output uses default OS permissions; no world-writable
   mode is set and no file outside the named path is touched.

## Recommendations for this tool specifically (most important in this set)

- **This store contains identifiable individuals.** Treat every roster and every
  exported report as sensitive: store on an **encrypted volume**, restrict with
  `chmod 600`, and **never commit** a roster or its reports to a public
  repository.
- **Do not export care data into a shared/public path.** CSV/markdown reports are
  human-readable and leak names and times; write them only where access is
  controlled.
- **Confidentiality is on you, not the code.** The tool guarantees no network
  egress and no exfiltration path; it does **not** encrypt at rest. Disk
  encryption (`FileVault`/`LUKS`/`BitLocker`) is the control that actually
  protects this data.

## Reporting a vulnerability

Open an issue labelled `security`. Describe the version
(`python -m care_roster --version`), the command or file that triggered it, and a
redacted example. Do not include real care-recipient or care-giver names.

---

## Independent security audit (2026-10-21)

**Performed by:** `InGarlicBreadWeTrust` · **Type:** static source + dependency
review · **Result:** no vulnerabilities found.

**Method:** static review of every `.py` source, the `pyproject.toml` build
config, and the dependency graph; grep for the runtime-risk surface
(`subprocess`, `os.system`, `eval`/`exec`/`compile`, `pickle`/`marshal`,
`ctypes`, sockets/network).

**Findings for `care-roster`:**
- No `subprocess`, `os.system`, `exec`, `eval`, `compile`, `pickle`, `marshal`,
  or `ctypes` present.
- No network I/O (no sockets, no HTTP, no telemetry); zero runtime dependencies.
- No hardcoded secrets or credentials.
- No build-time backdoor: stock `setuptools` build-meta, no custom hooks or
  `setup.py` side-effects in the runtime surface.
- Persistence writes JSON with default OS permissions; no world-writable mode,
  no path escape, and no exfiltration path exists because there is no network.
- `Coverage`/`Gap` and the single-day `CareEvent` invariant are enforced, so a
  mis-dated event can't silently create an unfilled shift.

**Verdict:** no code vulnerability found. The dominant risk for this tool is
**data protection, not code**: it carries the highest-priority PII of the set, so
the recommendations above (encrypted volume, `chmod 600`, no public export) are
the real controls. No code changes required.
