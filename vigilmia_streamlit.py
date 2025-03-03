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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Configure Secrets (via Streamlit Cloud)
TOGETHER_API_KEY = st.secrets.get("TOGETHER_API_KEY")

# Initialize Together client at module level
try:
    together_client = Together(api_key=TOGETHER_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Together client: {e}")
    together_client = None

# Cache for geocoding results
@st.cache_data(ttl=86400)
def get_cached_coordinates(address: str) -> Optional[tuple[float, float]]:
    """Get cached coordinates for an address."""
    return geocode_address(address)

def parse_incidents(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Parse incident data from BeautifulSoup object."""
    incidents = []
    try:
        # Find all tables and rows
        tables = soup.find_all('table')
        
        # Debug: Show number of tables found
        st.write(f"Found {len(tables)} tables in response")
        
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 6:
                    incident = {
                        'time': cols[0].text.strip(),
                        'type': cols[1].text.strip(),
                        'location': cols[2].text.strip(),
                        'units': cols[3].text.strip(),
                        'status': cols[4].text.strip(),
                        'details': cols[5].text.strip()
                    }
                    incidents.append(incident)
                    
                    # Debug: Show parsed incident
                    st.write(f"Parsed incident: {incident}")
    
    except Exception as e:
        logger.error(f"Error parsing incidents: {e}")
        st.error(f"Parsing error: {str(e)}")
        
    return incidents

def geocode_address(address: str) -> Optional[tuple[float, float]]:
    """Geocode an address to (latitude, longitude)."""
    try:
        geolocator = Nominatim(user_agent="VigilMIA")
        full_address = f"{address}, Miami-Dade, FL"
        location = geolocator.geocode(full_address, timeout=10)
        return (location.latitude, location.longitude) if location else None
    except GeocoderTimedOut:
        logger.warning(f"Geocoding timed out for address: {address}")
        return None
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        return None

@st.cache_data(ttl=3600)
def process_for_mapping(incidents: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert incidents to DataFrame with geocoded coordinates."""
    if not incidents:
        return pd.DataFrame(columns=['lat', 'lon', 'type', 'details', 'location', 'status'])
    
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
    """Fetch live emergency data with enhanced error handling."""
    try:
        # Add cache-buster parameter
        timestamp = int(time.time())
        cad_url = f"https://www.miamidade.gov/firecad/calls_include.asp?_={timestamp}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        response = requests.get(cad_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Validate response content
        if len(response.content) < 500:
            st.error("Received incomplete response from server")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        return parse_incidents(soup)
        
    except RequestException as e:
        logger.error(f"Network error: {str(e)}")
        st.error("Unable to connect to emergency data server")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return []

def generate_safety_tips(incidents: List[Dict[str, Any]], placeholder: st.empty) -> str:
    """Generate safety tips based on current incidents."""
    if not together_client or not incidents:
        return "Unable to generate safety tips at this time."
    
    try:
        incident_summary = "\n".join([f"- {inc['type']} at {inc['location']}" for inc in incidents[:3]])
        prompt = f"""Current emergencies:\n{incident_summary}\nProvide 3 safety tips:"""
        
        response = together_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            stream=True
        )
        
        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
                placeholder.markdown(full_response + "▌")
                
        placeholder.markdown(full_response)
        return full_response
        
    except Exception as e:
        logger.error(f"AI error: {str(e)}")
        return "Safety tips service unavailable"

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
    
    with st.spinner("Loading emergency data..."):
        incidents = fetch_live_data()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📍 Live Emergency Map")
        df = process_for_mapping(incidents)
        if not df.empty:
            st.map(df, latitude='lat', longitude='lon', color='#FF4B4B', size=50)
        else:
            st.info("No active incidents to display")
        
        st.subheader("📊 Active Incidents")
        if incidents:
            st.dataframe(pd.DataFrame(incidents), use_container_width=True, hide_index=True)
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
