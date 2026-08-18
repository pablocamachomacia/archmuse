# ArchMuse

**Urban feasibility, financial viability and AI-assisted spatial generation for residential architecture.**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Three.js](https://img.shields.io/badge/Three.js-r1xx-black?logo=three.js&logoColor=white)](https://threejs.org/)
[![Claude API](https://img.shields.io/badge/Claude-API-D97757?logo=anthropic&logoColor=white)](https://www.anthropic.com/api)
[![IFC / BIM](https://img.shields.io/badge/IFC4-BIM%20export-orange)](https://technical.buildingsmart.org/standards/ifc/)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)

---

## Executive Summary

**EN —** ArchMuse is a full-stack platform for early-stage residential architecture: it turns a plot
of land (via Mapbox GIS) into a *sólido capaz* (buildable envelope), evaluates a design — either
uploaded as a DXF plan or generated from scratch by an AI layout engine — against Spanish building
code (CTE) and habitability regulation, models financial viability (developer margin, static cash
flow, surface efficiency ratio), and exports the result as technical deliverables: IFC4 BIM spaces
and a PDF investment dossier. A rule engine (~3,500 lines, 20+ CTE/DB-SI/DB-SUA checks) does the
compliance scoring; Claude (Anthropic API) is layered on top to generate spatial proposals and
narrative diagnosis — and is explicitly never allowed to invent a cost, price or compliance number
that the user hasn't provided.

**ES —** ArchMuse es una plataforma full-stack para las fases tempranas del proyecto residencial:
convierte una parcela (vía Mapbox GIS) en su **sólido capaz** (envolvente edificable), evalúa un
diseño — subido como plano DXF o generado desde cero por un motor de IA — contra el **CTE** y la
normativa de habitabilidad, modela la **viabilidad financiera** (margen del promotor, cash flow
estático, ratio de eficiencia de superficie) y exporta el resultado como entregables técnicos:
espacios **IFC4/BIM** y un **dossier de inversión en PDF**. Un motor de reglas (~3.500 líneas, 20+
comprobaciones CTE/DB-SI/DB-SUA) hace el scoring normativo; **Claude** (API de Anthropic) se apoya
encima para generar propuestas espaciales y diagnóstico narrativo — y tiene explícitamente prohibido
inventar un coste, precio o dato de cumplimiento que el usuario no haya introducido.

---

## Architecture & Key Features

### 🗺️ 3D viewer & Sólido Capaz analysis
Interactive **Three.js** viewer (building + unit level, shared rendering core) over real terrain and
context fetched from the **Mapbox GIS API**. Given a plot's geocoded boundary and local zoning
parameters (occupancy, buildability, max height, setbacks), computes the *sólido capaz* — the
maximum legally buildable volume — and lets the architect sandbox massing options directly on it.

### 📐 CTE rule engine & compliance checklist
`analyzer/evaluator.py` runs 20+ independent checks (room proportions, bedroom/bathroom hierarchy,
useful/built area efficiency, solar orientation, cross-ventilation, corridor width, accessible
itineraries, natural lighting, fire evacuation distance, acoustic adjacency...) against thresholds
that vary by housing typology and by **CTE climate zone**, keyed off the project's city. Findings
are aggregated into a single CTE/DB-SI/DB-SUA **compliance checklist** so the architect sees one
verdict per rule, not raw output from three different modules.

### 💰 Financial viability module
Developer margin (%), static cash flow (investment vs. revenue totals) and surface efficiency ratio
— computed from figures the *user* enters, never a fabricated market default. No IRR is computed on
purpose: an IRR requires a real construction/sales timeline ArchMuse doesn't model, and a plausible
-looking-but-invented number was judged worse than no number.

### 🤖 LLM integration (Claude API)
Two AI-assisted flows on top of the deterministic rule engine:
- **Diagnosis** — Claude reads the evaluator's structured findings on an uploaded DXF plan and
  produces an expert narrative assessment per dwelling unit.
- **Generation** — given a plot, program of needs and zoning constraints, Claude lays out a full
  residential floor plan (rooms + units) from scratch, which then runs through the *same* CTE
  evaluator as any uploaded plan.

### 📤 Technical export
- **IFC4/BIM** (`ifcopenshell`) — exports each analyzed space as a real `IfcSpace` (area, name),
  deliberately scoped to what the pipeline actually knows (no invented wall thickness or slab
  geometry) so it never overstates itself as a full BIM model.
- **PDF investment dossier** (`ReportLab`) — cover page, urban-planning fact sheet, per-floor 2D
  plans and the financial viability summary, composed only from data the app already computed or the
  user already captured (map image via Mapbox Static API, 3D render only if the client supplied it).

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12+, Flask (JSON REST API) |
| **Geometry / CAD** | `ezdxf`, `shapely`, `trimesh` + `mapbox_earcut` (mesh triangulation) |
| **BIM export** | `ifcopenshell` (IFC4) |
| **PDF generation** | `ReportLab` |
| **AI** | Anthropic Claude API (`anthropic`) — diagnosis & generative layout |
| **Frontend** | Vanilla JS SPA, **Three.js** (3D building/unit viewer), Mapbox GL / Static Images API |
| **Rules corpus** | YAML + `jsonschema` (curator-editable normative corpus), `pypdf` (official CTE PDF ingestion) |
| **Testing** | `pytest` — ~100 test modules covering the rule engine, exports, endpoints and golden-file regressions |

---

## Getting Started

### Prerequisites
- Python 3.12+
- API keys (never committed — see `.gitignore`):
  - `ANTHROPIC_API_KEY` — required for AI diagnosis/generation
  - `MAPBOX_TOKEN` — required for the GIS plot picker, terrain and static map images
  - `GEMINI_API_KEY` — optional, used only by the separate `JarvisApp.py` assistant

Copy `.env.example` to `.env` and fill it in. That file is the canonical list of
every variable the project reads — what each one does, which module reads it,
and its default. `app.py`, `main.py` and the test suite all load `.env` (via
`analyzer/entorno.py`); anything already exported in your shell wins over the
file, so a stray `.env` can never override a deployment's real secrets.
`.env` is gitignored, `.env.example` is not — never put a real key in it.

### Installation

```bash
git clone <repo-url>
cd arquitecto-ai
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Running the app

```bash
# With a .env in place, just:
python app.py

# Or export them yourself (these win over .env):
# PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:MAPBOX_TOKEN = "pk...."
python app.py
```

The API/SPA serves at **http://127.0.0.1:5000**, behind `waitress` (a real WSGI
server, multi-threaded). `PORT` overrides the port. It binds to loopback only.

For development with auto-reload and the interactive debugger:

```bash
$env:FLASK_DEBUG = "1"
python app.py
```

That mode runs Flask's development server, whose Werkzeug debugger executes
arbitrary Python from the browser — it is opt-in on purpose, and local only.

### Running the test suite

```bash
pytest
```

Around 360 tests, ~14 minutes. Two shapes coexist under `tests/`:

- **Native pytest tests** (25 files) — collected and reported per test function.
- **Standalone check scripts** (72 files) — the original style: they run their
  assertions at module level and report via the exit code. `conftest.py` keeps
  them out of normal collection (importing one runs it) and
  `tests/test_scripts_legacy.py` executes each in a subprocess, so each script
  shows up as **one** pytest result. Its captured output carries the per-check
  detail. Any one of them still runs on its own the way its docstring says:

```bash
python tests/test_acoustic_adjacency.py
python tests/golden.py          # the 9 golden fixtures, G1..G9
```

Raise `ARCHMUSE_TEST_TIMEOUT` (seconds, default 900) if a script needs longer.

Some tests need real DXF drawings, which are not in the repository (they are
actual client files). Without them those tests skip with an explicit reason
rather than failing:

- `ejemplo.dxf` — expected **next to** the repository directory. Same location
  is the default for `python main.py` and the `experimentos/` scripts.
- `v2s.dxf` — set `ARCHMUSE_DXF_V2S` to its full path to enable the
  surface-schedule tests (about 4 minutes of extra coverage).

`conftest.py` loads `.env` too, so those variables can live there instead of in
your shell — and the 72 subprocess scripts inherit them. Two entries in
`.env.example` change what the suite *does* rather than what it can reach:
`ARCHMUSE_TEST_RED=1` makes it hit boe.es and the Spanish cadastre live, and
`ARCHMUSE_TEST_IA=1` makes it spend real Anthropic tokens. Both are off by
default and flagged in place.

Two scripts are marked `xfail(strict=True)` in `conftest.py` (`ROJOS_CONOCIDOS`)
because they fail on one known, written-up defect — see
`docs/audits/2026-08-13-hallazgos-cierre-geometrico.md` §2. Strict is the point:
the day that defect is fixed, pytest reports XPASS and forces the marker to be
removed. Nothing else is marked, so any red is a real regression.

---

## Project Philosophy

Every module that touches a number the user will act on — cost, price, CTE compliance, a percentile
comparison — is held to one rule: **never fabricate a default**. Where the pipeline lacks a real
input (construction timeline, wall thickness, market comparables), the feature is scoped down or
left out rather than filled in with a plausible-looking placeholder. This constraint shapes several
deliberate design choices documented above (no IRR, IFC spaces only, dossier composed only from
already-captured data).
