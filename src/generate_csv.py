import json
import csv

# Load the already processed data
with open('../data/processed/sudan_map_data.json', 'r') as f:
    geojson = json.load(f)

# Field names for the CSV as requested by the user
fieldnames = [
    'Locality', 'State', 'Latitude', 'Longitude', 
    'IDP_Students_Added', 'Conflict_Risk_Score', 
    'Conflict_Events', 'Conflict_Deaths'
]

with open('../data/processed/data.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    
    for feature in geojson['features']:
        props = feature['properties']
        # Use center_lat/lon from the properties if available, 
        # or calculate centroid (simplified)
        lat = props.get('center_lat', 15.0)
        lon = props.get('center_lon', 30.0)
        
        writer.writerow({
            'Locality': props.get('adm2_name'),
            'State': props.get('adm1_name'),
            'Latitude': lat,
            'Longitude': lon,
            'IDP_Students_Added': props.get('idp_count', 0),
            'Conflict_Risk_Score': 100 - props.get('safety_score', 100),
            'Conflict_Events': props.get('conflict_events', 0),
            'Conflict_Deaths': props.get('conflict_deaths', 0)
        })

print("Created ../data/processed/data.csv for PapaParse integration.")
