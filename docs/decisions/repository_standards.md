# Repository standards decisions

This record documents selected repository-wide policies and the status of
operational settings that require periodic verification.

## License

**Status: MIT selected.** At the owner's direction, original project source
code and developer-authored documentation use the MIT License, with Long
Nguyen as the copyright holder for the 2026 release. The tracked production
history was checked for current contributors before applying the license.
Third-party dependencies, market data, model artifacts, and research evidence
are not relicensed by this decision and may carry separate terms. The license
text is in the root `LICENSE`; package metadata declares SPDX identifier `MIT`.

## Code of conduct

**Status: no standalone policy adopted.** The project does not currently
designate a private conduct-reporting contact or run a formal contributor
program. `CONTRIBUTING.md` describes the technical workflow. Revisit a standard
code of conduct if the project establishes a private reporting route and begins
actively onboarding external contributors.

## Security disclosure channel

**Status: verified enabled on 2026-11-01.** GitHub's read-only repository
endpoint returned `enabled: true` for private vulnerability reporting.
`SECURITY.md` directs reporters to the private advisory flow. Recheck this
setting if repository ownership or security configuration changes.
