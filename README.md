# Miami-Dade Fire Rescue Incident Map

A Streamlit application that visualizes real-time emergency incidents from the Miami-Dade Fire Rescue Computer Aided Dispatch (CAD) system.

## Features

- **Real-time Data**: Fetches the latest incident data from the Miami-Dade Fire Rescue CAD system
- **Interactive Map**: Displays incidents on a map with color-coded markers based on section
- **Filtering Options**: Filter incidents by section (North, Central, South, East, Medcom), incident type, and status
- **Data Analysis**: View charts showing incident distribution by section and type
- **Responsive Design**: Works on desktop and mobile devices

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/vigilmia.git
   cd vigilmia
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the Streamlit app:
   ```
   streamlit run app.py
   ```

2. Open your web browser and navigate to the URL displayed in the terminal (typically http://localhost:8501)

3. Use the sidebar filters to narrow down incidents by section, type, or status

4. Click on map markers to view detailed information about each incident

5. Use the "Refresh Data" button to fetch the latest incidents

## Data Source

The application fetches data from the [Miami-Dade Fire Rescue CAD system](https://www.miamidade.gov/firecad/calls_include.asp), which provides real-time information about emergency incidents in Miami-Dade County.

## Sections Explained

The application categorizes incidents into sections based on the responding units:

- **North**: Units 1-99
- **Central**: Units 200-399
- **South**: Units 400-699
- **East**: Units 700-999
- **Medcom**: Medical communication units
- **Unknown**: Units that don't match any of the above patterns

## Notes

- The geocoding in this demo uses random coordinates around Miami-Dade County. For a production application, you would want to use a proper geocoding service like Google Maps API or OpenStreetMap Nominatim.
- Data is cached for 5 minutes to reduce load on the source website.

## License

MIT License 