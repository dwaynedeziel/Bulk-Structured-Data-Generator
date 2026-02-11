"""
Claude API integration for JSON-LD structured data generation.
Sends page context + templates + rules to Claude and receives validated JSON-LD.
"""

import json
import anthropic

from knowledge import (
    TEMPLATES,
    WIKIDATA_COUNTRIES,
    WIKIDATA_STATES,
    WIKIDATA_CITIES,
    WIKIDATA_SERVICE_CONCEPTS,
    DEPRECATED_TYPES,
    DEPRECATED_PROPERTIES,
    INVALID_PROPERTIES,
)

# ─── System Prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Technical SEO and Semantic Web Engineer specializing in JSON-LD structured data generation.

Your job is to generate a single, valid JSON-LD block for a given URL based on the provided context.

## CRITICAL RULES

1. **@context**: Always `"https://schema.org"` (HTTPS, no www)
2. **@type**: MUST be a real schema.org type. NEVER fabricate types (no "HVACBusiness", "PlumbingService", etc.)
3. **@id**: Every major entity gets `{URL}#{Type}` format
4. **No script tags**: Output RAW JSON only — no `<script>` wrappers
5. **Property-type matching**: Only use properties valid for the declared @type
6. **Telephone**: E.164 format: `"+14045551234"`
7. **Dates**: ISO 8601: `"2008-03-15"`
8. **Don't fabricate data**: If information isn't available, OMIT the property entirely

## TYPE-SPECIFIC PROPERTY RULES

### Service (inherits from Thing → Intangible → Service)
- CAN use: name, description, disambiguatingDescription, url, sameAs, image, logo, provider, brand, areaServed, isRelatedTo, isSimilarTo, serviceType, hasOfferCatalog
- CANNOT use: `keywords` (CreativeWork property), `telephone`, `email`, `address`, `foundingDate`

### Organization
- CAN use: name, legalName, description, disambiguatingDescription, url, logo, image, telephone, email, sameAs, keywords, foundingDate, foundingLocation, numberOfEmployees, address, location, areaServed, subOrganization

### LocalBusiness
- Uses @graph array with GeoCoordinates as separate entity
- CAN use keywords (inherits from Organization)
- Must include parentOrganization pointing to Organization @id

### WebContent
- CAN use: keywords, about, creator, mentions, datePublished, headline
- about/creator/contributor/maintainer all point to Organization @id

### AboutPage
- Minimal schema. mainEntity + about point to Organization @id

### Person
- CANNOT use: keywords, logo
- worksFor points to Organization @id

## DEPRECATED — NEVER USE
- Types: WebPage, WebSite
- Properties: serviceArea (use areaServed), significantLink, significantLinks, isBasedOnUrl
- Context: Never use http://schema.org, http://www.schema.org, or https://www.schema.org

## COUNTRY ENTITY RULE
On Organization's PostalAddress, always FULLY define the country:
```json
"addressCountry": {
    "@type": "Country",
    "name": "United States",
    "@id": "http://www.wikidata.org/entity/Q30"
}
```
Other entities can use bare @id reference: `"addressCountry": { "@id": "http://www.wikidata.org/entity/Q30" }`

## areaServed RULE
First occurrence of each geographic entity must include @type + name + @id.
Subsequent references can use bare @id.

## OUTPUT FORMAT
Return ONLY the raw JSON-LD. No markdown code fences. No explanation. No commentary.
Just valid JSON starting with { and ending with }."""


# ─── Wikidata Quick-Reference for Prompt ─────────────────────────────────────

def build_wikidata_reference() -> str:
    """Build a compact Wikidata reference string for the prompt."""
    lines = ["## Known Wikidata URIs (use these when applicable)\n"]

    lines.append("### Countries")
    for name, uri in WIKIDATA_COUNTRIES.items():
        lines.append(f"- {name}: {uri}")

    lines.append("\n### Cities")
    for name, uri in WIKIDATA_CITIES.items():
        lines.append(f"- {name}: {uri}")

    lines.append("\n### Service Concepts")
    for name, uri in WIKIDATA_SERVICE_CONCEPTS.items():
        lines.append(f"- {name}: {uri}")

    return "\n".join(lines)


# ─── Per-Row Generation ─────────────────────────────────────────────────────

def generate_jsonld_for_row(
    api_key: str,
    schema_type: str,
    url: str,
    domain: str,
    page_data_text: str,
    org_data_text: str,
    csv_overrides_text: str,
    hierarchy_text: str,
    model: str = "claude-sonnet-4-20250514",
) -> tuple[str, str]:
    """
    Call Claude API to generate JSON-LD for a single URL.

    Returns (json_ld_string, error_message).
    If successful, error_message is empty.
    """
    template = TEMPLATES.get(schema_type, "")

    user_prompt = f"""Generate JSON-LD structured data for this URL.

## Target URL
{url}

## Schema Type
{schema_type}

## Domain
{domain}

## Template (fill in discovered values, remove properties with no data)
{template}

## Organization Data (shared across all entities)
{org_data_text}

## Page Data (scraped from target URL)
{page_data_text}

## CSV Overrides (highest priority — use these over discovered values)
{csv_overrides_text}

## Service Hierarchy (for Service type — wire isRelatedTo and isSimilarTo)
{hierarchy_text}

{build_wikidata_reference()}

## Instructions
1. Fill the template using: CSV overrides > page data > org data > omit
2. Remove any property where no data is available — do NOT use placeholder text
3. Remove empty arrays []
4. For areaServed, include @type + name + @id on first occurrence
5. Wire @id references correctly: {{domain}}/#Organization, {{url}}#{{Type}}
6. Ensure telephone is E.164 format
7. Ensure dates are ISO 8601
8. Return ONLY raw JSON — no markdown, no explanation"""

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = message.content[0].text.strip()

        # Clean up: strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

        # Validate it's parseable JSON
        try:
            json.loads(raw_text)
        except json.JSONDecodeError as e:
            return raw_text, f"JSON parse error: {e}"

        return raw_text, ""

    except anthropic.APIError as e:
        return "", f"API error: {e}"
    except Exception as e:
        return "", f"Unexpected error: {e}"


# ─── Graph Wiring Pass ──────────────────────────────────────────────────────

def graph_wiring_pass(
    api_key: str,
    all_jsonld_blocks: list[dict],
    model: str = "claude-sonnet-4-20250514",
) -> tuple[list[dict], str]:
    """
    Final pass: verify cross-references, bidirectional links, orphan check.
    Returns (corrected_blocks, report_text).
    """
    blocks_json = json.dumps(all_jsonld_blocks, indent=2)

    user_prompt = f"""Review these JSON-LD blocks for graph integrity and fix any issues.

## All Generated JSON-LD Blocks
{blocks_json}

## Checks to Perform
1. Every @id reference must point to a defined entity (in same block or another block) or be an external URI (Wikidata, Google Maps, etc.)
2. Bidirectional relationships must be complete:
   - If Service A has isRelatedTo B → B must have isRelatedTo A
   - If Organization has subOrganization B → B must have parentOrganization pointing back
   - If Service A has isSimilarTo B → B must have isSimilarTo A
3. Every non-Organization entity must connect back to Organization via provider, parentOrganization, about, worksFor, or mainEntity
4. Organization should list all LocalBusiness entities in subOrganization
5. Service CANNOT have keywords property
6. No fabricated @types

## Output Format
Return a JSON array of the corrected blocks. ONLY raw JSON array — no markdown, no explanation.
If no changes needed, return the blocks unchanged."""

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        corrected = json.loads(raw)
        if isinstance(corrected, list):
            return corrected, "Graph wiring pass completed successfully."
        else:
            return all_jsonld_blocks, "Graph wiring returned unexpected format. Using original blocks."

    except json.JSONDecodeError:
        return all_jsonld_blocks, "Graph wiring response was not valid JSON. Using original blocks."
    except Exception as e:
        return all_jsonld_blocks, f"Graph wiring error: {e}. Using original blocks."
