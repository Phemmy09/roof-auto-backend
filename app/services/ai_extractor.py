"""
AI extraction service.
Uploads PDFs to Claude Files API and extracts structured data per document type.
"""
import json
import re
import anthropic
from app.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

MODEL = "claude-opus-4-6"
BETA = ["files-api-2025-04-14"]

# ── Extraction prompts per document type ─────────────────────────────────────

PROMPTS = {
    "eagle_view": """You are analyzing an EagleView Precise Aerial Roof Measurement Report.
Extract ALL measurements and return ONLY a valid JSON object with these exact fields:

{
  "total_area_sqft": <number>,
  "total_squares": <number, area/100>,
  "roof_facets": <integer>,
  "predominant_pitch": "<string e.g. '4/12'>",
  "pitch_num": <number, the rise value e.g. 4>,
  "ridges_ft": <number>,
  "hips_ft": <number>,
  "valleys_ft": <number>,
  "rakes_ft": <number>,
  "eaves_ft": <number>,
  "flashing_ft": <number>,
  "step_flashing_ft": <number>,
  "drip_edge_ft": <number, eaves+rakes>,
  "obstructions_count": <integer>,
  "obstructions_perimeter_ft": <number>,
  "obstructions_area_sqft": <number>,
  "suggested_waste_pct": <number>,
  "squares_at_waste": <number, at suggested waste>,
  "stories": "<string>",
  "address": "<string>",
  "report_date": "<string>",
  "areas_by_pitch": [{"pitch": "<string>", "area_sqft": <number>, "pct": <number>}]
}

Use 0 for any field not found. Return ONLY the JSON object, no other text.""",

    "insurance": """You are analyzing a roofing insurance claim / scope of work document.
Extract all information and return ONLY a valid JSON object:

{
  "carrier": "<insurance company name>",
  "claim_number": "<string>",
  "policy_number": "<string>",
  "insured_name": "<string>",
  "property_address": "<string>",
  "claim_date": "<string>",
  "deductible": <number>,
  "rcv_total": <number>,
  "acv_total": <number>,
  "depreciation": <number>,
  "scope_type": "<Full Replacement|Partial|Repair>",
  "approved_line_items": [
    {"description": "<string>", "quantity": <number>, "unit": "<string>", "unit_price": <number>, "total": <number>}
  ],
  "roofing_items": [
    {"description": "<string>", "quantity": <number>, "unit": "<string>", "total": <number>}
  ],
  "supplements": ["<string>"],
  "exclusions": ["<string>"],
  "notes": "<string>"
}

Use null for missing strings, 0 for missing numbers, [] for missing arrays.
Return ONLY the JSON object.""",

    "contract": """You are analyzing a roofing contract or work agreement.
Extract all information and return ONLY a valid JSON object:

{
  "customer_name": "<string>",
  "property_address": "<string>",
  "contract_date": "<string>",
  "contract_value": <number>,
  "scope_of_work": "<string>",
  "shingle_brand": "<string>",
  "shingle_color": "<string>",
  "shingle_type": "<string e.g. Architectural, 3-Tab>",
  "include_gutters": <boolean>,
  "include_skylights": <boolean>,
  "special_requirements": ["<string>"],
  "warranty_info": "<string>",
  "notes": "<string>"
}

Return ONLY the JSON object.""",

    "city_code": """You are analyzing roofing permit and city/county code documents.
Extract all requirements and return ONLY a valid JSON object:

{
  "jurisdiction": "<city/county name>",
  "permit_required": <boolean>,
  "permit_number": "<string or null>",
  "code_requirements": ["<string>"],
  "fastener_requirements": "<string>",
  "underlayment_requirements": "<string>",
  "ice_water_requirements": "<string>",
  "ventilation_requirements": "<string>",
  "decking_requirements": "<string>",
  "inspection_required": <boolean>,
  "inspection_types": ["<string>"],
  "special_conditions": ["<string>"],
  "notes": "<string>"
}

Return ONLY the JSON object.""",

    "photos": """You are analyzing roofing job photos. Carefully examine every image and identify all roof features.
Count each item carefully and return ONLY a valid JSON object:

{
  "skylights_count": <integer>,
  "skylight_details": ["<description per skylight>"],
  "chimneys_count": <integer>,
  "chimney_details": ["<material/size per chimney>"],
  "pipe_boots_count": <integer>,
  "pipe_boot_sizes": ["<size: 1.5in|2in|3in|4in|lead>"],
  "vents_count": <integer>,
  "vent_types": ["<type: ridge|box|turbine|soffit|power>"],
  "satellite_dishes_count": <integer>,
  "existing_layers_count": <integer>,
  "current_material": "<3-tab|architectural|wood shake|metal|tile|other>",
  "decking_visible_damage": <boolean>,
  "decking_notes": "<string>",
  "overall_condition": "<poor|fair|good>",
  "special_observations": ["<string>"]
}

Return ONLY the JSON object.""",
}


def _parse_json_response(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code block if present
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        # Find first { to last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]
    return json.loads(text)


def extract_document(file_bytes: bytes, filename: str, doc_type: str) -> dict:
    """
    Upload PDF to Claude Files API and extract structured data.
    Returns the extracted data dict.
    """
    if doc_type not in PROMPTS:
        return {"error": f"Unknown doc_type: {doc_type}"}

    # Upload to Claude Files API
    file_obj = client.beta.files.upload(
        file=(filename, file_bytes, "application/pdf"),
    )
    file_id = file_obj.id

    try:
        prompt = PROMPTS[doc_type]

        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            betas=BETA,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {"type": "file", "file_id": file_id},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        # Find the text block in response
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        return _parse_json_response(text)

    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": text[:500]}
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Clean up the uploaded file from Claude
        try:
            client.beta.files.delete(file_id)
        except Exception:
            pass


def merge_extracted_data(documents: list[dict]) -> dict:
    """
    Merge extracted data from all documents into a single measurements dict
    used by the formula engine.
    """
    merged = {
        # Measurements (from Eagle View)
        "total_area_sqft": 0.0,
        "total_squares": 0.0,
        "squares_at_waste": 0.0,
        "suggested_waste_pct": 10.0,
        "roof_facets": 0,
        "predominant_pitch": "4/12",
        "pitch_num": 4.0,
        "ridges_ft": 0.0,
        "hips_ft": 0.0,
        "valleys_ft": 0.0,
        "rakes_ft": 0.0,
        "eaves_ft": 0.0,
        "flashing_ft": 0.0,
        "step_flashing_ft": 0.0,
        "drip_edge_ft": 0.0,
        "obstructions_count": 0,
        # From photos
        "skylights_count": 0,
        "chimneys_count": 0,
        "pipe_boots_count": 0,
        "pipe_boot_sizes": [],
        "vents_count": 0,
        "vent_types": [],
        "satellite_dishes_count": 0,
        "existing_layers_count": 1,
        "current_material": "",
        # From contract
        "shingle_brand": "",
        "shingle_color": "",
        "shingle_type": "Architectural",
        # From insurance
        "carrier": "",
        "claim_number": "",
        "deductible": 0.0,
        "scope_type": "",
        # From city code
        "permit_required": False,
        "jurisdiction": "",
        "code_requirements": [],
        "address": "",
        "customer_name": "",
    }

    for doc in documents:
        dtype = doc.get("doc_type")
        data = doc.get("extracted_data", {})
        if not data or "error" in data:
            continue

        if dtype == "eagle_view":
            for field in [
                "total_area_sqft", "total_squares", "squares_at_waste",
                "suggested_waste_pct", "roof_facets", "predominant_pitch",
                "pitch_num", "ridges_ft", "hips_ft", "valleys_ft", "rakes_ft",
                "eaves_ft", "flashing_ft", "step_flashing_ft", "drip_edge_ft",
                "obstructions_count",
            ]:
                if data.get(field) is not None:
                    merged[field] = data[field]
            if data.get("address"):
                merged["address"] = data["address"]

        elif dtype == "photos":
            for field in [
                "skylights_count", "chimneys_count", "pipe_boots_count",
                "pipe_boot_sizes", "vents_count", "vent_types",
                "satellite_dishes_count", "existing_layers_count", "current_material",
            ]:
                if data.get(field) is not None:
                    merged[field] = data[field]

        elif dtype == "contract":
            for field in ["shingle_brand", "shingle_color", "shingle_type", "address"]:
                if data.get(field):
                    merged[field] = data[field]
            if data.get("customer_name"):
                merged["customer_name"] = data["customer_name"]
            if data.get("property_address"):
                merged["address"] = data["property_address"]

        elif dtype == "insurance":
            for field in ["carrier", "claim_number", "deductible", "scope_type"]:
                if data.get(field) is not None:
                    merged[field] = data[field]
            if data.get("insured_name"):
                merged["customer_name"] = data["insured_name"]
            if data.get("property_address"):
                merged["address"] = data["property_address"]

        elif dtype == "city_code":
            for field in ["permit_required", "jurisdiction", "code_requirements"]:
                if data.get(field) is not None:
                    merged[field] = data[field]

    # Derive drip_edge_ft if not already set
    if merged["drip_edge_ft"] == 0 and (merged["eaves_ft"] or merged["rakes_ft"]):
        merged["drip_edge_ft"] = merged["eaves_ft"] + merged["rakes_ft"]

    # Default squares_at_waste from total_squares if not set
    if merged["squares_at_waste"] == 0 and merged["total_squares"] > 0:
        waste = merged["suggested_waste_pct"] / 100
        merged["squares_at_waste"] = round(merged["total_squares"] * (1 + waste), 2)

    return merged


def build_crew_order(merged: dict, documents: list[dict]) -> dict:
    """Build the initial crew order form from merged extracted data."""
    # Get insurance line items
    insurance_scope = ""
    insurance_items = []
    for doc in documents:
        if doc.get("doc_type") == "insurance":
            d = doc.get("extracted_data", {})
            insurance_scope = d.get("scope_type", "")
            insurance_items = d.get("roofing_items", []) or d.get("approved_line_items", [])
            break

    # Get city code notes
    code_notes = []
    for doc in documents:
        if doc.get("doc_type") == "city_code":
            d = doc.get("extracted_data", {})
            code_notes = d.get("code_requirements", [])
            break

    # Special features from photos
    special_features = []
    if merged["skylights_count"] > 0:
        special_features.append(f"Skylights: {merged['skylights_count']}")
    if merged["chimneys_count"] > 0:
        special_features.append(f"Chimneys: {merged['chimneys_count']}")
    if merged["pipe_boots_count"] > 0:
        sizes = ", ".join(merged.get("pipe_boot_sizes", []))
        special_features.append(
            f"Pipe Boots: {merged['pipe_boots_count']}" + (f" ({sizes})" if sizes else "")
        )
    if merged["vents_count"] > 0:
        vtypes = ", ".join(merged.get("vent_types", []))
        special_features.append(
            f"Vents: {merged['vents_count']}" + (f" ({vtypes})" if vtypes else "")
        )
    if merged["satellite_dishes_count"] > 0:
        special_features.append(f"Satellite Dishes: {merged['satellite_dishes_count']}")

    return {
        "customer_name": merged.get("customer_name", ""),
        "address": merged.get("address", ""),
        "scheduled_date": "",
        "target_completion": "",
        "measurements": {
            "total_squares": merged["total_squares"],
            "squares_at_waste": merged["squares_at_waste"],
            "predominant_pitch": merged["predominant_pitch"],
            "roof_facets": merged["roof_facets"],
            "existing_layers": merged["existing_layers_count"],
            "current_material": merged["current_material"],
            "ridges_ft": merged["ridges_ft"],
            "hips_ft": merged["hips_ft"],
            "valleys_ft": merged["valleys_ft"],
            "eaves_ft": merged["eaves_ft"],
            "rakes_ft": merged["rakes_ft"],
        },
        "scope_of_work": insurance_scope or "Full Replacement",
        "shingle_brand": merged.get("shingle_brand", ""),
        "shingle_color": merged.get("shingle_color", ""),
        "shingle_type": merged.get("shingle_type", "Architectural"),
        "special_features": special_features,
        "insurance": {
            "carrier": merged.get("carrier", ""),
            "claim_number": merged.get("claim_number", ""),
            "deductible": merged.get("deductible", 0),
        },
        "city_code": {
            "jurisdiction": merged.get("jurisdiction", ""),
            "permit_required": merged.get("permit_required", False),
            "requirements": code_notes,
        },
        "crew_lead": "",
        "crew_size": "",
        "equipment_notes": "",
        "special_instructions": "",
        "safety_notes": "",
    }
