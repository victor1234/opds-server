# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] - 2026-07-30

### Fixed

- Bound catalog pagination to prevent requests beyond the final page (#23).
- Made catalog ordering deterministic (#22).
- Omitted navigation links from empty catalog pages (#21).
- Validated configuration during startup readiness checks (#20).
- Handled invalid Calibre timestamps (#19).
- Returned HTTP 503 when the Calibre database is unavailable (#18).
- Honored the configured catalog prefix in OPDS feeds (#17).

## [0.1.2] - 2026-07-19

### Security

- Prevented book download requests from accessing files outside the configured Calibre library (#15).

## [0.1.1] - 2025-08-27

### Changed

- Updated the documented feature list.
- Added the MIT license and declared it in the project metadata.
- Added CI concurrency to cancel superseded builds (#13).
- Configured CI to build container images from version tags.

## [0.1.0] - 2025-08-26

### Added

- Initial release.

[Unreleased]: https://github.com/victor1234/opds-server/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/victor1234/opds-server/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/victor1234/opds-server/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/victor1234/opds-server/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/victor1234/opds-server/releases/tag/v0.1.0
