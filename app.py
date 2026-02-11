"""
Bulk Structured Data Generator — Streamlit App
Generates validated, graph-connected JSON-LD from a CSV of URLs using Claude API.
Updated with dual-type support and expanded model selection.
"""

import streamlit as st
import pandas as pd
import json
import io
import zipfile
import time
from urllib.parse import urlparse

from processor import (
    parse_csv, extract_domain, assign_types, build_service_hierarchy,
    build_location_relationships, fetch_page, format_page_data_for_prompt,
    get_csv_overrides, get_primary_entity_type,
)
from generator import generate_jsonld_for_row, graph_wiring_pass
from validator import validate_jsonld, generate_validation_report

st.set_page_config(
    page_title="Bulk Structured Data Generator",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    .status-pass { color: #22c55e; font-weight: bold; }
    .status-warn { color: #f59e0b; font-weight: bold; }
    .status-fail { color: #ef4444; font-weight: bold; }
    div[data-testid="stExpander"] { border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; }
    .metric-card { background: #f8fafc; border-radius: 8px; padding: 16px; text-align: center; border: 1px solid #e2e8f0; }
    .metric-value { font-size: 2rem; font-weight: 700; }
    .metric-label { font-size: 0.85rem; color: #64748b; }
    .dual-badge { background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
    .single-badge { background: #f0fdf4; color: #166534; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─── API Key ─────────────────────────────────────────────────────────────────

def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass
    return st.session_state.get("api_key", "")

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")

    api_key = get_api_key()
    if not api_key:
        api_key = st.text_input(
            "Anthropic API Key", type="password",
            help="Enter your API key. For permanent setup, add it to .streamlit/secrets.toml",
        )
        if api_key:
            st.session_state["api_key"] = api_key

    api_key_valid = bool(api_key and api_key.startswith("sk-"))
    if api_key_valid:
        st.success("API key configured")
    elif api_key:
        st.warning("API key should start with 'sk-'")

    st.divider()

    # Model selection — expanded with Opus
    model = st.selectbox(
        "Claude Model",
        options=[
            "claude-sonnet-4-20250514",
            "claude-opus-4-6",
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
        ],
        format_func=lambda x: {
            "claude-sonnet-4-20250514": "Claude Sonnet 4 (recommended)",
            "claude-opus-4-6": "Claude Opus 4.6 (highest quality)",
            "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
            "claude-haiku-4-5-20251001": "Claude Haiku 4.5 (fastest, cheapest)",
        }.get(x, x),
        index=0,
        help="Sonnet 4 is the best balance of quality and speed. Opus 4.6 is the most capable but slower and more expensive.",
    )

    st.divider()
    st.subheader("Processing Options")
    fetch_pages = st.checkbox("Fetch page content", value=True)
    run_graph_wiring = st.checkbox("Graph wiring pass", value=True)
    skip_org_discovery = st.checkbox("Skip homepage discovery", value=False)

    st.divider()
    st.caption("v2.0 — Dual-Type Support")
    st.caption("Built with Claude API + Streamlit")

# ─── Main Content ────────────────────────────────────────────────────────────

st.title("🔗 Bulk Structured Data Generator")
st.markdown("Generate validated, graph-connected JSON-LD structured data from a CSV of URLs.")

# ─── Upload ──────────────────────────────────────────────────────────────────

st.subheader("1. Upload CSV")

col1, col2 = st.columns([2, 1])
with col1:
    uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"],
        help="Only the URL column is required. All other data is auto-discovered.")
with col2:
    st.markdown("**Minimum CSV format:**")
    st.code("URL\nhttps://example.com/\nhttps://example.com/services/ac/\nhttps://example.com/about/", language="csv")
    with st.expander("Override columns & dual types"):
        st.markdown("""
        **Dual-type syntax** in `SchemaType` column:
        - `WebContent|Service` — service pages (auto-inferred for `/services/` URLs)
        - `WebContent|Person` — team bio pages (auto-inferred for `/team/` URLs)
        - `WebContent|LocalBusiness` — rich location pages

        **Override columns**: `BusinessName`, `Phone`, `Email`, `Logo`,
        `Street`, `City`, `State`, `Zip`, `AreaServedCities` (pipe-delimited),
        `Keywords`, `ServiceName`, `SubServices`, and more.
        """)

if not uploaded_file:
    st.info("Upload a CSV to get started. Only the **URL** column is required.")
    st.stop()

# ─── Parse & Preview ─────────────────────────────────────────────────────────

raw_content = uploaded_file.read()
rows = parse_csv(raw_content)

if not rows:
    st.error("No valid rows found. Make sure your CSV has a 'URL' column.")
    st.stop()

rows = assign_types(rows)

st.subheader("2. Review Detected Types")

preview_data = []
for r in rows:
    type_display = r["_inferred_type"]
    mode = "Dual" if r["_is_dual"] else "Single"
    preview_data.append({
        "URL": r["URL"],
        "Schema Type(s)": type_display,
        "Mode": mode,
        "Confidence": r["_type_confidence"],
    })

preview_df = pd.DataFrame(preview_data)
st.dataframe(preview_df, use_container_width=True, hide_index=True)

# Dual-type summary
dual_count = sum(1 for r in rows if r["_is_dual"])
single_count = len(rows) - dual_count
if dual_count > 0:
    st.info(f"📊 **{single_count}** single-type rows, **{dual_count}** dual-type rows (WebContent + nested entity)")

# Hierarchy
hierarchy = build_service_hierarchy(rows)
if hierarchy:
    with st.expander("🌳 Service Hierarchy"):
        for url, info in hierarchy.items():
            indent = "  " * (info["depth"] - 1)
            parent_label = f" ← parent: {info['parent']}" if info["parent"] else ""
            siblings_label = f" ↔ siblings: {len(info['siblings'])}" if info["siblings"] else ""
            st.text(f"{indent}{'├── ' if info['depth'] > 1 else ''}{url}{parent_label}{siblings_label}")

loc_rels = build_location_relationships(rows)
if loc_rels["location_urls"]:
    with st.expander("📍 Location Relationships"):
        st.text(f"Organization: {loc_rels['org_url']}")
        for loc in loc_rels["location_urls"]:
            st.text(f"  └── LocalBusiness: {loc}")

# ─── Generate ────────────────────────────────────────────────────────────────

st.subheader("3. Generate Structured Data")

if not api_key_valid:
    st.warning("Please enter a valid Anthropic API key in the sidebar to continue.")
    st.stop()

if st.button("🚀 Generate JSON-LD", type="primary", use_container_width=True):
    total = len(rows)
    domain = extract_domain(rows[0]["URL"])

    # Phase 1: Homepage
    org_data_text = "No organization data discovered."
    if not skip_org_discovery:
        with st.status("📡 Discovering organization data...", expanded=True):
            homepage_data = fetch_page(domain + "/")
            if homepage_data and homepage_data.get("status") != "error":
                org_data_text = format_page_data_for_prompt(homepage_data)
                st.write(f"✅ Homepage fetched. Business: {homepage_data.get('h1') or homepage_data.get('title', '?')}")
            else:
                st.write("⚠️ Homepage fetch failed — using CSV data only")

    # Phase 2: Fetch pages
    page_data_cache = {}
    if fetch_pages:
        with st.status(f"📄 Fetching {total} pages...", expanded=True):
            progress = st.progress(0)
            for i, row in enumerate(rows):
                url = row["URL"]
                st.write(f"Fetching: {url}")
                page_data_cache[url] = fetch_page(url)
                progress.progress((i + 1) / total)
                time.sleep(0.5)

    # Phase 3: Hierarchy
    hierarchy = build_service_hierarchy(rows)

    def get_hierarchy_text(url):
        info = hierarchy.get(url)
        if not info:
            return "No service hierarchy relationships."
        parts = [f"This service is at depth {info['depth']}."]
        if info["parent"]: parts.append(f"Parent service: {info['parent']}")
        if info["children"]: parts.append(f"Child services: {', '.join(info['children'])}")
        if info["siblings"]: parts.append(f"Sibling services: {', '.join(info['siblings'])}")
        parts.append("\nWire isRelatedTo for parent↔child. Wire isSimilarTo for siblings.")
        parts.append("Only reference URLs that exist in this batch.")
        return "\n".join(parts)

    # Phase 4: Generate
    results = []
    jsonld_blocks = []
    all_defined_ids = set()

    with st.status(f"🤖 Generating JSON-LD for {total} URLs...", expanded=True):
        progress = st.progress(0)
        for i, row in enumerate(rows):
            url = row["URL"]
            schema_type = row["_inferred_type"]
            mode_label = "dual-type" if row["_is_dual"] else "single"
            st.write(f"[{i+1}/{total}] {schema_type} ({mode_label}): {url}")

            page_text = format_page_data_for_prompt(page_data_cache.get(url, {}))
            csv_overrides = get_csv_overrides(row)
            hierarchy_text = get_hierarchy_text(url)

            jsonld_str, error = generate_jsonld_for_row(
                api_key=api_key, schema_type=schema_type, url=url, domain=domain,
                page_data_text=page_text, org_data_text=org_data_text,
                csv_overrides_text=csv_overrides, hierarchy_text=hierarchy_text,
                model=model,
            )

            if error:
                st.write(f"  ⚠️ Error: {error}")
                results.append({
                    "url": url, "type": schema_type, "jsonld": jsonld_str, "error": error,
                    "validation": {"status": "FAIL", "issues": [(0, "FAIL", error)], "auto_fixes": [], "parsed": None},
                })
            else:
                validation = validate_jsonld(jsonld_str, all_defined_ids)
                if validation["parsed"]:
                    parsed = validation["parsed"]
                    if "@graph" in parsed:
                        for entity in parsed["@graph"]:
                            if entity.get("@id"):
                                all_defined_ids.add(entity["@id"])
                    elif parsed.get("@id"):
                        all_defined_ids.add(parsed["@id"])

                icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(validation["status"], "?")
                st.write(f"  {icon} Validation: {validation['status']}")
                results.append({
                    "url": url, "type": schema_type, "jsonld": jsonld_str, "error": "",
                    "validation": validation,
                })
                if validation["parsed"]:
                    jsonld_blocks.append(validation["parsed"])

            progress.progress((i + 1) / total)
            time.sleep(0.3)

    # Phase 5: Graph wiring
    if run_graph_wiring and jsonld_blocks:
        with st.status("🔗 Running graph wiring pass...", expanded=True):
            corrected_blocks, wiring_report = graph_wiring_pass(
                api_key=api_key, all_jsonld_blocks=jsonld_blocks, model=model,
            )
            st.write(wiring_report)
            block_idx = 0
            for result in results:
                if result["validation"]["parsed"] and block_idx < len(corrected_blocks):
                    result["jsonld"] = json.dumps(corrected_blocks[block_idx], indent=2)
                    result["validation"]["parsed"] = corrected_blocks[block_idx]
                    block_idx += 1

    st.session_state["results"] = results
    st.session_state["rows"] = rows
    st.success(f"✅ Generation complete! {total} JSON-LD blocks generated.")

# ─── Results ─────────────────────────────────────────────────────────────────

if "results" in st.session_state:
    results = st.session_state["results"]
    rows = st.session_state["rows"]

    st.divider()
    st.subheader("4. Results")

    passed = sum(1 for r in results if r["validation"]["status"] == "PASS")
    warned = sum(1 for r in results if r["validation"]["status"] == "WARN")
    failed = sum(1 for r in results if r["validation"]["status"] == "FAIL")
    dual_count = sum(1 for r in rows if r.get("_is_dual"))

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(results)}</div><div class="metric-label">Total</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-value status-pass">{passed}</div><div class="metric-label">Passed</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-value status-warn">{warned}</div><div class="metric-label">Warnings</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-value status-fail">{failed}</div><div class="metric-label">Failed</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{dual_count}</div><div class="metric-label">Dual-Type</div></div>', unsafe_allow_html=True)

    st.markdown("")

    for i, (result, row) in enumerate(zip(results, rows)):
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(result["validation"]["status"], "?")
        dual_tag = " [DUAL]" if row.get("_is_dual") else ""
        label = f"{icon} [{result['type']}]{dual_tag} {result['url']}"

        with st.expander(label, expanded=False):
            if result["validation"]["issues"]:
                st.markdown("**Validation Issues:**")
                for rule_num, severity, msg in result["validation"]["issues"]:
                    sev_icon = {"FAIL": "❌", "WARN": "⚠️"}.get(severity, "ℹ️")
                    st.markdown(f"- {sev_icon} Rule {rule_num}: {msg}")

            if result["validation"]["auto_fixes"]:
                st.markdown("**Auto-Fixes:**")
                for fix in result["validation"]["auto_fixes"]:
                    st.markdown(f"- 🔧 {fix}")

            if result["error"]:
                st.error(f"Error: {result['error']}")

            if result["jsonld"]:
                st.markdown("**JSON-LD Output:**")
                st.code(result["jsonld"], language="json")
                wrapped = f'<script type="application/ld+json">\n{result["jsonld"]}\n</script>'
                st.markdown("**With `<script>` wrapper:**")
                st.code(wrapped, language="html")

    # ─── Downloads ───────────────────────────────────────────────────────

    st.divider()
    st.subheader("5. Download Results")

    c1, c2, c3 = st.columns(3)

    with c1:
        csv_rows = []
        for result, row in zip(results, rows):
            csv_rows.append({
                "URL": result["url"],
                "SchemaType": result["type"],
                "Mode": "Dual" if row.get("_is_dual") else "Single",
                "Validation": result["validation"]["status"],
                "Issues": "; ".join(f"Rule {n}: {m}" for n, s, m in result["validation"]["issues"]) or "—",
                "JSON-LD": result["jsonld"],
            })
        csv_df = pd.DataFrame(csv_rows)
        csv_buffer = io.StringIO()
        csv_df.to_csv(csv_buffer, index=False)
        st.download_button("📥 Download CSV", data=csv_buffer.getvalue(),
            file_name="structured_data_output.csv", mime="text/csv", use_container_width=True)

    with c2:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for result, row in zip(results, rows):
                if result["jsonld"]:
                    path = urlparse(result["url"]).path.strip("/")
                    slug = path.replace("/", "-") if path else "homepage"
                    type_prefix = result["type"].lower().replace("|", "-")
                    filename = f"{type_prefix}-{slug}.json"
                    zf.writestr(filename, result["jsonld"])
        st.download_button("📦 Download JSON (ZIP)", data=zip_buffer.getvalue(),
            file_name="structured_data_json_files.zip", mime="application/zip", use_container_width=True)

    with c3:
        val_results = [r["validation"] for r in results]
        report = generate_validation_report(val_results, rows)
        st.download_button("📋 Validation Report", data=report,
            file_name="validation_report.md", mime="text/markdown", use_container_width=True)
