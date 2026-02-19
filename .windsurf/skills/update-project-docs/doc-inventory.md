# Documentation Inventory

Complete inventory of all documentation files and their updatable sections.

## Root-Level Docs

### README.md
Primary project documentation. Sections to check:
- **Line 1-5**: No version string here (title + disclaimer)
- **"What's New in vX.Y"** (~line 67): Feature highlights for current version. Older releases go into `<details>` blocks.
- **"Features"** (~line 129): Extraction capabilities table. Update when new extraction modules added.
- **"Extraction Capabilities" table**: Module/Entities/CLI Flag. Update when new phases added.
- **"Project Structure"** (~line 529): Directory tree. Must match actual layout. Check when new top-level dirs added (e.g., `providers/`, `rendering/`).
- **"Testing"** (~line 599): Test commands and coverage table. Update test count and coverage % from live pytest output.
- **"Roadmap / TODO"** (~line 689): Checklist of planned/completed items. Move completed to `[x]`, add new planned items.

### USER_GUIDE.md
End-user guide. Sections to check:
- **Line 3**: `**Version:** X.Y`
- **Line 4**: `**Last Updated:** YYYY-MM-DD`
- **Line 6**: What's New banner (one-line summary)
- **"Testing" section** (~line 628): pytest commands. Must reference actual test files.
- **"Available Flags" table** (~line 196): CLI flags. Update when new flags added.
- **"Output Directory Structure"** (~line 286): Output file tree. Update when new output files added.
- **Last line**: `**Last Updated:** YYYY-MM-DD` (must match line 4)

### QUICK_REFERENCE.md
One-page command reference. Sections to check:
- **Line 3**: `**vX.Y**` version
- **Line 5**: Current features summary
- **"Output Files" tree** (~line 142): Add new output files.
- **"Testing" section** (~line 182): pytest commands. Must reference actual test files.
- **"Key Files" table** (~line 234): Important files. Add new key files.
- **Last 2 lines**: `**Last Updated:** YYYY-MM-DD` and `**Version:** X.Y`

### CHANGELOG.md
Change log. Sections to check:
- **Top entry**: Must be the current version with today's date if changes were made.
- Format: `## [X.Y.Z] – YYYY-MM-DD`
- Group by feature area, include tables for new files.
- Reference enhancement IDs (E7, P12, etc.) when applicable.

## docs/ Directory

### docs/ARCHITECTURE.md
Technical architecture. Update only when:
- New modules or packages added to pipeline
- Pipeline flow changed
- New rendering/validation paths
- Entity placement changes

### docs/FULL_PROJECT_REVIEW.md
Enhancement tracking. Sections to check:
- Enhancement tables: Mark completed items as `✅ FIXED`
- Update status of in-progress items
- Add new enhancement IDs if needed

### docs/ROADMAP.md
Future plans. Sections to check:
- Move completed items to "Completed Features" section
- Add new planned items to "Future Enhancements"

### docs/M11_RENDERER_ARCHITECTURE.md
M11 renderer architecture. Update when:
- New composers added
- Section mapper passes changed
- Conformance validator rules changed

### docs/M11_USDM_ALIGNMENT.md
USDM alignment tracking. Update when:
- New USDM gaps identified or fixed
- Promotion rules added/changed
- Schema alignment changes

### AGENTS.md (root)
AI assistant knowledge base. Must reflect the current codebase accurately. Sections to check:
- **§2.1 Pipeline Phases** (~line 110): Phase table, module line counts, dependency changes, new post-processing functions
- **§2.6 Validation Pipeline** (~line 203): Validation steps, output files (e.g., `compliance_log.json`)
- **§3 Key Files** (~line 271): Important files organized by category (pipeline, core, extraction, rendering, web-ui). Add new files here.
- **§5.7 Testing** (~line 479): Test count, new test files
- **§5.8 Web UI Architecture** (~line 490): Components, views, API routes
- **§6 Known Gaps** (~line 518): Mark completed items as ✅ Fixed, add new gaps
- **§6.4 Structural Debt** (~line 551): W-HIGH/W-CRIT item status
- **§8 Documentation Index** (~line 588): Doc file inventory table

**Do NOT update** `core/reference_data/AGENTS.md` — that is a static USDM controlled terminology reference and only changes when the CT spreadsheet is updated.

## Other Docs (rarely need updating)

- `docs/EXECUTION_MODEL_EXTENSIONS.md` — Execution model spec
- `docs/SAP_EXTENSIONS.md` — SAP extension schema
- `docs/SEMANTIC_EDITING_SPEC.md` — Semantic editing spec
- `docs/TIMELINE_REVIEW_GUIDE.md` — Timeline review guide
- `docs/WEB_UI_REVIEW.md` — Web UI review
- `web-ui/README.md` — Web UI setup
- `testing/README.md` — Testing tools
