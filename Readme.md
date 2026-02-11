# 🔗 Bulk Structured Data Generator

A Streamlit app that generates validated, graph-connected JSON-LD structured data from a CSV of URLs using the Claude API.

## What It Does

Upload a CSV with URLs → the app:

1. **Infers schema types** from URL patterns (Organization, LocalBusiness, Service, WebContent, AboutPage, Person)
2. **Fetches each page** to extract H1, meta description, phone, email, social links, existing JSON-LD
3. **Discovers org data** from the homepage (business name, address, logo, social profiles)
4. **Detects service hierarchy** (parent/child/sibling relationships from URL structure)
5. **Generates JSON-LD** for each URL using Claude API with embedded templates and rules
6. **Validates output** with a 15-point validation engine
7. **Wires the knowledge graph** — cross-references, bidirectional links, Wikidata entities
8. **Outputs** CSV with JSON-LD column, individual JSON files, and a validation report

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR-USERNAME/structured-data-generator.git
cd structured-data-generator
pip install -r requirements.txt
```

### 2. Add Your API Key

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml and add your Anthropic API key
```

### 3. Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## CSV Input Format

**Only the `URL` column is required.** Everything else is auto-discovered.

### Minimal CSV
```csv
URL
https://www.example.com/
https://www.example.com/locations/atlanta/
https://www.example.com/services/air-conditioning/
https://www.example.com/about/
```

### CSV with Overrides
```csv
URL,SchemaType,AreaServedCities,AreaServedCounties,AreaServedMetro
https://www.example.com/,Organization,Atlanta|Decatur|Marietta,DeKalb County|Fulton County,Atlanta metropolitan area
https://www.example.com/locations/atlanta/,LocalBusiness,,,
https://www.example.com/services/air-conditioning/,Service,,,
```

### URL Pattern → Type Inference

| URL Pattern | Inferred Type |
|---|---|
| `/` or domain root | Organization |
| `/about/` or `/about-us/` | AboutPage |
| `/about/team/{name}/` | Person |
| `/locations/{city}/` | LocalBusiness |
| `/services/{name}/` | Service |
| `/blog/{slug}/` | WebContent |
| `/industries/{name}/` | WebContent |

### Override Columns

When auto-discovery gets something wrong, add override columns:

| Column | What It Overrides |
|---|---|
| `SchemaType` | Force a specific schema type |
| `BusinessName` | Auto-extracted business name |
| `Phone` | Discovered phone number |
| `Email` | Discovered email |
| `Logo` | Logo URL |
| `Street`, `City`, `State`, `Zip` | Address components |
| `AreaServedCities` | Pipe-delimited cities |
| `AreaServedCounties` | Pipe-delimited counties |
| `AreaServedMetro` | Metro area name |
| `Keywords` | Pipe-delimited keywords |
| `Latitude`, `Longitude` | Coordinates |
| `GoogleMapsURL` | Google Maps link |
| `ServiceName`, `SubServices` | Service specifics |
| `FoundingDate`, `NumEmployees` | Organization details |
| `SameAs` | Social profile URLs (pipe-delimited) |

Use `|` (pipe) to separate multiple values in a single cell.

## Validation Engine

Every output is run through a 15-point validation engine:

**Critical (blocks output):**
1. Valid JSON syntax
2. `@context` present and correct (`https://schema.org`)
3. `@type` is a real schema.org type (no fabricated types)
4. `@id` present on major entities
5. No deprecated types (WebPage, WebSite)
6. No deprecated properties (serviceArea → areaServed)

**Warnings (flags but allows):**
7. Property-type compatibility (e.g., Service cannot use `keywords`)
8. areaServed entity completeness
9. Country entity defined
10. Telephone in E.164 format (auto-fixes when possible)
11. ISO 8601 date format
12. No `<script>` tag wrappers in JSON output

**Graph integrity:**
13. All `@id` references resolve
14. Bidirectional relationships complete
15. Graph connectivity (no orphan entities)

## Outputs

| Output | Description |
|---|---|
| **CSV** | Original CSV + JSON-LD column + validation status |
| **JSON Files (ZIP)** | One `.json` file per URL |
| **Validation Report** | Markdown report with per-row status, auto-fixes, and issues |

## Deploy to Streamlit Community Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo, set `app.py` as the main file
4. Add `ANTHROPIC_API_KEY` in the Secrets section (Settings → Secrets)
5. Deploy

Your team gets a URL like `https://your-app.streamlit.app` — no local setup needed.

## Architecture

```
app.py              → Streamlit UI (upload, preview, generate, download)
processor.py        → CSV parsing, type inference, hierarchy, web fetching
generator.py        → Claude API calls for JSON-LD generation + graph wiring
validator.py        → 15-point validation engine
knowledge.py        → Embedded templates, Wikidata URIs, schema rules
```

The app splits work between Python and Claude:
- **Python handles**: CSV parsing, web page fetching, URL hierarchy detection, JSON validation, file packaging
- **Claude handles**: Intelligent JSON-LD generation, data extraction from page content, graph wiring

## Customization

### Adding New Schema Types

1. Add the template to `TEMPLATES` in `knowledge.py`
2. Add URL pattern to `URL_TYPE_PATTERNS` in `knowledge.py`
3. Add property restrictions to `VALID_PROPERTIES` and `INVALID_PROPERTIES`
4. Update the system prompt in `generator.py` if needed

### Adding Wikidata URIs

Add entries to the dictionaries in `knowledge.py`:
- `WIKIDATA_CITIES` for new cities
- `WIKIDATA_STATES` for state lookups
- `WIKIDATA_SERVICE_CONCEPTS` for industry terms

## Cost Estimation

Each URL requires one Claude API call (~1-2K input tokens, ~1-2K output tokens). The graph wiring pass is one additional call with all blocks.

For a typical 15-URL batch on Claude Sonnet:
- ~15 generation calls + 1 wiring call ≈ ~50K total tokens
- Estimated cost: ~$0.15-0.30 per batch

## License

Internal tool — not for public distribution.
