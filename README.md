# ArchMuse

**An agentic copilot for architectural practice — one that refuses to guess.**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Claude API](https://img.shields.io/badge/Claude-API-D97757?logo=anthropic&logoColor=white)](https://www.anthropic.com/api)
[![IFC / BIM](https://img.shields.io/badge/IFC4-BIM%20export-orange)](https://technical.buildingsmart.org/standards/ifc/)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)
[![Status](https://img.shields.io/badge/status-experimental-yellow)](#status)

> **Status: experimental. V1 under construction.** Parts of this work end to end on real
> architectural files; other parts are scaffolding waiting for content. This README tries to be
> exact about which is which — see [Status](#status).
>
> **Language:** the code, comments and design documents are in **Spanish**, because that is the
> language of the building code it reasons about and of the architects it is built for. This README
> is in English.

---

## What ArchMuse is

ArchMuse takes the files an architect already has — a DXF floor plan, an IFC model — and does
pieces of the tedious work that surrounds a project: measuring rooms, filling in the area schedule,
checking a drawing against itself, and (eventually) justifying compliance with the Spanish building
code, the *Código Técnico de la Edificación*.

The distinguishing constraint is a negative one, and it is the whole point:

**ArchMuse is not allowed to produce a number it cannot trace.** Every figure it emits carries its
provenance — measured from this polygon, declared by the architect, or read from this cell of the
drawing — and anything it could not determine comes back as a **question with a reason**, never as
a silent blank and never as a plausible guess. A plan drawn in millimetres and read as metres
passes every minimum-area check and produces a beautiful, confident, wrong report; avoiding that
class of failure is the design centre of this repository.

### Vision

An **agentic copilot for architecture**: not a chatbot bolted onto a CAD viewer, but a set of
*versioned professional procedures* an architect can ask for by name and take away finished, each
with a record of what was checked, with what data, and what was deliberately left unanswered.

Every deliverable is marked as a **draft for review by a chartered architect**, with no option to
turn that off. ArchMuse advises; it does not sign.

---

## What actually works today

| Capability | State |
|---|---|
| **Read a DXF without assuming** — deduce the drawing unit and the layer holding the rooms; refuse and ask when either is uncertain | Working, on real client files |
| **Area schedule** (*cuadro de superficies*) — measure the rooms and fill in the drawing's own table, writing a **copy** and never the original | Working end to end; the input file's SHA-256 is verified before and after |
| **Plan coherence review** — overlapping rooms, outlines the file declares open that were closed on an assumption, repeated or missing labels, discarded geometry, and whether the schedule and the drawing name and count the same rooms | Working; found 9 real issues on the first real plan it was pointed at |
| **IFC reading and space export** | Working (`bim/`, `analyzer/ifc_export.py`) |
| **Provenance record** (*acta*) and draft marking on every deliverable | Working |
| **Building-code verification** | **Not yet.** The engine is built; the corpus holds **one rule, unsigned**, so ArchMuse asserts nothing about building code and says so — see [The normative corpus](#the-normative-corpus) |
| 3D viewer, financial viability, AI layout generation | Present in the repository but frozen: earlier exploration, not the current direction |

---

## Architecture

```
  agente/            The agentic core: capabilities, Skills, effects, verification, provenance
    herramientas/    Capabilities — one tool that does one thing, with a manifest
    skills/          Skills — versioned professional procedures
  analyzer/          Geometry and documents: DXF parsing, areas, schedules, PDF reports
  normativa/         The building-code engine and corpus (territorial resolution, rules, coverage)
  bim/               IFC reading
  modelo/            The shared architectural model
  scripts/           Runnable, offline entry points — the deliverables you can actually try
  tests/             ~900 tests, including golden files and policy tests
```

Three ideas hold it together.

**1. Capabilities and Skills are different things.** A *capability* knows how to do one thing: read
a DXF, resolve a municipality, measure the useful area. A *Skill* knows how a job is done — what is
looked at, in what order, with what checks, what is delivered, and what is declared as not checked.
The capability belongs to the engineer; the Skill belongs to the architect. Confusing the two is
what produces 400-line functions with professional judgement buried inside. Both are registered by
discovery: adding one is dropping a file in a directory, with no central list to edit.

**2. Nothing that touches the outside world happens without a declared, authorised effect.** A Skill
declares its effects and a capability declares its own, and the manifest cannot lie by omission —
a Skill that uses a capability with an undeclared effect fails to load. Writing a file requires an
explicit authorisation recording who granted it and for how long.

**3. Verification is part of the result, not a test suite.** Every Skill runs its own checks and
returns a verdict. Checks have three outcomes, and the third one is the one that matters: passed,
failed, or **could not be checked** — with the reason. Reporting "could not check" as "failed"
accuses the architect's drawing of a defect nobody looked at, and that is how a tool spends the
credibility it will need the day it is right.

### Skills

Currently in the registry (`agente/skills/`):

| Skill | What it does |
|---|---|
| `superficies.cuadro_de_vivienda` | Fills in a dwelling's area schedule; delivers the filled DXF plus a PDF explaining every cell |
| `revision.coherencia_del_plano` | Reviews a plan against itself before delivery — the one deliverable that does not depend on the corpus |
| `territorial.ficha_normativa_de_parcela` | Which building code applies to a plot, and what coverage exists for it |
| `revision.recorridos_de_evacuacion` | Evacuation route length against the DB-SI threshold, with the citation |
| `programa.registrar_requisitos_del_cliente` | Records client requirements with their source |

Each declares what it needs — and the **question** that unblocks each requirement — which
capabilities it may invoke, what it produces, what effects it has, what it verifies, and, in its own
manifest, **what it does not check**.

### DXF and IFC

DXF is the working format, because it is what Spanish practice actually exchanges. The parser
traverses block references, resolves layer inheritance through them, deduces the drawing unit from
`$INSUNITS` and from geometric plausibility, and **refuses rather than assumes** when it cannot
tell. Everything it discards is inventoried with a reason: a silent discard is floor area missing
without anyone knowing.

IFC is read through `ifcopenshell`, and spaces can be exported. Reading an IFC to tell an architect
what is in their own Revit model has little value; the value is cross-checking it against another
source, and that is future work.

### Verification and traceability

- **Claims, not values.** Every figure is an `Afirmacion` carrying its epistemic nature — fact,
  calculation, inference or proposal — plus its source, its unit and, where relevant, its citation.
  That distinction is the line between advising and signing.
- **Provenance record.** Every run produces an *acta*: which capabilities ran, with what arguments,
  what each produced, and **what was not checked** — derived from the manifests of what actually
  ran, not written by hand.
- **The original is never touched.** Any capability that writes verifies the input file's SHA-256
  before and after, refuses to write over its source, and refuses to overwrite an existing
  deliverable that may already have been reviewed and annotated.
- **Unsupported figures are detectable.** `agente/respaldo.py` checks every number in a generated
  text against the tool results that were actually available to produce it.

### The normative corpus

`normativa/` holds a working rule engine: territorial resolution from state down to municipality,
temporal validity, applicability, and coverage declared per subject area. It holds **one
transcribed rule**, and that rule is **unsigned by a chartered architect**, so it is declared
`transcrito_sin_firmar` — a state that is explicitly *not* assertable. ArchMuse therefore blocks on
missing coverage instead of answering.

That is the honest answer, and it stays that way until an architect signs. The bottleneck is
contractual, not technical.

---

## Running it locally

Requires **Python 3.12+**.

```bash
git clone https://github.com/pablocamachomacia/archmuse.git
cd archmuse

python -m venv venv
# Windows PowerShell:  .\venv\Scripts\Activate.ps1
# bash/zsh:            source venv/bin/activate

pip install -r requirements.txt
```

None of the commands below need an API key or a network connection — the whole procedure is
deterministic.

**See the agent work, without any files of your own:**

```bash
python scripts/demo_agente.py
```

**Fill in the area schedule of a DXF:**

```bash
python scripts/cuadro_de_superficies.py my_plan.dxf
```

It shows what it is about to do, then hands back a *copy* of the DXF with the schedule filled in
and a PDF saying, cell by cell, where each figure came from — or why that cell is blank. Anything
it could not work out comes back as an answerable question, never as a number.

**Review a plan before it leaves the studio:**

```bash
python scripts/revisar_plano.py my_plan.dxf
```

Checks whether the drawing is coherent *with itself* and writes a PDF report naming the entity
behind every finding — a label, an area, a DXF handle — so anyone can go and look at it. It does
**not** grade severity: it says what something is and how much it measures, and the judgement
belongs to the architect.

**Check the normative corpus**, for whoever transcribes building code into it:

```bash
python scripts/validar_corpus.py
```

**The web application** — the earlier, frozen exploration. Needs `ANTHROPIC_API_KEY` and
`MAPBOX_TOKEN`:

```bash
cp .env.example .env    # then fill in what you need
python app.py
```

`.env.example` documents every variable, which module reads it, and what happens without it.

## Running the tests

```bash
pytest -q
```

Around 900 tests. No network and no API key required: anything that would hit a live service or
spend tokens is skipped by default, and says so rather than failing. A few tests exercise real
client plans and skip with a reason unless you point `ARCHMUSE_DXF_V2S` at one of your own.

```bash
pytest tests/test_coherencia.py -q          # a single module
pytest -q -p no:randomly                    # deterministic order
```

---

## Do not put real project data in this repository

**No client plans, no DXF or IFC from real projects, no PDFs of real dossiers, no personal data, no
API keys.** This is a public repository.

- Tests that need a real plan read its path from `ARCHMUSE_DXF_V2S`. The file itself stays outside
  the repository, and those tests skip — with a reason — when it is absent.
- Secrets live in environment variables or in a local `.env`, which is git-ignored. `.env.example`
  documents every variable and **must never contain a real value**.
- Generated deliverables — filled DXFs, PDF reports — are written next to their source, outside the
  repository. Do not commit them.

If you contribute, check `git status` before staging. `.gitignore` covers the known cases; it
cannot cover a client's plan you copied into the working directory.

## Status

**Experimental. V1 under construction.**

Solid: the DXF pipeline, the agentic core (capabilities, Skills, effects, verification, provenance),
the area-schedule and plan-review deliverables, and the test suite around them.

Not solid: the normative corpus, which is one unsigned rule. Until it grows, ArchMuse cannot verify
building code — and is built to say so rather than to improvise.

Product decisions and design records live in `docs/` — `docs/prd/` for product requirements,
`docs/design/` for architecture decisions — along with the planning documents at the repository
root. They are candid about what does not work, which is why they are worth keeping.

## Licence

**No licence has been chosen yet.** Until one is added, default copyright applies: all rights
reserved by the author. The code is public so it can be read; it is not yet licensed for reuse.
