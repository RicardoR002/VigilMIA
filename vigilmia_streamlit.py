import streamlit as st
import requests
from bs4 import BeautifulSoup
from together import Together
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
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
@st.cache_data(ttl=86400)  # 24-hour cache for geocoding
def get_cached_coordinates(address: str) -> Optional[tuple[float, float]]:
    """Get cached coordinates for an address."""
    return geocode_address(address)

def parse_incidents(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Parse incident data from BeautifulSoup object."""
    incidents = []
    try:
        # Find all rows in the table
        rows = soup.find_all('tr')[1:]  # Skip header row
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:  # Ensure we have enough columns
                incident = {
                    'time': cols[0].text.strip(),
                    'type': cols[1].text.strip(),
                    'location': cols[2].text.strip(),
                    'units': cols[3].text.strip(),
                    'status': cols[4].text.strip(),
                    'details': cols[5].text.strip()
                }
                incidents.append(incident)
    except Exception as e:
        logger.error(f"Error parsing incidents: {e}")
    return incidents

def geocode_address(address: str) -> Optional[tuple[float, float]]:
    """Geocode an address to (latitude, longitude)."""
    try:
        geolocator = Nominatim(user_agent="VigilMIA")
        # Add "Miami-Dade, FL" to improve geocoding accuracy
        full_address = f"{address}, Miami-Dade, FL"
        location = geolocator.geocode(full_address, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None
    except GeocoderTimedOut:
        logger.warning(f"Geocoding timed out for address: {address}")
        return None
    except Exception as e:
        logger.error(f"Geocoding error for address {address}: {e}")
        return None

@st.cache_data(ttl=3600)  # Cache geocoding results for 1 hour
def process_for_mapping(incidents: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert incidents to a DataFrame with geocoded coordinates."""
    if not incidents:
        return pd.DataFrame(columns=['lat', 'lon', 'type', 'details', 'location', 'status'])
    
    # Create DataFrame
    df = pd.DataFrame(incidents)
    
    # Geocode locations
    coordinates = []
    for location in df['location']:
        coords = get_cached_coordinates(location)
        if coords:
            coordinates.append(coords)
        else:
            # Fallback to Miami-Dade center coordinates
            coordinates.append((25.7617, -80.1918))
        time.sleep(0.1)  # Reduced rate limiting since we're using caching
    
    df['lat'] = [coord[0] for coord in coordinates]
    df['lon'] = [coord[1] for coord in coordinates]
    
    return df

@st.cache_data(ttl=300)  # 5-minute cache
def fetch_live_data() -> List[Dict[str, Any]]:
    """Fetch live emergency data with error handling."""
    try:
        cad_url = "https://www.miamidade.gov/firecad/calls_include.asp"
        response = requests.get(cad_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        return parse_incidents(soup)
    except RequestException as e:
        logger.error(f"Error fetching data: {e}")
        st.error("Unable to fetch emergency data. Please try again later.")
        return []

def generate_safety_tips(incidents: List[Dict[str, Any]], placeholder: st.empty) -> str:
    """Generate safety tips based on current incidents."""
    if not together_client or not incidents:
        return "Unable to generate safety tips at this time."
    
    try:
        incident_summary = "\n".join([
            f"- {inc['type']} at {inc['location']}" 
            for inc in incidents[:3]
        ])
        
        prompt = f"""Based on these current emergencies in Miami:
        {incident_summary}
        
        Provide 3 brief, practical safety tips for residents in the affected areas. 
        Focus on immediate actions people can take to stay safe."""
        
        messages = [{"role": "user", "content": prompt}]
        
        response = together_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=messages,
            max_tokens=None,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>", "<|eom_id|>"],
            stream=True
        )
        
        # Collect streamed response with better UI updating
        full_response = ""
        for token in response:
            if hasattr(token, 'choices') and token.choices[0].delta.content is not None:
                content = token.choices[0].delta.content
                full_response += content
                # Update Streamlit display in real-time with markdown formatting
                placeholder.markdown(full_response + "▌")  # Add cursor effect
        
        # Final update without cursor
        placeholder.markdown(full_response)
        return full_response

    except Exception as e:
        logger.error(f"Error generating safety tips: {e}")
        return "Unable to generate safety tips at this time."

def display_twitter_feed():
    """Display relevant emergency tweets."""
    st.info("""🔄 Social Media Integration Coming Soon!
    
    We're working on integrating real-time emergency alerts from official Miami-Dade County social media channels.""")

def main():
    # 4. Dark Mode Dashboard
    st.set_page_config(
        layout="wide",
        page_title="VigilMIA Public Safety Monitor",
        page_icon="🚨",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS for better styling
    st.markdown("""
        <style>
        .stAlert {
            background-color: rgba(255, 75, 75, 0.1);
            border: 1px solid #FF4B4B;
        }
        .stDataFrame {
            max-height: 400px;
            overflow-y: auto;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("🚨 VigilMIA Public Safety Monitor")
    
    # Add refresh button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # Fetch data
    with st.spinner("Fetching latest emergency data..."):
        incidents = fetch_live_data()
    
    # Create columns for layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 5. Map Visualization
        st.subheader("📍 Live Emergency Map")
        with st.spinner("Loading map..."):
            df = process_for_mapping(incidents)
            if not df.empty:
                st.map(
                    df,
                    latitude='lat',
                    longitude='lon',
                    color='#FF4B4B',  # Emergency red
                    size=50
                )
            else:
                st.info("No active incidents to display on the map.")
            
        # Display incidents table
        st.subheader("📊 Active Incidents")
        if incidents:
            df_display = pd.DataFrame(incidents)
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No active incidents to display.")
    
    with col2:
        # 6. Real-Time Alerts
        st.subheader("🤖 AI Safety Recommendations")
        tips_placeholder = st.empty()
        if incidents:
            safety_tips = generate_safety_tips(incidents, tips_placeholder)
        else:
            tips_placeholder.info("No current incidents to analyze.")
        
        # 7. Official Alerts
        st.subheader("📢 Official Alerts")
        display_twitter_feed()

if __name__ == "__main__":
    main() 