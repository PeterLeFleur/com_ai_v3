# COM-AI v3 — Handover & Collaboration Protocol

## 1. Purpose
Defines mandatory rules for AI + human collaboration on COM-AI v3.  
Ensures continuity, prevents drift, and enforces compliance with the registry + tracker + session logging model.

---

## 2. Core Artifacts
- GitHub Repository: `com_ai_v3`
- Google Sheet: `COM-AI v3 Phase Tracker`
- Google Doc: `COM-AI v3 Handover Protocol`
- Repo File: `HANDOVER_PROTOCOL.md`

---

## 3. Master Plan (Anti-Drift Protocol)
1. **Registry is Law**
   - All Python files must appear in `FILE_REGISTRY.csv` & `manifest.json`.
   - Registry validated on CI and at the end of every session.
2. **Session Discipline**
   - Start: Review `PHASE2_TRACKER.tsv` and last `SESSION_NOTES.md`.
   - End: Run registry validation, update tracker, update notes.
3. **Single Source of Truth**
   - Code = GitHub repo  
   - Tasks = `PHASE2_TRACKER.tsv` (mirrored in Google Sheet)  
   - Logs = `SESSION_NOTES.md` (summarized in Google Doc + Sheet if needed)
4. **Decision Logging**
   - All PM/architectural decisions logged in Section 6 and in the DECISIONS tab of Google Sheet.

---

## 4. Session Workflow
1. Review tracker + session notes  
2. Work using registry-compliant imports/logging  
3. End with validations + updates  

---

## 5. Task Tracker Rules
- Every task has a Task ID (`API-001`, `BRAIN-001`, etc.)
- Task IDs must appear in:
  - `PHASE2_TRACKER.tsv`
  - Test file docstrings
  - `SESSION_NOTES.md`

---

## 6. Decisions & Changes Log (PM-Managed)
*(Append-only section, mirrored in Google Sheet)*

### Format
**Date:** YYYY-MM-DD  
**Decision Owner:** [PM/Claude/GPT/etc.]  
**Decision ID:** DEC-001  
**Context:** [Why this decision was needed]  
**Decision:** [Clear description of the change/choice]  
**Impact:** [Implications for code, process, or team]  
**Next Steps:** [Follow-up actions]  

---

### Example
**Date:** 2025-09-25  
**Decision Owner:** Scott (PM)  
**Decision ID:** DEC-001  
**Context:** Path chaos in `main_multi.py` during v2.  
**Decision:** Move to absolute imports with `src.*` package layout.  
**Impact:** Eliminates path drift, CI passes cleanly.  
**Next Steps:** Enforce via `registry_validate.py`.  
