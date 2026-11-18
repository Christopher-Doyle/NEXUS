# Version 1 release acceptance — 2026-11-18

The owner requested publication of `v1.0.0` on 2026-11-18, accepting the explicitly
bounded local-only scope and the documented limitations. The publication
workflow triggers only after the final release candidate's CI run succeeds.
A successful workflow creates the `v1.0.0` tag and GitHub Release; no release
is claimed if that automation does not finish successfully.

- [x] Every agreed v1 requirement is complete or has an explicit accepted
      limitation, including P1 items within the agreed scope. Owner accepted
      the local-only text-tool and provider-interface scope on 2026-11-18;
      unsupported general-purpose computer automation and provider-selection
      cards are planned for later work, not misrepresented as v1 features.
- [x] A real public HTTPS fetch passes with owner-approved external access;
      SSRF, approval and uncertain-recovery tests pass on Linux and Windows.
- [x] The same-user report directory replacement race is resolved or its
      residual risk is explicitly accepted for the local threat model.
      Owner accepted the documented limitation on 2026-11-18 for strictly
      local, single-owner use without hostile same-user processes.
- [x] Database migrations pass from a fresh checkout and from the prior
      supported schema. Backup and restore are exercised with artifacts.
- [x] Backend tests, Ruff, OpenAPI drift check, frontend tests, type check,
      production build, dependency audit policy and isolated browser suite
      passed at `03bfced4` (all three CI jobs). The owner-approved exception
      is *only* for development-tool picomatch advisory GHSA-fc5q-39xc-vjpf,
      expires end of 2026-12-18 UTC; full audit output is retained and a
      separate production audit must pass. Final release publication is
      additionally gated on CI success for the release candidate itself.
- [x] Installed-model Ollama plan and execution pass with the local
      `qwen3.5:9b` model in the opt-in browser suite.
- [x] Automated keyboard paths, responsive screens, recovery fault injection,
      a sustained loopback readiness sample and a 40-task supervised worker
      sample are recorded.
- [x] Manual assistive technology review is recorded with an actual screen
      reader and keyboard on the supported desktop and mobile views.
      On 2026-11-18 the owner reported successful keyboard operation and
      Windows Narrator announcements of buttons, labels and status messages.
      The owner then confirmed the responsive interface worked in Chrome's
      device emulation at 400px, after being asked to test navigation with
      Narrator. This is owner-attested manual evidence, not independent audit
      certification or testing on a physical mobile device.
- [x] User, security, API, architecture, operations and troubleshooting docs
      describe the bounded local-only behaviour. Screenshots are from verified
      application runs. Known limits and the expiry of the dev-tool exception
      are disclosed in the v1 release notes.
- [x] Owner approved MIT licensing and Semantic Versioning on 2026-11-18.
      LICENSE is present; the first stable tag will be v1.0.0 only after the
      remaining release gates pass.
- [x] The release publication workflow enforces final successful CI on the
      **same** `main` release candidate commit and verifies `main` still
      points to that commit before creating the tag/release. The release notes
      disclose known limitations. This item records a CI-enforced gate, not a
      claim that an asynchronous workflow already finished.

The verified P0 baseline is 10/10. That percentage measures only baseline
functional IDs and is not a release-readiness percentage.

## Manual release decisions

- Owner reported a successful desktop Windows Narrator and keyboard review,
  then confirmed the mobile-width check worked in Chrome at 400px on 2026-11-18.
  The mobile result uses browser emulation, not a physical phone.
- Owner accepted the documented same-user directory risk for a strictly
  local single-owner threat model on 2026-11-18. Reassess for any remote or
  hostile same-user environment.
- Owner approved the MIT licence, Semantic Versioning and the narrowly scoped
  dependency exception expiring end of 2026-12-18 UTC.
- Owner-reported Windows Narrator, keyboard navigation and responsive
  400px mobile-emulation checks passed on 2026-11-18. Any future release
  with material UI changes should repeat these checks.
- The three GitHub CI jobs passed at `03bfced4`. Publication of `v1.0.0`
  is conditional on a successful fresh CI run for the release-candidate
  commit, verified by the one-time release workflow.
