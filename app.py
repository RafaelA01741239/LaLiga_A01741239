
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# -------------------------------------
# 🧩 Configuración general
# -------------------------------------
st.set_page_config(page_title="LaLiga Player Dashboard", layout="wide")
st.title("⚽ Estadísticas de Jugadores de LaLiga")

st.markdown("""
Este tablero permite analizar estadísticas de jugadores de LaLiga filtrando por equipo y métrica seleccionada.
""")

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# -------------------------------------
# 🔹 Cargar dataset con soporte de acentos (modo latino)
# -------------------------------------
try:
    df = pd.read_csv("database.csv", encoding="latin1")
except Exception as e:
    st.error(f"❌ Error al cargar el archivo: {e}")
    st.stop()

# Evitar edad duplicada en gráficos de barras
df_age_unique = df.drop_duplicates(subset=["Player"], keep="last")

# Convertir todas las columnas de texto a string con modo latino
df = df.apply(
    lambda col: col.astype(str).str.encode('latin1', errors='ignore').str.decode('latin1')
    if col.dtypes == 'object' else col
)

# Definir columnas métricas (desde 'Goals' hasta antes de 'Date')
metric_columns = df.loc[:, 'Goals':'Date'].columns[:-1]

# Asegurar que las columnas numéricas del hexágono sean numéricas
hex_numeric_cols = [
    "Goals",
    "Assists",
    "Shoot on Target",
    "Dribbles",
    "Dribble Attempts",        # <- nombre correcto
    "Successful Dribbles",
    "Passes Completion %",
    "Progressive Passes",
    "Progressive Carries",
    "Tackles",
    "Blocks",
]

for c in hex_numeric_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# -------------------------------------
# 🔹 PRE-CÁLCULO: ratings 1–99 por jugador
# -------------------------------------

def safe_sum_player(df_player, column_name):
    if column_name in df_player.columns:
        return pd.to_numeric(df_player[column_name], errors="coerce").sum()
    return 0

players_unique = df["Player"].unique()
rows = []

for p in players_unique:
    df_p = df[df["Player"] == p]

    ataque_raw = (
        safe_sum_player(df_p, "Goals") +
        safe_sum_player(df_p, "Assists") +
        safe_sum_player(df_p, "Shoot on Target")
    )

    regate_raw = (
        safe_sum_player(df_p, "Dribbles") +
        safe_sum_player(df_p, "Dribble Attempts") +
        safe_sum_player(df_p, "Successful Dribbles")
    )

    pases_raw = safe_sum_player(df_p, "Passes Completion %")

    creacion_raw = (
        safe_sum_player(df_p, "Progressive Passes") +
        safe_sum_player(df_p, "Progressive Carries")
    )

    defensa_raw = (
        safe_sum_player(df_p, "Tackles") +
        safe_sum_player(df_p, "Blocks")
    )

    rows.append({
        "Player": p,
        "Ataque_raw": ataque_raw,
        "Regate_raw": regate_raw,
        "Pases_raw": pases_raw,
        "Creación_raw": creacion_raw,
        "Defensa_raw": defensa_raw,
    })

df_hex = pd.DataFrame(rows)

def scale_1_99(series):
    min_v = series.min()
    max_v = series.max()
    if max_v == min_v:  # evitar división entre cero
        return pd.Series([50] * len(series), index=series.index)
    return 1 + (series - min_v) * 98 / (max_v - min_v)

# Escalamos cada categoría a 1–99
df_hex["Ataque"] = scale_1_99(df_hex["Ataque_raw"])
df_hex["Regate"] = scale_1_99(df_hex["Regate_raw"])
df_hex["Pases"] = scale_1_99(df_hex["Pases_raw"])
df_hex["Creación de juego"] = scale_1_99(df_hex["Creación_raw"])
df_hex["Defensa"] = scale_1_99(df_hex["Defensa_raw"])

# Pesos para el OVERALL (puedes cambiarlos)
weights = {
    "Ataque": 0.30,
    "Regate": 0.20,
    "Pases": 0.20,
    "Creación de juego": 0.15,
    "Defensa": 0.15
}

df_hex["Overall"] = (
    df_hex["Ataque"] * weights["Ataque"] +
    df_hex["Regate"] * weights["Regate"] +
    df_hex["Pases"] * weights["Pases"] +
    df_hex["Creación de juego"] * weights["Creación de juego"] +
    df_hex["Defensa"] * weights["Defensa"]
)

# Redondear Overall a entero tipo FIFA
df_hex["Overall"] = df_hex["Overall"].round().clip(1, 99)

# -------------------------------------
# 🔹 Tabs principales
# -------------------------------------
tab1, tab2, tab3 = st.tabs(["Bar Chart", "Soccer Rating Hexagon", "Pie Chart"])

# =====================================
# TAB 1 – BAR CHART
# =====================================
with tab1:
    st.markdown("## 🏃‍♂️ Rendimiento por jugador")

    col1, col2 = st.columns(2)
    with col1:
        selected_team_bar = st.selectbox("Selecciona un equipo (Bar Chart)", sorted(df['Team'].unique()))
    with col2:
        selected_metric_bar = st.selectbox("Selecciona la métrica (Bar Chart)", metric_columns)

    if selected_metric_bar == "Age":
        df_bar = df_age_unique[df_age_unique['Team'] == selected_team_bar]
    else:
        df_bar = df[df['Team'] == selected_team_bar]

    df_bar = df_bar.sort_values(by=selected_metric_bar, ascending=False)

    fig_bar = px.bar(
        df_bar,
        x="Player",
        y=selected_metric_bar,
        color=selected_metric_bar,
        color_continuous_scale="PuBu",
        title=f"{selected_metric_bar} por jugador en {selected_team_bar}"
    )
    fig_bar.update_layout(
        xaxis_title="Jugador",
        yaxis_title=selected_metric_bar,
        title_x=0.5
    )

    st.plotly_chart(fig_bar, use_container_width=True)

# =====================================
# TAB 2 – SOCCER RATING HEXAGON
# =====================================
with tab2:
    st.markdown("## ⭐ Soccer Rating Hexagon")

    col1, col2 = st.columns(2)
    with col1:
        selected_team_hex = st.selectbox(
            "Selecciona un equipo (Hexagon)",
            sorted(df['Team'].unique())
        )

    players_in_team = sorted(df[df["Team"] == selected_team_hex]["Player"].unique())

    with col2:
        selected_player_hex = st.selectbox(
            "Selecciona un jugador",
            players_in_team
        )

    # Fila del jugador en el dataframe de ratings 1–99
    row = df_hex[df_hex["Player"] == selected_player_hex]
    if row.empty:
        st.warning("No se encontraron métricas para ese jugador.")
    else:
        row = row.iloc[0]

        ataque = row["Ataque"]
        regate = row["Regate"]
        pases = row["Pases"]
        creacion_juego = row["Creación de juego"]
        defensa = row["Defensa"]
        overall = int(row["Overall"])

        categorias = ["Ataque", "Regate", "Pases", "Creación de juego", "Defensa"]
        valores = [ataque, regate, pases, creacion_juego, defensa]

        categorias_cerradas = categorias + [categorias[0]]
        valores_cerrados = valores + [valores[0]]

        # Mostrar OVERALL tipo carta FIFA
        st.metric(label="OVERALL", value=f"{overall}")

        fig_hex = go.Figure()
        fig_hex.add_trace(
            go.Scatterpolar(
                r=valores_cerrados,
                theta=categorias_cerradas,
                fill="toself",
                name=selected_player_hex
            )
        )

        fig_hex.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]  # escala 0–100 pero valores 1–99
                )
            ),
            showlegend=False,
            title=f"Perfil de {selected_player_hex} (Rating 1–99)"
        )

        st.plotly_chart(fig_hex, use_container_width=True)

        st.markdown("### 📊 Detalle de ratings (1–99)")
        resumen_df = pd.DataFrame({
            "Categoría": categorias,
            "Rating (1–99)": [round(v, 1) for v in valores]
        })
        st.dataframe(resumen_df, use_container_width=True)

# =====================================
# TAB 3 – PIE CHART
# =====================================
with tab3:
    st.markdown("## 🌍 Distribución por nacionalidad")

    col1, col2 = st.columns(2)
    with col1:
        selected_team_pie = st.selectbox("Selecciona un equipo (Pie Chart)", sorted(df['Team'].unique()))
    with col2:
        selected_metric_pie = st.selectbox("Selecciona la métrica (Pie Chart)", metric_columns)

    if selected_metric_pie == "Age":
        df_team = df_age_unique[df_age_unique['Team'] == selected_team_pie]
        df_pie = df_team.groupby("Nation")[selected_metric_pie].mean().reset_index()
    else:
        df_team = df[df['Team'] == selected_team_pie]
        df_pie = df_team.groupby("Nation")[selected_metric_pie].sum().reset_index()

    fig_pie = px.pie(
        df_pie,
        values=selected_metric_pie,
        names="Nation",
        title=f"Distribución de {selected_metric_pie} por nacionalidad - {selected_team_pie}"
    )

    fig_pie.update_layout(title_x=0.5)
    st.plotly_chart(fig_pie, use_container_width=True)
