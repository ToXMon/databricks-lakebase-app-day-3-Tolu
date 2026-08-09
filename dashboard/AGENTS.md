# Dashboard

## Purpose

Owns the read-only Flask weather desk, its Databricks App configuration, and browser template. Inherits repository-wide rules from `../AGENTS.md`.

## Local Contracts

- `app.py` serves `/`, `/healthz`, `/api/current_weather`, `/api/forecast`, and `/api/recommendation`.
- Keep these DOM IDs stable: `current-location`, `current-btn`, `current-result`, `forecast-location`, `forecast-days`, `forecast-btn`, `forecast-result`, `rec-location`, `rec-date`, `rec-activity`, `rec-btn`, and `rec-result`.
- Preserve input types, defaults, bounds, URL encoding, result fields, error handling, and `escapeHtml` behavior.
- Keep the dashboard read-only and dependency-free in the browser.

## UI and Accessibility

- Use the weather field-desk visual language: map texture, editorial type, teal ink, and orange signal accents.
- Support desktop and mobile layouts, visible keyboard focus, semantic labels and headings, live result regions, dark color preference, and reduced motion.
- Escape every API-derived value before inserting HTML.

## Verification

- Run `/opt/venv/bin/python -m pytest -q` from the repository root.
- Run `git diff --check`.
- For interaction changes, verify all three lookup flows and the browser console in a real browser.

## Child DOX Index

- None.
