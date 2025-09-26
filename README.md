markdown# COM-AI v3 - Multi-Provider AI Brain System

A clean, resilient rebuild of the COM-AI system with graceful provider degradation and proper separation of concerns using Brain methodology.

## Quick Start

1. **Clone Repository**
```bash
   git clone https://github.com/PeterLeFleur/com_ai_v3.git
   cd com_ai_v3

Configure Environment

bash   copy .env.example .env
   # Edit .env with your API keys

Start George's Brain

bash   start_george.bat

Access Interfaces

API: http://localhost:8000
Docs: http://localhost:8000/docs
Health: http://localhost:8000/api/health



Handover Artifacts

Handover Protocol
Session Notes
Phase Tracker

Project Structure
src/
├── api/          # FastAPI application layer
├── brain/        # AI orchestration engine
├── memory/       # Persistence systems
└── utils/        # Shared utilities

tools/            # Registry & validation tools
tests/            # Test suite
frontend/         # React UI (separate build)
Development Workflow
For AI Collaborators (Claude, GPT, etc.)

Session Start

Review PHASE2_TRACKER.tsv for open tasks
Check SESSION_NOTES.md for previous session context
Run registry validation: python tools/registry_validate.py


During Work

Follow absolute import pattern: from src.brain.cerebrum.cadre import CerebrumCadre
Update registry after adding files: python tools/registry_update.py
Test changes: pytest tests/


Session End

Run: python tools/generate_manifest.py --repo . --write-registry
Run: python tools/registry_validate.py
Update PHASE2_TRACKER.tsv with progress
MANDATORY: Append entry to SESSION_NOTES.md



Core Principles

Graceful Degradation: Individual provider failures don't crash the system
Absolute Imports: No relative imports to avoid path confusion
Registry Compliance: All file changes tracked and validated
Session Logging: Every AI session documented for continuity

Architecture
Provider System

ProviderManager handles graceful degradation
Individual providers isolated from each other
Health monitoring and automatic fallbacks

Brain Orchestration

CerebrumCadre coordinates multi-provider synthesis
Convergence detection for quality assurance
Configurable rounds and thresholds

Memory Systems

Firestore for instant/session memory
PostgreSQL for long-term persistence
Mock backends for development

Testing
bash# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test category
pytest tests/test_brain/
Contributing

Check PHASE2_TRACKER.tsv for available tasks
Follow the session workflow above
Maintain registry compliance
Document your session in SESSION_NOTES.md

Support

Check session logs in SESSION_NOTES.md
Review task tracker in PHASE2_TRACKER.tsv
Validate environment: python tools/registry_validate.py


### `HANDOVER_PROTOCOL.md`
```markdown
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
   - Tasks = PHASE2_TRACKER.tsv (mirrored in Google Sheet)
   - Logs = SESSION_NOTES.md (summarized in Google Doc + Sheet if needed)
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

Format:
Date — Decision — Rationale

Examples:
2025-09-25 — Retained cerebrum/cadre naming with BrainOrchestrator alias — Preserves v2 compatibility while modernizing imports.
2025-09-26 — Added CI check for session notes — Enforces session discipline and prevents drift.

---

## 7. Compliance Checklist (End of Session)
✅ Run `python tools/registry_validate.py`  
✅ Update `PHASE2_TRACKER.tsv`  
✅ Append to `SESSION_NOTES.md`  
✅ Confirm session IDs in test files + tracker  
✅ PM logs major decisions here + Google Sheet  

---

⚠️ **Non-compliance may trigger rollback or CI failure.**