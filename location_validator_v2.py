# ============================================================
#  location_validator.py — Prevents LLM from hallucinating locations
#  
#  This file contains EVERY valid location in Pokemon Unbound.
#  If the LLM mentions a location not on this list, it's a hallucination.
#
#  VERSION 2 - Fixed regex patterns for better accuracy
# ============================================================

# ALL valid towns and cities in Pokemon Unbound (verified from unboundwiki.com)
VALID_TOWNS = {
    "Frozen Heights",
    "Bellin Town",
    "Dresco Town",
    "Crater Town",
    "Blizzard City",
    "Tehl Town",
    "Fallshore City",
    "Epidimy Town",
    "Tarmigan Town",
    "Dehara City",
    "Gurun Town",
    "Vivill Town",
    "Antisis City",
    "Seaport City",
    "Polder Town",
    "Magnolia Town",
    "Redwood Village",
}

# ALL valid routes in Pokemon Unbound (Routes 1-18 only)
VALID_ROUTES = {
    "Route 1", "Route 2", "Route 3", "Route 4", "Route 5", "Route 6",
    "Route 7", "Route 8", "Route 9", "Route 10", "Route 11", "Route 12",
    "Route 13", "Route 14", "Route 15", "Route 16", "Route 17", "Route 18",
}

# Other valid areas (caves, buildings, special locations)
VALID_AREAS = {
    "Shadow Base",
    "Icicle Cave",
    "Grim Woods",
    "Cinder Volcano",
    "Pokemon Day Care",
    "KBT Expressway",
    "Valley Cave",
    "Frost Mountain",
    "Frozen Forest",
    "Underground Pass",
    "Thundercap Mountain",
    "Cliff Cave",
    "Tarmigan Mansion",
    "Great Desert",
    "Auburn Waterway",
    "Lost Tunnel",
    "Ruins of Void",
    "Vivill Woods",
    "Vivill Warehouse",
    "Antisis Port",
    "Antisis Sewers",
    "Safari Zone",
    "Cootes Bog",
    "Magnolia Fields",
    "Redwood Forest",
    "Cube Corp",
    "Crystal Peak",
    "Victory Road",
    "Pokemon League",
    "Battle Frontier",
    "Battle Tower",
    "Icy Hole",
    "Path Connector",
    "Flower Paradise",
    "Dehara Dept",
    "Pokemon Center",
    "Trainer House",
}

# Combine all valid locations
ALL_VALID_LOCATIONS = VALID_TOWNS | VALID_ROUTES | VALID_AREAS


def is_valid_location(location_name: str) -> bool:
    """
    Check if a location name is valid in Pokemon Unbound.
    
    Returns True if the location exists, False if it's hallucinated.
    Case-insensitive matching.
    """
    if not location_name:
        return False
    
    # Exact match (case-insensitive)
    for valid_loc in ALL_VALID_LOCATIONS:
        if location_name.lower() == valid_loc.lower():
            return True
    
    # Partial match for common patterns
    # Example: "Route 5" vs "Roue 5" (typo in map_lookup.json)
    if "route" in location_name.lower():
        # Extract number from "Route X" or "Route-X" or "RouteX"
        import re
        match = re.search(r'route[- ]?(\d+)', location_name.lower())
        if match:
            route_num = int(match.group(1))
            if 1 <= route_num <= 18:
                return True
    
    return False


def validate_llm_response(response: str) -> tuple[bool, list[str]]:
    """
    Scan an LLM response for location names and validate them.
    
    Returns:
        (all_valid, hallucinated_locations)
        
    Example:
        valid, fakes = validate_llm_response("Navigate to Dresco Town")
        if not valid:
            print(f"LLM hallucinated: {fakes}")
    """
    import re
    
    hallucinated = []
    
    # Pattern 1: <<FLY:Destination>> - Most critical!
    fly_pattern = r'<<FLY:([^>]+)>>'
    fly_matches = re.findall(fly_pattern, response)
    for dest in fly_matches:
        dest = dest.strip()
        if dest and not is_valid_location(dest):
            hallucinated.append(f"<<FLY:{dest}>>")
    
    # Pattern 2: Route numbers that are too high
    route_matches = re.findall(r'\bRoute[- ]?(\d+)\b', response, re.IGNORECASE)
    for route_num in route_matches:
        if int(route_num) > 18:
            hallucinated.append(f"Route {route_num}")
    
    # Pattern 3: Specific navigation commands - IMPROVED REGEX
    # Only capture the location name itself, not extra words
    nav_patterns = [
        r'(?:navigate|go|fly|head|travel)\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:\s+and|\s+to|\.|,|$)',
        r'(?:from|at|in|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:\s+and|\s+to|\.|,|$)',
    ]
    
    for pattern in nav_patterns:
        matches = re.findall(pattern, response)
        for match in matches:
            match = match.strip()
            # Check if it looks like a location (ends with Town/City/etc or is 2-3 words)
            if match and not is_valid_location(match):
                # Only flag if it actually looks like a place name
                if any(keyword in match for keyword in ['Town', 'City', 'Village', 'Cave', 
                                                          'Mountain', 'Forest', 'Woods', 
                                                          'Desert', 'Peak', 'Base', 'Heights']):
                    hallucinated.append(match)
    
    # Pattern 4: Standalone location-like words (Town, City, etc.)
    # IMPROVED: Only match complete location patterns, not partial phrases
    location_pattern = r'\b([A-Z][a-z]+\s+(?:Town|City|Village|Heights))\b'
    possible_locations = re.findall(location_pattern, response)
    for loc in possible_locations:
        loc = loc.strip()
        if loc and not is_valid_location(loc):
            hallucinated.append(loc)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_hallucinated = []
    for item in hallucinated:
        if item not in seen:
            seen.add(item)
            unique_hallucinated.append(item)
    
    all_valid = len(unique_hallucinated) == 0
    return all_valid, unique_hallucinated


def get_suggestion(hallucinated_name: str) -> str:
    """
    Suggest a real location that's similar to the hallucinated one.
    Uses simple string similarity.
    """
    from difflib import get_close_matches
    
    # Clean up the input (remove <<FLY:>> wrapper if present)
    clean_name = hallucinated_name.replace('<<FLY:', '').replace('>>', '').strip()
    
    matches = get_close_matches(
        clean_name.lower(), 
        [loc.lower() for loc in ALL_VALID_LOCATIONS],
        n=1,
        cutoff=0.6
    )
    
    if matches:
        # Find the original case version
        for loc in ALL_VALID_LOCATIONS:
            if loc.lower() == matches[0]:
                return loc
    
    return "Unknown (no similar location found)"


# ============================================================
# TESTING - Run this file directly to test the validator
# ============================================================

if __name__ == "__main__":
    print("🔍 Testing Location Validator v2 (FIXED)\n")
    
    # Test valid locations
    print("=== Testing VALID locations ===")
    test_valid = [
        "Dresco Town",
        "Route 5",
        "Dehara City",
        "Crystal Peak",
        "Tarmigan Mansion",
    ]
    
    for loc in test_valid:
        result = is_valid_location(loc)
        print(f"  {loc}: {'✅ VALID' if result else '❌ INVALID'}")
    
    # Test fake locations
    print("\n=== Testing FAKE locations ===")
    test_fake = [
        "Vermillion City",
        "Pallet Town",
        "Route 25",
        "Mystic Grove",
        "Silverleaf Town",
    ]
    
    for loc in test_fake:
        result = is_valid_location(loc)
        print(f"  {loc}: {'✅ VALID' if result else '❌ INVALID (correctly rejected!)'}")
    
    # Test LLM responses - THESE SHOULD NOW WORK CORRECTLY
    print("\n=== Testing LLM Response Validation (FIXED) ===")
    
    test_responses = [
        "Navigate to Dresco Town and heal at the Pokemon Center. <<FLY:Dresco Town>>",
        "Go to Vermillion City and challenge the gym leader. <<FLY:Vermillion City>>",
        "Head north to Route 5, then continue to Mystic Grove.",
        "Take Route 25 east to reach Silverleaf Town.",
        "I'll fly to Fallshore City now. <<FLY:Fallshore City>>",
        "Let's go to Crystal Peak and catch some Pokemon. <<FLY:Crystal Peak>>",
        "Navigate to Pallet Town. <<FLY:Pallet Town>>",
    ]
    
    for i, response in enumerate(test_responses, 1):
        valid, fakes = validate_llm_response(response)
        print(f"\n  Response {i}:")
        print(f"    \"{response[:70]}{'...' if len(response) > 70 else ''}\"")
        if valid:
            print(f"    ✅ ALL LOCATIONS VALID")
        else:
            print(f"    ❌ HALLUCINATIONS DETECTED:")
            for fake in fakes:
                suggestion = get_suggestion(fake)
                print(f"       - '{fake}' (did you mean '{suggestion}'?)")
    
    print("\n✅ Validator test complete!")
    print("\nℹ️  The validator is now integrated into agent.py and will automatically")
    print("   reject any LLM responses that contain hallucinated locations.")
