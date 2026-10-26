# Windows 7 便携网页包 Implementation Plan

> **For agentic workers:** Use executing-plans to implement and verify these steps. Main agent owns edits; scouts only inspect.

**Goal:** Deliver Word Isle 1.4.1 as an extract-and-launch ZIP for Windows 7 Ultimate x64 SP1, with no Python installation.

**Architecture:** Bundle official CPython 3.8.10 embeddable x64 and existing stdlib server/resources. A batch file runs a small launcher, stores SQLite under LOCALAPPDATA/WordIsleWeb, binds loopback and opens an installed supported browser. Ship only public resources, never existing databases/configuration/recordings.

**Tech Stack:** Python stdlib, existing HTML/CSS/JS, ZIP. No extra application dependencies.

- [x] Add failing regression checks for Windows file replacement and asynchronously loaded browser voices.
- [x] Fix shared resource UTF-8 reads, close-before-replace configuration save, and bounded voice-loading wait.
- [x] Add Windows launcher and pinned-runtime ZIP builder; include Chinese usage instructions and Win7 prerequisites.
- [x] Build ZIP, verify runtime checksum/PE x64/import paths and absence of private data.
- [x] Extract to a path containing Chinese/spaces, exercise startup, bundled books/media and persistence with a temporary user directory; run shared and browser regressions.
- [x] Deliver ZIP and state verification boundary: this Mac cannot provide Windows 7 real-machine validation. Win7 needs SP1, KB2533623 or superseding updates, and UCRT. Browser and voices remain target-machine prerequisites; OpenPronounce remains macOS-only, Tencent remains available.
