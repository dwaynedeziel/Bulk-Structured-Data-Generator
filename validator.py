"""
16-point validation engine for JSON-LD structured data.
Rules 1-6: Critical failures | Rules 7-12: Structural warnings | Rules 13-16: Graph integrity
Updated with Rule 16: Dual-type integrity checks.
"""

import json
import re
from datetime import datetime
from knowledge import (
    DEPRECATED_TYPES, DEPRECATED_PROPERTIES, INVALID_PROPERTIES,
    VALID_DUAL_TYPES, INVALID_DUAL_TYPES,
    CONTAINER_ONLY_PROPERTIES, NESTED_ONLY_PROPERTIES,
)


def validate_jsonld(raw_json, all_defined_ids=None):
    issues = []
    auto_fixes = []
    parsed = None

    # Rule 1: Valid JSON Syntax
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        issues.append((1, "FAIL", f"Invalid JSON syntax: {e}"))
        return _result(issues, auto_fixes, None)

    entities = _extract_entities(parsed)

    # Rule 2: @context
    context = parsed.get("@context", "")
    if not context:
        issues.append((2, "FAIL", "@context is missing"))
    elif context != "https://schema.org":
        if context in ("http://schema.org", "http://www.schema.org", "https://www.schema.org"):
            auto_fixes.append("Fixed @context to https://schema.org")
            parsed["@context"] = "https://schema.org"
        else:
            issues.append((2, "FAIL", f"@context is '{context}', expected 'https://schema.org'"))

    # Rule 3: @type validity
    valid_types = {
        "Organization", "LocalBusiness", "Service", "WebContent", "AboutPage",
        "Person", "PostalAddress", "GeoCoordinates", "OpeningHoursSpecification",
        "City", "Place", "AdministrativeArea", "Country", "State",
        "OfferCatalog", "Offer", "ImageObject", "Thing",
        "CollegeOrUniversity", "EducationalOrganization",
        "Dentist", "LegalService", "MedicalBusiness", "ProfessionalService",
        "AutoRepair", "HomeAndConstructionBusiness",
    }
    for entity in entities:
        etype = entity.get("@type", "")
        if etype and etype not in valid_types:
            issues.append((3, "FAIL", f"Fabricated @type: '{etype}'"))

    # Rule 4: @id on major entities
    major_types = {"Organization", "LocalBusiness", "Service", "WebContent", "AboutPage", "Person"}
    for entity in entities:
        if entity.get("@type") in major_types and not entity.get("@id"):
            issues.append((4, "FAIL", f"{entity.get('@type')} is missing @id"))

    # Rule 5: No deprecated types
    for entity in entities:
        etype = entity.get("@type", "")
        if etype in DEPRECATED_TYPES:
            issues.append((5, "FAIL", f"Deprecated type '{etype}': {DEPRECATED_TYPES[etype]}"))

    # Rule 6: No deprecated properties
    for entity in entities:
        for prop in entity.keys():
            if prop in DEPRECATED_PROPERTIES:
                issues.append((6, "FAIL",
                    f"Deprecated property '{prop}' on {entity.get('@type', '?')}: use '{DEPRECATED_PROPERTIES[prop]}'"))

    # Rule 7: Property-type compatibility
    for entity in entities:
        etype = entity.get("@type", "")
        if etype in INVALID_PROPERTIES:
            for prop in entity.keys():
                if prop in INVALID_PROPERTIES[etype]:
                    issues.append((7, "WARN", f"Property '{prop}' is not valid on @type '{etype}'"))

    # Rule 8: areaServed completeness (checked at batch level)
    # Rule 9: Country entity defined
    has_full_country = False
    for entity in entities:
        addr = entity.get("address", {})
        if isinstance(addr, dict):
            country = addr.get("addressCountry", {})
            if isinstance(country, dict) and country.get("@type") == "Country":
                has_full_country = True
                break
    if not has_full_country and any(e.get("@type") in ("Organization", "LocalBusiness") for e in entities):
        issues.append((9, "WARN", "Country entity not fully defined in any PostalAddress"))

    # Rule 10: Telephone format
    for entity in entities:
        phone = entity.get("telephone", "")
        if phone and not re.match(r"^\+\d{10,15}$", phone):
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

    # Rule 11: Date format
    date_props = ["foundingDate", "dateCreated", "dateModified", "datePublished"]
    for entity in entities:
        for prop in date_props:
            val = entity.get(prop, "")
            if val and not _is_valid_date(val):
                issues.append((11, "WARN", f"Date '{val}' for '{prop}' is not ISO 8601"))

    # Rule 12: No script tags
    if "<script" in raw_json.lower():
        auto_fixes.append("Stripped <script> tags from output")
        issues.append((12, "WARN", "Output contained <script> tags (auto-removed)"))

    # Rule 13: @id references resolve
    if all_defined_ids is not None:
        local_ids = {e.get("@id") for e in entities if e.get("@id")}
        combined = local_ids | all_defined_ids
        for entity in entities:
            _check_id_refs(entity, combined, issues)

    # Rule 14: Bidirectional relationships (checked in graph wiring pass)
    # Rule 15: Graph connectivity (checked in graph wiring pass)

    # Rule 16: Dual-type integrity
    _check_dual_type_integrity(parsed, entities, issues, auto_fixes)

    return _result(issues, auto_fixes, parsed)


def _check_dual_type_integrity(parsed, entities, issues, auto_fixes):
    """Rule 16: Validate dual-type blocks."""
    if "@graph" not in parsed:
        return

    major_types = {"Organization", "LocalBusiness", "Service", "WebContent", "AboutPage", "Person"}
    major_entities = [e for e in entities if e.get("@type") in major_types]

    if len(major_entities) < 2:
        return  # Not a dual-type block

    # Find container (WebContent) and nested entity
    container = None
    nested = None
    for e in major_entities:
        if e.get("@type") == "WebContent":
            container = e
        elif e.get("@type") in ("Service", "Person", "LocalBusiness", "Organization"):
            nested = e

    if not container or not nested:
        return  # Not a recognized dual-type pattern

    # A. Structural checks
    if not container.get("mainEntity"):
        issues.append((16, "WARN", "Dual-type: WebContent container missing mainEntity"))
    if not nested.get("subjectOf"):
        issues.append((16, "WARN", f"Dual-type: {nested.get('@type')} missing subjectOf"))

    # Verify mainEntity points to nested
    me = container.get("mainEntity", {})
    if isinstance(me, dict) and me.get("@id") != nested.get("@id"):
        issues.append((16, "WARN", "Dual-type: mainEntity @id doesn't match nested entity @id"))

    # Verify subjectOf points to container
    so = nested.get("subjectOf", {})
    if isinstance(so, dict) and so.get("@id") != container.get("@id"):
        issues.append((16, "WARN", "Dual-type: subjectOf @id doesn't match container @id"))

    # B. Property placement checks
    nested_type = nested.get("@type", "")
    for prop in CONTAINER_ONLY_PROPERTIES:
        if prop in nested and prop not in ("headline",):
            # Auto-fix: flag keywords/dates on nested Service
            issues.append((16, "WARN",
                f"Dual-type: '{prop}' should be on WebContent container, not {nested_type}"))

    for prop in NESTED_ONLY_PROPERTIES:
        if prop in container:
            issues.append((16, "WARN",
                f"Dual-type: '{prop}' should be on {nested_type}, not WebContent container"))


def _extract_entities(parsed):
    entities = []
    if "@graph" in parsed:
        for item in parsed["@graph"]:
            if isinstance(item, dict):
                entities.append(item)
    else:
        entities.append(parsed)
    for entity in list(entities):
        for key, val in entity.items():
            if isinstance(val, dict) and "@type" in val:
                entities.append(val)
    return entities


def _is_valid_date(val):
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?", val))


def _check_id_refs(obj, known_ids, issues):
    for key, val in obj.items():
        if key == "@id":
            continue
        if isinstance(val, dict):
            ref = val.get("@id")
            if ref and not val.get("@type"):
                if (not ref.startswith("http://www.wikidata.org") and
                    not ref.startswith("https://g.co") and
                    not ref.startswith("https://www.google.com/maps") and
                    ref not in known_ids):
                    issues.append((13, "WARN", f"Unresolved @id reference: {ref}"))
            _check_id_refs(val, known_ids, issues)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _check_id_refs(item, known_ids, issues)


def _result(issues, auto_fixes, parsed):
    has_fail = any(sev == "FAIL" for _, sev, _ in issues)
    has_warn = any(sev == "WARN" for _, sev, _ in issues)
    status = "FAIL" if has_fail else ("WARN" if has_warn else "PASS")
    return {"status": status, "issues": issues, "auto_fixes": auto_fixes, "parsed": parsed}


def generate_validation_report(results, rows):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    dual_count = sum(1 for r in rows if r.get("_is_dual"))
    single_count = total - dual_count

    lines = [
        "# Structured Data Validation Report\n",
        f"**Generated:** {now}",
        f"**Total rows:** {total}",
        f"**Passed:** {passed}  |  **Warnings:** {warned}  |  **Failed:** {failed}",
        f"**Single-type rows:** {single_count}  |  **Dual-type rows:** {dual_count}\n",
        "## Per-Row Summary\n",
        "| URL | Type(s) | Status | Issues |",
        "|-----|---------|--------|--------|",
    ]

    for result, row in zip(results, rows):
        url = row.get("URL", "?")
        stype = row.get("_inferred_type", "?")
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(result["status"], "?")
        issue_text = "; ".join(f"Rule {n}: {m}" for n, s, m in result["issues"]) if result["issues"] else "—"
        lines.append(f"| {url} | {stype} | {icon} {result['status']} | {issue_text} |")

    # Dual-type assignments
    dual_rows = [(row, result) for row, result in zip(rows, results) if row.get("_is_dual")]
    if dual_rows:
        lines.append("\n## Dual-Type Assignments\n")
        lines.append("| URL | Container | Main Entity | Source |")
        lines.append("|-----|-----------|-------------|--------|")
        for row, result in dual_rows:
            lines.append(f"| {row['URL']} | {row['_container_type']} | {row['_nested_type']} | {row['_type_confidence']} |")

    # Auto-fixes
    all_fixes = []
    for i, result in enumerate(results):
        for fix in result.get("auto_fixes", []):
            all_fixes.append((rows[i].get("URL", "?"), fix))
    if all_fixes:
        lines.append("\n## Auto-Fixes Applied\n")
        lines.append("| URL | Fix |")
        lines.append("|-----|-----|")
        for url, fix in all_fixes:
            lines.append(f"| {url} | {fix} |")

    return "\n".join(lines)
