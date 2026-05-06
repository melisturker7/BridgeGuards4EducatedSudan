import csv
import json
import collections

# HELPER: Normalize names for matching
def normalize(name):
    if not name: return ""
    return name.strip().lower().replace("-", " ").replace("  ", " ")

# 1. LOAD LOCALITY BOUNDARIES (The "Master List" of Sudan localities)
print("Loading official Sudan localities...")
localities = {}
with open('raw-data/admin_boundaries/sdn_admin2.geojson', 'r') as f:
    geojson = json.load(f)
    for feature in geojson['features']:
        props = feature['properties']
        pcode = props.get('adm2_pcode')
        name = props.get('adm2_name')
        localities[pcode] = {
            'name': name,
            'state': props.get('adm1_name'),
            'pcode': pcode,
            'lat': props.get('center_lat'),
            'lon': props.get('center_lon'),
            'idp_count': 0,
            'conflict_events': 0,
            'conflict_deaths': 0
        }

# 2. LOAD & CLEAN IDP DATA (Using PCodes for 100% accuracy)
print("Processing IDP data...")
with open('raw-data/sudan-idps.csv', 'r') as f:
    reader = csv.DictReader(f)
    # Track latest reporting date per locality
    latest_idp = {} # pcode -> {count, date}
    for row in reader:
        pcode = row.get('admin2Pcode')
        if not pcode or pcode not in localities: continue
        
        try:
            count = int(row.get('numPresentIdpInd', 0))
        except:
            count = 0
            
        date = row.get('reportingDate', '')
        if pcode not in latest_idp or date > latest_idp[pcode]['date']:
            latest_idp[pcode] = {'count': count, 'date': date}

    for pcode, data in latest_idp.items():
        localities[pcode]['idp_count'] = data['count']

# 3. LOAD & CLEAN CONFLICT DATA (Using Name Matching + Normalization)
print("Processing Conflict data (2024-2026)...")
# Create a name-to-pcode map for conflict matching
name_to_pcode = {normalize(loc['name']): pcode for pcode, loc in localities.items()}

with open('raw-data/sudan-conflict-ucdp.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Only process Sudan (SDN) and recent years
        if row.get('iso3') != 'SDN': continue
        
        date = row.get('date_start', '')
        if date < '2024-01-01': continue
        
        adm2_raw = row.get('adm_2', '')
        pcode = name_to_pcode.get(normalize(adm2_raw))
        
        if pcode:
            localities[pcode]['conflict_events'] += 1
            try:
                localities[pcode]['conflict_deaths'] += int(row.get('best', 0))
            except:
                pass

# 4. CALCULATE CLEAN SAFETY/RISK SCORES
print("Calculating risk metrics...")
for pcode, loc in localities.items():
    # Conflict Risk Score (0-100)
    # Weighted: Events (60%) + Fatalities (40%)
    event_weight = min(loc['conflict_events'] * 5, 60) # Max out at 12 events for 60%
    death_weight = min(loc['conflict_deaths'] * 1, 40) # Max out at 40 deaths for 40%
    loc['risk_score'] = event_weight + death_weight

# 5. OUTPUT CLEAN CSV
fieldnames = [
    'Locality', 'State', 'PCode', 'Latitude', 'Longitude', 
    'IDP_Students_Added', 'Conflict_Risk_Score', 
    'Conflict_Events', 'Conflict_Deaths'
]

with open('data.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for loc in localities.values():
        writer.writerow({
            'Locality': loc['name'],
            'State': loc['state'],
            'PCode': loc['pcode'],
            'Latitude': loc['lat'],
            'Longitude': loc['lon'],
            'IDP_Students_Added': loc['idp_count'],
            'Conflict_Risk_Score': round(loc['risk_score'], 1),
            'Conflict_Events': loc['conflict_events'],
            'Conflict_Deaths': loc['conflict_deaths']
        })

print(f"Clean dataset generated: data.csv ({len(localities)} localities processed)")
