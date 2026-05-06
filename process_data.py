import csv
import json
import collections

# Load IDP data
idp_data = collections.defaultdict(lambda: {"count": 0, "date": ""})
with open('raw-data/sudan-idps.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        pcode = row.get('admin2Pcode')
        if not pcode: continue
        count = int(row.get('numPresentIdpInd', 0))
        date = row.get('reportingDate', '')
        # Only keep the latest record for each pcode
        if date > idp_data[pcode]["date"]:
            idp_data[pcode] = {"count": count, "date": date}

# Load Conflict data (UCDP)
conflict_data = collections.defaultdict(lambda: {"events": 0, "deaths": 0})
# We'll use the names to match later if possible, but for now let's just count
with open('raw-data/sudan-conflict-ucdp.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        adm2 = row.get('adm_2')
        deaths = int(row.get('best', 0))
        date = row.get('date_start', '')
        # Filter for recent events (e.g., 2024-2026)
        if date >= '2024-01-01':
            conflict_data[adm2]["events"] += 1
            conflict_data[adm2]["deaths"] += deaths

# Load GeoJSON to create the mapping and final output
# Using the original OCHA GeoJSON from raw-data
with open('raw-data/admin_boundaries/sdn_admin2.geojson', 'r') as f:
    geojson = json.load(f)

# Join data into GeoJSON properties
for feature in geojson['features']:
    props = feature['properties']
    pcode = props.get('adm2_pcode')
    name = props.get('adm2_name')
    
    # Add IDP data
    feature['properties']['idp_count'] = idp_data[pcode]['count']
    
    # Add Conflict data (match by name - might be fuzzy)
    # Try direct match, then lowercase
    c_info = conflict_data.get(name) or conflict_data.get(name.lower()) or {"events": 0, "deaths": 0}
    feature['properties']['conflict_events'] = c_info['events']
    feature['properties']['conflict_deaths'] = c_info['deaths']
    
    # Calculate "Safety Score"
    safety = 100
    if c_info['events'] > 0:
        safety -= min(c_info['events'] * 10, 50)
    if c_info['deaths'] > 0:
        safety -= min(c_info['deaths'] * 2, 40)
    
    feature['properties']['safety_score'] = max(safety, 0)

# Write to the tracked data directory
with open('data/sudan_map_data.json', 'w') as f:
    json.dump(geojson, f)

print("Processed data saved to data/sudan_map_data.json")
