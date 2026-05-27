import csv
import json
import collections
import pandas as pd

# HELPER: Normalize names for matching
def normalize(name):
    if not name: return ""
    # Remove " district" which is common in UCDP data
    name = name.lower().replace(" district", "").strip()
    return name.replace("-", " ").replace("  ", " ")

# 1. LOAD LOCALITY BOUNDARIES
print("Loading official Sudan localities...")
localities = {}
with open('../data/raw/admin_boundaries/sdn_admin2.geojson', 'r') as f:
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
            'conflict_deaths': 0,
            # School stats
            'total_schools': 0,
            'students_total': 0,
            'teachers': 0,
            'classrooms': 0,
            'needs_rehab': 0,
            'water_access': 0,
            'elec_access': 0
        }

# 2. LOAD & CLEAN IDP DATA
print("Processing IDP data...")
with open('../data/raw/sudan-idps.csv', 'r') as f:
    reader = csv.DictReader(f)
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

# 3. LOAD & CLEAN CONFLICT DATA
print("Processing Conflict data (UCDP)...")
# Create a robust name-to-pcode map
name_to_pcode = {normalize(loc['name']): pcode for pcode, loc in localities.items()}

# Add common manual aliases if needed
name_to_pcode['khartoum'] = 'SD01001' # Ensure Khartoum matches

with open('../data/raw/sudan-conflict-ucdp.csv', 'r') as f:
    reader = csv.DictReader(f)
    matched_count = 0
    for row in reader:
        if row.get('iso3') != 'SDN': continue
        
        date = row.get('date_start', '')
        if date < '2024-01-01': continue
        
        adm2_raw = row.get('adm_2', '')
        pcode = name_to_pcode.get(normalize(adm2_raw))
        
        if pcode:
            matched_count += 1
            localities[pcode]['conflict_events'] += 1
            try:
                localities[pcode]['conflict_deaths'] += int(row.get('best', 0))
            except: pass

print(f"Matched {matched_count} conflict events to localities.")

# 4. LOAD & AGGREGATE SCHOOL HXL DATA
print("Processing HXL School data (19k records)...")
try:
    df_schools = pd.read_excel('../data/raw/sudan-schools_hxl.xlsx', skiprows=[1])
    
    # Ensure numeric types
    cols_to_fix = ['students_total', 'teachers', 'Total_Classrooms', 'Needs Rehabilitation']
    for col in cols_to_fix:
        df_schools[col] = pd.to_numeric(df_schools[col], errors='coerce').fillna(0)
    
    # Group by LOCCODE
    stats = df_schools.groupby('LOCCODE').agg({
        'students_total': 'sum',
        'teachers': 'sum',
        'Total_Classrooms': 'sum',
        'Needs Rehabilitation': 'sum',
        'Potable_Water_source': lambda x: (x.astype(str).str.lower() == 'yes').sum(),
        'electricity': lambda x: (x.astype(str).str.lower() == 'yes').sum(),
        'School ID': 'count'
    })
    
    for pcode, row in stats.iterrows():
        if pcode in localities:
            localities[pcode]['total_schools'] = int(row['School ID'])
            localities[pcode]['students_total'] = int(row['students_total'])
            localities[pcode]['teachers'] = int(row['teachers'])
            localities[pcode]['classrooms'] = int(row['Total_Classrooms'])
            localities[pcode]['needs_rehab'] = int(row['Needs Rehabilitation'])
            localities[pcode]['water_access'] = int(row['Potable_Water_source'])
            localities[pcode]['elec_access'] = int(row['electricity'])
except Exception as e:
    print(f"Error processing school data: {e}")

# 5. CALCULATE RISK & RECOMMENDATIONS
print("Finalizing metrics...")
output_rows = []
for pcode, loc in localities.items():
    # Risk Score logic (More sensitive)
    # 1 event = 10 pts, 1 death = 2 pts
    risk_score = (loc['conflict_events'] * 10) + (loc['conflict_deaths'] * 2)
    
    risk_level = "Low"
    if risk_score >= 50: risk_level = "High"
    elif risk_score >= 10: risk_level = "Medium"
    
    # Recommendation logic based on IDP and Schools
    idp_impact = loc['idp_count']
    rehab_ratio = (loc['needs_rehab'] / loc['total_schools'] * 100) if loc['total_schools'] > 0 else 0
    
    rec = "Maintain Support"
    if risk_level == "High":
        rec = "DANGER: Active Conflict Zone - Evacuate and Suspend Operations"
    elif risk_level == "Medium":
        rec = "Monitor: Security Assessment Required Before Operation"
    elif idp_impact > 10000:
        rec = f"CRITICAL: Capacity Overload ({idp_impact} IDPs). Build Temp Classrooms."
    elif rehab_ratio > 40:
        rec = "PRIORITY: Infrastructure Rehabilitation Needed."
    elif loc['water_access'] < (loc['total_schools'] * 0.5):
        rec = "URGENT: WASH Support Required (Water Access < 50%)"

    output_rows.append({
        'School_Name': f"Locality: {loc['name']}",
        'Latitude': loc['lat'],
        'Longitude': loc['lon'],
        'IDP_Students_Added': loc['idp_count'],
        'Conflict_Risk_Score': risk_level,
        'Action_Recommendation': rec,
        'Last_Conflict_Event': f"{loc['conflict_events']} events, {loc['conflict_deaths']} deaths",
        # Extra fields for the popup
        'Total_Schools': loc['total_schools'],
        'Total_Students': loc['students_total'],
        'Student_Teacher_Ratio': round(loc['students_total'] / loc['teachers'], 1) if loc['teachers'] > 0 else "N/A"
    })

# 6. OUTPUT TO CSV
fieldnames = [
    'School_Name', 'Latitude', 'Longitude', 'IDP_Students_Added', 
    'Conflict_Risk_Score', 'Action_Recommendation', 'Last_Conflict_Event',
    'Total_Schools', 'Total_Students', 'Student_Teacher_Ratio'
]

with open('../data/processed/data.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)

print(f"Clean dataset generated: ../data/processed/data.csv ({len(output_rows)} localities processed)")
