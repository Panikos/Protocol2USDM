# Protocol2USDM Web UI

Modern web interface for viewing and editing USDM protocol data with full provenance tracking.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:3000
```

## Technology Stack

- **Next.js 16** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components
- **AG Grid** - SoA table (Enterprise)
- **Cytoscape.js** - Timeline diagrams
- **Zustand** - State management
- **TanStack Query** - Server state
- **Zod** - Schema validation

## Project Structure

```
web-ui/
├── app/                    # Next.js App Router pages
│   ├── api/               # API routes
│   │   └── protocols/     # Protocol CRUD + semantic + documents
│   ├── protocols/         # Protocol pages
│   │   └── [id]/         # Protocol detail
│   ├── layout.tsx        # Root layout
│   └── page.tsx          # Home page
├── components/            # React components
│   ├── documents/        # Document/artifact viewers
│   ├── overlay/          # Layout draft/publish controls
│   ├── semantic/         # Semantic editing controls
│   ├── soa/              # SoA table (AG Grid)
│   ├── timeline/         # Timeline (Cytoscape)
│   └── ui/               # Base UI components
├── lib/                   # Core libraries
│   ├── adapters/         # USDM → view model
│   ├── overlay/          # Layout overlay schema
│   ├── semantic/         # Semantic editing (JSON Patch)
│   └── provenance/       # Provenance types
├── stores/               # Zustand stores
└── styles/               # CSS and themes
```

## Architecture

### Data Layers

1. **USDM (canonical)** - Semantic source of truth from pipeline
2. **Overlay (presentation)** - Layout, ordering, visual settings
3. **Adapters** - Transform USDM + Overlay → view models

### USDM Structure (v7.2)

The UI reads data from USDM-compliant locations per `dataStructure.yml`:

| Data | USDM Path |
|------|----------|
| Eligibility Criteria | `studyDesign.eligibilityCriteria[]` |
| Criterion Items (text) | `studyVersion.eligibilityCriterionItems[]` |
| Organizations | `studyVersion.organizations[]` |
| Interventions | `studyVersion.studyInterventions[]` |
| Products | `studyVersion.administrableProducts[]` |
| Devices | `studyVersion.medicalDevices[]` |
| Timings | `scheduleTimeline.timings[]` |
| Indications | `studyDesign.indications[]` |
| Procedures | `activity.definedProcedures[]` |

### Key Principles

- USDM can be edited via semantic patches (JSON Patch RFC 6902)
- Overlay stores presentation-only data (layout, ordering)
- Draft/Publish workflow for both semantic and layout changes
- Full provenance tracking
- Validation on publish (schema + USDM + CORE conformance)

## Environment Variables

Create `.env.local`:

```env
# Path to Protocol2USDM output directory
PROTOCOL_OUTPUT_DIR=/path/to/output

# Path to semantic editing storage (drafts, history)
SEMANTIC_DIR=/path/to/semantic

# Path to input documents directory
PROTOCOL_INPUT_DIR=/path/to/input

# Optional: AG Grid license key
AG_GRID_LICENSE_KEY=your-license-key
```

## Features

### Schedule of Activities (AG Grid)
- Provenance-colored cells
- Row/column reordering
- Grouping by epoch
- Footnote references
- CSV export

### Timeline Diagram (Cytoscape.js)
- Drag-and-drop node positioning
- Snap-to-grid
- Lock/unlock nodes
- Preset layout from overlay

### Provenance Tracking
- Cell-level source tracking
- PDF page references
- Color coding:
  - 🟢 Green: Confirmed (text + vision)
  - 🔵 Blue: Text-only
  - 🟠 Orange: Vision-only (needs review)
  - 🔴 Red: Orphaned (no provenance)

### Draft/Publish Workflow

**Layout (Overlay):**
- Save Draft - persist layout changes
- Publish - make layout visible
- Reset - discard layout changes

**Semantic Editing (USDM Data):**
- Inline field editing with JSON Patch
- Draft persistence with revision tracking
- Publish with auto-validation (schema, USDM, CORE)
- Version history and rollback support

## API Endpoints

### Core APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/protocols` | GET | List all protocols |
| `/api/protocols/[id]/usdm` | GET | Get USDM + provenance |

### Layout Overlay APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/protocols/[id]/overlay/draft` | GET/PUT | Draft overlay |
| `/api/protocols/[id]/overlay/published` | GET | Published overlay |
| `/api/protocols/[id]/overlay/publish` | POST | Promote draft |

### Semantic Editing APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/protocols/[id]/semantic/draft` | GET/PUT/DELETE | Semantic draft |
| `/api/protocols/[id]/semantic/publish` | POST | Apply patch + validate |
| `/api/protocols/[id]/semantic/history` | GET | Version history |

### Document APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/protocols/[id]/documents` | GET | List source documents |
| `/api/protocols/[id]/documents/[filename]` | GET | Download/preview |
| `/api/protocols/[id]/intermediate` | GET | List extraction artifacts |
| `/api/protocols/[id]/intermediate/[filename]` | GET | Preview/download JSON |

## Development

```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Build for production
npm run build
```

## Recent Updates

### v7.2.1 — Semantic Editing & Documents
- **Semantic Editing** - Edit USDM data directly via JSON Patch (RFC 6902)
- **Documents Tab** - View/download source documents (protocol PDF, SAP, sites)
- **Intermediate Tab** - Browse extraction JSON artifacts with tree view
- **Validation on Publish** - Auto-validate schema, USDM, and CORE conformance
- New components: `SemanticDraftControls`, `EditableField`, `DocumentsTab`, `IntermediateFilesTab`
- New store: `semanticStore.ts` for draft state management
- New library: `lib/semantic/` for JSON Patch operations

### v7.2 — Execution Model Promotion
- New USDM entity dataclasses: `ScheduledDecisionInstance`, `ConditionAssignment`, `StudyElement`
- `Encounter` now supports `transitionStartRule`/`transitionEndRule`, `previousId`/`nextId`
- `StudyDesign` now has `conditions[]`, `estimands[]`, `elements[]` collections

### v6.10/6.11 — SAP & ARS Integration
- **SAP Data tab** (`SAPDataView.tsx`) — analysis populations, statistical methods, STATO codes
- **CDISC ARS tab** (`ARSDataView.tsx`) — reporting events, analyses, analysis sets, methods
- Extensions view updated with 8 SAP extension types

### v6.9 — Execution Model View
- Visit Windows epoch resolution with day-based matching
- Quality Metrics dashboard improvements

## Milestones

- [x] **M1**: Next.js setup, schemas, stores, API routes
- [x] **M2**: AG Grid SoA table with provenance
- [x] **M3**: Cytoscape.js timeline diagram
- [x] **M4**: Execution Model view with visit windows
- [x] **M4.5**: SAP Data and CDISC ARS views
- [x] **M5**: Semantic editing workflow
- [x] **M5.1**: Documents and Intermediate Files tabs

## License

See root repository README for license terms.
