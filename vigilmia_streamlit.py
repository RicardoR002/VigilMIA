import streamlit as st
import requests
from bs4 import BeautifulSoup
from together import Together
import pandas as pd
from typing import List, Dict, Any, Optional
import logging
from requests.exceptions import RequestException
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
import pydeck as pdk  

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Secrets
TOGETHER_API_KEY = st.secrets.get("TOGETHER_API_KEY")

# Initialize Together client
try:
    together_client = Together(api_key=TOGETHER_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Together client: {e}")
    together_client = None

# Cache for geocoding
@st.cache_data(ttl=86400)
def get_cached_coordinates(address: str) -> Optional[tuple[float, float]]:
    return geocode_address(address)

def parse_incidents(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    incidents = []
    try:
        # Target the main content table specifically
        main_table = soup.find('table', {'cellpadding': '2', 'cellspacing': '0'})
        
        if not main_table:
            st.error("Main incident table not found in response")
            return []
            
        rows = main_table.find_all('tr')[1:]  # Skip header
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                incident = {
                    'time': cols[0].text.strip(),
                    'type': cols[1].text.strip(),
                    'location': cols[2].text.strip(),
                    'units': cols[3].text.strip().replace('\n', ', '),
                    'status': cols[4].text.strip(),
                    'details': cols[5].text.strip()
                }
                incidents.append(incident)
                
        # Debug output
        if not incidents:
            st.write("Raw table data:", main_table.prettify())
            
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        st.error(f"Failed to parse incidents: {str(e)}")
        
    return incidents

def geocode_address(address: str) -> Optional[tuple[float, float]]:
    try:
        geolocator = Nominatim(user_agent="VigilMIA")
        full_address = f"{address}, Miami-Dade, FL"
        location = geolocator.geocode(full_address, timeout=10)
        return (location.latitude, location.longitude) if location else None
    except Exception as e:
        logger.warning(f"Geocoding failed for {address}: {e}")
        return None

@st.cache_data(ttl=3600)
def process_for_mapping(incidents: List[Dict[str, Any]]) -> pd.DataFrame:
    if not incidents:
        return pd.DataFrame()

    df = pd.DataFrame(incidents)
    coordinates = []
    
    for location in df['location']:
        coords = get_cached_coordinates(location)
        coordinates.append(coords if coords else (25.7617, -80.1918))
        time.sleep(0.1)
    
    df['lat'] = [coord[0] for coord in coordinates]
    df['lon'] = [coord[1] for coord in coordinates]
    
    return df

@st.cache_data(ttl=300, show_spinner="Fetching live emergency data...")
def fetch_live_data() -> List[Dict[str, Any]]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        
        # Add random query parameter to bypass cache
        cad_url = f"https://www.miamidade.gov/firecad/calls_include.asp?t={time.time()}"
        response = requests.get(cad_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        if len(response.content) < 500:
            st.error("Incomplete response received")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        return parse_incidents(soup)
        
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        st.error("Failed to retrieve emergency data")
        return []

def create_interactive_map(df: pd.DataFrame):
    """Create a PyDeck map with tooltips"""
    if df.empty:
        return
    
    layer = pdk.Layer(
        'ScatterplotLayer',
        data=df,
        get_position='[lon, lat]',
        get_color='[200, 30, 0, 160]',
        get_radius=100,
        pickable=True
    )
    
    tooltip = {
        "html": "<b>Type:</b> {type}<br/>"
                "<b>Location:</b> {location}<br/>"
                "<b>Time:</b> {time}<br/>"
                "<b>Status:</b> {status}",
        "style": {
            "backgroundColor": "steelblue",
            "color": "white"
        }
    }
    
    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/light-v9',
        initial_view_state=pdk.ViewState(
            latitude=25.7617,
            longitude=-80.1918,
            zoom=10,
            pitch=50,
        ),
        layers=[layer],
        tooltip=tooltip
    ))

def main():
    st.set_page_config(
        layout="wide",
        page_title="VigilMIA Public Safety Monitor",
        page_icon="🚨",
        initial_sidebar_state="collapsed"
    )
    
    st.markdown("""
        <style>
        .stAlert { background-color: rgba(255,75,75,0.1); border: 1px solid #FF4B4B; }
        .stDataFrame { max-height: 400px; overflow-y: auto; }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("🚨 VigilMIA Public Safety Monitor")
    
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    with st.spinner("Loading real-time emergency data..."):
        incidents = fetch_live_data()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📍 Live Emergency Map")
        df = process_for_mapping(incidents)
        
        if not df.empty:
            create_interactive_map(df)
        else:
            st.info("No active incidents to display")
        
        st.subheader("📊 Active Incidents")
        if incidents:
            st.dataframe(
                df[['time', 'type', 'location', 'status']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "time": "Time",
                    "type": "Incident Type",
                    "location": "Location",
                    "status": "Status"
                }
            )
        else:
            st.info("No current incidents reported")
    
    with col2:
        st.subheader("🤖 AI Safety Recommendations")
        tips_placeholder = st.empty()
        if incidents:
            generate_safety_tips(incidents, tips_placeholder)
        else:
            tips_placeholder.info("No incidents to analyze")

if __name__ == "__main__":
    main()
