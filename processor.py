"""
Processing pipeline: CSV parsing, URL type inference (single + dual), hierarchy building, web page fetching.
"""

import re
import csv
import io
import json
import requests
from urllib.parse import urlparse
from typing import Optional
from bs4 import BeautifulSoup

from knowledge import URL_TYPE_PATTERNS, VALID_DUAL_TYPES, INVALID_DUAL_TYPES


def parse_csv(file_content):
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(file_content))
    rows = []
    for row in reader:
        cleaned = {k.strip(): v.strip() if v else "" for k, v in row.items()}
        if cleaned.get("URL"):
            rows.append(cleaned)
    return rows


def extract_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def get_url_path(url):
    return urlparse(url).path


def is_dual_type(schema_type):
    """Check if a schema type string represents a dual type (pipe-delimited)."""
    return "|" in schema_type


def parse_dual_type(schema_type):
    """Parse a dual type string into (container_type, nested_type). Returns (type, None) for single."""
    if "|" in schema_type:
        parts = schema_type.split("|", 1)
        return parts[0].strip(), parts[1].strip()
    return schema_type, None


def validate_dual_type(schema_type):
    """Validate a dual-type combination. Returns (is_valid, error_message)."""
    if not is_dual_type(schema_type):
        return True, ""
    if schema_type in VALID_DUAL_TYPES:
        return True, ""
    if schema_type in INVALID_DUAL_TYPES:
        return False, INVALID_DUAL_TYPES[schema_type]
    container, nested = parse_dual_type(schema_type)
    if container == nested:
        return False, "Same type twice"
    if container != "WebContent":
        return False, "Container type must be WebContent for dual-type"
    return True, ""


def infer_schema_type(url):
    """Infer schema type(s) from URL pattern. Returns (type_string, confidence)."""
    path = get_url_path(url).rstrip("/") + "/"
    if path == "/":
        return "Organization", "High"
    for pattern, schema_type, confidence in URL_TYPE_PATTERNS:
        if re.match(pattern, path):
            return schema_type, confidence
    return "WebContent", "Low"


def assign_types(rows):
    """Assign schema types to rows. CSV override takes priority."""
    for row in rows:
        if row.get("SchemaType"):
            raw_type = row["SchemaType"]
            is_valid, error = validate_dual_type(raw_type)
            if is_valid:
                row["_inferred_type"] = raw_type
                row["_type_confidence"] = "Override"
            else:
                row["_inferred_type"] = raw_type
                row["_type_confidence"] = f"Override (INVALID: {error})"
        else:
            inferred, confidence = infer_schema_type(row["URL"])
            row["_inferred_type"] = inferred
            row["_type_confidence"] = confidence
        # Parse dual-type components for display
        container, nested = parse_dual_type(row["_inferred_type"])
        row["_container_type"] = container
        row["_nested_type"] = nested if nested else ""
        row["_is_dual"] = bool(nested)
    return rows


def get_primary_entity_type(row):
    """Get the primary entity type for hierarchy/relationship purposes.
    For dual-type, this is the nested entity (Service, Person, etc.)."""
    if row.get("_is_dual"):
        return row["_nested_type"]
    return row["_inferred_type"]


def build_service_hierarchy(rows):
    """Build parent/child/sibling relationships from service URLs."""
    service_urls = []
    for r in rows:
        primary = get_primary_entity_type(r)
        if primary == "Service":
            service_urls.append(r["URL"])
    if not service_urls:
        return {}

    hierarchy = {}
    for url in service_urls:
        path = get_url_path(url).strip("/")
        segments = [s for s in path.split("/") if s]
        hierarchy[url] = {
            "segments": segments,
            "depth": len(segments),
            "parent": None,
            "children": [],
            "siblings": [],
        }

    for url, info in hierarchy.items():
        for other_url, other_info in hierarchy.items():
            if url == other_url:
                continue
            if (other_info["depth"] == info["depth"] - 1 and
                    get_url_path(url).startswith(get_url_path(other_url).rstrip("/"))):
                info["parent"] = other_url
                other_info["children"].append(url)

    for url, info in hierarchy.items():
        for other_url, other_info in hierarchy.items():
            if url == other_url:
                continue
            if (info["parent"] and info["parent"] == other_info.get("parent")
                    and info["depth"] == other_info["depth"]):
                if other_url not in info["siblings"]:
                    info["siblings"].append(other_url)

    return hierarchy


def build_location_relationships(rows):
    org_url = None
    lb_urls = []
    for r in rows:
        primary = get_primary_entity_type(r)
        if r.get("_inferred_type") == "Organization":
            org_url = r["URL"]
        elif primary == "LocalBusiness":
            lb_urls.append(r["URL"])
    return {"org_url": org_url, "location_urls": lb_urls}


def fetch_page(url, timeout=15):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; StructuredDataBot/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        data = {
            "url": url, "status": resp.status_code, "title": "", "h1": "",
            "meta_description": "", "og_image": "", "og_site_name": "",
            "body_text": "", "phone_numbers": [], "email_addresses": [],
            "social_links": [], "logo_url": "", "existing_jsonld": [],
            "internal_links": [],
        }

        if soup.title:
            data["title"] = soup.title.get_text(strip=True)
        h1 = soup.find("h1")
        if h1:
            data["h1"] = h1.get_text(strip=True)
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            data["meta_description"] = meta["content"].strip()
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            data["og_image"] = og_image["content"]
        og_site = soup.find("meta", attrs={"property": "og:site_name"})
        if og_site and og_site.get("content"):
            data["og_site_name"] = og_site["content"]

        main = soup.find("main") or soup.find("article") or soup.find("body")
        if main:
            text = main.get_text(separator=" ", strip=True)
            data["body_text"] = " ".join(text.split()[:500])

        for a in soup.find_all("a", href=re.compile(r"^tel:")):
            phone = a["href"].replace("tel:", "").strip()
            if phone and phone not in data["phone_numbers"]:
                data["phone_numbers"].append(phone)

        for a in soup.find_all("a", href=re.compile(r"^mailto:")):
            email = a["href"].replace("mailto:", "").strip().split("?")[0]
            if email and email not in data["email_addresses"]:
                data["email_addresses"].append(email)

        social_patterns = [
            "facebook.com", "linkedin.com", "twitter.com", "x.com",
            "youtube.com", "instagram.com", "nextdoor.com", "bbb.org",
            "yelp.com", "mapquest.com",
        ]
        for a in soup.find_all("a", href=True):
            href = a["href"]
            for pattern in social_patterns:
                if pattern in href and href not in data["social_links"]:
                    data["social_links"].append(href)
                    break

        logo = soup.find("link", rel="icon")
        if logo and logo.get("href"):
            data["logo_url"] = logo["href"]
            if not data["logo_url"].startswith("http"):
                data["logo_url"] = extract_domain(url) + data["logo_url"]

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data["existing_jsonld"].append(json.loads(script.string))
            except (json.JSONDecodeError, TypeError):
                pass

        domain = extract_domain(url)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                data["internal_links"].append(domain + href)
            elif href.startswith(domain):
                data["internal_links"].append(href)

        return data
    except requests.RequestException as e:
        return {"url": url, "status": "error", "error": str(e)}


def format_page_data_for_prompt(page_data):
    if not page_data or page_data.get("status") == "error":
        return f"[Page fetch failed: {page_data.get('error', 'unknown error')}]"
    parts = [f"URL: {page_data['url']}"]
    if page_data.get("title"): parts.append(f"Title: {page_data['title']}")
    if page_data.get("h1"): parts.append(f"H1: {page_data['h1']}")
    if page_data.get("meta_description"): parts.append(f"Meta Description: {page_data['meta_description']}")
    if page_data.get("og_site_name"): parts.append(f"Site Name: {page_data['og_site_name']}")
    if page_data.get("og_image"): parts.append(f"OG Image: {page_data['og_image']}")
    if page_data.get("logo_url"): parts.append(f"Logo: {page_data['logo_url']}")
    if page_data.get("phone_numbers"): parts.append(f"Phone: {', '.join(page_data['phone_numbers'])}")
    if page_data.get("email_addresses"): parts.append(f"Email: {', '.join(page_data['email_addresses'])}")
    if page_data.get("social_links"): parts.append(f"Social Links: {', '.join(page_data['social_links'][:10])}")
    if page_data.get("body_text"):
        parts.append(f"Body Text (excerpt): {page_data['body_text'][:2000]}")
    if page_data.get("existing_jsonld"):
        parts.append(f"Existing JSON-LD found: {len(page_data['existing_jsonld'])} block(s)")
    return "\n".join(parts)


def get_csv_overrides(row):
    skip_cols = {"URL", "SchemaType", "_inferred_type", "_type_confidence",
                 "_container_type", "_nested_type", "_is_dual"}
    overrides = []
    for k, v in row.items():
        if k not in skip_cols and v and not k.startswith("_"):
            overrides.append(f"{k}: {v}")
    if overrides:
        return "CSV Override Values:\n" + "\n".join(overrides)
    return "No CSV overrides provided."
