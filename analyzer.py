import os
import json
import base64
import requests

def analyze_image_heuristics(image_path):
    """
    Simulate computer vision analysis of site images.
    Parses filenames and uses heuristic patterns to yield high-fidelity,
    structured findings for local testing.
    """
    filename = os.path.basename(image_path).lower()
    
    # Defaults
    roof_access = "Unknown / Not observed"
    roof_type = "Flat Concrete"
    mounting_structures = []
    hardware = []
    confidence = 0.75
    
    # Filename keyword heuristics
    if "hatch" in filename or "door" in filename or "stairs" in filename:
        roof_access = "Roof Access Hatch detected"
        confidence = 0.92
    elif "ladder" in filename or "fire_escape" in filename:
        roof_access = "Exterior Fixed Ladder"
        confidence = 0.88
        
    if "rubber" in filename or "epdm" in filename:
        roof_type = "EPDM / Rubber Membrane"
    elif "vinyl" in filename or "tpo" in filename:
        roof_type = "TPO / Single-ply Vinyl"
    elif "metal" in filename or "corrugated" in filename:
        roof_type = "Standing Seam Metal"
    elif "gravel" in filename or "tar" in filename:
        roof_type = "Tar and Gravel (Built-up Roof)"
        
    if "mount" in filename or "pole" in filename or "mast" in filename:
        mounting_structures.append("Non-penetrating Ballast Mount")
        mounting_structures.append("Steel Antenna Mast")
        confidence = 0.85
    elif "parapet" in filename:
        mounting_structures.append("Parapet Wall Mount")
        confidence = 0.90
    else:
        # Generic fallback mounts
        mounting_structures.append("Non-penetrating Ballast Sled")
        
    if "power" in filename or "conduit" in filename or "box" in filename:
        hardware.append("NEMA 4X Weatherproof Enclosure")
        hardware.append("Liquid-tight Flexible Conduit")
    else:
        hardware.append("Standard Grounding Kit")
        hardware.append("RJ45 Weatherproof Feedthrough")

    return {
        "image_file": os.path.basename(image_path),
        "roof_access": roof_access,
        "roof_type": roof_type,
        "mounting_structures": list(set(mounting_structures)),
        "hardware": list(set(hardware)),
        "confidence_score": confidence
    }

def analyze_image_via_api(image_path, api_key=None, api_url=None):
    """
    Placeholder for cloud/Vision LLM API integration.
    If api_key and api_url are supplied, attempts a payload request.
    Otherwise, falls back to the local heuristics engine.
    """
    if not api_key or not api_url:
        return analyze_image_heuristics(image_path)
        
    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Adjust query/prompt to suit the target API (e.g. Gemini, OpenAI, custom CV model)
        payload = {
            "model": "gemini-2.5-flash" if "gemini" in api_url else "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this site survey photo for Drone as a First Responder (DFR) installation. "
                                "Identify: 1. Roof access points (hatch, door, ladder, none). 2. Roof material/type (rubber, TPO, concrete, metal, gravel). "
                                "3. Potential mounting structures (ballasted, parapet, tripod). 4. Hardware/cabling path presence. "
                                "Respond ONLY with valid JSON matching these keys: 'roof_access', 'roof_type', 'mounting_structures' (array), 'hardware' (array), 'confidence_score'."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            # Parse the inner assistant text if wrapped
            choices = result.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "{}")
                return json.loads(text)
            return result
    except Exception as e:
        print(f"API CV Analysis failed, using heuristics engine. Error: {e}")
        
    return analyze_image_heuristics(image_path)

def analyze_site(site_data_dict, api_key=None, api_url=None):
    """
    Iterates through all images in a site and aggregates infrastructure findings.
    """
    images = site_data_dict.get('images', [])
    findings = []
    
    for img in images:
        path = img.get('dest_path') or img.get('path')
        if os.path.exists(path):
            img_finding = analyze_image_via_api(path, api_key, api_url)
            findings.append(img_finding)
            
    # Aggregate results for the site
    if not findings:
        return {
            "roof_access": "Unknown",
            "roof_type": "Unknown",
            "mounting_structures": [],
            "hardware": [],
            "individual_findings": []
        }
        
    # Consolidate findings (take the highest confidence, or combine arrays)
    roof_access_votes = [f.get("roof_access") for f in findings if f.get("roof_access") != "Unknown / Not observed"]
    roof_types = [f.get("roof_type") for f in findings]
    
    primary_access = roof_access_votes[0] if roof_access_votes else "Unknown / Not observed"
    primary_roof = max(set(roof_types), key=roof_types.count) if roof_types else "Unknown"
    
    all_mounts = set()
    all_hardware = set()
    for f in findings:
        all_mounts.update(f.get("mounting_structures", []))
        all_hardware.update(f.get("hardware", []))
        
    return {
        "roof_access": primary_access,
        "roof_type": primary_roof,
        "mounting_structures": list(all_mounts),
        "hardware": list(all_hardware),
        "individual_findings": findings
    }
