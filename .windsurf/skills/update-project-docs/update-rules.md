# Documentation Update Rules

Strict rules to follow when updating any project documentation.

## General Rules

1. **Never fabricate numbers** — Test counts, coverage percentages, entity counts must come from live tool output (pytest, grep, etc.), never from memory or estimation.
2. **Version consistency** — All docs must show the same version number. If bumping version, update ALL docs.
3. **ISO-8601 dates** — All dates formatted as `YYYY-MM-DD`.
4. **File references must be valid** — Any `test_*.py` referenced in docs must exist in `tests/` or `testing/`. Verify with `find_by_name` if unsure.
5. **Project Structure must match reality** — The directory tree in README.md must reflect actual files. Verify with `list_dir` or `find_by_name`.
6. **Don't update if nothing changed** — If docs are already current, report "up to date" and stop. Don't make cosmetic-only edits.
7. **Preserve existing style** — Match the formatting conventions already in each doc (table style, heading levels, list format).
8. **No emojis unless already present** — Some docs use emojis in headers (README.md does), others don't. Match existing style.

## Per-Document Rules

### CHANGELOG.md
- New entry goes at TOP, after the `---` separator on line 5
- Format: `## [X.Y.Z] – YYYY-MM-DD`
- Group changes by feature area (e.g., "### ICH M11 Rendering", "### Testing Infrastructure")
- Include tables for new files: `| File | Purpose |`
- Reference enhancement IDs: E7, E8, P12, etc.
- Include "Files Changed" section listing modified files with one-line descriptions
- If only a patch (bug fix), use patch version bump (X.Y.Z+1)
- If new features, use minor version bump (X.Y+1.0)

### README.md
- **What's New**: Only the CURRENT version gets a full section. Previous versions go into collapsible `<details><summary>` blocks.
- **Project Structure**: Use exact directory tree format with comments. Include new top-level directories. Don't list every file in subdirectories — use `*/` for groups.
- **Testing section**: Format as:
  ```
  # Run all unit tests (N tests, ~X min)
  python -m pytest tests/ -v
  ```
  Include coverage table with module-level breakdown.
- **Roadmap**: Use `- [x]` for completed, `- [ ]` for planned. Include version where completed.

### USER_GUIDE.md
- Version appears in TWO places: line 3 (`**Version:** X.Y`) and last line (`**Last Updated:** YYYY-MM-DD`). Both must be updated.
- What's New banner is a single `>` blockquote line summarizing the release.
- Testing section should have subsections: "Unit Tests", "E2E Integration Tests", "Benchmarking".
- Don't duplicate README content — USER_GUIDE is for end-user workflows, not architecture.

### QUICK_REFERENCE.md
- Version appears in TWO places: line 3 and second-to-last line. Both must be updated.
- Keep it concise — this is a one-page reference card.
- Output Files tree should show the star emoji (⭐) on primary outputs.
- Testing commands should be copy-pasteable (no placeholders).

### docs/ARCHITECTURE.md
- Only update for structural changes (new modules, changed pipeline flow).
- Include ASCII diagrams for architecture changes.
- Reference `dataStructure.yml` for USDM entity placement.

### docs/FULL_PROJECT_REVIEW.md
- Enhancement status table uses: `HIGH`, `MEDIUM`, `LOW` for pending, `✅ FIXED` for completed.
- Don't change effort estimates for completed items.
- Add new enhancement IDs sequentially (E14, E15, etc.).

### docs/ROADMAP.md
- "Future Enhancements" section for planned work.
- "Completed Features" section for done items, with version and date.
- Keep entries brief — one line per item.

## Version Bumping Guidelines

| Change Type | Version Bump | Example |
|-------------|-------------|---------|
| Bug fix only | Patch (X.Y.Z+1) | 7.3.0 → 7.3.1 |
| New feature | Minor (X.Y+1.0) | 7.3.0 → 7.4.0 |
| Breaking change | Major (X+1.0.0) | 7.3.0 → 8.0.0 |
| Doc-only update | No bump | — |

## Verification Checklist

After all edits, verify:
- [ ] All version strings match across docs
- [ ] All `test_*.py` references point to existing files
- [ ] CHANGELOG has entry for current version
- [ ] README Project Structure matches actual directory layout
- [ ] Test count in docs matches `pytest --co -q` output
- [ ] No broken markdown links (check `[text](path)` references)
- [ ] Dates are consistent and current
