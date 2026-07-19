# Audit Remediation Report

> **Project**: Par Infinite Minesweeper (`par_infini_sweeper`)
> **Audit Date**: 2026-07-18
> **Remediation Date**: 2026-07-18
> **Severity Filter Applied**: `all` (full remediation)
> **Base commit**: `05373bd` → **Head**: `002d683` (branch `fix/audit-remediation`)

---

## Execution Summary

| Phase | Status | Agent (model) | Targeted | Resolved | Partial | Manual/Deferred |
|-------|--------|---------------|:--------:|:--------:|:-------:|:---------------:|
| 1 — Critical Security + CI Integrity | ✅ | fix-security (opus) | 8 | 7 | 0 | 1 (ARC-009) |
| 2 — Critical Correctness + Test Harness | ✅ | fix-architecture (opus) | 5 | 5 | 0 | 0 |
| 3b-i — Architecture (surgical) | ✅ | fix-architecture (opus) | 11 | 11 | 0 | 0 |
| 3b-ii — Architecture (decomposition) | ✅ | fix-architecture (opus) | 2 | 1 | 1 (ARC-005) | 1 (ARC-016) |
| 3a — Security (remaining) | ✅ | fix-security (sonnet) | 3 | 3 | 0 | 0 |
| 3c — Code Quality (all) | ✅ | fix-code-quality (opus) | 10 | 10 | 0 | 0 |
| 3d — Documentation (all) | ✅ | fix-documentation (sonnet) ×2 | 19 | 19 | 0 | 0 |
| 4 — Verification | ✅ | orchestrator | — | — | — | — |

**Overall**: **56 issues resolved**, 1 partial (ARC-005 safe-part done, risky-part deferred), 2 deferred (ARC-009 manual, ARC-016), 1 verified no-op (SEC-008). All gates green: `make checkall` (format-check + lint-check + pyright 0 errors + 36 tests) and every pre-commit hook (incl. gitleaks).

**Scope note**: Every item in AUDIT.md's `## Remediation Plan` Phase tables was executed. The audit's unscoped "Low Priority" bullets (ARC-020–027, QA-013–020) were **not** assigned to any Phase by `/audit` and remain as optional backlog (see Next Steps).

---

## Resolved Issues ✅

### Security
- **[SEC-001]** OAuth2 missing PKCE — `auth.py` — generate `code_verifier` and pass to both `create_authorization_url` and `fetch_token` (`code_challenge_method=S256`).
- **[SEC-002]** Plaintext token storage — `db.py` — `os.chmod(db_path, 0o600)`, `os.chmod(db_bak_path, 0o600)`, `db_folder.mkdir(mode=0o700)` + explicit chmod.
- **[SEC-003]** Exception text leaked from callback — `auth.py` — `send_error(500, "Authentication failed")`; raw error to stderr only.
- **[SEC-004]** Reflected `Host` header — `auth.py` — `authorization_response` built from pinned `LOOPBACK_AUTHORITY` derived from `REDIRECT_URI`.
- **[SEC-005]** Loose callback path match — `auth.py` — exact `/oauth/callback` path match (query stripped) + early `return`.
- **[SEC-006]** Inconsistent nickname validation — `models.py`, `db.py`, `__main__.py`, `dialogs/login_dialog.py` — centralized `validate_nickname` (regex charset `[A-Za-z0-9._-]` + 20-char cap) across all 5 sites, atomically.
- **[SEC-008]** DB backup file mode — `db.py` — verified already covered by SEC-002 (both `.bak` writers chmod 0600).
- **[SEC-009]** Silent nickname-migration truncation — `db.py` — migration now warns to stderr (names affected nicknames) and truncates to the 20-char cap matching `validate_nickname`.
- **[SEC-010]** `--server` localhost exposure — `__main__.py` — stderr warning that the web server is unauthenticated/localhost-only (docs half covered by DOC-006).

### Architecture
- **[ARC-001]** `get_user()` TypeError on missing user — `db.py` — `fetchone()` None-check before `dict()`; re-SELECT on requested username.
- **[ARC-002]** `get_highscores()` returned 10 oldest — `db.py` — `ORDER BY score DESC, created_ts DESC LIMIT 10`.
- **[ARC-003]** `is_logged_in()` inverted expiry — `game/state.py` — `is_expired = time_remaining <= grace_time`.
- **[ARC-004]** 865-LOC god module — `data_structures.py` decomposed into `game/{cells,subgrid,state,types}.py` + `persistence.py` + `leaderboard.py` + `renderer.py`; `data_structures.py` is now a 33-LOC re-export shim (identity-preserving).
- **[ARC-005]** Model↔UI coupling — `main_grid.py` — **safe part done**: `adjust_mouse_pos` returns explicit `(x,y)` instead of mutating `event._x`/`event._y`. *(Risky parent→Message rewiring deferred — see Manual.)*
- **[ARC-006]** Per-connection backup check — `db.py` — hoisted to once-per-launch `init_storage()`/`ensure_backup()`.
- **[ARC-007]** Import-time side effects — `__init__.py`/`__main__.py`/`db.py` — `load_dotenv`/`USER_AGENT`/`PimApp` re-export moved to `__main__.main()`; DB dir creation lazy in `init_storage`.
- **[ARC-008]** `make checkall` auto-fixing in CI — `Makefile` — added non-mutating `lint-check`/`format-check`; `checkall` now validates the committed tree.
- **[ARC-010]** `init_db` misleading signature — `db.py` — honest required-conn signature.
- **[ARC-011]** `get_user` write-on-read — `db.py` — nickname written only when changed.
- **[ARC-012]** Obscure `is_expired() in [None, True]` — `auth.py` — readable boolean with explanatory comment.
- **[ARC-013]** Duration timer fires unfocused — `main_grid.py` — guards on `has_focus`.
- **[ARC-014]** No-op self-assignment + dead code — `main_grid.py` — removed `offset = offset` and dead commented blocks.
- **[ARC-015]** `border_cell` shadowing — `game/state.py` — renamed to `target`/`candidate`.
- **[ARC-017]** `PimApp.__init__` heavy DB I/O — `pim_app.py` — deferred to `on_mount` (construction is now ~6 ms, no FS access).
- **[ARC-018]** Hardcoded port 1999 / no SO_REUSEADDR — `auth.py`/`messages.py`/`pim_app.py` — `ReusableTCPServer` (`allow_reuse_address`), `OSError` collision handling, new `AuthServerError` message + dialog.
- **[ARC-019]** Hardcoded Auth0 client ID — `auth.py`/`__main__.py` — one-time stderr warning when the production default is in use.

### Code Quality
- **[QA-001]** Zero test coverage — `tests/`, `Makefile`, `build.yml`, `pyproject.toml` — pytest + pytest-asyncio; 36 tests (4 critical-bug regressions + `SubGrid.generate_cells`, `check_subgrid_solved`, `to_dict`/`from_dict` round-trips, DB migrations, Textual `run_test()` integration); `test` wired into `checkall` + CI; `pyrightconfig` now includes `tests/`.
- **[QA-002]** First-click scrubs whole flood-fill — `game/state.py` — `first_click` cleared at entry call before recursion.
- **[QA-003]** `reveal_cell` complexity 28 + magic depth cap — `game/state.py` — iterative BFS (visited set + deque), `MAX_REVEAL_ITERATIONS` constant, extracted `_relocate_first_click_mine`/`_flood_fill_reveal`/`_ensure_neighbor_subgrids`.
- **[QA-004]** 8 bare `except Exception` — narrowed to `OAuth2Error`/`RequestException`/`JWTError`/`sqlite3.Error`/`OSError` + module logger.
- **[QA-005]** `type: ignore[reportAttributeAccessIssue]` — `leaderboard.py` — typed `_auth_post` helper (`cast(requests.Session, ...)`); all such ignores removed.
- **[QA-006]** Committed `pyproject.toml~` — deleted; `*.bak` added to `.gitignore`.
- **[QA-007]** `assert` for runtime validation — 6 sites → typed `raise ValueError`/`RuntimeError`.
- **[QA-008]** 8-neighbor loop duplicated 7× — extracted `_iter_neighbor_coords` helper.
- **[QA-009]** "Par LLAMA" docstring — `dialogs/__init__.py` → "Par Infinite Minesweeper".
- **[QA-010]** `compute_board_center` ZeroDivision — `game/state.py` — guarded empty-subgrids; documented `+5`/`-3` anchor.
- **[QA-011]** `# noqa: F821` silencers — 4 dialogs — root cause already resolved; silencers removed (verified F821 does not fire).
- **[QA-012]** pre-commit Python 3.12 → 3.13 — `.pre-commit-config.yaml`.

### Documentation
- **[DOC-001]** (Critical) Undocumented `a` leaderboard hotkey — `README.md`, `help.md` — added to both Controls lists.
- **[DOC-002]** (Critical) 30-vs-20 char limit — `README.md` — corrected to 20 + charset; added to CLI Options.
- **[DOC-003]** No CHANGELOG — created `CHANGELOG.md` (Keep-a-Changelog); fixed duplicate 0.2.6, "Addata" typo, 30-char claim; `[Unreleased]` for this remediation (version not bumped).
- **[DOC-004]** Undocumented env vars — created `docs/CONFIGURATION.md`.
- **[DOC-005]** OAuth provider list — `README.md`, `help.md` → "Google, Facebook, or GitHub".
- **[DOC-006]** `--server` docs — `README.md` — Web Server Mode subsection (localhost:8000, port-1999 OAuth collision).
- **[DOC-007]** No CONTRIBUTING — created `CONTRIBUTING.md`.
- **[DOC-008]** No architecture docs — created `docs/ARCHITECTURE.md` (post-decomposition layout, schema, OAuth PKCE, model↔UI coupling noted honestly).
- **[DOC-009]** No troubleshooting — created `docs/TROUBLESHOOTING.md` (port-1999 firewall FAQ, `--server` warning, nickname limits).
- **[DOC-010]** No release docs — created `docs/RELEASE.md` (4-stage CI, Sigstore, OIDC).
- **[DOC-011]** help.md gaps — mirrored Storage section + post-score warning.
- **[DOC-012]** Badge alt-text "x86-63" → "x86-64".
- **[DOC-013]** Duplicate Scoring sentence + grammar — fixed.
- **[DOC-014]** No build badge — added (links `build.yml`).
- **[DOC-015]** No CLI examples — added.
- **[DOC-016]** Vague roadmap — made concrete/accurate.
- **[DOC-017]** `.aider.conventions.md` Python 3.12 → 3.13 *(local-only — file is gitignored; see Manual)*.
- **[DOC-018]** Docstring coverage — Google-style sweep across `game/state.py`, `game/cells.py`, `game/subgrid.py`, `auth.py`, `db.py` (~14 docstrings; logic unchanged).
- **[DOC-019]** No SECURITY/CODE_OF_CONDUCT — created both.

---

## Requires Manual Intervention / Deferred 🔧

### [ARC-009] Static obfuscated "API key" — **MANUAL (opt-in per security policy)**
- **Why deferred**: `db.py:392` ships `headers = {"api-key": base64.b64decode("V29vdFdvb3RXb290").decode()}` (= `"WootWootWoot"`). Per the project security policy, credential rotation/externalization is opt-in and must be done manually — `/fix-audit` must not auto-rotate or auto-generate a replacement. Verified byte-for-byte untouched across all phases (gitleaks does not catch it because it is constructed at runtime).
- **Recommended approach**: (1) move the value to an env var via `python-dotenv` (e.g. `PIM_ANTIBOT_KEY`); (2) rotate the leaked value server-side; (3) consider dropping the header entirely in favor of the existing OAuth bearer token. Surface for manual review before committing any change.
- **Estimated effort**: small (code) — but requires a coordinated server-side rotation, so it is a human decision.

### [ARC-005] Model↔UI decoupling — **PARTIAL (risky part deferred)**
- **What's done**: stopped mutating Textual's private `event._x`/`event._y` (forward-compat fix).
- **Why the rest is deferred**: replacing `GameState.parent = self` and every `self.parent.notify()`/`self.parent.refresh()` (8 sites in `game/state.py`) with Textual `Message`s cannot be safely verified by `make checkall` — typecheck cannot detect broken message wiring. Doing it blind would leave the UI silently broken.
- **The prerequisite now exists**: `tests/test_app_integration.py` boots the app via `run_test()` and exercises the real click→reveal→save/load path; it also pins the `parent ↔ sweeper_widget` bridge so a future rewiring will fail loudly here. A follow-up can take this on with the harness as a safety net.

### [ARC-016] Dialog boilerplate consolidation — **DEFERRED**
- **Why deferred**: consolidating boilerplate across 12 dialogs is a broad refactor of marginal value (a `TextDialog` base already exists). Left for a dedicated pass.

### [DOC-017] `.aider.conventions.md` — **local-only**
- Fixed on disk (3.12 → 3.13), but `.aider*` is gitignored, so the change will not appear in commits. This is correct (aider is a local dev tool); noted for transparency.

---

## Verification Results

| Gate | Result |
|------|--------|
| Format check (`ruff format --check`) | ✅ 37 files already formatted |
| Lint check (`ruff check`) | ✅ All checks passed! |
| Type check (`pyright`, src/ + tests/) | ✅ 0 errors, 0 warnings, 0 informations |
| Tests (`pytest`) | ✅ 36 passed (9 db + 25 game + 2 integration) |
| Pre-commit (`pre-commit run --all-files`) | ✅ All hooks pass — incl. **Detect hardcoded secrets** (gitleaks), detect-private-key, pyright, format, lint |
| Import smoke test (all 32 modules) | ✅ No circular imports; `PimApp()` constructs without DB I/O |

No regressions. Every checkpoint commit was verified with the real gate before proceeding; agent self-reports were independently confirmed (the harness's language server emitted stale false-positives throughout — e.g. phantom "could not be resolved" for the new `game/` package and a non-existent `verify_imports.py` — all disproven by `uv run pyright` + runtime imports).

---

## Files Changed (43 files, +4168 / −1077, 20 new)

**New (20):** `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/{ARCHITECTURE,CONFIGURATION,RELEASE,TROUBLESHOOTING}.md`, `src/par_infini_sweeper/game/{__init__,cells,state,subgrid,types}.py`, `src/par_infini_sweeper/{leaderboard,persistence,renderer}.py`, `tests/{conftest,test_app_integration,test_db,test_game}.py`

**Modified (23):** `.github/workflows/build.yml`, `.gitignore`, `.pre-commit-config.yaml`, `Makefile`, `README.md`, `pyproject.toml`, `pyrightconfig.json`, `src/par_infini_sweeper/{__init__,__main__,auth,db,main_grid,messages,models}.py`, `src/par_infini_sweeper/data_structures.py` (881→33 LOC shim), `src/par_infini_sweeper/dialogs/{__init__,highscore_dialog,login_dialog,text_dialog,url_dialog}.py`, `src/par_infini_sweeper/help.md`, `uv.lock`

---

## Commits (base `05373bd` → head `002d683`)

```
002d683 docs: document leaderboard feature, CHANGELOG, env vars, architecture, release, security (3d)
f8f58f3 fix(quality): iterative BFS reveal, specific exceptions, remove type:ignore/silencers/noqa (3c)
5963b66 fix(security): warn on nickname migration truncation + --server localhost exposure (3a)
b990209 refactor(architecture): decompose 881-LOC god module into game/ + persistence/leaderboard/renderer (ARC-004)
3223466 refactor(architecture): surgical fixes — backup hoist, import side effects, port reuse, deferred init
3cc1695 fix(correctness): guard get_user None, highscores DESC, first_click ordering, is_logged_in expiry + pytest harness
2157301 fix(security): PKCE, token storage hardening, callback hardening, nickname validation, CI integrity
```

Each commit is an independent rollback point (e.g. `git revert b990209` undoes only the decomposition).

---

## Next Steps

1. **Manual review of ARC-009** (the static API key) — coordinate server-side rotation before externalizing.
2. **Optional follow-up PR for ARC-005** (parent→Message rewiring) — the UI integration harness now exists to verify it safely.
3. **Optional backlog** — the audit's unscoped Low items not assigned to any Phase: `ARC-022` (`App[None]` generic), `ARC-023` (dup `USER` fallback), `ARC-025` (CI Python 3.11/3.12/3.13 matrix), `ARC-026` (unused `defineConstant DEBUG`), `ARC-027` (redundant ruff `E501` ignore), `QA-016` (Pydantic `User` model), `QA-017` (`escape_brackets` → Textual `Text`), `QA-019` (`Cell.from_dict` key check), `QA-020` (dead `PimApp.set_debug`). These are all small; a single cleanup PR could clear them.
4. **Merge the branch** to `main` after review (rebase onto latest `main` first). The branch is `fix/audit-remediation`.
5. **Re-run `/audit`** to confirm the findings are cleared and generate a fresh AUDIT.md reflecting current state.
