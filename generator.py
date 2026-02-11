"""
Claude API integration for JSON-LD structured data generation.
Updated with dual-type support and expanded model list.
"""

import json
import anthropic
from knowledge import (
    TEMPLATES, WIKIDATA_COUNTRIES, WIKIDATA_CITIES, WIKIDATA_SERVICE_CONCEPTS,
)

SYSTEM_PROMPT = """You are an expert Technical SEO and Semantic Web Engineer specializing in JSON-LD structured data generation.

Your job is to generate a single, valid JSON-LD block for a given URL based on the provided context.

## CRITICAL RULES

1. **@context**: Always `"https://schema.org"` (HTTPS, no www)
2. **@type**: MUST be a real schema.org type. NEVER fabricate types (no "HVACBusiness", "PlumbingService", etc.)
3. **@id**: Every major entity gets `{URL}#{Type}` format
4. **No script tags**: Output RAW JSON only
5. **Property-type matching**: Only use properties valid for the declared @type
6. **Telephone**: E.164 format: `"+14045551234"`
7. **Dates**: ISO 8601: `"2008-03-15"`
8. **Don't fabricate data**: If information isn't available, OMIT the property entirely

## DUAL-TYPE RULES

When generating dual-type output (e.g. WebContent|Service):
- Use @graph with TWO major entities
- **Container (WebContent)** gets: headline, keywords, dates, creator, contributor, maintainer, contentLocation, locationCreated, countryOfOrigin, mainEntity
- **Nested entity (Service/Person/etc.)** gets: domain-specific properties + subjectOf pointing back to container
- Wire mainEntity (container → nested) and subjectOf (nested → container) bidirectionally
- NEVER put keywords, dates, or creator on the nested Service entity
- NEVER put provider, brand, areaServed, isRelatedTo on the WebContent container

## TYPE-SPECIFIC PROPERTY RULES

### Service (inherits from Thing → Intangible → Service)
- CAN use: name, description, disambiguatingDescription, url, sameAs, image, logo, provider, brand, areaServed, isRelatedTo, isSimilarTo, serviceType, hasOfferCatalog, subjectOf
- CANNOT use: `keywords`, `telephone`, `email`, `address`, `foundingDate`, `datePublished`, `dateModified`, `dateCreated`

### Organization
- CAN use: name, legalName, description, disambiguatingDescription, url, logo, image, telephone, email, sameAs, keywords, foundingDate, foundingLocation, numberOfEmployees, address, location, areaServed, subOrganization

### LocalBusiness
- Uses @graph with GeoCoordinates as separate entity
- CAN use keywords (inherits from Organization)
- Must include parentOrganization pointing to Organization @id

### WebContent
- CAN use: headline, keywords, about, creator, mentions, datePublished, mainEntity
- In dual-type, this is the container entity

### AboutPage — Minimal. mainEntity + about point to Organization @id

### Person
- CANNOT use: keywords, logo
- worksFor points to Organization @id
- In dual-type with WebContent, Person is the nested entity with subjectOf

## DEPRECATED — NEVER USE
- Types: WebPage, WebSite
- Properties: serviceArea (use areaServed), significantLink, significantLinks, isBasedOnUrl
- Context: Never use http://schema.org or variants with www

## COUNTRY ENTITY RULE
On Organization's PostalAddress, always FULLY define the country with @type, name, and @id.
Other entities can use bare @id reference.

## areaServed RULE
First occurrence needs @type + name + @id. Subsequent can use bare @id.

## OUTPUT FORMAT
Return ONLY raw JSON. No markdown code fences. No explanation. Just valid JSON."""


def build_wikidata_reference():
    lines = ["## Known Wikidata URIs\n"]
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


def generate_jsonld_for_row(
    api_key, schema_type, url, domain, page_data_text, org_data_text,
    csv_overrides_text, hierarchy_text, model="claude-sonnet-4-20250514",
):
    template = TEMPLATES.get(schema_type, "")

    is_dual = "|" in schema_type
    dual_instruction = ""
    if is_dual:
        container, nested = schema_type.split("|", 1)
        dual_instruction = f"""
## DUAL-TYPE MODE: {container}|{nested}
This is a DUAL-TYPE row. Generate @graph with:
1. A {container} entity (container) with mainEntity pointing to the {nested}
2. A {nested} entity (nested) with subjectOf pointing back to the {container}
- Put keywords, dates, creator, contentLocation on the {container} ONLY
- Put domain-specific properties (provider, brand, areaServed, hierarchy) on the {nested} ONLY
"""

    user_prompt = f"""Generate JSON-LD structured data for this URL.

## Target URL
{url}

## Schema Type
{schema_type}

## Domain
{domain}
{dual_instruction}
## Template
{template}

## Organization Data
{org_data_text}

## Page Data
{page_data_text}

## CSV Overrides (highest priority)
{csv_overrides_text}

## Service Hierarchy
{hierarchy_text}

{build_wikidata_reference()}

## Instructions
1. Fill the template using: CSV overrides > page data > org data > omit
2. Remove any property where no data is available
3. Remove empty arrays []
4. For areaServed, include @type + name + @id on first occurrence
5. Wire @id references correctly
6. Ensure telephone is E.164 format, dates are ISO 8601
7. Return ONLY raw JSON"""

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=model, max_tokens=4096, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = message.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()
        try:
            json.loads(raw_text)
        except json.JSONDecodeError as e:
            return raw_text, f"JSON parse error: {e}"
        return raw_text, ""
    except anthropic.APIError as e:
        return "", f"API error: {e}"
    except Exception as e:
        return "", f"Unexpected error: {e}"


def graph_wiring_pass(api_key, all_jsonld_blocks, model="claude-sonnet-4-20250514"):
    blocks_json = json.dumps(all_jsonld_blocks, indent=2)

    user_prompt = f"""Review these JSON-LD blocks for graph integrity and fix any issues.

## All Generated JSON-LD Blocks
{blocks_json}

## Checks to Perform
1. Every @id reference must resolve to a defined entity or be external (Wikidata, etc.)
2. Bidirectional relationships:
   - isRelatedTo A↔B, isSimilarTo A↔B, subOrganization↔parentOrganization
   - mainEntity↔subjectOf (dual-type blocks)
3. Every non-Organization entity connects back to Organization
4. Organization lists all LocalBusiness entities in subOrganization
5. Service CANNOT have keywords, dates, or creator properties
6. In dual-type blocks: keywords/dates/creator ONLY on WebContent container
7. No fabricated @types

## Output Format
Return a JSON array of the corrected blocks. ONLY raw JSON array."""

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=model, max_tokens=16000, system=SYSTEM_PROMPT,
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
        return all_jsonld_blocks, "Graph wiring returned unexpected format. Using originals."
    except json.JSONDecodeError:
        return all_jsonld_blocks, "Graph wiring response was not valid JSON. Using originals."
    except Exception as e:
        return all_jsonld_blocks, f"Graph wiring error: {e}. Using originals."
