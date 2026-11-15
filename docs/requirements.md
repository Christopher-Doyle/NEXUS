# P0 requirement traceability

The source is the [20-page design specification](design-spec.pdf), section 02.
"Verified baseline" means the implemented behavior has a local test or demo;
it does not mean the v1 release gate has passed.

| ID | State | Evidence and remaining acceptance work |
| --- | --- | --- |
| NX-F01 | Verified baseline | Task API and composer accept goal, constraints and bounded text files. API tests cover input scope. |
| NX-F02 | Verified baseline | Numbered persisted plans can be generated and edited before execution; version conflict is tested. |
| NX-F03 | Verified baseline | Registry schemas, capability grant and argument hash are checked at dispatch; invalid output is rejected. |
| NX-F04 | Verified baseline | File writes require exact approval. Outbound fetch remains disabled until SSRF controls are complete. |
| NX-F05 | Partial | SSE, task states, journal, search excerpts and artifact links work; accessible operational detail and full tool receipts still need review. |
| NX-F06 | Partial | Journal, leases, safe read replay after a real worker kill, bounded attempts and uncertain-write stop are tested. The recovery API and cockpit can verify and accept an existing report or confirm absence; complete resumed multi-step workflow acceptance remains. |
| NX-F07 | Verified baseline | Downloaded Markdown reports include numbered source citations, line ranges and SHA-256 snapshots. A tampered read receipt prevents report creation; browser and backend tests cover export. Semantic claims are not independently verified. |
| NX-N01 | Verified baseline | Registry contains no shell tool and tool grants are checked server-side. |
| NX-N02 | Verified baseline | Executions carry stable unique keys; a killed worker after report file creation leaves one file and one execution, and recovery stops for review without replaying the write. Safe reads retry within a three-attempt limit. |
| NX-N03 | Verified baseline | Synthetic fixture demo runs without an LLM, including automated approval and rejection browser tests. |

**Measured baseline:** 8 of 10 P0 IDs, or **80%**. Release readiness is lower:
security, accessibility, clean-clone and documentation gates are still open.
