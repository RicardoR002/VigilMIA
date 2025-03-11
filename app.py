import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import folium
from streamlit_folium import folium_static
import plotly.express as px
from datetime import datetime
import re

# Set page configuration
st.set_page_config(
    page_title="Miami-Dade Fire Rescue Incident Map",
    page_icon="🚒",
    layout="wide"
)

# Title and description
st.title("Miami-Dade Fire Rescue Incident Map")
st.markdown("Real-time visualization of emergency incidents from Miami-Dade Fire Rescue CAD system")

# Function to scrape incident data
@st.cache_data(ttl=300)  # Cache data for 5 minutes
def get_incident_data():
    url = "https://www.miamidade.gov/firecad/calls_include.asp"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all tables - each section (North, Central, South, etc.) has its own table
        tables = soup.find_all('table')
        
        if not tables:
            st.error("Could not find incident data tables on the webpage")
            return pd.DataFrame()
        
        # Extract section headers
        section_headers = []
        for header in soup.find_all('h5'):
            text = header.get_text().strip()
            if "Calls" in text:
                # Extract section name (e.g., "NORTH - 9 Calls" -> "NORTH")
                section = text.split('-')[0].strip()
                section_headers.append(section)
        
        # Process each table and combine data
        all_data = []
        
        for i, table in enumerate(tables):
            if i >= len(section_headers):
                section = "Unknown"
            else:
                section = section_headers[i]
            
            # Extract rows from table
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text().strip() for td in tr.find_all('td')]
                if cells and len(cells) > 1:  # Skip empty rows
                    rows.append(cells)
            
            # Skip tables with no data
            if not rows:
                continue
                
            # Process the rows to extract incident data
            # The data structure is in groups of rows, where each incident spans multiple rows
            current_incident = {}
            for row in rows:
                # Check if this is a header row or data row
                if len(row) == 1 and row[0] in ['RCVD', 'FC', 'INC TYPE', 'ADDRESS', 'UNITS']:
                    current_header = row[0]
                else:
                    # This is a data row
                    if current_header == 'RCVD':
                        current_incident = {'RCVD': row[0], 'Section': section}
                    elif current_header == 'FC' and current_incident:
                        current_incident['FC'] = row[0] if row else ''
                    elif current_header == 'INC TYPE' and current_incident:
                        current_incident['INC TYPE'] = row[0] if row else ''
                    elif current_header == 'ADDRESS' and current_incident:
                        current_incident['ADDRESS'] = row[0] if row else ''
                    elif current_header == 'UNITS' and current_incident:
                        current_incident['UNITS'] = row[0] if row else ''
                        # Add the completed incident to our data
                        all_data.append(current_incident.copy())
        
        # Create DataFrame
        if all_data:
            df = pd.DataFrame(all_data)
            # Clean and process data
            return process_data(df)
        else:
            st.warning("No incident data found")
            return pd.DataFrame()
    
    except Exception as e:
        st.error(f"Error fetching incident data: {e}")
        return pd.DataFrame()

# Function to process and clean the data
def process_data(df):
    if df.empty:
        return df
    
    # Rename columns to more user-friendly names
    df = df.rename(columns={
        'RCVD': 'Time Received',
        'FC': 'Fire Code',
        'INC TYPE': 'Incident Type',
        'ADDRESS': 'Address',
        'UNITS': 'Units'
    })
    
    # Clean up the data
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].str.strip()
    
    # Get coordinates for each address
    df['Latitude'], df['Longitude'] = zip(*df['Address'].apply(geocode_address))
    
    return df

# Function to determine section based on unit number (not needed anymore as we extract section from the page)
def determine_section(units_str):
    if pd.isna(units_str) or not units_str:
        return "Unknown"
    
    units = units_str.split()
    
    # Define patterns for each section
    north_pattern = r'^[ER]?[0-9]{1,2}$'  # Units 1-99 (E01, R01, etc.)
    central_pattern = r'^[ER]?[2-3][0-9]{2}$'  # Units 200-399
    south_pattern = r'^[ER]?[4-6][0-9]{2}$'  # Units 400-699
    east_pattern = r'^[ER]?[7-9][0-9]{2}$'  # Units 700-999
    medcom_pattern = r'^(MEDCOM|MED)'  # MEDCOM units
    
    for unit in units:
        unit = unit.strip()
        if re.match(north_pattern, unit):
            return "NORTH"
        elif re.match(central_pattern, unit):
            return "CENTRAL"
        elif re.match(south_pattern, unit):
            return "SOUTH"
        elif re.match(east_pattern, unit):
            return "EAST"
        elif re.match(medcom_pattern, unit, re.IGNORECASE):
            return "MEDCOM"
    
    return "Unknown"

# Function to geocode addresses (simplified for demo)
def geocode_address(address):
    # In a real application, you would use a geocoding service like Google Maps API
    # For this demo, we'll generate random coordinates around Miami-Dade County
    import random
    
    # Miami-Dade County approximate boundaries
    miami_lat = 25.7617
    miami_lng = -80.1918
    
    # Generate random coordinates within ~10 miles of Miami
    lat = miami_lat + (random.random() - 0.5) * 0.3
    lng = miami_lng + (random.random() - 0.5) * 0.3
    
    return (lat, lng)

# Load data
with st.spinner("Loading incident data..."):
    df = get_incident_data()

# Check if data was loaded successfully
if df.empty:
    st.warning("No incident data available. Please try again later.")
    # Show a sample dataframe for demonstration purposes
    st.info("Showing sample data for demonstration purposes")
    
    # Create sample data
    sample_data = {
        'Time Received': ['21:09', '21:13', '21:20', '21:21', '21:37', '21:38'],
        'Fire Code': ['', 'C3', '', '', '', ''],
        'Incident Type': ['MEDICAL', 'MEDICAL', 'MEDICAL', 'MEDICAL', 'OTHER', 'MEDICAL'],
        'Address': ['NW 83RD ST / NW 17TH AVE', '3100 BLOCK & NW 156TH ST', 'NW 97TH ST / NW 27TH AVE', 
                   'NW 62ND ST / NW 22ND AVE', '7400 BLOCK & NW 104TH AVE', 'NW 7TH AVE / NW 119TH ST'],
        'Units': ['AB4 E07', 'E11 R01 R54', 'R07', 'R02 R202', 'E69', 'P26'],
        'Section': ['NORTH', 'NORTH', 'NORTH', 'NORTH', 'NORTH', 'NORTH']
    }
    
    df = pd.DataFrame(sample_data)
    df['Latitude'], df['Longitude'] = zip(*df['Address'].apply(geocode_address))

# Sidebar filters
st.sidebar.header("Filters")

# Section filter
all_sections = ["All"] + sorted(df["Section"].unique().tolist())
selected_section = st.sidebar.selectbox("Select Section", all_sections)

# Incident type filter
all_types = ["All"] + sorted(df["Incident Type"].unique().tolist())
selected_type = st.sidebar.selectbox("Select Incident Type", all_types)

# Apply filters
filtered_df = df.copy()

if selected_section != "All":
    filtered_df = filtered_df[filtered_df["Section"] == selected_section]
    
if selected_type != "All":
    filtered_df = filtered_df[filtered_df["Incident Type"] == selected_type]

# Display map
st.subheader("Incident Map")

if not filtered_df.empty and 'Latitude' in filtered_df.columns and 'Longitude' in filtered_df.columns:
    # Create map centered on Miami-Dade
    m = folium.Map(location=[25.7617, -80.1918], zoom_start=10)
    
    # Add markers for each incident
    for idx, row in filtered_df.iterrows():
        if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
            # Determine marker color based on section
            colors = {
                "NORTH": "blue",
                "CENTRAL": "green",
                "SOUTH": "red",
                "EAST": "purple",
                "MEDCOM": "orange",
                "Unknown": "gray"
            }
            color = colors.get(row['Section'], "gray")
            
            # Create popup content
            popup_content = f"""
            <b>Time Received:</b> {row['Time Received']}<br>
            <b>Incident Type:</b> {row['Incident Type']}<br>
            <b>Address:</b> {row['Address']}<br>
            <b>Fire Code:</b> {row.get('Fire Code', 'N/A')}<br>
            <b>Units:</b> {row['Units']}<br>
            <b>Section:</b> {row['Section']}
            """
            
            # Add marker to map
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color=color, icon="fire", prefix="fa"),
                tooltip=f"{row['Incident Type']} - {row['Address']}"
            ).add_to(m)
    
    # Display map
    folium_static(m)
else:
    st.warning("No incidents to display on the map with the current filters.")

# Display incident data table
st.subheader("Incident Data")
st.dataframe(filtered_df.drop(columns=['Latitude', 'Longitude'], errors='ignore'))

# Create charts
st.subheader("Incident Analysis")

col1, col2 = st.columns(2)

with col1:
    # Incidents by section
    section_counts = df['Section'].value_counts().reset_index()
    section_counts.columns = ['Section', 'Count']
    
    fig1 = px.bar(
        section_counts, 
        x='Section', 
        y='Count',
        title='Incidents by Section',
        color='Section',
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    # Incidents by type
    type_counts = df['Incident Type'].value_counts().head(10).reset_index()
    type_counts.columns = ['Type', 'Count']
    
    fig2 = px.pie(
        type_counts, 
        values='Count', 
        names='Type',
        title='Top 10 Incident Types',
        hole=0.3
    )
    st.plotly_chart(fig2, use_container_width=True)

# Add refresh button
if st.button("Refresh Data"):
    st.cache_data.clear()
    st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("Data source: [Miami-Dade Fire Rescue CAD](https://www.miamidade.gov/firecad/calls_include.asp)")
st.markdown("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")) 