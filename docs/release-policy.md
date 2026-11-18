# NEXUS release and risk-acceptance policy

Approved by the repository owner on **2026-11-18**.

## Licence and versioning

- The project is licensed under [MIT](../LICENSE), copyright 2026 Christopher Doyle.
- Versions use [Semantic Versioning](https://semver.org/) in the form MAJOR.MINOR.PATCH.
- The first stable release is planned as `v1.0.0` **only after** the [release checklist](release-checklist.md) passes.
- No tag or stable release is authorised by this policy alone.

## Local deployment boundary

NEXUS v1 targets **single-owner localhost use**. Remote or multi-user deployment is unsupported.
The owner explicitly accepts the documented residual same-user report-directory race
only in a trusted environment without hostile same-user processes. This is not a
claim of isolation against malware, local adversaries, or process compromise.
See [security audit](security-audit.md) for the precise limitations.

## Temporary npm advisory exception

- Advisory: [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), picomatch repeated-extglob ReDoS.
- Scope: only the exact locked **development-only** picomatch/Vite/Vitest dependency tree.
- Approved: 2026-11-18. **Expires at end of 2026-12-18 UTC.**
- Audit implementation: `apps/web/scripts/audit-dependencies.mjs`. The full audit output remains visible in CI.
- Every other high/critical finding, changed package path/version, or expired exception **fails CI**.
- The production-dependency audit must separately pass. This exception does not affect runtime code, network permissions, or any other security finding.
- Review at every release candidate and immediately if an upstream patch becomes available; remove the exception in favour of a tested, compatible fix.
- Never accept untrusted glob patterns in project tooling while this vulnerability remains.

## Unresolved manual release gate

On 2026-11-18 the owner reported successful desktop keyboard navigation and
Windows Narrator announcements of buttons, labels and status messages in NEXUS.
A documented view-by-view assistive-technology check at mobile width is still
outstanding. Do not mark the application stable or create `v1.0.0` until that
check and the remaining release gates pass.
