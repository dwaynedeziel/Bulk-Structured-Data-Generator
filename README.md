# 🔗 Bulk Structured Data Generator v2.0

Streamlit app that generates validated, graph-connected JSON-LD structured data from a CSV of URLs using the Claude API. Now with **dual-type support** and **expanded model selection**.

## What's New in v2.0

- **Dual-type output**: Service pages generate `WebContent|Service`, team pages generate `WebContent|Person`
- **mainEntity/subjectOf wiring**: Bidirectional container ↔ nested entity connections
- **Rule 16 validation**: Dual-type integrity checks (property placement, structural wiring)
- **Model selection**: Claude Opus 4.6, Sonnet 4, Sonnet 4.5, Haiku 4.5
- **Updated type inference**: `/services/` → `WebContent|Service`, `/team/` → `WebContent|Person`

## Quick Start

```bash
git clone https://github.com/YOUR-USERNAME/structured-data-generator.git
cd structured-data-generator
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml with your API key
streamlit run app.py
```

## Dual-Type System

A single URL can generate **two connected entities** in one `@graph`:

| URL Pattern | Generated Types | Container → Nested |
|---|---|---|
| `/services/air-conditioning/` | `WebContent\|Service` | WebContent → Service |
| `/about/team/jane/` | `WebContent\|Person` | WebContent → Person |
| `/locations/atlanta/` | `LocalBusiness` | Single type (page IS the entity) |
| `/blog/my-post/` | `WebContent` | Single type (pure content) |

The **container** (WebContent) holds page metadata: headline, keywords, dates, creator.
The **nested entity** holds domain properties: provider, areaServed, hierarchy.
They connect via `mainEntity` (container → entity) and `subjectOf` (entity → container).

## CSV Input

**Only `URL` column required.** Override with `SchemaType` to force types:

```csv
URL,SchemaType
https://example.com/,Organization
https://example.com/services/ac/,WebContent|Service
https://example.com/team/jane/,WebContent|Person
https://example.com/locations/atlanta/,LocalBusiness
```

## Models

| Model | Best For | Speed | Cost |
|---|---|---|---|
| Claude Sonnet 4 | Recommended default | Fast | Moderate |
| Claude Opus 4.6 | Highest quality output | Slower | Higher |
| Claude Sonnet 4.5 | Alternative balance | Fast | Moderate |
| Claude Haiku 4.5 | Large batches, budget | Fastest | Lowest |

## 16-Point Validation

Rules 1-6: Critical failures (block output)
Rules 7-12: Structural warnings (flag but allow)
Rules 13-15: Graph integrity (references, bidirectional links, connectivity)
**Rule 16: Dual-type integrity** (mainEntity/subjectOf wiring, property placement)

## Deploy to Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo, set `app.py` as main file
4. Add `ANTHROPIC_API_KEY` in Settings → Secrets
5. Share URL with team

## Architecture

```
app.py          → Streamlit UI
processor.py    → CSV parsing, dual-type inference, hierarchy, web fetching
generator.py    → Claude API with dual-type prompting + graph wiring
validator.py    → 16-point validation (including Rule 16 dual-type checks)
knowledge.py    → Templates (single + dual), Wikidata URIs, property rules
```
