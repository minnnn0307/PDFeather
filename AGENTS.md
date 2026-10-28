# PDFeather maintenance rules

- Manage versions autonomously using SemVer 2.0.0: PATCH for fixes and identity-only corrections, MINOR for backward-compatible new features, MAJOR for incompatible changes. A task with both fixes and a feature uses MINOR.
- `app_meta.py` is the source of application name, version and publisher. Display the product name exactly as `PDFeather`; do not append a role description or version to application/window names. Show version separately in About and file metadata.
- Publisher is `조민혁` for Korean UI and `Minhyeok Cho` for English UI. Keep bilingual EXE resources and localized installer AppPublisher. Do not claim digital signing without an actual certificate.
- Run `python scripts/build_metadata.py` after changing metadata. Do not hand-edit generated `installer/version_info.txt` or `installer/version.iss`.
- Update RELEASE_NOTES.md for every release. Never ship different application code under an already published version; bump PATCH or higher before publishing.
- Windows workflow builds, tests and publishes `v<VERSION>` on main pushes. Keep update notification parsing and the release installer asset name aligned. Do not enable prerelease notifications in the stable channel.
- PDF reading, rendering, text copy, capture and printing must work offline. Update checks alone may contact GitHub, are optional, asynchronous and bounded; they never upload documents. Installer downloads and installation require an explicit in-app install click, a canonical repository URL, exact asset size and SHA-256 verification.
- Icon filenames identify artwork revisions, not the application version. Change the versioned icon path only when artwork changes to avoid stale Windows icon caches.
