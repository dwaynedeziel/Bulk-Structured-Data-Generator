"""
Embedded knowledge base for structured data generation.
Contains JSON-LD templates, validation rules, Wikidata URIs, and schema rules.
"""

# ─── JSON-LD Templates ───────────────────────────────────────────────────────

TEMPLATES = {
    "Organization": """{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "{{domain}}/#Organization",
  "name": "{{business_name}}",
  "legalName": "{{legal_name}}",
  "description": "{{description_150_300_chars}}",
  "disambiguatingDescription": "{{extended_description}}",
  "url": "{{domain}}/",
  "logo": "{{logo_url}}",
  "image": "{{image_url}}",
  "telephone": "+1{{phone_no_formatting}}",
  "email": "{{email}}",
  "foundingDate": "{{YYYY-MM-DD}}",
  "foundingLocation": { "@id": "{{wikidata_city_uri}}" },
  "numberOfEmployees": "{{number}}",
  "address": {
    "@type": "PostalAddress",
    "@id": "{{domain}}/#PostalAddress",
    "name": "{{business_name}} - Address",
    "streetAddress": "{{street}}",
    "addressLocality": "{{city}}",
    "addressRegion": "{{state_abbrev}}",
    "postalCode": "{{zip}}",
    "addressCountry": {
      "@type": "Country",
      "name": "United States",
      "@id": "http://www.wikidata.org/entity/Q30"
    }
  },
  "location": { "@id": "{{domain}}/#PostalAddress" },
  "areaServed": [],
  "sameAs": [],
  "keywords": [],
  "subOrganization": []
}""",

    "LocalBusiness": """{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "GeoCoordinates",
      "@id": "{{url}}#GeoCoordinates",
      "name": "{{location_name}} Geocoordinates",
      "latitude": "{{latitude}}",
      "longitude": "{{longitude}}"
    },
    {
      "@type": "LocalBusiness",
      "@id": "{{url}}#LocalBusiness",
      "name": "{{business_name}} - {{location_name}}",
      "legalName": "{{legal_name}}",
      "alternateName": "{{alternate_name}}",
      "description": "{{description}}",
      "disambiguatingDescription": "{{extended_description}}",
      "url": "{{url}}",
      "logo": "{{logo_url}}",
      "telephone": "+1{{phone}}",
      "email": "{{email}}",
      "priceRange": "$$",
      "foundingDate": "{{YYYY-MM-DD}}",
      "foundingLocation": { "@id": "{{wikidata_founding_city}}" },
      "numberOfEmployees": "{{number}}",
      "address": {
        "@type": "PostalAddress",
        "@id": "{{url}}#PostalAddress",
        "name": "{{location_name}} Address",
        "streetAddress": "{{street}}",
        "addressLocality": "{{city}}",
        "addressRegion": "{{state}}",
        "postalCode": "{{zip}}",
        "addressCountry": { "@id": "http://www.wikidata.org/entity/Q30" }
      },
      "location": { "@id": "{{url}}#PostalAddress" },
      "geo": { "@id": "{{url}}#GeoCoordinates" },
      "hasMap": "{{google_maps_url}}",
      "parentOrganization": { "@id": "{{domain}}/#Organization" },
      "areaServed": [],
      "openingHoursSpecification": {
        "@type": "OpeningHoursSpecification",
        "@id": "{{url}}#OpeningHoursSpecification",
        "name": "Opening Hours",
        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "opens": "08:00:00",
        "closes": "17:00:00"
      },
      "sameAs": [],
      "keywords": []
    }
  ]
}""",

    "Service": """{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Service",
      "@id": "{{url}}#Service",
      "name": "{{service_name}}",
      "serviceType": "{{service_category}}",
      "description": "{{description}}",
      "disambiguatingDescription": "{{extended_description}}",
      "url": "{{url}}",
      "logo": "{{logo_url}}",
      "provider": { "@id": "{{domain}}/#Organization" },
      "brand": { "@id": "{{domain}}/#Organization" },
      "areaServed": [],
      "sameAs": [],
      "isRelatedTo": [],
      "isSimilarTo": [],
      "hasOfferCatalog": {
        "@type": "OfferCatalog",
        "@id": "{{url}}#OfferCatalog",
        "name": "{{service_name}} Services",
        "itemListElement": []
      }
    }
  ]
}""",

    "WebContent": """{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebContent",
      "@id": "{{url}}#WebContent",
      "headline": "{{h1_title}}",
      "description": "{{description}}",
      "disambiguatingDescription": "{{extended_description}}",
      "url": "{{url}}",
      "image": "{{featured_image_url}}",
      "dateCreated": "{{ISO_datetime}}",
      "dateModified": "{{ISO_datetime}}",
      "datePublished": "{{YYYY-MM-DD}}",
      "about": { "@id": "{{domain}}/#Organization" },
      "creator": { "@id": "{{domain}}/#Organization" },
      "contributor": { "@id": "{{domain}}/#Organization" },
      "maintainer": { "@id": "{{domain}}/#Organization" },
      "contentLocation": { "@id": "{{wikidata_metro_area}}" },
      "locationCreated": { "@id": "{{wikidata_city}}" },
      "countryOfOrigin": { "@id": "http://www.wikidata.org/entity/Q30" },
      "mentions": [],
      "keywords": []
    }
  ]
}""",

    "AboutPage": """{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "AboutPage",
      "@id": "{{url}}#AboutPage",
      "name": "{{page_title}}",
      "description": "{{description}}",
      "url": "{{url}}",
      "about": { "@id": "{{domain}}/#Organization" },
      "mainEntity": { "@id": "{{domain}}/#Organization" }
    }
  ]
}""",

    "Person": """{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Person",
      "@id": "{{url}}#Person",
      "name": "{{full_name}}",
      "givenName": "{{first_name}}",
      "familyName": "{{last_name}}",
      "jobTitle": "{{job_title}}",
      "description": "{{bio_description}}",
      "url": "{{url}}",
      "image": {
        "@type": "ImageObject",
        "url": "{{headshot_url}}",
        "width": 800,
        "height": 800,
        "caption": "{{full_name}}, {{job_title}}"
      },
      "worksFor": { "@id": "{{domain}}/#Organization" },
      "sameAs": [],
      "alumniOf": [],
      "knowsAbout": []
    }
  ]
}"""
}

# ─── Common Wikidata URIs ────────────────────────────────────────────────────

WIKIDATA_COUNTRIES = {
    "United States": "http://www.wikidata.org/entity/Q30",
    "Canada": "http://www.wikidata.org/entity/Q16",
    "United Kingdom": "http://www.wikidata.org/entity/Q145",
    "Mexico": "http://www.wikidata.org/entity/Q96",
}

WIKIDATA_STATES = {
    "Alabama": "http://www.wikidata.org/entity/Q173",
    "Alaska": "http://www.wikidata.org/entity/Q797",
    "Arizona": "http://www.wikidata.org/entity/Q816",
    "Arkansas": "http://www.wikidata.org/entity/Q1612",
    "California": "http://www.wikidata.org/entity/Q99",
    "Colorado": "http://www.wikidata.org/entity/Q1261",
    "Connecticut": "http://www.wikidata.org/entity/Q779",
    "Delaware": "http://www.wikidata.org/entity/Q1393",
    "Florida": "http://www.wikidata.org/entity/Q812",
    "Georgia": "http://www.wikidata.org/entity/Q1428",
    "Hawaii": "http://www.wikidata.org/entity/Q782",
    "Idaho": "http://www.wikidata.org/entity/Q1221",
    "Illinois": "http://www.wikidata.org/entity/Q1204",
    "Indiana": "http://www.wikidata.org/entity/Q1415",
    "Iowa": "http://www.wikidata.org/entity/Q1546",
    "Kansas": "http://www.wikidata.org/entity/Q1558",
    "Kentucky": "http://www.wikidata.org/entity/Q1603",
    "Louisiana": "http://www.wikidata.org/entity/Q1588",
    "Maine": "http://www.wikidata.org/entity/Q724",
    "Maryland": "http://www.wikidata.org/entity/Q1391",
    "Massachusetts": "http://www.wikidata.org/entity/Q771",
    "Michigan": "http://www.wikidata.org/entity/Q1166",
    "Minnesota": "http://www.wikidata.org/entity/Q1527",
    "Mississippi": "http://www.wikidata.org/entity/Q1494",
    "Missouri": "http://www.wikidata.org/entity/Q1581",
    "Montana": "http://www.wikidata.org/entity/Q1212",
    "Nebraska": "http://www.wikidata.org/entity/Q1553",
    "Nevada": "http://www.wikidata.org/entity/Q1227",
    "New Hampshire": "http://www.wikidata.org/entity/Q759",
    "New Jersey": "http://www.wikidata.org/entity/Q1408",
    "New Mexico": "http://www.wikidata.org/entity/Q1522",
    "New York": "http://www.wikidata.org/entity/Q1384",
    "North Carolina": "http://www.wikidata.org/entity/Q1454",
    "North Dakota": "http://www.wikidata.org/entity/Q1207",
    "Ohio": "http://www.wikidata.org/entity/Q1397",
    "Oklahoma": "http://www.wikidata.org/entity/Q1649",
    "Oregon": "http://www.wikidata.org/entity/Q824",
    "Pennsylvania": "http://www.wikidata.org/entity/Q1400",
    "Rhode Island": "http://www.wikidata.org/entity/Q1387",
    "South Carolina": "http://www.wikidata.org/entity/Q1456",
    "South Dakota": "http://www.wikidata.org/entity/Q1211",
    "Tennessee": "http://www.wikidata.org/entity/Q1509",
    "Texas": "http://www.wikidata.org/entity/Q1439",
    "Utah": "http://www.wikidata.org/entity/Q829",
    "Vermont": "http://www.wikidata.org/entity/Q16551",
    "Virginia": "http://www.wikidata.org/entity/Q1370",
    "Washington": "http://www.wikidata.org/entity/Q1223",
    "West Virginia": "http://www.wikidata.org/entity/Q1371",
    "Wisconsin": "http://www.wikidata.org/entity/Q1537",
    "Wyoming": "http://www.wikidata.org/entity/Q1214",
}

WIKIDATA_CITIES = {
    "New York City, NY": "http://www.wikidata.org/entity/Q60",
    "Los Angeles, CA": "http://www.wikidata.org/entity/Q65",
    "Chicago, IL": "http://www.wikidata.org/entity/Q1297",
    "Houston, TX": "http://www.wikidata.org/entity/Q16555",
    "Phoenix, AZ": "http://www.wikidata.org/entity/Q16556",
    "Philadelphia, PA": "http://www.wikidata.org/entity/Q1345",
    "San Antonio, TX": "http://www.wikidata.org/entity/Q975",
    "San Diego, CA": "http://www.wikidata.org/entity/Q16552",
    "Dallas, TX": "http://www.wikidata.org/entity/Q16557",
    "San Jose, CA": "http://www.wikidata.org/entity/Q16553",
    "Austin, TX": "http://www.wikidata.org/entity/Q16559",
    "Jacksonville, FL": "http://www.wikidata.org/entity/Q16568",
    "San Francisco, CA": "http://www.wikidata.org/entity/Q62",
    "Seattle, WA": "http://www.wikidata.org/entity/Q5083",
    "Denver, CO": "http://www.wikidata.org/entity/Q16554",
    "Boston, MA": "http://www.wikidata.org/entity/Q100",
    "Detroit, MI": "http://www.wikidata.org/entity/Q12439",
    "Miami, FL": "http://www.wikidata.org/entity/Q8652",
    "Atlanta, GA": "http://www.wikidata.org/entity/Q23556",
    "Minneapolis, MN": "http://www.wikidata.org/entity/Q36091",
}

WIKIDATA_SERVICE_CONCEPTS = {
    "Water damage": "http://www.wikidata.org/entity/Q929023",
    "Fire": "http://www.wikidata.org/entity/Q3196",
    "Mold": "http://www.wikidata.org/entity/Q37212",
    "Plumbing": "http://www.wikidata.org/entity/Q165029",
    "HVAC": "http://www.wikidata.org/entity/Q166111",
    "Roofing": "http://www.wikidata.org/entity/Q190928",
    "Kitchen remodeling": "http://www.wikidata.org/entity/Q11406",
    "Construction": "http://www.wikidata.org/entity/Q385378",
    "Restoration": "http://www.wikidata.org/entity/Q217845",
    "Cleaning": "http://www.wikidata.org/entity/Q507166",
}

# ─── URL Pattern → Type Inference ────────────────────────────────────────────

URL_TYPE_PATTERNS = [
    (r"^/$", "Organization", "High"),
    (r"^/about/?$", "AboutPage", "High"),
    (r"^/about-us/?$", "AboutPage", "High"),
    (r"^/about/team/[^/]+/?$", "Person", "High"),
    (r"^/team/[^/]+/?$", "Person", "High"),
    (r"^/locations/[^/]+/?$", "LocalBusiness", "High"),
    (r"^/contact/[^/]+/?$", "LocalBusiness", "High"),
    (r"^/services/?$", "Service", "High"),
    (r"^/services/.+/?$", "Service", "High"),
    (r"^/solutions/.+/?$", "Service", "High"),
    (r"^/blog/.+/?$", "WebContent", "Medium"),
    (r"^/news/.+/?$", "WebContent", "Medium"),
    (r"^/industries/.+/?$", "WebContent", "Medium"),
    (r"^/areas-we-serve/.+/?$", "WebContent", "Medium"),
]

# ─── Deprecated Types & Properties ───────────────────────────────────────────

DEPRECATED_TYPES = {
    "WebPage": "Do not use - implied by URL. Use WebContent for content pages",
    "WebSite": "Do not use - implied by domain",
}

DEPRECATED_PROPERTIES = {
    "serviceArea": "areaServed",
    "significantLink": "relatedLink or remove",
    "significantLinks": "relatedLink or remove",
    "isBasedOnUrl": "isBasedOn",
}

# ─── Property-Type Restrictions ──────────────────────────────────────────────

# Properties that are NOT valid on certain types
INVALID_PROPERTIES = {
    "Service": ["keywords", "email", "telephone", "address", "foundingDate"],
    "Person": ["keywords", "logo"],
}

# Properties that ARE valid on each type
VALID_PROPERTIES = {
    "Service": [
        "name", "description", "disambiguatingDescription", "url", "sameAs",
        "image", "logo", "provider", "brand", "areaServed", "isRelatedTo",
        "isSimilarTo", "serviceType", "hasOfferCatalog", "offers",
    ],
    "Organization": [
        "name", "legalName", "description", "disambiguatingDescription", "url",
        "logo", "image", "telephone", "email", "sameAs", "keywords",
        "foundingDate", "foundingLocation", "numberOfEmployees", "address",
        "location", "areaServed", "subOrganization", "alternateName",
    ],
    "LocalBusiness": [
        "name", "legalName", "description", "disambiguatingDescription", "url",
        "logo", "image", "telephone", "email", "sameAs", "keywords",
        "foundingDate", "foundingLocation", "numberOfEmployees", "address",
        "location", "areaServed", "parentOrganization", "geo", "hasMap",
        "openingHoursSpecification", "priceRange", "alternateName",
    ],
    "WebContent": [
        "headline", "description", "disambiguatingDescription", "url", "image",
        "dateCreated", "dateModified", "datePublished", "about", "creator",
        "contributor", "maintainer", "contentLocation", "locationCreated",
        "countryOfOrigin", "mentions", "keywords", "sameAs",
    ],
    "AboutPage": [
        "name", "description", "url", "about", "mainEntity",
    ],
    "Person": [
        "name", "givenName", "familyName", "jobTitle", "description", "url",
        "image", "worksFor", "sameAs", "alumniOf", "knowsAbout",
    ],
}
