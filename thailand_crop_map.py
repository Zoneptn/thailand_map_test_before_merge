"""
Example: Thailand province map showing dominant/selected crop cultivation.
Uses apisit/thailand.json (thailandWithName.json) for province boundaries.

Run with: streamlit run thailand_crop_map_example.py
"""

import json
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

GEOJSON_URL = (
    "https://raw.githubusercontent.com/apisit/thailand.json"
    "/master/thailandWithName.json"
)

@st.cache_data
def load_geojson():
    resp = requests.get(GEOJSON_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()

DATA_PATH = "crop_area_by_provinces_TEMPLATE.xlsx"  # your real workbook, same folder as this script

@st.cache_data
def load_crop_data():
    df = pd.read_excel(DATA_PATH, sheet_name="crop_area_by_provinces")
    df = df.rename(columns={"province_name_en": "province"})
    return df[["province", "region", "SHK_region", "crop", "crop_group",
               "area_planted_rai", "area_harvested_rai"]]

def build_name_lookup(geojson):
    """Province names as they appear in the geojson — use this to check
    your crop-data spellings actually match before plotting."""
    return sorted(f["properties"]["name"] for f in geojson["features"])

def main():
    st.set_page_config(layout="wide")
    st.title("Crop Cultivation by Province")

    geojson = load_geojson()
    df = load_crop_data()

    with st.expander("Debug: province names in geojson vs your data"):
        geo_names = set(build_name_lookup(geojson))
        data_names = set(df["province"].unique())
        st.write("In your data but NOT in geojson (fix spelling):", data_names - geo_names)

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_crop = st.selectbox("Select crop", sorted(df["crop"].unique()))
    with col2:
        metric = st.selectbox("Metric", ["area_planted_rai", "area_harvested_rai"])
    with col3:
        shk_options = ["All"] + sorted(df["SHK_region"].dropna().unique())
        selected_shk = st.selectbox("Company sales region (SHK_region)", shk_options)

    filtered = df[df["crop"] == selected_crop]
    if selected_shk != "All":
        filtered = filtered[filtered["SHK_region"] == selected_shk]
    # If a province still has more than one row here (e.g. duplicate entries),
    # sum them so the choropleth gets exactly one value per province.
    filtered = filtered.groupby("province", as_index=False)[metric].sum()

    fig = px.choropleth_mapbox(
        filtered,
        geojson=geojson,
        locations="province",
        featureidkey="properties.name",   # <-- the join key
        color=metric,
        color_continuous_scale="Greens",
        mapbox_style="carto-positron",
        zoom=4.5,
        center={"lat": 13.7, "lon": 101.0},
        opacity=0.75,
        labels={metric: metric.replace("_", " ").title()},
    )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=650)
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
