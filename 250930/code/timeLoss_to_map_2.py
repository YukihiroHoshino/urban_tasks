import pandas as pd
import folium

# --- 1. Data Loading and Preparation (Done once for both maps) ---

csv_file = '250930/data/tripinfo_with_coords_4.csv'
print(f"Loading '{csv_file}'...")
df = pd.read_csv(csv_file)

# Drop rows if ANY of the departure or arrival coordinates are missing
original_count = len(df)
df.dropna(subset=['depart_lon', 'depart_lat', 'arrival_lon', 'arrival_lat'], inplace=True)
print(f"Removed {original_count - len(df)} rows with missing coordinates.")

# Randomly sample 10,000 trips
if len(df) > 10000:
    print(f"Data is large. Randomly sampling 10,000 trips.")
    df_sampled = df.sample(n=10000, random_state=42) # Use random_state for reproducibility
    print(f"Number of trips after sampling: {len(df_sampled)}")
else:
    df_sampled = df

# Calculate the difference in TimeLoss and assign color
df_sampled['timeloss_diff'] = df_sampled['step4_timeLoss'] - df_sampled['step1_timeLoss']

def assign_color(diff):
    if diff > 0: return 'red'    # Worsened
    elif diff < 0: return 'blue'   # Improved
    else: return 'green'  # No change

df_sampled['color'] = df_sampled['timeloss_diff'].apply(assign_color)

# HTML/CSS for the map legend (reused for both maps)
legend_html = '''
     <div style="position: fixed;
     bottom: 50px; left: 50px; width: 180px; height: 90px;
     border:2px solid grey; z-index:9999; font-size:14px;
     background-color: white;
     ">&nbsp; <b>Legend (TimeLoss Diff)</b><br>
     &nbsp; <i class="fa fa-circle" style="color:red"></i>&nbsp; Worsened (> 0)<br>
     &nbsp; <i class="fa fa-circle" style="color:blue"></i>&nbsp; Improved (< 0)<br>
     &nbsp; <i class="fa fa-circle" style="color:green"></i>&nbsp; No Change (= 0)</div>
     '''

# --- 2. Generate and Save DEPARTURE Map ---

print("\n--- Creating Departure Map ---")
center_lat_dep = df_sampled['depart_lat'].mean()
center_lon_dep = df_sampled['depart_lon'].mean()
m_depart = folium.Map(location=[center_lat_dep, center_lon_dep], zoom_start=12, tiles='CartoDB positron')

for idx, row in df_sampled.iterrows():
    popup_html = f"""
    <b>Trip ID:</b> {row['id']}<br>
    <b>TimeLoss Diff:</b> {row['timeloss_diff']:.2f} seconds<br>
    <b>Depart Coords:</b> ({row['depart_lat']:.4f}, {row['depart_lon']:.4f})
    """
    folium.CircleMarker(
        location=[row['depart_lat'], row['depart_lon']],
        radius=2, color=row['color'], fill=True,
        fill_color=row['color'], fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m_depart)

m_depart.get_root().html.add_child(folium.Element(legend_html))
output_html_dep = '250930/data/departure_timeloss_map_4_sampled.html'
m_depart.save(output_html_dep)
print(f"Departure map successfully saved to '{output_html_dep}'")


# --- 3. Generate and Save ARRIVAL Map ---

print("\n--- Creating Arrival Map ---")
center_lat_arr = df_sampled['arrival_lat'].mean()
center_lon_arr = df_sampled['arrival_lon'].mean()
m_arrival = folium.Map(location=[center_lat_arr, center_lon_arr], zoom_start=12, tiles='CartoDB positron')

for idx, row in df_sampled.iterrows():
    popup_html = f"""
    <b>Trip ID:</b> {row['id']}<br>
    <b>TimeLoss Diff:</b> {row['timeloss_diff']:.2f} seconds<br>
    <b>Arrival Coords:</b> ({row['arrival_lat']:.4f}, {row['arrival_lon']:.4f})
    """
    folium.CircleMarker(
        location=[row['arrival_lat'], row['arrival_lon']],
        radius=2, color=row['color'], fill=True,
        fill_color=row['color'], fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m_arrival)

m_arrival.get_root().html.add_child(folium.Element(legend_html))
output_html_arr = '250930/data/arrival_timeloss_map_4_sampled.html'
m_arrival.save(output_html_arr)
print(f"Arrival map successfully saved to '{output_html_arr}'")

print("\nProcessing complete! ✨")