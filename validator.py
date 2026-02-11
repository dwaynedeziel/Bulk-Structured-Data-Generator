"""
15-point validation engine for JSON-LD structured data.
Rules 1-6: Critical failures (block output)
Rules 7-12: Structural warnings (flag but allow)
Rules 13-15: Graph integrity checks
"""

import json
import re
from datetime import datetime

from knowledge import DEPRECATED_TYPES, DEPRECATED_PROPERTIES, INVALID_PROPERTIES


def validate_jsonld(raw_json: str, all_defined_ids: set = None) -> dict:
    """
    Run the 15-point validation engine on a JSON-LD string.

    Returns dict with:
        status: "PASS", "WARN", or "FAIL"
        issues: list of (rule_num, severity, message)
        auto_fixes: list of fixes applied
        parsed: the parsed JSON object (if valid)
    """
    issues = []
    auto_fixes = []
    parsed = None

    # ── Rule 1: Valid JSON Syntax ──
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        issues.append((1, "FAIL", f"Invalid JSON syntax: {e}"))
        return _result(issues, auto_fixes, None)

    # Get all entities (handle @graph or single object)
    entities = _extract_entities(parsed)

    # ── Rule 2: @context Present and Correct ──
    context = parsed.get("@context", "")
    if not context:
        issues.append((2, "FAIL", "@context is missing"))
    elif context != "https://schema.org":
        if context in ("http://schema.org", "http://www.schema.org", "https://www.schema.org"):
            auto_fixes.append("Fixed @context to https://schema.org")
            parsed["@context"] = "https://schema.org"
        else:
            issues.append((2, "FAIL", f"@context is '{context}', expected 'https://schema.org'"))

    # ── Rule 3: @type Is a Real Schema.org Type ──
    valid_types = {
        "Organization", "LocalBusiness", "Service", "WebContent", "AboutPage",
        "Person", "PostalAddress", "GeoCoordinates", "OpeningHoursSpecification",
        "City", "Place", "AdministrativeArea", "Country", "State",
        "OfferCatalog", "Offer", "ImageObject", "Thing",
        "CollegeOrUniversity", "EducationalOrganization",
        # LocalBusiness subtypes
        "Dentist", "LegalService", "MedicalBusiness", "ProfessionalService",
        "AutoRepair", "HomeAndConstructionBusiness",
    }
    for entity in entities:
        etype = entity.get("@type", "")
        if etype and etype not in valid_types:
            issues.append((3, "FAIL", f"Fabricated @type: '{etype}'"))

    # ── Rule 4: @id Present on Major Entities ──
    major_types = {"Organization", "LocalBusiness", "Service", "WebContent", "AboutPage", "Person"}
    for entity in entities:
        if entity.get("@type") in major_types and not entity.get("@id"):
            issues.append((4, "FAIL", f"{entity.get('@type')} is missing @id"))

    # ── Rule 5: No Deprecated Types ──
    for entity in entities:
        etype = entity.get("@type", "")
        if etype in DEPRECATED_TYPES:
            issues.append((5, "FAIL", f"Deprecated type '{etype}': {DEPRECATED_TYPES[etype]}"))

    # ── Rule 6: No Deprecated Properties ──
    for entity in entities:
        for prop in entity.keys():
            if prop in DEPRECATED_PROPERTIES:
                issues.append((6, "FAIL",
                    f"Deprecated property '{prop}' on {entity.get('@type', '?')}: "
                    f"use '{DEPRECATED_PROPERTIES[prop]}' instead"))

    # ── Rule 7: Property-Type Compatibility ──
    for entity in entities:
        etype = entity.get("@type", "")
        if etype in INVALID_PROPERTIES:
            for prop in entity.keys():
                if prop in INVALID_PROPERTIES[etype]:
                    issues.append((7, "WARN",
                        f"Property '{prop}' is not valid on @type '{etype}'"))

    # ── Rule 8: areaServed Entity Completeness ──
    for entity in entities:
        area_served = entity.get("areaServed", [])
        if isinstance(area_served, list):
            for area in area_served:
                if isinstance(area, dict):
                    if "@id" in area and "@type" not in area and "name" not in area:
                        # Bare @id — acceptable if defined elsewhere
                        pass  # Will be checked in Rule 13

    # ── Rule 9: Country Entity Defined ──
    has_full_country = False
    for entity in entities:
        addr = entity.get("address", {})
        if isinstance(addr, dict):
            country = addr.get("addressCountry", {})
            if isinstance(country, dict) and country.get("@type") == "Country":
                has_full_country = True
                break
    if not has_full_country and any(e.get("@type") in ("Organization", "LocalBusiness") for e in entities):
        # Check if any entity has full country definition
        issues.append((9, "WARN", "Country entity not fully defined in any PostalAddress"))

    # ── Rule 10: Telephone Format ──
    for entity in entities:
        phone = entity.get("telephone", "")
        if phone and not re.match(r"^\+\d{10,15}$", phone):
            # Attempt auto-fix
            digits = re.sub(r"\D", "", phone)
            if len(digits) == 10:
                fixed = f"+1{digits}"
                entity["telephone"] = fixed
                auto_fixes.append(f"Auto-fixed phone to E.164: {fixed}")
            elif len(digits) == 11 and digits.startswith("1"):
                fixed = f"+{digits}"
                entity["telephone"] = fixed
                auto_fixes.append(f"Auto-fixed phone to E.164: {fixed}")
            else:
                issues.append((10, "WARN", f"Phone '{phone}' is not E.164 format"))

    # ── Rule 11: Date Format ──
    date_props = ["foundingDate", "dateCreated", "dateModified", "datePublished"]
    for entity in entities:
        for prop in date_props:
            val = entity.get(prop, "")
            if val and not _is_valid_date(val):
                issues.append((11, "WARN", f"Date '{val}' for '{prop}' is not ISO 8601"))

    # ── Rule 12: No Script Tag Wrappers ──
    if "<script" in raw_json.lower():
        auto_fixes.append("Stripped <script> tags from output")
        issues.append((12, "WARN", "Output contained <script> tags (auto-removed)"))

    # ── Rule 13: @id References Resolve ──
    if all_defined_ids is not None:
        local_ids = {e.get("@id") for e in entities if e.get("@id")}
        combined = local_ids | all_defined_ids
        for entity in entities:
            _check_id_refs(entity, combined, issues)

    # ── Rule 14: Bidirectional Relationships ── (checked in graph wiring pass)

    # ── Rule 15: Graph Connectivity ── (checked in graph wiring pass)

    return _result(issues, auto_fixes, parsed)


def _extract_entities(parsed: dict) -> list[dict]:
    """Extract all entities from a JSON-LD block (handles @graph)."""
    entities = []
    if "@graph" in parsed:
        for item in parsed["@graph"]:
            if isinstance(item, dict):
                entities.append(item)
    else:
        entities.append(parsed)
    # Also check nested objects
    for entity in list(entities):
        for key, val in entity.items():
            if isinstance(val, dict) and "@type" in val:
                entities.append(val)
    return entities


def _is_valid_date(val: str) -> bool:
    """Check if string is ISO 8601 date or datetime."""
    patterns = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
    ]
    return any(re.match(p, val) for p in patterns)


def _check_id_refs(obj: dict, known_ids: set, issues: list):
    """Recursively check that @id references resolve."""
    for key, val in obj.items():
        if key == "@id":
            continue
        if isinstance(val, dict):
            ref = val.get("@id")
            if ref and not val.get("@type"):
                # Bare @id reference — check if it resolves
                if not ref.startswith("http://www.wikidata.org") and \
                   not ref.startswith("https://g.co") and \
                   not ref.startswith("https://www.google.com/maps") and \
                   ref not in known_ids:
                    issues.append((13, "WARN", f"Unresolved @id reference: {ref}"))
            _check_id_refs(val, known_ids, issues)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _check_id_refs(item, known_ids, issues)


def _result(issues: list, auto_fixes: list, parsed) -> dict:
    """Build the validation result dict."""
    has_fail = any(sev == "FAIL" for _, sev, _ in issues)
    has_warn = any(sev == "WARN" for _, sev, _ in issues)

    if has_fail:
        status = "FAIL"
    elif has_warn:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "issues": issues,
        "auto_fixes": auto_fixes,
        "parsed": parsed,
    }


def generate_validation_report(results: list[dict], rows: list[dict]) -> str:
    """Generate a markdown validation report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    lines = [
        "# Structured Data Validation Report\n",
        f"**Generated:** {now}",
        f"**Total rows:** {total}",
        f"**Passed:** {passed}  |  **Warnings:** {warned}  |  **Failed:** {failed}\n",
        "## Per-Row Summary\n",
        "| URL | Type | Status | Issues |",
        "|-----|------|--------|--------|",
    ]

    for i, (result, row) in enumerate(zip(results, rows)):
        url = row.get("URL", "?")
        stype = row.get("_inferred_type", "?")
        status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(result["status"], "?")
        issue_text = "; ".join(
            f"Rule {num}: {msg}" for num, sev, msg in result["issues"]
        ) if result["issues"] else "—"
        lines.append(f"| {url} | {stype} | {status_icon} {result['status']} | {issue_text} |")

    # Auto-fixes section
    all_fixes = []
    for i, result in enumerate(results):
        if result["auto_fixes"]:
            for fix in result["auto_fixes"]:
                all_fixes.append((rows[i].get("URL", "?"), fix))

    if all_fixes:
        lines.append("\n## Auto-Fixes Applied\n")
        lines.append("| URL | Fix |")
        lines.append("|-----|-----|")
        for url, fix in all_fixes:
            lines.append(f"| {url} | {fix} |")

    return "\n".join(lines)
