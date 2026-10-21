# Privacy

`care-roster` handles **no network** and collects **no data** of its own. Because
this tool holds the **most sensitive PII in the collection** (care-recipients and
care-givers), read this carefully — and alongside `SECURITY.md`.

## In one line
It reads and writes locally on your disk only, and it phones home to no one.

## What the tool does NOT do
- **No telemetry, no analytics, no crash reporting, no usage tracking.** Nothing in
   the code measures or reports what you do.
- **No network of any kind.** No sockets, no HTTP/HTTPS, no background sync;
   `pyproject.toml` declares zero runtime dependencies and no socket is opened.
- **It never uploads your data.** A roster file cannot leave your machine — the tool
   has no network capability. This is the property that matters most for PII.

## What the tool DOES touch
Only the files you give it:
- the roster / events it builds for you, and
- a report/markdown only if you explicitly ask for one, written to a path you choose.
Nothing is transformed, aggregated, or retained for any purpose beyond the run. The
tool does not remember between runs or index your data.

## Data sensitivity here is the HIGHEST in the collection
A care roster holds **identifiable, sensitive personal data of two kinds of people**:
- *recipients* — name, any contact/route, and care needs, and
- *givers* — name, contact detail, and their duty times.

The tool itself never leaks that data (no network, no telemetry). The only path to
leakage is a **leaked file or a leaked report** — so your controls are all about the
file, not the code.

## Your controls (please)
- Store roster files on an **encrypted volume** (FileVault / LUKS / BitLocker). This
   is the control that actually protects this data; the tool does not encrypt at rest.
- Restrict every roster/report file: `chmod 600` so only your OS account can read it.
- **Never export rosters or reports to a shared/public location or a public
   repository** — reports are human-readable and contain names and duty times.
- Retention is entirely yours: delete a file and the data is gone; the tool keeps no
   copy, backup, or cache.

## Data sharing
None. The tool contacts no third party, has no accounts or API keys, and retains no
data itself — your roster lives only in the file you create on your own machine.

---

## Independent privacy audit (2026-10-21)

**Performed by:** `InGarlicBreadWeTrust` · **Type:** static source + dependency
review · **Result:** no privacy leakage; posture strong but data is high-sensitivity.

- No telemetry / analytics / crash reporting / background sync (no network, no
   external service).
- No network I/O anywhere; zero runtime dependencies.
- No data leaves the machine; the roster file is created only by an explicit write to
   a user-chosen path.
- No third-party services or accounts.

**Recommendation (elevated priority, not a vulnerability):** this is the most
   PII-bearing tool in the set — store on an **encrypted volume**, `chmod 600` all
   roster/report files, and **never export** to a public location. No code change
   required.
