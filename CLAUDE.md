# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

This is a single-file Streamlit application. The venv already exists at `.venv/`.

```bash
# From repo root, using the in-repo venv (Windows / Git Bash):
.venv/Scripts/streamlit.exe run present.py
```

There is no test suite, lint config, or build step. `readme.md` (Chinese) is the product spec — read it for feature intent before changing simulation behavior.

## Architecture

`present.py` is the entire app. It is a Streamlit script that re-runs top-to-bottom on every interaction; all persistent state lives in `st.session_state`. There is no module structure to navigate — the architecture is a state machine driven by button callbacks.

### Page state machine

`st.session_state.page` is `"start"` → `"game"` → `"end"`. The bottom of the file dispatches on `page`. `init_state(params)` is the only entry point that initializes/resets all session keys; the `required_keys` guard near the top of the dispatch re-runs `init_state` if a session predates a schema change — preserve this guard when adding new session keys (add the key to `required_keys`).

### Depreciation engine

`monthly_schedule(method, book_value, salvage_value, remaining_months)` is a pure function that returns a list of monthly depreciation amounts for the three supported methods (`Straight-Line`, `Double-Declining`, `SYD`). It is **re-called** (via `recalc_schedule()`) every time book value or remaining life changes — i.e. after capitalization acceptance, impairment, or transfer. The current period's depreciation is always `current_schedule[0]`, consumed by `advance_one_month()`.

### Two-company tracking

The simulation always maintains parallel arrays `history_company_a` and `history_company_b`, even when no transfer has occurred (the inactive company records `0.0` each month). `current_owner` (`"A"` or `"B"`) determines which array receives the non-zero entry in `advance_one_month()`. The end page sums both arrays for totals. When adding new event types, preserve this invariant: every month must append exactly one value to *each* array.

### Two-step upgrade flow

Capitalization is a two-button protocol gated by `upgrade_pending`:
1. `apply_upgrade_request()` — sets `upgrade_pending = True` and stores `upgrade_pending_delta`. While pending, `advance_one_month()` records 0 for both companies and the Impairment / Transfer buttons are disabled.
2. `apply_upgrade_acceptance()` — adds the delta to `book_value` and calls `recalc_schedule()`.

The left button's label and handler swap based on `upgrade_pending`. Don't break this gating when adding new actions — anything that mutates `book_value` should refuse to run while `upgrade_pending` is true (see existing guards in `apply_impairment` / `apply_transfer`).

### Auto-advance loop

When `running` is true, the bottom of the game page calls `advance_one_month()`, sleeps 0.35s, and `st.rerun()`s. This is the entire animation loop — Streamlit's rerun model is what drives the "one month per tick" behavior. `running` flips to false automatically when `month_idx` reaches `total_months`, transitioning to the `end` page.

### Event annotations

Every business action appends to `st.session_state.events` with `{month, label, color}`. `render_chart_company()` overlays these as marker+text traces on both A and B charts. New event types should follow this same dict shape.
