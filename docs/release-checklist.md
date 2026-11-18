# Version 1 release checklist

No stable release or tag exists. Before declaring v1.0, record evidence for
every item and update the [requirement matrix](v1-requirement-matrix.md).

- [ ] Every agreed v1 requirement is complete or has an explicit accepted
      limitation, including P1 items within the agreed scope.
- [x] A real public HTTPS fetch passes with owner-approved external access;
      SSRF, approval and uncertain-recovery tests pass on Linux and Windows.
- [ ] The same-user report directory replacement race is resolved or its
      residual risk is explicitly accepted for the local threat model.
- [ ] Database migrations pass from a fresh checkout and from the prior
      supported schema. Backup and restore are exercised with artifacts.
- [ ] Backend tests, Ruff, OpenAPI drift check, frontend tests, type check,
      production build, dependency audit and isolated browser suite pass.
      Full audit currently fails on unpatched development-tool
      `picomatch` [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
- [ ] Installed-model Ollama plan and execution pass when a local model is
      available; otherwise record that this gate was not run.
- [ ] Manual keyboard and assistive technology review, responsive screens,
      recovery fault injection and sustained performance checks are recorded.
- [ ] User, security, API, architecture, operations and troubleshooting docs
      match observed behavior. Screenshots show the current UI.
- [ ] Owner decides the legal license and versioning policy. No license is
      inferred from the specification alone.
- [ ] Final GitHub Actions run passes on the release candidate commit; the
      tree is clean and the release notes list known limitations.

The verified P0 baseline is 10/10. That percentage measures only baseline
functional IDs and is not a release-readiness percentage.
