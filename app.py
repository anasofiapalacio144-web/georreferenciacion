import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import MarkerCluster
import zipfile
import io
import shapefile  # pyshp
from shapely.geometry import shape, Point

# =========================
# DASHBOARD DE MAPA SIN GEOPANDAS
# =========================
st.title("🗺️ Mapa temático: Densidad de puntos por departamento")
st.caption("Versión compatible con Streamlit Cloud (sin GeoPandas)")

# -------------------------
# 1️⃣ Subir archivos
# -------------------------
st.sidebar.header("📂 Cargar datos")
uploaded_zip = st.sidebar.file_uploader("Sube tu shapefile comprimido (.zip)", type=["zip"])
uploaded_csv = st.sidebar.file_uploader("Sube tu archivo de puntos (CSV, opcional)", type=["csv"])

if uploaded_zip is None:
    st.warning("Por favor sube un archivo .zip que contenga tu shapefile (.shp, .dbf, .shx).")
    st.stop()

# -------------------------
# 2️⃣ Leer shapefile desde ZIP
# -------------------------
with zipfile.ZipFile(uploaded_zip, "r") as z:
    filenames = [f for f in z.namelist() if f.endswith((".shp", ".dbf", ".shx"))]
    z.extractall("temp_shp")

sf = shapefile.Reader("temp_shp/" + [f for f in filenames if f.endswith(".shp")][0])

shapes = sf.shapes()
records = sf.records()
fields = [f[0] for f in sf.fields[1:]]  # nombres de columnas

df_shapes = pd.DataFrame(records, columns=fields)
st.success(f"✅ Capa cargada ({len(df_shapes)} polígonos)")
st.dataframe(df_shapes.head())

# Convertir a geometrías Shapely
geoms = [shape(s.__geo_interface__) for s in shapes]
df_shapes["geometry"] = geoms

# -------------------------
# 3️⃣ Leer o generar puntos
# -------------------------
if uploaded_csv:
    pts_df = pd.read_csv(uploaded_csv)
    st.info("✅ CSV cargado correctamente.")
else:
    st.info("No se subió CSV, generando 100 puntos aleatorios.")
    minx, miny, maxx, maxy = df_shapes["geometry"].total_bounds if hasattr(df_shapes["geometry"], "total_bounds") else (
        -80, -5, -66, 13
    )
    np.random.seed(42)
    pts_df = pd.DataFrame({
        "longitude": np.random.uniform(minx, maxx, 100),
        "latitude": np.random.uniform(miny, maxy, 100)
    })

# -------------------------
# 4️⃣ Conteo de puntos por polígono
# -------------------------
df_shapes["n_points"] = 0

for i, poly in enumerate(df_shapes["geometry"]):
    count = 0
    for _, row in pts_df.iterrows():
        if poly.contains(Point(row["longitude"], row["latitude"])):
            count += 1
    df_shapes.loc[i, "n_points"] = count

df_shapes["area_km2"] = df_shapes["geometry"].apply(lambda g: g.area / 1e6)
df_shapes["points_per_1000km2"] = ((df_shapes["n_points"] / df_shapes["area_km2"]) * 1000).round(2)

# -------------------------
# 5️⃣ Mapa interactivo
# -------------------------
m = folium.Map(location=[5, -74], zoom_start=5, tiles="CartoDB positron")

# Polígonos coloreados
for _, row in df_shapes.iterrows():
    color = "#%02x%02x%02x" % (int(255 - min(row["points_per_1000km2"] * 5, 255)), 120, 150)
    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda x, col=color: {"fillColor": col, "color": "black", "weight": 0.5, "fillOpacity": 0.7},
        tooltip=f"Densidad: {row['points_per_1000km2']} pts / 1000 km²"
    ).add_to(m)

# Puntos
cluster = MarkerCluster().add_to(m)
for _, row in pts_df.iterrows():
    folium.Marker([row["latitude"], row["longitude"]]).add_to(cluster)

st.subheader("🌎 Mapa interactivo")
st.components.v1.html(m._repr_html_(), height=600)

# -------------------------
# 6️⃣ Estadísticas
# -------------------------
st.subheader("📊 Resumen estadístico")
st.dataframe(df_shapes[["n_points", "area_km2", "points_per_1000km2"]].describe())

top = df_shapes.sort_values("points_per_1000km2", ascending=False).head(5)
st.subheader("🏆 Top 5 por densidad de puntos")
st.dataframe(top)

st.success("✅ Análisis completado exitosamente.")


