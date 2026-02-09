"""
Forest Health Monitoring App for Nepal
A Streamlit application using Google Earth Engine and Folium
for monitoring forest health through NDVI analysis.
"""

import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import utility functions
from utils.gee_utils import (
    get_sentinel_composite,
    compute_mean_ndvi,
    calculate_ndvi_timeseries,
    get_ndvi_visualization_params,
    create_aoi_from_point
)
from utils.nepal_data import (
    NEPAL_CENTER,
    NEPAL_DISTRICTS,
    COMMUNITY_FORESTS,
    get_all_locations,
    search_location,
    get_location_coords
)

# Page configuration
st.set_page_config(
    page_title="Nepal Forest Health Monitor",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a5f2a;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4a7c59;
        text-align: center;
        margin-bottom: 2rem;
    }
    .alert-box {
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .alert-danger {
        background-color: #ffebee;
        border: 2px solid #f44336;
        color: #c62828;
    }
    .alert-success {
        background-color: #e8f5e9;
        border: 2px solid #4caf50;
        color: #2e7d32;
    }
    .alert-warning {
        background-color: #fff3e0;
        border: 2px solid #ff9800;
        color: #e65100;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
    }
    .stButton>button {
        background-color: #1a5f2a;
        color: white;
        font-weight: 600;
        border-radius: 10px;
        padding: 0.5rem 2rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #2e7d32;
    }
</style>
""", unsafe_allow_html=True)


def initialize_gee():
    """Initialize Google Earth Engine using project ID from environment variables."""
    project_id = os.getenv('GEE_PROJECT_ID')
    
    if not project_id:
        st.error("❌ GEE_PROJECT_ID not found in .env file")
        st.info("Please add `GEE_PROJECT_ID=your_project_id` to your .env file")
        return False
    
    try:
        ee.Initialize(project=project_id)
        return True
    except Exception as e:
        st.error(f"❌ Failed to initialize Earth Engine: {str(e)}")
        st.info("Please run `earthengine authenticate` in your terminal if you haven't already.")
        return False


def get_ee_tile_layer(image, vis_params, name):
    """
    Get a tile layer URL from an Earth Engine image.
    
    Args:
        image: ee.Image - The image to display
        vis_params: dict - Visualization parameters
        name: str - Layer name
    
    Returns:
        tuple - (tile_url, name)
    """
    map_id_dict = image.getMapId(vis_params)
    return map_id_dict['tile_fetcher'].url_format, name


def create_folium_map(center_lat, center_lon, zoom=12):
    """
    Create a Folium map centered on given coordinates.
    
    Args:
        center_lat: float - Center latitude
        center_lon: float - Center longitude
        zoom: int - Zoom level
    
    Returns:
        folium.Map
    """
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri Satellite'
    )
    
    # Add a marker at center
    folium.Marker(
        [center_lat, center_lon],
        popup=f"Analysis Center: {center_lat:.4f}°N, {center_lon:.4f}°E",
        icon=folium.Icon(color='green', icon='tree-conifer', prefix='fa')
    ).add_to(m)
    
    return m


def add_ee_layer(folium_map, image, vis_params, name, opacity=0.8):
    """
    Add an Earth Engine image layer to a Folium map.
    
    Args:
        folium_map: folium.Map - The map to add the layer to
        image: ee.Image - The Earth Engine image
        vis_params: dict - Visualization parameters
        name: str - Layer name
        opacity: float - Layer opacity (0-1)
    """
    try:
        map_id_dict = image.getMapId(vis_params)
        tile_url = map_id_dict['tile_fetcher'].url_format
        
        folium.TileLayer(
            tiles=tile_url,
            attr='Google Earth Engine',
            name=name,
            overlay=True,
            control=True,
            opacity=opacity,
            show=True  # Make sure layer is shown by default
        ).add_to(folium_map)
        
        return True
    except Exception as e:
        st.warning(f"Could not load layer '{name}': {str(e)}")
        return False


def display_degradation_alert(ndvi_change_pct):
    """
    Display degradation alert based on NDVI change.
    
    Args:
        ndvi_change_pct: float - Percentage change in NDVI
    """
    if ndvi_change_pct < -10:
        st.markdown(f"""
        <div class="alert-box alert-danger">
            <h3>🚨 DEGRADATION ALERT</h3>
            <p style="font-size: 1.3rem;">
                <strong>Significant vegetation loss detected!</strong><br>
                NDVI has dropped by <strong>{abs(ndvi_change_pct):.1f}%</strong>
            </p>
            <p>This indicates potential forest degradation, deforestation, or environmental stress in the selected area.</p>
        </div>
        """, unsafe_allow_html=True)
    elif ndvi_change_pct < -5:
        st.markdown(f"""
        <div class="alert-box alert-warning">
            <h3>⚠️ MODERATE CHANGE</h3>
            <p style="font-size: 1.2rem;">
                NDVI has decreased by <strong>{abs(ndvi_change_pct):.1f}%</strong>
            </p>
            <p>Some vegetation change detected. Continue monitoring this area.</p>
        </div>
        """, unsafe_allow_html=True)
    elif ndvi_change_pct >= 0:
        st.markdown(f"""
        <div class="alert-box alert-success">
            <h3>✅ FOREST HEALTH STABLE</h3>
            <p style="font-size: 1.2rem;">
                NDVI has <strong>{'increased' if ndvi_change_pct > 0 else 'remained stable'}</strong>
                {f'by {ndvi_change_pct:.1f}%' if ndvi_change_pct > 0 else ''}
            </p>
            <p>The forest appears healthy with no significant degradation.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="alert-box alert-success">
            <h3>✅ MINOR CHANGE</h3>
            <p style="font-size: 1.2rem;">
                NDVI has changed by <strong>{ndvi_change_pct:.1f}%</strong>
            </p>
            <p>Change is within normal seasonal variation.</p>
        </div>
        """, unsafe_allow_html=True)


def create_ndvi_trend_chart(timeseries_data, title="NDVI Trend Over Time"):
    """
    Create an interactive NDVI trend line chart.
    
    Args:
        timeseries_data: list - List of dicts with 'month' and 'ndvi' keys
        title: str - Chart title
    
    Returns:
        plotly figure
    """
    if not timeseries_data:
        return None
    
    df = pd.DataFrame(timeseries_data)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['month'],
        y=df['ndvi'],
        mode='lines+markers',
        name='NDVI',
        line=dict(color='#2e7d32', width=3),
        marker=dict(size=10, color='#1a5f2a'),
        fill='tozeroy',
        fillcolor='rgba(46, 125, 50, 0.2)'
    ))
    
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=20, color='#1a5f2a')
        ),
        xaxis_title="Month",
        yaxis_title="NDVI Value",
        yaxis=dict(range=[0, 1]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Arial", size=12),
        hovermode='x unified'
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')
    
    return fig


def create_ndvi_colorbar():
    """Create a custom NDVI colorbar legend as HTML."""
    return """
    <div style="padding: 10px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 10px 0;">
        <h4 style="margin: 0 0 10px 0; color: #333;">NDVI Legend</h4>
        <div style="display: flex; align-items: center; height: 20px; border-radius: 4px; overflow: hidden;">
            <div style="flex: 1; background: #d73027; height: 100%;"></div>
            <div style="flex: 1; background: #fc8d59; height: 100%;"></div>
            <div style="flex: 1; background: #fee08b; height: 100%;"></div>
            <div style="flex: 1; background: #d9ef8b; height: 100%;"></div>
            <div style="flex: 1; background: #91cf60; height: 100%;"></div>
            <div style="flex: 1; background: #1a9850; height: 100%;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #666; margin-top: 5px;">
            <span>0.0</span>
            <span>0.2</span>
            <span>0.4</span>
            <span>0.6</span>
            <span>0.8</span>
        </div>
        <div style="font-size: 11px; color: #888; margin-top: 5px;">
            Low vegetation → High vegetation
        </div>
    </div>
    """


def generate_forest_health_report(api_key, location_name, lat, lon, buffer_km,
                                   year1, year2, start_month, end_month,
                                   mean_ndvi1, mean_ndvi2, ndvi_change_pct, timeseries_data):
    """
    Generate a professional forest health report using Google Gemini AI.
    
    Args:
        api_key: str - Gemini API key
        location_name: str - Name of the location
        lat, lon: float - Coordinates
        buffer_km: int - Analysis radius
        year1, year2: int - Comparison years
        start_month, end_month: int - Analysis period months
        mean_ndvi1, mean_ndvi2: float - Mean NDVI values
        ndvi_change_pct: float - Percentage change
        timeseries_data: list - Monthly NDVI data
    
    Returns:
        str - Generated report text
    """
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Prepare trend description
        trend_desc = ""
        if timeseries_data:
            trend_desc = f"Monthly NDVI values for {year2}: " + ", ".join(
                [f"{d['month']}: {d['ndvi']}" for d in timeseries_data]
            )
        
        # Determine health status
        if ndvi_change_pct < -10:
            status = "CRITICAL - Significant Degradation Detected"
        elif ndvi_change_pct < -5:
            status = "WARNING - Moderate Vegetation Loss"
        elif ndvi_change_pct < 0:
            status = "STABLE - Minor Changes Within Normal Range"
        else:
            status = "HEALTHY - Vegetation Stable or Improving"
        
        month_names = {1: "January", 2: "February", 3: "March", 4: "April", 
                      5: "May", 6: "June", 7: "July", 8: "August",
                      9: "September", 10: "October", 11: "November", 12: "December"}
        
        # Format NDVI values properly
        ndvi1_str = f"{mean_ndvi1:.4f}" if mean_ndvi1 else "N/A"
        ndvi2_str = f"{mean_ndvi2:.4f}" if mean_ndvi2 else "N/A"
        
        prompt = f"""You are an expert environmental scientist specializing in forest conservation and satellite-based monitoring in Nepal. Generate a professional forest health assessment report based on the following satellite data analysis:

**ANALYSIS PARAMETERS:**
- Location: {location_name}
- Coordinates: {lat:.4f}°N, {lon:.4f}°E
- Analysis Radius: {buffer_km} km
- Analysis Period: {month_names[start_month]} to {month_names[end_month]}
- Comparison Years: {year1} vs {year2}

**SATELLITE DATA (Sentinel-2 NDVI Analysis):**
- Mean NDVI {year1}: {ndvi1_str}
- Mean NDVI {year2}: {ndvi2_str}
- NDVI Change: {ndvi_change_pct:+.2f}%
- Status: {status}
{f"- {trend_desc}" if trend_desc else ""}

**INSTRUCTIONS:**
Write a comprehensive but concise forest health report with the following sections:
1. **Executive Summary** (2-3 sentences)
2. **Key Findings** (bullet points)
3. **Vegetation Health Analysis** (based on NDVI values)
4. **Risk Assessment** (if degradation detected)
5. **Recommendations** (actionable steps for forest management)

Use professional scientific language. Include specific numbers from the data. Keep the report under 400 words.
"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error generating report: {str(e)}"


def display_ai_report(report_text):
    """Display the AI-generated report in a professional format."""
    st.markdown("""
    <style>
        .report-container {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 2rem;
            border-radius: 15px;
            margin: 1rem 0;
            border-left: 5px solid #1a5f2a;
        }
        .report-title {
            color: #1a5f2a;
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .report-content {
            color: #333;
            line-height: 1.8;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="report-container">
        <div class="report-title">📋 AI Forest Health Report</div>
        <div class="report-content">
            {report_text.replace(chr(10), '<br>')}
        </div>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main application function."""
    
    # Header
    st.markdown('<h1 class="main-header">🌲 Nepal Forest Health Monitor</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Satellite-based forest monitoring using NDVI analysis</p>', unsafe_allow_html=True)
    
    # Initialize GEE from environment variables
    if not initialize_gee():
        st.stop()
    
    # Sidebar controls
    with st.sidebar:
        st.header("📍 Location Selection")
        
        location_method = st.radio(
            "Select location by:",
            ["District/Forest", "Coordinates"],
            horizontal=True
        )
        
        if location_method == "District/Forest":
            all_locations = get_all_locations()
            location_names = sorted(all_locations.keys())
            
            # Add search functionality
            search_query = st.text_input("🔍 Search location", placeholder="Type to search...")
            
            if search_query:
                filtered_locations = search_location(search_query)
            else:
                filtered_locations = location_names
            
            if filtered_locations:
                selected_location = st.selectbox(
                    "Select a location:",
                    filtered_locations,
                    index=0
                )
                lat, lon = get_location_coords(selected_location)
            else:
                st.warning("No matching locations found")
                lat, lon = NEPAL_CENTER['lat'], NEPAL_CENTER['lon']
                selected_location = "Unknown Location"
        else:
            col1, col2 = st.columns(2)
            with col1:
                lat = st.number_input("Latitude", value=NEPAL_CENTER['lat'], 
                                     min_value=26.0, max_value=31.0, step=0.0001,
                                     format="%.4f")
            with col2:
                lon = st.number_input("Longitude", value=NEPAL_CENTER['lon'],
                                     min_value=80.0, max_value=89.0, step=0.0001,
                                     format="%.4f")
            selected_location = f"Custom Location ({lat:.4f}°N, {lon:.4f}°E)"
        
        # Buffer size
        buffer_km = st.slider("Analysis radius (km)", min_value=1, max_value=20, value=5)
        
        st.divider()
        st.header("📅 Time Period Selection")
        
        # Year selection
        current_year = datetime.now().year
        col1, col2 = st.columns(2)
        with col1:
            year1 = st.selectbox("Year 1 (Earlier)", 
                                range(2019, current_year), 
                                index=3)  # Default to 2022
        with col2:
            year2 = st.selectbox("Year 2 (Later)", 
                                range(2019, current_year + 1),
                                index=4)  # Default to 2023
        
        # Month range selection (avoid monsoon)
        st.caption("💡 Jan-March recommended to avoid monsoon clouds")
        col1, col2 = st.columns(2)
        with col1:
            start_month = st.selectbox("Start Month", range(1, 13), index=0,
                                      format_func=lambda x: datetime(2000, x, 1).strftime('%B'))
        with col2:
            end_month = st.selectbox("End Month", range(1, 13), index=2,
                                    format_func=lambda x: datetime(2000, x, 1).strftime('%B'))
        
        st.divider()
        
        # AI Report toggle (API key from env)
        generate_report = st.checkbox("🤖 Generate AI Forest Health Report", value=True,
                                     help="Uses Gemini API from .env file")
        
        # Analyze button
        analyze_button = st.button("🔍 Analyze Forest Health", type="primary", use_container_width=True)
    
    # Main content area
    if analyze_button:
        with st.spinner("🛰️ Fetching satellite imagery and analyzing..."):
            try:
                # Create AOI
                aoi = create_aoi_from_point(lat, lon, buffer_km)
                
                # Format dates
                start_date1 = f"{year1}-{start_month:02d}-01"
                end_date1 = f"{year1}-{end_month:02d}-28"
                start_date2 = f"{year2}-{start_month:02d}-01"
                end_date2 = f"{year2}-{end_month:02d}-28"
                
                # Get composites
                progress = st.progress(0, text="Loading Year 1 imagery...")
                composite1 = get_sentinel_composite(aoi, start_date1, end_date1)
                
                progress.progress(30, text="Loading Year 2 imagery...")
                composite2 = get_sentinel_composite(aoi, start_date2, end_date2)
                
                # Calculate mean NDVI
                progress.progress(50, text="Calculating NDVI values...")
                mean_ndvi1 = compute_mean_ndvi(composite1, aoi)
                mean_ndvi2 = compute_mean_ndvi(composite2, aoi)
                
                progress.progress(70, text="Creating visualizations...")
                
                # Calculate change
                if mean_ndvi1 and mean_ndvi2 and mean_ndvi1 != 0:
                    ndvi_change_pct = ((mean_ndvi2 - mean_ndvi1) / mean_ndvi1) * 100
                else:
                    ndvi_change_pct = 0
                
                progress.progress(100, text="Analysis complete!")
                progress.empty()
                
                # Display results
                st.success("✅ Analysis Complete!")
                
                # Metrics row
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(
                        label=f"📊 Mean NDVI ({year1})",
                        value=f"{mean_ndvi1:.4f}" if mean_ndvi1 else "N/A"
                    )
                with col2:
                    st.metric(
                        label=f"📊 Mean NDVI ({year2})",
                        value=f"{mean_ndvi2:.4f}" if mean_ndvi2 else "N/A"
                    )
                with col3:
                    st.metric(
                        label="📈 Change",
                        value=f"{ndvi_change_pct:+.1f}%",
                        delta=f"{ndvi_change_pct:.1f}%"
                    )
                with col4:
                    st.metric(
                        label="📍 Location",
                        value=f"{lat:.2f}°N, {lon:.2f}°E"
                    )
                
                # Degradation Alert
                st.subheader("🚦 Forest Health Status")
                display_degradation_alert(ndvi_change_pct)
                
                # NDVI Maps in tabs
                st.subheader("🗺️ NDVI Comparison Maps")
                st.info(f"📍 Analyzing {buffer_km}km radius around the selected location")
                
                vis_params = get_ndvi_visualization_params()
                
                # Create tabs for year comparison
                tab1, tab2 = st.tabs([f"📅 NDVI {year1}", f"📅 NDVI {year2}"])
                
                with tab1:
                    st.caption(f"NDVI visualization for {year1} ({datetime(2000, start_month, 1).strftime('%B')} - {datetime(2000, end_month, 1).strftime('%B')})")
                    m1 = create_folium_map(lat, lon, zoom=11)
                    layer_added1 = add_ee_layer(m1, composite1.select('NDVI'), vis_params, f'NDVI {year1}')
                    
                    # Add AOI circle (transparent with yellow border)
                    folium.Circle(
                        location=[lat, lon],
                        radius=buffer_km * 1000,  # Convert km to meters
                        color='#FFD700',  # Gold/Yellow border
                        fill=False,  # No fill - transparent
                        weight=3,
                        opacity=1.0,
                        popup=f"Analysis Area: {buffer_km}km radius"
                    ).add_to(m1)
                    
                    folium.LayerControl(collapsed=False).add_to(m1)
                    st_folium(m1, width=None, height=500, returned_objects=[], use_container_width=True)
                    
                    if layer_added1:
                        st.markdown(create_ndvi_colorbar(), unsafe_allow_html=True)
                    else:
                        st.warning("NDVI layer could not be loaded. Try selecting a different date range or location.")
                
                with tab2:
                    st.caption(f"NDVI visualization for {year2} ({datetime(2000, start_month, 1).strftime('%B')} - {datetime(2000, end_month, 1).strftime('%B')})")
                    m2 = create_folium_map(lat, lon, zoom=11)
                    layer_added2 = add_ee_layer(m2, composite2.select('NDVI'), vis_params, f'NDVI {year2}')
                    
                    # Add AOI circle (transparent with yellow border)
                    folium.Circle(
                        location=[lat, lon],
                        radius=buffer_km * 1000,
                        color='#FFD700',  # Gold/Yellow border
                        fill=False,  # No fill - transparent
                        weight=3,
                        opacity=1.0,
                        popup=f"Analysis Area: {buffer_km}km radius"
                    ).add_to(m2)
                    
                    folium.LayerControl(collapsed=False).add_to(m2)
                    st_folium(m2, width=None, height=500, returned_objects=[], use_container_width=True)
                    
                    if layer_added2:
                        st.markdown(create_ndvi_colorbar(), unsafe_allow_html=True)
                    else:
                        st.warning("NDVI layer could not be loaded. Try selecting a different date range or location.")
                
                # NDVI Trend Chart
                st.subheader("📈 NDVI Monthly Trend")
                
                with st.spinner("Calculating monthly NDVI values..."):
                    # Get timeseries for the more recent year
                    timeseries = calculate_ndvi_timeseries(aoi, year2, start_month, end_month)
                    
                    if timeseries:
                        fig = create_ndvi_trend_chart(
                            timeseries, 
                            f"Monthly NDVI Trend ({year2})"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Unable to generate trend chart. Limited data available for the selected period.")
                
                # Additional info
                with st.expander("ℹ️ About NDVI"):
                    st.markdown("""
                    **Normalized Difference Vegetation Index (NDVI)** is a measure of vegetation health and density.
                    
                    - **NDVI Range**: -1 to 1
                    - **High NDVI (0.6-0.9)**: Dense, healthy vegetation (dark green)
                    - **Medium NDVI (0.3-0.6)**: Moderate vegetation (light green)
                    - **Low NDVI (0-0.3)**: Sparse vegetation, bare soil (yellow/brown)
                    - **Negative NDVI**: Water, snow, or clouds (blue/gray)
                    
                    **Degradation Alert Thresholds:**
                    - 🔴 **>10% decrease**: Significant degradation - requires attention
                    - 🟡 **5-10% decrease**: Moderate change - continue monitoring
                    - 🟢 **<5% change**: Normal variation - forest appears healthy
                    """)
                
                # AI-Generated Professional Report
                if generate_report:
                    st.divider()
                    st.subheader("📋 AI Forest Health Report")
                    
                    # Get API key from environment
                    gemini_api_key = os.getenv('GEMINI_API_KEY')
                    
                    if gemini_api_key and gemini_api_key != "your_gemini_api_key_here":
                        with st.spinner("🤖 Generating professional report with AI..."):
                            report = generate_forest_health_report(
                                api_key=gemini_api_key,
                                location_name=selected_location,
                                lat=lat,
                                lon=lon,
                                buffer_km=buffer_km,
                                year1=year1,
                                year2=year2,
                                start_month=start_month,
                                end_month=end_month,
                                mean_ndvi1=mean_ndvi1,
                                mean_ndvi2=mean_ndvi2,
                                ndvi_change_pct=ndvi_change_pct,
                                timeseries_data=timeseries if 'timeseries' in dir() else []
                            )
                            
                            if report and not report.startswith("Error"):
                                # Format the report nicely
                                st.markdown("""
                                <style>
                                    .ai-report {
                                        background: linear-gradient(135deg, #1a472a 0%, #2d5a3d 100%);
                                        color: white;
                                        padding: 2rem;
                                        border-radius: 15px;
                                        margin: 1rem 0;
                                        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                                    }
                                    .ai-report h1, .ai-report h2, .ai-report h3, .ai-report h4 {
                                        color: #90EE90;
                                    }
                                    .ai-report strong {
                                        color: #FFD700;
                                    }
                                </style>
                                """, unsafe_allow_html=True)
                                
                                st.markdown(f'<div class="ai-report">{report}</div>', unsafe_allow_html=True)
                                
                                # Download button for report
                                st.download_button(
                                    label="📥 Download Report",
                                    data=report,
                                    file_name=f"forest_health_report_{selected_location.replace(' ', '_')}_{year2}.txt",
                                    mime="text/plain"
                                )
                            else:
                                st.error(report)
                    else:
                        st.warning("⚠️ GEMINI_API_KEY not found in .env file. Please add your API key to generate AI reports.")
                
            except Exception as e:
                st.error(f"Error during analysis: {str(e)}")
                st.info("Try adjusting the date range or selecting a different location.")
    
    else:
        # Default map when no analysis is running
        st.info("👈 Configure your analysis parameters in the sidebar and click 'Analyze Forest Health'")
        
        # Show default Nepal map (without center marker for cleaner view)
        m = folium.Map(
            location=[NEPAL_CENTER['lat'], NEPAL_CENTER['lon']],
            zoom_start=NEPAL_CENTER['zoom'],
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri Satellite'
        )
        st_folium(m, width=None, height=500, returned_objects=[], use_container_width=True)
        
        # Info cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("🛰️ **Sentinel-2 Imagery**\nHigh-resolution satellite data updated every 5 days")
        with col2:
            st.info("🌲 **NDVI Analysis**\nQuantify vegetation health and detect changes")
        with col3:
            st.info("🚨 **Smart Alerts**\nAutomatic detection of forest degradation")


if __name__ == "__main__":
    main()
