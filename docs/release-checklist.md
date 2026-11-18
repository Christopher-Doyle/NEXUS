# Version 1 release checklist

No stable release or tag exists. Before declaring v1.0, record evidence for
every item and update the [requirement matrix](v1-requirement-matrix.md).

- [ ] Every agreed v1 requirement is complete or has an explicit accepted
      limitation, including P1 items within the agreed scope.
- [x] A real public HTTPS fetch passes with owner-approved external access;
      SSRF, approval and uncertain-recovery tests pass on Linux and Windows.
- [x] The same-user report directory replacement race is resolved or its
      residual risk is explicitly accepted for the local threat model.
      Owner accepted the documented limitation on 2026-11-18 for strictly
      local, single-owner use without hostile same-user processes.
- [x] Database migrations pass from a fresh checkout and from the prior
      supported schema. Backup and restore are exercised with artifacts.
- [ ] Backend tests, Ruff, OpenAPI drift check, frontend tests, type check,
      production build, dependency audit and isolated browser suite pass.
      Owner approved an exception only for development-tool
      `picomatch` [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)
      through 2026-12-18; CI must verify the narrowly scoped policy and
      independently pass the production audit before this gate is checked.
- [x] Installed-model Ollama plan and execution pass with the local
      `qwen3.5:9b` model in the opt-in browser suite.
- [x] Automated keyboard paths, responsive screens, recovery fault injection,
      a sustained loopback readiness sample and a 40-task supervised worker
      sample are recorded.
- [ ] Manual assistive technology review is recorded with an actual screen
      reader and keyboard on the supported desktop and mobile views.
- [ ] User, security, API, architecture, operations and troubleshooting docs
      match observed behavior. Screenshots show the current UI.
- [x] Owner approved MIT licensing and Semantic Versioning on 2026-11-18.
      LICENSE is present; the first stable tag will be v1.0.0 only after the
      remaining release gates pass.
- [ ] Final GitHub Actions run passes on the release candidate commit; the
      tree is clean and the release notes list known limitations.

The verified P0 baseline is 10/10. That percentage measures only baseline
functional IDs and is not a release-readiness percentage.

## Manual release decisions

- Test dashboard, plan, approval, cockpit, report comparison and Settings
  with a screen reader and keyboard at desktop and mobile widths.
- Owner accepted the documented same-user directory risk for a strictly
  local single-owner threat model on 2026-11-18. Reassess for any remote or
  hostile same-user environment.
- Owner approved the MIT licence, Semantic Versioning and the narrowly scoped
  dependency exception expiring end of 2026-12-18 UTC.
- Still outstanding: a real manual screen-reader review and the final tested
  release-candidate CI result.
