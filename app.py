"""
Forest Health Monitoring App — Himalayan Carbon AI
v2.0 — Adds:
  Feature 3: Multi-year NDVI trend (2017–present)
  Feature 4: Carbon stock estimation (tonnes CO2e/ha)
  Feature 5: GeoJSON boundary upload
  Feature 8: Professional PDF export (ReportLab)
"""

import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os, json, io, math, tempfile
from dotenv import load_dotenv

load_dotenv()

# ── Utility imports ────────────────────────────────────────────────────────────
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

# ── ReportLab imports ──────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus import Image as RLImage
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Design constants ──────────────────────────────────────────────────────────
DARK_GREEN  = "#1A4731"
MID_GREEN   = "#2D6A4F"
ACCENT      = "#40916C"
LIGHT_GREEN = "#D8F3DC"
PALE_GREEN  = "#F0FBF4"
WHITE       = "#FFFFFF"
DARK_GRAY   = "#2C2C2C"

# ReportLab colors
RL_DARK_GREEN  = colors.HexColor("#1A4731")
RL_MID_GREEN   = colors.HexColor("#2D6A4F")
RL_ACCENT      = colors.HexColor("#40916C")
RL_LIGHT_GREEN = colors.HexColor("#D8F3DC")
RL_PALE_GREEN  = colors.HexColor("#F0FBF4")
RL_GOLD        = colors.HexColor("#B7950B")
RL_DARK_GRAY   = colors.HexColor("#2C2C2C")
RL_MED_GRAY    = colors.HexColor("#888888")
RL_RISK_RED    = colors.HexColor("#C0392B")
RL_RISK_ORANGE = colors.HexColor("#E67E22")
RL_RISK_GREEN  = colors.HexColor("#27AE60")

# ── Nepal-specific carbon constants (FAO/ICIMOD literature values) ────────────
# Source: FAO Nepal Forest Reference Level 2017, ICIMOD biomass studies
NEPAL_FOREST_CARBON = {
    "tropical_broadleaf": {
        "agb_tonnes_ha": 180,   # Above-ground biomass tonnes/ha
        "bgb_ratio": 0.26,      # Below-ground biomass ratio (IPCC Tier 1)
        "carbon_fraction": 0.47, # Carbon fraction of dry matter
        "co2_factor": 3.667,    # CO2 equivalent factor
    },
    "subtropical_broadleaf": {
        "agb_tonnes_ha": 150,
        "bgb_ratio": 0.28,
        "carbon_fraction": 0.47,
        "co2_factor": 3.667,
    },
    "temperate_broadleaf": {
        "agb_tonnes_ha": 120,
        "bgb_ratio": 0.30,
        "carbon_fraction": 0.47,
        "co2_factor": 3.667,
    },
    "conifer": {
        "agb_tonnes_ha": 100,
        "bgb_ratio": 0.32,
        "carbon_fraction": 0.51,
        "co2_factor": 3.667,
    },
    "default": {
        "agb_tonnes_ha": 140,
        "bgb_ratio": 0.28,
        "carbon_fraction": 0.47,
        "co2_factor": 3.667,
    }
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Himalayan Carbon AI — Forest Monitor",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; color: {DARK_GRAY}; }}

  section[data-testid="stSidebar"] {{ background: {DARK_GREEN}; }}
  section[data-testid="stSidebar"] * {{ color: {WHITE} !important; }}
  section[data-testid="stSidebar"] .stSelectbox label,
  section[data-testid="stSidebar"] .stSlider label,
  section[data-testid="stSidebar"] .stRadio label,
  section[data-testid="stSidebar"] .stTextInput label,
  section[data-testid="stSidebar"] .stFileUploader label {{
    color: {LIGHT_GREEN} !important; font-size:0.82rem; font-weight:600;
    letter-spacing:0.05em; text-transform:uppercase;
  }}
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3 {{
    color:{WHITE} !important; font-family:'DM Serif Display',serif !important;
    font-size:1rem !important; border-bottom:1px solid rgba(216,243,220,0.25);
    padding-bottom:0.4rem; margin-top:1.2rem !important;
  }}
  section[data-testid="stSidebar"] .stButton > button {{
    background:{ACCENT} !important; color:{WHITE} !important; font-weight:700;
    border:none; border-radius:6px; padding:0.65rem 1.5rem;
    font-size:0.92rem; width:100%; margin-top:0.5rem; transition:background 0.2s;
  }}
  section[data-testid="stSidebar"] .stButton > button:hover {{ background:{MID_GREEN} !important; }}
  section[data-testid="stSidebar"] hr {{ border-color:rgba(216,243,220,0.2) !important; }}

  .main .block-container {{ padding-top:1.5rem; padding-bottom:3rem; max-width:1400px; }}

  .hca-header {{
    background:linear-gradient(135deg,{DARK_GREEN} 0%,{MID_GREEN} 60%,{ACCENT} 100%);
    border-radius:12px; padding:2rem 2.5rem; margin-bottom:1.5rem;
    display:flex; justify-content:space-between; align-items:center;
  }}
  .hca-header-title {{ font-family:'DM Serif Display',serif; font-size:2.1rem; color:{WHITE}; margin:0; }}
  .hca-header-sub {{ color:{LIGHT_GREEN}; font-size:0.88rem; margin-top:0.3rem; letter-spacing:0.04em; }}
  .hca-badge {{
    background:rgba(255,255,255,0.12); border:1px solid rgba(216,243,220,0.4);
    border-radius:8px; padding:0.6rem 1.1rem; color:{LIGHT_GREEN}; font-size:0.78rem;
    font-weight:600; text-align:center; letter-spacing:0.06em; text-transform:uppercase;
  }}

  .section-heading {{
    font-family:'DM Serif Display',serif; font-size:1.25rem; color:{DARK_GREEN};
    border-bottom:2px solid {LIGHT_GREEN}; padding-bottom:0.4rem; margin:1.6rem 0 0.8rem 0;
  }}

  .status-card {{ border-radius:10px; padding:1.2rem 1.5rem; margin:1rem 0; display:flex; align-items:flex-start; gap:1rem; }}
  .status-critical {{ background:#FFF0F0; border-left:5px solid #C0392B; }}
  .status-warning  {{ background:#FFFBF0; border-left:5px solid #E67E22; }}
  .status-stable   {{ background:#F0FBF4; border-left:5px solid {ACCENT}; }}
  .status-healthy  {{ background:#F0FBF4; border-left:5px solid {MID_GREEN}; }}
  .status-icon {{ font-size:2rem; line-height:1; }}
  .status-title {{ font-weight:700; font-size:1.05rem; margin-bottom:0.2rem; }}
  .status-desc {{ font-size:0.87rem; color:#555; line-height:1.5; }}

  /* Carbon box */
  .carbon-box {{
    background:linear-gradient(135deg, {DARK_GREEN} 0%, {MID_GREEN} 100%);
    border-radius:12px; padding:1.5rem 2rem; margin:1rem 0; color:{WHITE};
  }}
  .carbon-title {{ font-family:'DM Serif Display',serif; font-size:1.1rem; color:{LIGHT_GREEN}; margin-bottom:1rem; }}
  .carbon-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; }}
  .carbon-cell {{ background:rgba(255,255,255,0.1); border-radius:8px; padding:0.8rem; text-align:center; }}
  .carbon-label {{ font-size:0.65rem; text-transform:uppercase; letter-spacing:0.08em; color:{LIGHT_GREEN}; margin-bottom:4px; font-weight:700; }}
  .carbon-val {{ font-family:'DM Serif Display',serif; font-size:1.6rem; }}
  .carbon-unit {{ font-size:0.7rem; color:rgba(216,243,220,0.7); margin-top:2px; }}
  .carbon-disclaimer {{ font-size:0.72rem; color:rgba(216,243,220,0.7); margin-top:1rem; font-style:italic; }}

  /* Report */
  .report-outer {{ background:{PALE_GREEN}; border:1px solid {LIGHT_GREEN}; border-radius:12px; margin:1.5rem 0; overflow:hidden; }}
  .report-header {{ background:{DARK_GREEN}; padding:1.4rem 2rem; display:flex; justify-content:space-between; align-items:center; }}
  .report-header-title {{ font-family:'DM Serif Display',serif; color:{WHITE}; font-size:1.3rem; margin:0; }}
  .report-header-meta {{ color:{LIGHT_GREEN}; font-size:0.78rem; text-align:right; }}
  .report-body {{ padding:1.8rem 2rem; }}
  .report-section-title {{ font-family:'DM Serif Display',serif; color:{MID_GREEN}; font-size:1.05rem; margin:1.4rem 0 0.5rem 0; border-left:4px solid {ACCENT}; padding-left:0.7rem; }}
  .report-callout {{ background:{WHITE}; border:1px solid {LIGHT_GREEN}; border-radius:8px; padding:1rem 1.3rem; margin:0.8rem 0; font-size:0.9rem; line-height:1.7; color:{DARK_GRAY}; }}
  .report-data-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:0.8rem; margin:0.8rem 0; }}
  .report-data-cell {{ background:{WHITE}; border:1px solid {LIGHT_GREEN}; border-radius:8px; padding:0.75rem 1rem; text-align:center; }}
  .rdc-label {{ font-size:0.7rem; text-transform:uppercase; letter-spacing:0.07em; color:{ACCENT}; font-weight:700; }}
  .rdc-value {{ font-family:'DM Serif Display',serif; font-size:1.5rem; color:{DARK_GREEN}; }}
  .report-footer {{ background:{DARK_GREEN}; padding:0.9rem 2rem; display:flex; justify-content:space-between; align-items:center; }}
  .report-footer-text {{ color:{LIGHT_GREEN}; font-size:0.74rem; }}
  .integrity-seal {{ background:{ACCENT}; color:{WHITE}; font-size:0.7rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; padding:0.35rem 0.8rem; border-radius:4px; }}

  .info-card {{ background:{WHITE}; border:1px solid {LIGHT_GREEN}; border-radius:10px; padding:1.2rem 1.4rem; margin:0.5rem 0; box-shadow:0 1px 4px rgba(26,71,49,0.05); }}
  .info-card-icon {{ font-size:1.6rem; margin-bottom:0.4rem; }}
  .info-card-title {{ font-weight:700; color:{DARK_GREEN}; margin-bottom:0.3rem; }}
  .info-card-desc {{ font-size:0.84rem; color:#555; line-height:1.5; }}

  .ndvi-bar-wrap {{ background:{WHITE}; border:1px solid {LIGHT_GREEN}; border-radius:8px; padding:0.8rem 1rem; margin:0.6rem 0; }}

  .stTabs [data-baseweb="tab"] {{ font-weight:600; color:{ACCENT}; }}
  .stTabs [aria-selected="true"] {{ color:{DARK_GREEN} !important; border-bottom-color:{DARK_GREEN} !important; }}
  div[data-testid="stExpander"] summary {{ font-weight:600; color:{DARK_GREEN}; }}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# GEE INIT
# ══════════════════════════════════════════════════════════════════════════════
def initialize_gee():
    project_id = os.getenv('GEE_PROJECT_ID')
    if not project_id:
        st.error("❌ GEE_PROJECT_ID not found in .env file")
        return False
    try:
        ee.Initialize(project=project_id)
        return True
    except Exception as e:
        st.error(f"❌ Earth Engine init failed: {str(e)}")
        st.info("Run `earthengine authenticate` in your terminal first.")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 3 — MULTI-YEAR NDVI TREND
# ══════════════════════════════════════════════════════════════════════════════
def get_annual_ndvi(aoi, year, start_month, end_month):
    """Compute single mean NDVI for a given year over the season window."""
    start = f"{year}-{start_month:02d}-01"
    end   = f"{year}-{end_month:02d}-28"
    try:
        composite = get_sentinel_composite(aoi, start, end)
        ndvi = compute_mean_ndvi(composite, aoi)
        return ndvi
    except Exception:
        return None


def build_multiyear_trend(aoi, start_month, end_month, start_year=2019):
    """
    Collect annual mean NDVI from start_year to current year.
    Returns list of {year, ndvi} dicts.
    Note: Sentinel-2 SR data is available from 2017 but we default to 2019
    for more reliable data coverage across Nepal.
    """
    current_year = datetime.now().year
    results = []
    for yr in range(start_year, current_year + 1):
        ndvi = get_annual_ndvi(aoi, yr, start_month, end_month)
        if ndvi is not None:
            results.append({"year": yr, "ndvi": round(ndvi, 4)})
    return results


def create_multiyear_chart(trend_data, location_name, forest_type="default"):
    """
    Plot multi-year NDVI trend with:
    - Annual NDVI line
    - Degradation threshold bands
    - Trend direction annotation
    """
    if not trend_data or len(trend_data) < 2:
        return None

    df = pd.DataFrame(trend_data)
    years = df['year'].tolist()
    ndvi_vals = df['ndvi'].tolist()

    # Linear trend
    n = len(years)
    x_mean = sum(years) / n
    y_mean = sum(ndvi_vals) / n
    slope = sum((years[i] - x_mean) * (ndvi_vals[i] - y_mean) for i in range(n)) / \
            sum((years[i] - x_mean) ** 2 for i in range(n))
    intercept = y_mean - slope * x_mean
    trend_line = [slope * yr + intercept for yr in years]
    trend_direction = "improving 📈" if slope > 0.001 else ("declining 📉" if slope < -0.001 else "stable ➡️")

    fig = go.Figure()

    # Healthy band
    fig.add_hrect(y0=0.6, y1=1.0, fillcolor="rgba(39,174,96,0.06)", line_width=0,
                  annotation_text="Healthy", annotation_position="top right",
                  annotation_font_size=10, annotation_font_color=ACCENT)
    # Moderate band
    fig.add_hrect(y0=0.3, y1=0.6, fillcolor="rgba(230,126,34,0.05)", line_width=0)
    # Degraded band
    fig.add_hrect(y0=0.0, y1=0.3, fillcolor="rgba(192,57,43,0.05)", line_width=0,
                  annotation_text="Degraded", annotation_position="bottom right",
                  annotation_font_size=10, annotation_font_color="#C0392B")

    # Trend line
    fig.add_trace(go.Scatter(
        x=years, y=trend_line,
        mode='lines', name='Trend',
        line=dict(color='rgba(64,145,108,0.4)', width=2, dash='dash'),
        showlegend=True
    ))

    # NDVI line
    fig.add_trace(go.Scatter(
        x=years, y=ndvi_vals,
        mode='lines+markers',
        name='Annual NDVI',
        line=dict(color=ACCENT, width=3),
        marker=dict(size=10, color=DARK_GREEN, line=dict(color=WHITE, width=2)),
        fill='tozeroy',
        fillcolor='rgba(64,145,108,0.12)',
        hovertemplate='<b>%{x}</b><br>NDVI: %{y:.4f}<extra></extra>'
    ))

    fig.update_layout(
        title=dict(
            text=f"Multi-Year NDVI Trend — {location_name}  <span style='font-size:13px;color:#888'>({trend_direction})</span>",
            font=dict(size=16, color=DARK_GREEN, family="DM Serif Display")
        ),
        xaxis=dict(title="Year", tickmode='linear', dtick=1,
                   showgrid=True, gridcolor='rgba(64,145,108,0.1)'),
        yaxis=dict(title="Mean NDVI", range=[0, 1],
                   showgrid=True, gridcolor='rgba(64,145,108,0.1)'),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="DM Sans", size=12),
        hovermode='x unified',
        margin=dict(l=40, r=20, t=60, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    return fig, slope, trend_direction


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 4 — CARBON STOCK ESTIMATION
# ══════════════════════════════════════════════════════════════════════════════
def estimate_carbon_stock(mean_ndvi, area_ha, forest_type="default", ndvi_change_pct=None):
    """
    Estimate carbon stock using NDVI-scaled biomass approach.

    Method:
    1. Base AGB from Nepal forest type literature values (FAO/ICIMOD)
    2. Scale AGB by NDVI ratio (NDVI / 0.75 reference for healthy Himalayan forest)
    3. Add BGB using IPCC Tier 1 root-to-shoot ratios
    4. Convert to carbon using standard carbon fraction
    5. Convert to CO2e

    IMPORTANT: These are satellite-based estimates only.
    They are NOT verified carbon credits. Field calibration required.
    """
    if mean_ndvi is None or area_ha <= 0:
        return None

    params = NEPAL_FOREST_CARBON.get(forest_type, NEPAL_FOREST_CARBON["default"])

    # NDVI-scaled AGB (reference NDVI = 0.75 for healthy Himalayan broadleaf)
    ndvi_ref = 0.75
    ndvi_scale = max(0.1, min(1.5, mean_ndvi / ndvi_ref))
    agb_ha = params["agb_tonnes_ha"] * ndvi_scale

    # Below-ground biomass
    bgb_ha = agb_ha * params["bgb_ratio"]

    # Total biomass per ha
    total_biomass_ha = agb_ha + bgb_ha

    # Carbon stock per ha
    carbon_ha = total_biomass_ha * params["carbon_fraction"]

    # CO2 equivalent per ha
    co2e_ha = carbon_ha * params["co2_factor"]

    # Total over area
    total_carbon = carbon_ha * area_ha
    total_co2e   = co2e_ha * area_ha

    result = {
        "agb_ha":           round(agb_ha, 1),
        "bgb_ha":           round(bgb_ha, 1),
        "total_biomass_ha": round(total_biomass_ha, 1),
        "carbon_ha":        round(carbon_ha, 1),
        "co2e_ha":          round(co2e_ha, 1),
        "total_carbon_t":   round(total_carbon, 0),
        "total_co2e_t":     round(total_co2e, 0),
        "area_ha":          round(area_ha, 1),
        "forest_type":      forest_type,
    }

    # If we have change data, estimate carbon change
    if ndvi_change_pct is not None:
        change_fraction = ndvi_change_pct / 100
        co2e_change = total_co2e * change_fraction
        result["co2e_change_t"]   = round(co2e_change, 0)
        result["co2e_change_pct"] = round(ndvi_change_pct, 1)

    return result


def render_carbon_box(carbon_data):
    """Render the carbon stock estimation panel."""
    if not carbon_data:
        return

    change_html = ""
    if "co2e_change_t" in carbon_data:
        change_val = carbon_data["co2e_change_t"]
        change_color = "#C0392B" if change_val < 0 else "#27AE60"
        change_sign  = "▼" if change_val < 0 else "▲"
        change_html = f"""
        <div class="carbon-cell">
          <div class="carbon-label">CO&#x2082;e Change</div>
          <div class="carbon-val" style="color:{change_color};">{change_sign} {abs(change_val):,.0f}</div>
          <div class="carbon-unit">tonnes CO&#x2082;e</div>
        </div>"""

    st.markdown(f"""
    <div class="carbon-box">
      <div class="carbon-title">🌿 Carbon Stock Estimate (Satellite-Based)</div>
      <div class="carbon-grid">
        <div class="carbon-cell">
          <div class="carbon-label">Above-Ground Biomass</div>
          <div class="carbon-val">{carbon_data['agb_ha']:,.0f}</div>
          <div class="carbon-unit">tonnes / ha</div>
        </div>
        <div class="carbon-cell">
          <div class="carbon-label">Total Carbon Stock</div>
          <div class="carbon-val">{carbon_data['total_carbon_t']:,.0f}</div>
          <div class="carbon-unit">tonnes C</div>
        </div>
        <div class="carbon-cell">
          <div class="carbon-label">Total CO&#x2082; Equivalent</div>
          <div class="carbon-val">{carbon_data['total_co2e_t']:,.0f}</div>
          <div class="carbon-unit">tonnes CO&#x2082;e</div>
        </div>
        {change_html}
      </div>
      <div class="carbon-disclaimer">
        ⚠️ Satellite-based estimates only · Based on Nepal FAO/ICIMOD literature values ·
        Forest type: {carbon_data['forest_type'].replace('_', ' ').title()} ·
        Area: {carbon_data['area_ha']:,.0f} ha ·
        Field calibration required before use in verified carbon projects
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 5 — GEOJSON BOUNDARY UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
def parse_geojson_upload(uploaded_file):
    """
    Parse uploaded GeoJSON file and extract:
    - ee.Geometry AOI
    - centroid lat/lon
    - area in hectares
    - feature name if present
    Returns (aoi_geometry, lat, lon, area_ha, name) or raises ValueError.
    """
    try:
        content = uploaded_file.read()
        data = json.loads(content)
    except Exception as e:
        raise ValueError(f"Could not parse file as JSON: {str(e)}")

    # Handle both FeatureCollection and single Feature/Geometry
    geom = None
    name = "Uploaded Boundary"

    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError("GeoJSON FeatureCollection has no features.")
        # Merge all features into one geometry
        if len(features) == 1:
            feat = features[0]
            geom = feat.get("geometry")
            props = feat.get("properties", {})
            name = props.get("name") or props.get("NAME") or props.get("forest_name") or "Uploaded Boundary"
        else:
            # Union all geometries
            ee_geoms = []
            for feat in features:
                g = feat.get("geometry")
                if g:
                    ee_geoms.append(ee.Geometry(g))
            if not ee_geoms:
                raise ValueError("No valid geometries found in FeatureCollection.")
            geom = None
            aoi = ee.Geometry.MultiPolygon([eg for eg in ee_geoms]).dissolve()
            # Get centroid
            centroid = aoi.centroid(maxError=1)
            coords = centroid.coordinates().getInfo()
            lon, lat = coords[0], coords[1]
            area_m2 = aoi.area(maxError=1).getInfo()
            area_ha = area_m2 / 10000
            return aoi, lat, lon, area_ha, "Uploaded Boundary (Multi-feature)"

    elif data.get("type") == "Feature":
        geom = data.get("geometry")
        props = data.get("properties", {})
        name = props.get("name") or props.get("NAME") or "Uploaded Boundary"

    elif data.get("type") in ["Polygon", "MultiPolygon", "Point"]:
        geom = data
    else:
        raise ValueError(f"Unsupported GeoJSON type: {data.get('type')}")

    if geom is None:
        raise ValueError("No geometry found in uploaded file.")

    try:
        aoi = ee.Geometry(geom)
        centroid = aoi.centroid(maxError=1)
        coords = centroid.coordinates().getInfo()
        lon, lat = coords[0], coords[1]
        area_m2 = aoi.area(maxError=1).getInfo()
        area_ha = area_m2 / 10000
        return aoi, lat, lon, area_ha, name
    except Exception as e:
        raise ValueError(f"Earth Engine could not process geometry: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 8 — PDF EXPORT (ReportLab)
# ══════════════════════════════════════════════════════════════════════════════
def build_pdf_report(
    report_data, location_name, lat, lon, buffer_km, area_ha,
    year1, year2, start_month, end_month,
    mean_ndvi1, mean_ndvi2, ndvi_change_pct,
    carbon_data, trend_data, timeseries_data,
    ndvi_chart_img_bytes=None
):
    """
    Generate a professional PDF report matching the HCA green color scheme.
    Returns bytes object ready for st.download_button.
    """
    month_names = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
                   7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
    month_short = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                   7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

    buffer = io.BytesIO()
    PAGE_W, PAGE_H = A4
    MARGIN = 20*mm

    # ── Styles ──
    def style(name, **kwargs):
        base = dict(fontName="Helvetica", fontSize=10, leading=14,
                    textColor=RL_DARK_GRAY, spaceAfter=4)
        base.update(kwargs)
        return ParagraphStyle(name, **base)

    S = {
        "title":        style("title",   fontName="Helvetica-Bold", fontSize=22,
                               textColor=colors.white, alignment=TA_LEFT, spaceAfter=4),
        "subtitle":     style("subtitle", fontSize=10, textColor=RL_LIGHT_GREEN,
                               spaceAfter=0),
        "h1":           style("h1", fontName="Helvetica-Bold", fontSize=14,
                               textColor=RL_DARK_GREEN, spaceBefore=12, spaceAfter=6),
        "h2":           style("h2", fontName="Helvetica-Bold", fontSize=11,
                               textColor=RL_MID_GREEN, spaceBefore=8, spaceAfter=4),
        "body":         style("body", fontSize=9, leading=14, textColor=RL_DARK_GRAY,
                               spaceAfter=6),
        "body_small":   style("body_small", fontSize=8, leading=12, textColor=RL_MED_GRAY,
                               spaceAfter=4),
        "bullet":       style("bullet", fontSize=9, leading=13, leftIndent=14,
                               bulletIndent=4, textColor=RL_DARK_GRAY, spaceAfter=4),
        "callout":      style("callout", fontSize=9, leading=14, leftIndent=8,
                               rightIndent=8, backColor=RL_PALE_GREEN,
                               borderColor=RL_LIGHT_GREEN, borderWidth=1,
                               borderPadding=8, textColor=RL_DARK_GRAY, spaceAfter=8),
        "disclaimer":   style("disclaimer", fontSize=7.5, leading=11,
                               textColor=RL_MED_GRAY, fontName="Helvetica-Oblique",
                               spaceAfter=6),
        "table_header": style("th", fontName="Helvetica-Bold", fontSize=8.5,
                               textColor=colors.white, alignment=TA_CENTER),
        "table_cell":   style("td", fontSize=8.5, leading=12, alignment=TA_LEFT),
        "table_cell_c": style("tdc", fontSize=8.5, leading=12, alignment=TA_CENTER),
        "footer":       style("footer", fontSize=7.5, textColor=RL_MED_GRAY,
                               alignment=TA_CENTER),
        "seal":         style("seal", fontName="Helvetica-Bold", fontSize=8,
                               textColor=colors.white, alignment=TA_CENTER),
    }

    risk = report_data.get("risk_level", "MEDIUM") if report_data else "N/A"
    risk_color_map = {"LOW": RL_RISK_GREEN, "MEDIUM": RL_RISK_ORANGE,
                      "HIGH": RL_RISK_RED,  "CRITICAL": RL_RISK_RED}
    risk_rl_color = risk_color_map.get(risk, RL_MED_GRAY)
    generated_on = datetime.now().strftime("%d %B %Y, %H:%M UTC")
    ndvi1_str = f"{mean_ndvi1:.4f}" if mean_ndvi1 else "N/A"
    ndvi2_str = f"{mean_ndvi2:.4f}" if mean_ndvi2 else "N/A"
    change_str = f"{ndvi_change_pct:+.1f}%" if ndvi_change_pct is not None else "N/A"

    story = []

    # ── Cover header (green banner table) ──────────────────────────────────────
    header_data = [[
        Paragraph(f"<b>HIMALAYAN CARBON AI</b>", S["title"]),
        Paragraph(f"Risk Level<br/><b>{risk}</b>", S["seal"])
    ]]
    header_table = Table(header_data, colWidths=[PAGE_W - 2*MARGIN - 45*mm, 45*mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), RL_DARK_GREEN),
        ("BACKGROUND",   (1,0), (1,0),   risk_rl_color),
        ("TOPPADDING",   (0,0), (-1,-1), 16),
        ("BOTTOMPADDING",(0,0), (-1,-1), 16),
        ("LEFTPADDING",  (0,0), (0,0),   16),
        ("RIGHTPADDING", (1,0), (1,0),   12),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [RL_DARK_GREEN]),
    ]))
    story.append(header_table)

    # Sub-header row
    sub_data = [[
        Paragraph(f"Forest Health Due Diligence Report — {location_name}", S["subtitle"]),
        Paragraph(f"Generated: {generated_on}", S["subtitle"])
    ]]
    sub_table = Table(sub_data, colWidths=[(PAGE_W - 2*MARGIN)*0.65, (PAGE_W - 2*MARGIN)*0.35])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), RL_MID_GREEN),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (0,0),   16),
        ("RIGHTPADDING",  (1,0), (1,0),   12),
        ("ALIGN",         (1,0), (1,0),   "RIGHT"),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 8*mm))

    # ── Key metrics grid ────────────────────────────────────────────────────────
    def metric_cell(label, value, unit="", bg=RL_PALE_GREEN):
        inner = Table([
            [Paragraph(label.upper(), style("ml", fontSize=7, fontName="Helvetica-Bold",
                                             textColor=RL_ACCENT, alignment=TA_CENTER))],
            [Paragraph(str(value), style("mv", fontSize=16, fontName="Helvetica-Bold",
                                          textColor=RL_DARK_GREEN, alignment=TA_CENTER))],
            [Paragraph(unit, style("mu", fontSize=7, textColor=RL_MED_GRAY,
                                    alignment=TA_CENTER))],
        ], colWidths=["100%"])
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), bg),
            ("BOX",        (0,0), (-1,-1), 0.5, RL_LIGHT_GREEN),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ]))
        return inner

    col_w = (PAGE_W - 2*MARGIN - 3*3*mm) / 4
    metrics_row = [[
        metric_cell(f"NDVI {year1}", ndvi1_str),
        metric_cell(f"NDVI {year2}", ndvi2_str),
        metric_cell("Change", change_str),
        metric_cell("Area", f"{area_ha:,.0f}" if area_ha else f"{(math.pi * buffer_km**2 * 100):.0f}", "hectares"),
    ]]
    metrics_table = Table(metrics_row, colWidths=[col_w]*4, hAlign="LEFT")
    metrics_table.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 3),
        ("RIGHTPADDING", (0,0),(-1,-1), 3),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 6*mm))

    # ── Analysis parameters ─────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1.5, color=RL_LIGHT_GREEN, spaceAfter=4))
    story.append(Paragraph("Analysis Parameters", S["h1"]))

    params_data = [
        [Paragraph("Parameter", S["table_header"]), Paragraph("Value", S["table_header"])],
        ["Location", location_name],
        ["Coordinates", f"{lat:.4f}°N, {lon:.4f}°E"],
        ["Analysis Radius", f"{buffer_km} km"],
        ["Season Window", f"{month_names[start_month]} – {month_names[end_month]}"],
        ["Comparison Years", f"{year1} vs {year2}"],
        ["Satellite", "Sentinel-2 SR (10m resolution)"],
        ["Report Date", generated_on],
    ]
    params_table = Table(params_data, colWidths=[(PAGE_W-2*MARGIN)*0.4, (PAGE_W-2*MARGIN)*0.6])
    params_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  RL_DARK_GREEN),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, RL_PALE_GREEN]),
        ("GRID",          (0,0), (-1,-1), 0.4, RL_LIGHT_GREEN),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("FONTNAME",      (0,1), (0,-1),  "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,1), (0,-1),  RL_ACCENT),
    ]))
    story.append(params_table)
    story.append(Spacer(1, 5*mm))

    # ── Carbon stock section ────────────────────────────────────────────────────
    if carbon_data:
        story.append(HRFlowable(width="100%", thickness=1.5, color=RL_LIGHT_GREEN, spaceAfter=4))
        story.append(Paragraph("Carbon Stock Estimate", S["h1"]))

        carbon_rows = [
            [Paragraph("Metric", S["table_header"]),
             Paragraph("Per Hectare", S["table_header"]),
             Paragraph("Total (Area)", S["table_header"])],
            ["Above-Ground Biomass",
             f"{carbon_data['agb_ha']:,.0f} t/ha",
             f"{carbon_data['agb_ha']*carbon_data['area_ha']:,.0f} tonnes"],
            ["Below-Ground Biomass",
             f"{carbon_data['bgb_ha']:,.0f} t/ha",
             f"{carbon_data['bgb_ha']*carbon_data['area_ha']:,.0f} tonnes"],
            ["Total Biomass",
             f"{carbon_data['total_biomass_ha']:,.0f} t/ha",
             f"{(carbon_data['total_biomass_ha']*carbon_data['area_ha']):,.0f} tonnes"],
            ["Carbon Stock",
             f"{carbon_data['carbon_ha']:,.0f} tC/ha",
             f"{carbon_data['total_carbon_t']:,.0f} tonnes C"],
            ["CO\u2082 Equivalent",
             f"{carbon_data['co2e_ha']:,.0f} tCO\u2082e/ha",
             f"{carbon_data['total_co2e_t']:,.0f} tCO\u2082e"],
        ]
        if "co2e_change_t" in carbon_data:
            sign = "+" if carbon_data["co2e_change_t"] >= 0 else ""
            carbon_rows.append([
                "CO\u2082e Change (NDVI-based)",
                f"{carbon_data['co2e_change_pct']:+.1f}%",
                f"{sign}{carbon_data['co2e_change_t']:,.0f} tCO\u2082e"
            ])

        carbon_table = Table(carbon_rows, colWidths=[(PAGE_W-2*MARGIN)*0.45,
                                                      (PAGE_W-2*MARGIN)*0.275,
                                                      (PAGE_W-2*MARGIN)*0.275])
        carbon_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),  (-1,0),  RL_DARK_GREEN),
            ("ROWBACKGROUNDS",(0,1),  (-1,-1), [colors.white, RL_PALE_GREEN]),
            ("GRID",          (0,0),  (-1,-1), 0.4, RL_LIGHT_GREEN),
            ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
            ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
            ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#FFF8E1")),
            ("FONTSIZE",      (0,0),  (-1,-1), 8.5),
            ("TOPPADDING",    (0,0),  (-1,-1), 5),
            ("BOTTOMPADDING", (0,0),  (-1,-1), 5),
            ("LEFTPADDING",   (0,0),  (-1,-1), 8),
            ("ALIGN",         (1,0),  (-1,-1), "CENTER"),
            ("FONTNAME",      (0,1),  (0,-1),  "Helvetica-Bold"),
            ("TEXTCOLOR",     (0,1),  (0,-1),  RL_DARK_GREEN),
        ]))
        story.append(carbon_table)
        story.append(Paragraph(
            "⚠ Satellite-based estimates. Forest type: " +
            carbon_data['forest_type'].replace('_',' ').title() +
            ". Based on Nepal FAO/ICIMOD literature. "
            "Field calibration required before use in verified carbon projects.",
            S["disclaimer"]
        ))

    # ── Multi-year trend table ──────────────────────────────────────────────────
    if trend_data and len(trend_data) > 1:
        story.append(HRFlowable(width="100%", thickness=1.5, color=RL_LIGHT_GREEN, spaceAfter=4))
        story.append(Paragraph("Multi-Year NDVI Record", S["h1"]))

        trend_header = [Paragraph(h, S["table_header"]) for h in
                        ["Year"] + [str(d["year"]) for d in trend_data]]
        trend_values = ["NDVI"] + [str(d["ndvi"]) for d in trend_data]

        col_count = len(trend_data) + 1
        col_w_trend = (PAGE_W - 2*MARGIN) / col_count
        trend_table = Table(
            [trend_header, trend_values],
            colWidths=[col_w_trend] * col_count
        )
        trend_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  RL_DARK_GREEN),
            ("BACKGROUND",    (0,1), (0,1),   RL_PALE_GREEN),
            ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTNAME",      (0,1), (0,1),   "Helvetica-Bold"),
            ("TEXTCOLOR",     (0,1), (0,1),   RL_ACCENT),
            ("FONTSIZE",      (0,0), (-1,-1), 8.5),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("GRID",          (0,0), (-1,-1), 0.4, RL_LIGHT_GREEN),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white]),
        ]))
        story.append(trend_table)
        story.append(Spacer(1, 3*mm))

    # ── AI Report sections ──────────────────────────────────────────────────────
    if report_data:
        story.append(PageBreak())
        story.append(HRFlowable(width="100%", thickness=1.5, color=RL_LIGHT_GREEN, spaceAfter=4))
        story.append(Paragraph("AI-Generated Due Diligence Analysis", S["h1"]))
        story.append(Paragraph(
            "The following analysis was generated using Llama 3 (Groq) based on satellite data inputs. "
            "It does not constitute certified verification and should be reviewed by qualified environmental scientists.",
            S["disclaimer"]
        ))
        story.append(Spacer(1, 3*mm))

        sections = [
            ("Executive Summary",         report_data.get("executive_summary", "")),
            ("Vegetation Health Analysis", report_data.get("vegetation_analysis", "")),
            ("Carbon Stock Implications",  report_data.get("carbon_implications", "")),
            ("Risk Assessment",            report_data.get("risk_assessment", "")),
            ("Data Confidence",            report_data.get("data_confidence", "")),
            ("Next Monitoring",            report_data.get("next_monitoring_date", "")),
        ]

        for sec_title, sec_body in sections:
            if sec_body:
                story.append(Paragraph(sec_title, S["h2"]))
                story.append(Paragraph(sec_body, S["body"]))

        # Key findings
        findings = report_data.get("key_findings", [])
        if findings:
            story.append(Paragraph("Key Findings", S["h2"]))
            for f in findings:
                story.append(Paragraph(f"• {f}", S["bullet"]))

        # Recommendations
        recs = report_data.get("recommendations", [])
        if recs:
            story.append(Paragraph("Recommendations", S["h2"]))
            for i, r in enumerate(recs, 1):
                story.append(Paragraph(f"{i}.  {r}", S["bullet"]))

    # ── Footer page ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=RL_LIGHT_GREEN))
    footer_data = [[
        Paragraph("Satellite data: Sentinel-2 SR via Google Earth Engine", S["footer"]),
        Paragraph("Himalayan Carbon AI · Digital MRV Platform", S["footer"]),
        Paragraph("Estimates pending field validation", S["footer"]),
    ]]
    footer_table = Table(footer_data, colWidths=[(PAGE_W-2*MARGIN)/3]*3)
    footer_table.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("ALIGN",         (0,0),(0,-1),  "LEFT"),
        ("ALIGN",         (1,0),(1,-1),  "CENTER"),
        ("ALIGN",         (2,0),(2,-1),  "RIGHT"),
    ]))
    story.append(footer_table)

    # ── Build ──────────────────────────────────────────────────────────────────
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(RL_DARK_GREEN)
        canvas.rect(0, 0, PAGE_W, 8*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, 2.5*mm,
            f"Himalayan Carbon AI — {location_name} — Generated {generated_on}")
        canvas.drawRightString(PAGE_W - MARGIN, 2.5*mm,
            f"Page {doc.page} — CONFIDENTIAL — Satellite estimates only")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=18*mm,
        title=f"HCA Forest Report — {location_name}",
        author="Himalayan Carbon AI",
        subject="Forest Health Due Diligence Report"
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ══════════════════════════════════════════════════════════════════════════════
# MAP HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def create_folium_map(center_lat, center_lon, zoom=12):
    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=zoom,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri Satellite'
    )
    folium.Marker([center_lat, center_lon],
                  popup=f"Centre: {center_lat:.4f}°N, {center_lon:.4f}°E",
                  icon=folium.Icon(color='green', icon='tree-conifer', prefix='fa')
                  ).add_to(m)
    return m


def add_ee_layer(folium_map, image, vis_params, name, opacity=0.85):
    try:
        tile_url = image.getMapId(vis_params)['tile_fetcher'].url_format
        folium.TileLayer(tiles=tile_url, attr='GEE', name=name,
                         overlay=True, control=True, opacity=opacity).add_to(folium_map)
        return True
    except Exception as e:
        st.warning(f"Could not load layer '{name}': {str(e)}")
        return False


def create_ndvi_colorbar():
    return f"""
    <div class="ndvi-bar-wrap">
      <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:{ACCENT};margin-bottom:6px;">NDVI Scale</div>
      <div style="display:flex;height:16px;border-radius:4px;overflow:hidden;">
        <div style="flex:1;background:#d73027;"></div><div style="flex:1;background:#fc8d59;"></div>
        <div style="flex:1;background:#fee08b;"></div><div style="flex:1;background:#d9ef8b;"></div>
        <div style="flex:1;background:#91cf60;"></div><div style="flex:1;background:#1a9850;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-top:4px;">
        <span>0.0 · Bare</span><span>0.2</span><span>0.4</span><span>0.6</span><span>0.8</span><span>1.0 · Dense</span>
      </div>
    </div>"""


def display_status_card(ndvi_change_pct):
    if ndvi_change_pct < -10:
        cls, icon, title = "status-critical", "🚨", "DEGRADATION ALERT — Significant Vegetation Loss"
        desc = f"NDVI dropped <strong>{abs(ndvi_change_pct):.1f}%</strong>. Active deforestation, fire, or severe stress. Immediate ground verification recommended."
    elif ndvi_change_pct < -5:
        cls, icon, title = "status-warning", "⚠️", "MODERATE CHANGE — Continued Monitoring Required"
        desc = f"NDVI decreased <strong>{abs(ndvi_change_pct):.1f}%</strong>. May indicate selective logging or early encroachment."
    elif ndvi_change_pct >= 0:
        cls, icon, title = "status-healthy", "✅", "FOREST HEALTHY — Stable or Improving"
        desc = f"NDVI {'increased <strong>' + str(round(ndvi_change_pct,1)) + '%</strong>' if ndvi_change_pct > 0 else 'stable'}. No significant degradation detected."
    else:
        cls, icon, title = "status-stable", "🟡", "MINOR VARIATION — Within Normal Range"
        desc = f"NDVI change of <strong>{ndvi_change_pct:.1f}%</strong> is within expected seasonal variation."
    st.markdown(f"""
    <div class="status-card {cls}">
      <div class="status-icon">{icon}</div>
      <div><div class="status-title">{title}</div><div class="status-desc">{desc}</div></div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# GROQ AI REPORT
# ══════════════════════════════════════════════════════════════════════════════
def generate_report_with_groq(api_key, location_name, lat, lon, buffer_km,
                               year1, year2, start_month, end_month,
                               mean_ndvi1, mean_ndvi2, ndvi_change_pct,
                               timeseries_data, carbon_data, trend_data):
    try:
        from groq import Groq
    except ImportError:
        return None, "groq_not_installed"

    try:
        client = Groq(api_key=api_key)
        month_names = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
                       7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}

        status = ("CRITICAL" if ndvi_change_pct < -10 else
                  "WARNING"  if ndvi_change_pct < -5 else
                  "STABLE"   if ndvi_change_pct < 0 else "HEALTHY")

        trend_str = ""
        if trend_data:
            trend_str = "Multi-year NDVI: " + ", ".join([f"{d['year']}:{d['ndvi']}" for d in trend_data])

        carbon_str = ""
        if carbon_data:
            carbon_str = (f"Carbon stock: {carbon_data['co2e_ha']:.0f} tCO2e/ha, "
                          f"Total: {carbon_data['total_co2e_t']:,.0f} tCO2e")
            if "co2e_change_t" in carbon_data:
                carbon_str += f", Change: {carbon_data['co2e_change_t']:+,.0f} tCO2e"

        prompt = f"""You are a senior environmental scientist specializing in satellite forest monitoring and carbon MRV in Nepal.

ANALYSIS DATA:
- Location: {location_name} ({lat:.4f}N, {lon:.4f}E)
- Period: {month_names[start_month]}-{month_names[end_month]}, {year1} vs {year2}
- NDVI {year1}: {mean_ndvi1:.4f if mean_ndvi1 else 'N/A'}
- NDVI {year2}: {mean_ndvi2:.4f if mean_ndvi2 else 'N/A'}
- NDVI Change: {ndvi_change_pct:+.2f}%
- Status: {status}
{trend_str}
{carbon_str}

Return ONLY valid JSON, no markdown, no preamble:
{{
  "executive_summary": "2-3 sentences on overall forest health and key finding.",
  "key_findings": ["finding 1", "finding 2", "finding 3", "finding 4"],
  "vegetation_analysis": "Paragraph on NDVI values, biomass, canopy health, seasonal patterns with specific numbers.",
  "carbon_implications": "Paragraph on carbon stock change implications for MRV integrity. Reference CO2e figures if available.",
  "risk_level": "LOW",
  "risk_assessment": "Paragraph on deforestation risk, drivers, and threat level.",
  "recommendations": ["rec 1", "rec 2", "rec 3", "rec 4"],
  "data_confidence": "Assessment of data reliability given cloud cover, seasonality, Sentinel-2 limits.",
  "next_monitoring_date": "Suggested next review timeframe."
}}"""

        resp = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=1400
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        return json.loads(raw), None

    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {str(e)}"
    except Exception as e:
        return None, str(e)


def render_report_html(report_data, location_name, lat, lon, year1, year2,
                       mean_ndvi1, mean_ndvi2, ndvi_change_pct, buffer_km,
                       start_month, end_month):
    month_short = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                   7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    risk = report_data.get("risk_level", "MEDIUM")
    risk_colors = {"LOW":"#27AE60","MEDIUM":"#E67E22","HIGH":"#C0392B","CRITICAL":"#922B21"}
    risk_color = risk_colors.get(risk, "#888")
    ndvi1_str = f"{mean_ndvi1:.4f}" if mean_ndvi1 else "N/A"
    ndvi2_str = f"{mean_ndvi2:.4f}" if mean_ndvi2 else "N/A"
    generated_on = datetime.now().strftime("%d %B %Y")

    st.markdown(f"""
    <div class="report-outer">
      <div class="report-header">
        <div>
          <div class="report-header-title">🌲 Forest Health Due Diligence Report</div>
          <div style="color:{LIGHT_GREEN};font-size:0.8rem;margin-top:0.2rem;">{location_name} · {lat:.4f}°N, {lon:.4f}°E · {buffer_km}km radius</div>
        </div>
        <div class="report-header-meta">
          <div>Generated: {generated_on}</div>
          <div>{month_short[start_month]}–{month_short[end_month]} · {year1} vs {year2}</div>
          <div style="margin-top:6px;background:rgba(216,243,220,0.15);border:1px solid rgba(216,243,220,0.3);border-radius:4px;padding:3px 8px;display:inline-block;">
            Risk: <strong style="color:{risk_color};">{risk}</strong>
          </div>
        </div>
      </div>
      <div class="report-body">
        <div class="report-data-grid">
          <div class="report-data-cell"><div class="rdc-label">NDVI {year1}</div><div class="rdc-value">{ndvi1_str}</div></div>
          <div class="report-data-cell"><div class="rdc-label">NDVI {year2}</div><div class="rdc-value">{ndvi2_str}</div></div>
          <div class="report-data-cell"><div class="rdc-label">Change</div><div class="rdc-value" style="color:{'#C0392B' if ndvi_change_pct<-5 else '#27AE60'};">{ndvi_change_pct:+.1f}%</div></div>
        </div>
        <div class="report-section-title">Executive Summary</div>
        <div class="report-callout">{report_data.get('executive_summary','')}</div>
        <div class="report-section-title">Key Findings</div>
        <div class="report-callout">{''.join([f'<div style="padding:4px 0;border-bottom:1px solid {LIGHT_GREEN};">&#x2022;&nbsp;{f}</div>' for f in report_data.get('key_findings',[])])}</div>
        <div class="report-section-title">Vegetation Health Analysis</div>
        <div class="report-callout">{report_data.get('vegetation_analysis','')}</div>
        <div class="report-section-title">Carbon Stock Implications</div>
        <div class="report-callout">{report_data.get('carbon_implications','')}</div>
        <div class="report-section-title">Risk Assessment</div>
        <div class="report-callout" style="border-left:4px solid {risk_color};"><strong style="color:{risk_color};">Risk Level: {risk}</strong><br><br>{report_data.get('risk_assessment','')}</div>
        <div class="report-section-title">Recommendations</div>
        <div class="report-callout">{''.join([f'<div style="padding:5px 0;border-bottom:1px solid {LIGHT_GREEN};"><strong style=color:{ACCENT};>{i+1}.</strong>&nbsp;{r}</div>' for i,r in enumerate(report_data.get('recommendations',[]))])}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.8rem;margin-top:0.8rem;">
          <div class="report-callout">
            <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:{ACCENT};margin-bottom:4px;">Data Confidence</div>
            {report_data.get('data_confidence','N/A')}
          </div>
          <div class="report-callout">
            <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:{ACCENT};margin-bottom:4px;">Next Monitoring</div>
            {report_data.get('next_monitoring_date','N/A')}
          </div>
        </div>
      </div>
      <div class="report-footer">
        <div class="report-footer-text">Sentinel-2 SR · Himalayan Carbon AI · Estimates pending field validation</div>
        <div class="integrity-seal">⬡ Satellite Integrity Seal</div>
      </div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
def main():

    # ── Header ──
    st.markdown(f"""
    <div class="hca-header">
      <div>
        <div class="hca-header-title">Himalayan Carbon AI</div>
        <div class="hca-header-sub">Digital MRV · Satellite Forest Monitoring · Nepal</div>
      </div>
      <div style="display:flex;gap:0.8rem;">
        <div class="hca-badge">🛰️ Sentinel-2<br>10m</div>
        <div class="hca-badge">🌿 Carbon<br>Estimate</div>
        <div class="hca-badge">📈 Multi-Year<br>Trend</div>
        <div class="hca-badge">📄 PDF<br>Report</div>
      </div>
    </div>""", unsafe_allow_html=True)

    if not initialize_gee():
        st.stop()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 📍 Location")

        location_method = st.radio("Select by:", ["District / Forest", "Coordinates", "Upload GeoJSON"], horizontal=False)

        aoi_custom   = None
        area_ha      = None
        uploaded_name = None

        if location_method == "District / Forest":
            all_locs = get_all_locations()
            search_q = st.text_input("🔍 Search", placeholder="Type to filter…")
            filtered = search_location(search_q) if search_q else sorted(all_locs.keys())
            selected_location = st.selectbox("Location", filtered) if filtered else "Unknown"
            lat, lon = get_location_coords(selected_location) if filtered else (NEPAL_CENTER['lat'], NEPAL_CENTER['lon'])

        elif location_method == "Coordinates":
            c1, c2 = st.columns(2)
            with c1:
                lat = st.number_input("Lat", value=NEPAL_CENTER['lat'], min_value=26.0, max_value=31.0, step=0.0001, format="%.4f")
            with c2:
                lon = st.number_input("Lon", value=NEPAL_CENTER['lon'], min_value=80.0, max_value=89.0, step=0.0001, format="%.4f")
            selected_location = f"Custom ({lat:.3f}°N, {lon:.3f}°E)"

        else:  # Upload GeoJSON — Feature 5
            uploaded_file = st.file_uploader(
                "Upload GeoJSON boundary",
                type=["geojson","json"],
                help="Upload your community forest or project boundary as GeoJSON. "
                     "The app will use it as the exact AOI instead of a radius buffer."
            )
            if uploaded_file:
                try:
                    aoi_custom, lat, lon, area_ha, uploaded_name = parse_geojson_upload(uploaded_file)
                    selected_location = uploaded_name
                    st.success(f"✅ Boundary loaded: {area_ha:,.0f} ha")
                    st.caption(f"Centroid: {lat:.4f}°N, {lon:.4f}°E")
                except ValueError as e:
                    st.error(f"GeoJSON error: {str(e)}")
                    lat, lon = NEPAL_CENTER['lat'], NEPAL_CENTER['lon']
                    selected_location = "Upload failed"
            else:
                st.info("Upload a .geojson file to use your exact forest boundary.")
                lat, lon = NEPAL_CENTER['lat'], NEPAL_CENTER['lon']
                selected_location = "Awaiting upload"

        if aoi_custom is None:
            buffer_km = st.slider("Analysis radius (km)", 1, 20, 5)
        else:
            buffer_km = 5  # not used when custom AOI is set, but keep for PDF metadata
            st.caption("Radius buffer not used — exact boundary from GeoJSON")

        st.markdown("## 📅 Time Period")
        st.caption("Jan–Mar recommended (avoids monsoon cloud cover)")
        current_year = datetime.now().year
        c1, c2 = st.columns(2)
        with c1:
            year1 = st.selectbox("Year 1 (earlier)", range(2019, current_year), index=3)
        with c2:
            year2 = st.selectbox("Year 2 (later)", range(2019, current_year+1), index=4)
        c1, c2 = st.columns(2)
        with c1:
            start_month = st.selectbox("Start", range(1,13), index=0,
                                       format_func=lambda x: datetime(2000,x,1).strftime('%b'))
        with c2:
            end_month   = st.selectbox("End", range(1,13), index=2,
                                       format_func=lambda x: datetime(2000,x,1).strftime('%b'))

        st.markdown("## 🌿 Forest Type")
        forest_type = st.selectbox(
            "Select for carbon estimate",
            list(NEPAL_FOREST_CARBON.keys()),
            format_func=lambda x: x.replace('_',' ').title(),
            help="Affects biomass and carbon stock calculation. "
                 "Use 'Default' if unsure — it averages Himalayan forest types."
        )

        st.markdown("## 📈 Multi-Year Trend")
        run_multiyear = st.checkbox("Build 2019–present trend", value=True,
                                    help="Adds ~30s. Highly recommended for NGO demos.")

        st.markdown("## 🤖 AI Report")
        generate_report = st.checkbox("Generate due diligence report", value=True)
        groq_key = os.getenv('GROQ_API_KEY','')
        if generate_report:
            if groq_key:
                st.success("✅ Groq API key loaded")
            else:
                st.info("Add GROQ_API_KEY to .env\nFree key: console.groq.com")

        st.markdown("---")
        analyze_button = st.button("🔍 Analyse Forest Health", type="primary", use_container_width=True)

    # ── Main content ──────────────────────────────────────────────────────────
    if analyze_button:
        with st.spinner("🛰️ Fetching satellite data…"):
            try:
                # AOI — use uploaded boundary or radius buffer
                if aoi_custom is not None:
                    aoi = aoi_custom
                else:
                    aoi = create_aoi_from_point(lat, lon, buffer_km)
                    area_ha = math.pi * buffer_km**2 * 100  # approx ha

                start_date1 = f"{year1}-{start_month:02d}-01"
                end_date1   = f"{year1}-{end_month:02d}-28"
                start_date2 = f"{year2}-{start_month:02d}-01"
                end_date2   = f"{year2}-{end_month:02d}-28"

                prog = st.progress(0, text="Loading Year 1 imagery…")
                composite1 = get_sentinel_composite(aoi, start_date1, end_date1)
                prog.progress(20, text="Loading Year 2 imagery…")
                composite2 = get_sentinel_composite(aoi, start_date2, end_date2)
                prog.progress(40, text="Computing NDVI…")
                mean_ndvi1 = compute_mean_ndvi(composite1, aoi)
                mean_ndvi2 = compute_mean_ndvi(composite2, aoi)
                prog.progress(55, text="Building time-series…")
                timeseries = calculate_ndvi_timeseries(aoi, year2, start_month, end_month)
                prog.progress(70, text="Done!")
                prog.empty()

                ndvi_change_pct = 0.0
                if mean_ndvi1 and mean_ndvi2 and mean_ndvi1 != 0:
                    ndvi_change_pct = ((mean_ndvi2 - mean_ndvi1) / mean_ndvi1) * 100

                # ── CARBON ESTIMATE (Feature 4) ──
                carbon_data = estimate_carbon_stock(
                    mean_ndvi=mean_ndvi2,
                    area_ha=area_ha or 0,
                    forest_type=forest_type,
                    ndvi_change_pct=ndvi_change_pct
                )

                st.success("✅ Analysis complete")

                # ── Metrics ──
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric(f"NDVI {year1}", f"{mean_ndvi1:.4f}" if mean_ndvi1 else "N/A")
                with c2: st.metric(f"NDVI {year2}", f"{mean_ndvi2:.4f}" if mean_ndvi2 else "N/A")
                with c3: st.metric("Change", f"{ndvi_change_pct:+.1f}%", delta=f"{ndvi_change_pct:.1f}%")
                with c4: st.metric("Area", f"{area_ha:,.0f} ha" if area_ha else f"{lat:.2f}°N")

                # ── Status ──
                st.markdown('<div class="section-heading">🚦 Forest Health Status</div>', unsafe_allow_html=True)
                display_status_card(ndvi_change_pct)

                # ── Carbon estimate (Feature 4) ──
                st.markdown('<div class="section-heading">🌿 Carbon Stock Estimate</div>', unsafe_allow_html=True)
                render_carbon_box(carbon_data)

                # ── Maps ──
                st.markdown('<div class="section-heading">🗺️ NDVI Comparison Maps</div>', unsafe_allow_html=True)
                vis_params = get_ndvi_visualization_params()
                tab1, tab2 = st.tabs([f"📅 {year1}", f"📅 {year2}"])
                for tab, year, composite in [(tab1, year1, composite1), (tab2, year2, composite2)]:
                    with tab:
                        m = create_folium_map(lat, lon, zoom=11)
                        added = add_ee_layer(m, composite.select('NDVI'), vis_params, f'NDVI {year}')
                        if aoi_custom is None:
                            folium.Circle(location=[lat,lon], radius=buffer_km*1000,
                                          color='#FFD700', fill=False, weight=3).add_to(m)
                        folium.LayerControl(collapsed=False).add_to(m)
                        st_folium(m, width=None, height=460, returned_objects=[], use_container_width=True)
                        if added:
                            st.markdown(create_ndvi_colorbar(), unsafe_allow_html=True)

                # ── Monthly trend ──
                st.markdown('<div class="section-heading">📈 Monthly NDVI Trend</div>', unsafe_allow_html=True)
                if timeseries:
                    fig = go.Figure()
                    df_ts = pd.DataFrame(timeseries)
                    fig.add_trace(go.Scatter(
                        x=df_ts['month'], y=df_ts['ndvi'], mode='lines+markers',
                        line=dict(color=ACCENT, width=3),
                        marker=dict(size=9, color=DARK_GREEN, line=dict(color=WHITE, width=2)),
                        fill='tozeroy', fillcolor='rgba(64,145,108,0.12)',
                        name='Monthly NDVI'
                    ))
                    fig.update_layout(
                        title=dict(text=f"Monthly NDVI ({year2}) — {selected_location}",
                                   font=dict(size=16, color=DARK_GREEN, family="DM Serif Display")),
                        xaxis_title="Month", yaxis_title="NDVI",
                        yaxis=dict(range=[0,1]), plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)', font=dict(family="DM Sans", size=12),
                        margin=dict(l=40, r=20, t=50, b=40)
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # ── MULTI-YEAR TREND (Feature 3) ──────────────────────────────
                trend_data = []
                if run_multiyear:
                    st.markdown('<div class="section-heading">📊 Multi-Year NDVI Trend (2019–Present)</div>', unsafe_allow_html=True)
                    with st.spinner("Computing annual NDVI for each year… (this takes ~20s)"):
                        trend_data = build_multiyear_trend(aoi, start_month, end_month, start_year=2019)

                    if trend_data and len(trend_data) >= 2:
                        result = create_multiyear_chart(trend_data, selected_location, forest_type)
                        if result:
                            fig_trend, slope, trend_direction = result
                            st.plotly_chart(fig_trend, use_container_width=True)

                            # Trend summary callout
                            years_span = trend_data[-1]["year"] - trend_data[0]["year"]
                            total_change = (trend_data[-1]["ndvi"] - trend_data[0]["ndvi"]) / trend_data[0]["ndvi"] * 100
                            st.markdown(f"""
                            <div class="report-callout" style="background:{PALE_GREEN};">
                              <strong>Trend summary:</strong> Over {years_span} years, NDVI has changed
                              <strong>{total_change:+.1f}%</strong> ({trend_direction}).
                              Annual slope: <strong>{slope:+.4f} NDVI units/year</strong>.
                              {'⚠️ This multi-year decline is a strong signal warranting field investigation.' if slope < -0.005 else ''}
                            </div>""", unsafe_allow_html=True)

                            # Trend data table
                            with st.expander("📋 View raw annual NDVI data"):
                                df_trend = pd.DataFrame(trend_data)
                                df_trend.columns = ["Year", "Mean NDVI"]
                                df_trend["YoY Change"] = df_trend["Mean NDVI"].pct_change().mul(100).round(1).astype(str).add("%")
                                df_trend.iloc[0, 2] = "—"
                                st.dataframe(df_trend, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Insufficient annual data for trend chart. Try a broader year range.")

                # ── AI REPORT ─────────────────────────────────────────────────
                report_data = None
                if generate_report:
                    st.markdown('<div class="section-heading">📋 AI Due Diligence Report</div>', unsafe_allow_html=True)
                    if not groq_key:
                        st.warning("**GROQ_API_KEY not set.** Free key at console.groq.com → add to .env → restart.")
                    else:
                        with st.spinner("🤖 Generating report with Groq + Llama 3…"):
                            report_data, error = generate_report_with_groq(
                                api_key=groq_key,
                                location_name=selected_location,
                                lat=lat, lon=lon, buffer_km=buffer_km,
                                year1=year1, year2=year2,
                                start_month=start_month, end_month=end_month,
                                mean_ndvi1=mean_ndvi1, mean_ndvi2=mean_ndvi2,
                                ndvi_change_pct=ndvi_change_pct,
                                timeseries_data=timeseries or [],
                                carbon_data=carbon_data,
                                trend_data=trend_data
                            )
                        if error == "groq_not_installed":
                            st.error("Run: pip install groq")
                        elif error:
                            st.error(f"Report failed: {error}")
                        elif report_data:
                            render_report_html(
                                report_data, selected_location, lat, lon,
                                year1, year2, mean_ndvi1, mean_ndvi2,
                                ndvi_change_pct, buffer_km, start_month, end_month
                            )

                # ── PDF EXPORT (Feature 8) ────────────────────────────────────
                st.markdown('<div class="section-heading">📄 Export Report</div>', unsafe_allow_html=True)
                st.markdown("Download a professional PDF version of this analysis — ready to attach to NGO donor reports or VERRA project documentation.")

                if st.button("📄 Generate PDF Report", use_container_width=True):
                    with st.spinner("Building PDF…"):
                        try:
                            pdf_bytes = build_pdf_report(
                                report_data=report_data,
                                location_name=selected_location,
                                lat=lat, lon=lon,
                                buffer_km=buffer_km,
                                area_ha=area_ha or 0,
                                year1=year1, year2=year2,
                                start_month=start_month, end_month=end_month,
                                mean_ndvi1=mean_ndvi1, mean_ndvi2=mean_ndvi2,
                                ndvi_change_pct=ndvi_change_pct,
                                carbon_data=carbon_data,
                                trend_data=trend_data,
                                timeseries_data=timeseries or []
                            )
                            fname = f"HCA_{selected_location.replace(' ','_')}_{year2}.pdf"
                            st.download_button(
                                label="📥 Download PDF",
                                data=pdf_bytes,
                                file_name=fname,
                                mime="application/pdf",
                                use_container_width=True
                            )
                            st.success("PDF ready! Click Download PDF above.")
                        except Exception as e:
                            st.error(f"PDF generation failed: {str(e)}")
                            st.info("Make sure reportlab is installed: pip install reportlab")

                # ── NDVI Info expander ────────────────────────────────────────
                with st.expander("ℹ️ Understanding NDVI & Carbon Estimates"):
                    st.markdown(f"""
                    **NDVI (Normalized Difference Vegetation Index)** measures live green vegetation using Sentinel-2 near-infrared and red bands.

                    | NDVI Range | Interpretation |
                    |---|---|
                    | 0.6 – 0.9 | Dense, healthy forest |
                    | 0.3 – 0.6 | Moderate vegetation |
                    | 0.0 – 0.3 | Sparse / bare soil |
                    | < 0.0 | Water, snow, clouds |

                    **Carbon estimates** use Nepal forest literature values from FAO/ICIMOD, scaled by NDVI relative to a 0.75 reference for healthy Himalayan broadleaf forest. They are **indicative only** — field-based allometric measurements are required for any certified carbon project under VERRA or ART-TREES standards.

                    **Multi-year trend** uses annual Sentinel-2 composites from 2019 to present, restricted to your chosen season window to control for monsoon cloud contamination.
                    """)

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
                st.info("Try adjusting the date range or selecting a different location.")

    else:
        st.info("👈 Configure parameters in the sidebar, then click **Analyse Forest Health**")
        m = folium.Map(
            location=[NEPAL_CENTER['lat'], NEPAL_CENTER['lon']], zoom_start=NEPAL_CENTER['zoom'],
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri Satellite'
        )
        st_folium(m, width=None, height=460, returned_objects=[], use_container_width=True)
        c1, c2, c3, c4 = st.columns(4)
        for col, icon, title, desc in [
            (c1,"🛰️","Sentinel-2","10m resolution, 5-day revisit, cloud-masked composites for Nepal."),
            (c2,"🌿","Carbon Estimate","NDVI-scaled biomass converted to CO₂e using Nepal FAO/ICIMOD values."),
            (c3,"📈","Multi-Year Trend","2019–present annual NDVI trend line with slope and degradation bands."),
            (c4,"📄","PDF Export","Professional ReportLab PDF with all data, carbon table, and AI analysis."),
        ]:
            with col:
                st.markdown(f"""
                <div class="info-card">
                  <div class="info-card-icon">{icon}</div>
                  <div class="info-card-title">{title}</div>
                  <div class="info-card-desc">{desc}</div>
                </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()