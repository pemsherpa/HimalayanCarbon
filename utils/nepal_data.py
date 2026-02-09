"""
Nepal Districts Data
Contains coordinates for all 77 districts of Nepal for easy location selection
"""

# Nepal center coordinates
NEPAL_CENTER = {
    'lat': 28.3949,
    'lon': 84.1240,
    'zoom': 7
}

# Dictionary of Nepal districts with their approximate center coordinates
# Organized by province
NEPAL_DISTRICTS = {
    # Province 1 (Koshi)
    "Bhojpur": {"lat": 27.1767, "lon": 87.0508},
    "Dhankuta": {"lat": 26.9826, "lon": 87.3469},
    "Ilam": {"lat": 26.9093, "lon": 87.9264},
    "Jhapa": {"lat": 26.5455, "lon": 87.8942},
    "Khotang": {"lat": 27.0217, "lon": 86.8425},
    "Morang": {"lat": 26.6650, "lon": 87.4628},
    "Okhaldhunga": {"lat": 27.3145, "lon": 86.5006},
    "Panchthar": {"lat": 27.1321, "lon": 87.7567},
    "Sankhuwasabha": {"lat": 27.3517, "lon": 87.2017},
    "Solukhumbu": {"lat": 27.7909, "lon": 86.6617},
    "Sunsari": {"lat": 26.6544, "lon": 87.1780},
    "Taplejung": {"lat": 27.3512, "lon": 87.6698},
    "Terhathum": {"lat": 27.1267, "lon": 87.5517},
    "Udayapur": {"lat": 26.9333, "lon": 86.5167},
    
    # Province 2 (Madhesh)
    "Bara": {"lat": 27.0167, "lon": 85.0000},
    "Dhanusha": {"lat": 26.8333, "lon": 85.9167},
    "Mahottari": {"lat": 26.8667, "lon": 85.7667},
    "Parsa": {"lat": 27.1333, "lon": 84.8667},
    "Rautahat": {"lat": 27.0000, "lon": 85.2667},
    "Saptari": {"lat": 26.6333, "lon": 86.7333},
    "Sarlahi": {"lat": 26.9833, "lon": 85.5667},
    "Siraha": {"lat": 26.6533, "lon": 86.2178},
    
    # Province 3 (Bagmati)
    "Bhaktapur": {"lat": 27.6710, "lon": 85.4298},
    "Chitwan": {"lat": 27.5291, "lon": 84.3542},
    "Dhading": {"lat": 27.8667, "lon": 84.9167},
    "Dolakha": {"lat": 27.7833, "lon": 86.0667},
    "Kathmandu": {"lat": 27.7172, "lon": 85.3240},
    "Kavrepalanchok": {"lat": 27.5500, "lon": 85.5500},
    "Lalitpur": {"lat": 27.6667, "lon": 85.3167},
    "Makwanpur": {"lat": 27.4167, "lon": 85.0333},
    "Nuwakot": {"lat": 27.9000, "lon": 85.1667},
    "Ramechhap": {"lat": 27.5333, "lon": 86.0833},
    "Rasuwa": {"lat": 28.0833, "lon": 85.3833},
    "Sindhuli": {"lat": 27.2500, "lon": 85.9667},
    "Sindhupalchok": {"lat": 27.9500, "lon": 85.7000},
    
    # Province 4 (Gandaki)
    "Baglung": {"lat": 28.2667, "lon": 83.5833},
    "Gorkha": {"lat": 28.0000, "lon": 84.6333},
    "Kaski": {"lat": 28.2096, "lon": 83.9856},
    "Lamjung": {"lat": 28.2833, "lon": 84.3500},
    "Manang": {"lat": 28.5500, "lon": 84.0167},
    "Mustang": {"lat": 28.9983, "lon": 83.8500},
    "Myagdi": {"lat": 28.5500, "lon": 83.4667},
    "Nawalpur": {"lat": 27.6500, "lon": 84.1000},
    "Parbat": {"lat": 28.2000, "lon": 83.6833},
    "Syangja": {"lat": 28.0833, "lon": 83.8667},
    "Tanahun": {"lat": 27.9333, "lon": 84.2500},
    
    # Province 5 (Lumbini)
    "Arghakhanchi": {"lat": 27.9333, "lon": 83.1167},
    "Banke": {"lat": 28.0600, "lon": 81.6300},
    "Bardiya": {"lat": 28.4167, "lon": 81.4167},
    "Dang": {"lat": 28.1167, "lon": 82.3000},
    "Gulmi": {"lat": 28.0833, "lon": 83.2667},
    "Kapilvastu": {"lat": 27.5500, "lon": 83.0500},
    "Palpa": {"lat": 27.8667, "lon": 83.5500},
    "Parasi": {"lat": 27.5000, "lon": 83.6667},
    "Pyuthan": {"lat": 28.1000, "lon": 82.8500},
    "Rolpa": {"lat": 28.3667, "lon": 82.6500},
    "Rukum East": {"lat": 28.5500, "lon": 82.5167},
    "Rupandehi": {"lat": 27.4833, "lon": 83.4333},
    
    # Province 6 (Karnali)
    "Dailekh": {"lat": 28.8500, "lon": 81.7000},
    "Dolpa": {"lat": 29.0833, "lon": 82.8667},
    "Humla": {"lat": 29.9667, "lon": 81.8500},
    "Jajarkot": {"lat": 28.7167, "lon": 82.1833},
    "Jumla": {"lat": 29.2833, "lon": 82.1833},
    "Kalikot": {"lat": 29.1333, "lon": 81.6167},
    "Mugu": {"lat": 29.5000, "lon": 82.0833},
    "Rukum West": {"lat": 28.6167, "lon": 82.3333},
    "Salyan": {"lat": 28.3833, "lon": 82.1667},
    "Surkhet": {"lat": 28.6000, "lon": 81.6167},
    
    # Province 7 (Sudurpashchim)
    "Achham": {"lat": 29.0500, "lon": 81.2500},
    "Baitadi": {"lat": 29.5167, "lon": 80.4167},
    "Bajhang": {"lat": 29.5333, "lon": 81.1833},
    "Bajura": {"lat": 29.4500, "lon": 81.4833},
    "Dadeldhura": {"lat": 29.3000, "lon": 80.5667},
    "Darchula": {"lat": 29.8500, "lon": 80.5500},
    "Doti": {"lat": 29.2667, "lon": 80.9500},
    "Kailali": {"lat": 28.8000, "lon": 80.8833},
    "Kanchanpur": {"lat": 28.8500, "lon": 80.3167},
}

# Community forests in Nepal - sample locations
COMMUNITY_FORESTS = {
    "Churia Community Forest (Chitwan)": {"lat": 27.4500, "lon": 84.3500},
    "Shivapuri National Park Buffer (Kathmandu)": {"lat": 27.8000, "lon": 85.4000},
    "Annapurna Conservation Area (Kaski)": {"lat": 28.5500, "lon": 83.9500},
    "Langtang National Park (Rasuwa)": {"lat": 28.2000, "lon": 85.5000},
    "Sagarmatha Buffer Zone (Solukhumbu)": {"lat": 27.9000, "lon": 86.7500},
    "Bardiya National Park Buffer": {"lat": 28.4000, "lon": 81.4500},
    "Parsa Wildlife Reserve": {"lat": 27.3500, "lon": 84.8500},
    "Koshi Tappu Wildlife Reserve": {"lat": 26.6500, "lon": 87.0000},
}


def get_all_locations():
    """
    Get all available locations (districts + community forests).
    
    Returns:
        dict - Combined dictionary of all locations
    """
    all_locations = {}
    all_locations.update(NEPAL_DISTRICTS)
    all_locations.update(COMMUNITY_FORESTS)
    return all_locations


def search_location(query):
    """
    Search for a location by name.
    
    Args:
        query: str - Search query
        
    Returns:
        list - List of matching location names
    """
    all_locations = get_all_locations()
    query_lower = query.lower()
    matches = [name for name in all_locations.keys() 
               if query_lower in name.lower()]
    return sorted(matches)


def get_location_coords(name):
    """
    Get coordinates for a location by name.
    
    Args:
        name: str - Location name
        
    Returns:
        tuple - (lat, lon) or None if not found
    """
    all_locations = get_all_locations()
    if name in all_locations:
        loc = all_locations[name]
        return loc['lat'], loc['lon']
    return None
