from flask import Flask, request, render_template_string
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from datetime import datetime

app = Flask(__name__)

# Correct URL to the raw CSV file
url = "https://raw.githubusercontent.com/OA143614/bustimetable/a20f604a97a37cd28155dad340900eb0205bcf05/buscommon.csv"

# Read the CSV file using pandas
df = pd.read_csv(url)

# Function to convert the geometry string to a Point object
def convert_to_point(geom_str):
    geom_str = geom_str.replace("POINT(", "").replace(")", "")
    lon, lat = map(float, geom_str.split(','))
    return Point(lon, lat)

# Apply the function to the 'geometry' column
df['geometry'] = df['geometry'].apply(convert_to_point)

# Convert the DataFrame to a GeoDataFrame
gdf = gpd.GeoDataFrame(df, geometry='geometry')

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Geolocation and Bus Timetable</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    </head>
    <body>
        <h1>Geolocation and Bus Timetable</h1>
        <button onclick="getLocation()">Get Location</button>
        <p id="location"></p>
        <div id="map" style="height: 500px;"></div>

        <script>
            function getLocation() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(showPosition, showError);
                } else {
                    document.getElementById("location").innerHTML = "Geolocation is not supported by this browser.";
                }
            }

            function showPosition(position) {
                var latitude = position.coords.latitude;
                var longitude = position.coords.longitude;
                document.getElementById("location").innerHTML = 
                    "Latitude: " + latitude + 
                    "<br>Longitude: " + longitude;

                // Update map with user's location
                var map = L.map('map').setView([latitude, longitude], 15);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }).addTo(map);

                L.marker([latitude, longitude]).addTo(map)
                    .bindPopup('Your Location')
                    .openPopup();

                // Send location to Flask server
                fetch('/process', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ latitude: latitude, longitude: longitude }),
                })
                .then(response => response.text())
                .then(data => {
                    document.getElementById('map').innerHTML = data;
                });
            }

            function showError(error) {
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        document.getElementById("location").innerHTML = "User denied the request for Geolocation.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        document.getElementById("location").innerHTML = "Location information is unavailable.";
                        break;
                    case error.TIMEOUT:
                        document.getElementById("location").innerHTML = "The request to get user location timed out.";
                        break;
                    case error.UNKNOWN_ERROR:
                        document.getElementById("location").innerHTML = "An unknown error occurred.";
                        break;
                }
            }
        </script>
    </body>
    </html>
    ''')

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    user_latitude = data['latitude']
    user_longitude = data['longitude']

    # Get the current date and time
    current_datetime = datetime.now()

    # Get the current day of the week and time
    current_day_of_week = current_datetime.strftime("%A")
    current_time = current_datetime.strftime("%H:%M:%S")

    # Convert current time to float for comparison
    current_time_float = 8.45

    # Match day of the week and time greater than or equal to the timetable for each station
    matching_stops = df[(df['day'] == current_day_of_week) & (df['time'] >= current_time_float)]

    # Create a map centered around the given location
    m = folium.Map(location=[user_latitude, user_longitude], zoom_start=15)

    # Add a marker for the user's location
    folium.Marker(
        [user_latitude, user_longitude],
        popup="Your Location",
        tooltip="Your Location",
        icon=folium.Icon(color='red', icon='star')
    ).add_to(m)

    # Add markers for each bus stop and highlight the matching one with a standard icon
    for station in df['station'].unique():
        station_stops = matching_stops[matching_stops['station'] == station]
        if not station_stops.empty:
            stop_latitude, stop_longitude = station_stops.iloc[0]['geometry'].x, station_stops.iloc[0]['geometry'].y
            popup_text = f"{station}<br>Bus Times: {station_stops.head(1)['time'].values[0]} on {station_stops.head(1)['day'].values[0]}"
            folium.Marker(
                [stop_latitude, stop_longitude],
                popup=popup_text,
                tooltip=station,
                icon=folium.Icon(color='purple')
            ).add_to(m)

    # Save the map to an HTML file
    m.save('templates/ohio_university_bus_stations.html')

    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bus Stations Map</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    </head>
    <body>
        <h1>Bus Stations Map</h1>
        <div id="map" style="height: 500px;"></div>

        <script>
            var map = L.map('map').setView([{{ latitude }}, {{ longitude }}], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);

            L.marker([{{ latitude }}, {{ longitude }}]).addTo(map)
                .bindPopup('Your Location')
                .openPopup();

            // Add bus stops from Python-generated map (ohio_university_bus_stations.html)
            fetch('/static/ohio_university_bus_stations.html')
                .then(response => response.text())
                .then(data => {
                    var parser = new DOMParser();
                    var doc = parser.parseFromString(data, 'text/html');
                    var busStopsScript = doc.querySelector('script');
                    eval(busStopsScript.innerText);
                });
        </script>
    </body>
    </html>
    ''', latitude=user_latitude, longitude=user_longitude)

if __name__ == '__main__':
    app.run(debug=True)