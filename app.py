"""
CubaPrecios — App Streamlit v3
Navegación con tabs, sidebar solo filtros, diseño limpio y moderno
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

from config import DB_PATH

st.set_page_config(
    page_title="CubaPrecios — Electrónica",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# ESTILOS
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif;
    background-color: #f8f9fb;
    color: #1a1a2e;
}

/* SIDEBAR */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e8eaf0 !important;
    min-width: 280px !important;
    width: 280px !important;
}
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}

/* Ocultar elementos Streamlit */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* TABS — navbar horizontal */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #ffffff;
    border-bottom: 1px solid #e8eaf0;
    padding: 0 1rem;
    margin-bottom: 1.5rem;
    border-radius: 0;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.875rem;
    font-weight: 500;
    color: #8890a4;
    padding: 0.8rem 1.2rem;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    border-radius: 0;
    background: transparent;
}
.stTabs [aria-selected="true"] {
    color: #1a1a2e !important;
    border-bottom: 2px solid #1a1a2e !important;
    background: transparent !important;
    font-weight: 600;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #1a1a2e;
    background: #f8f9fb !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    display: none;
}
.stTabs [data-baseweb="tab-border"] {
    display: none;
}

/* Contenido principal */
.block-container {
    padding-top: 0 !important;
    max-width: 1200px;
}

/* Header de la app */
.app-header {
    background: #ffffff;
    border-bottom: 1px solid #e8eaf0;
    padding: 0.9rem 1.5rem;
    margin-bottom: 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.app-titulo {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1a1a2e;
    letter-spacing: -0.5px;
}
.app-subtitulo {
    font-size: 0.85rem;
    color: #8890a4;
    margin-top: 2px;
    margin-bottom: 1.2rem;
}

/* Cards métricas */
.card-metrica {
    background: #ffffff;
    border: 1px solid #e8eaf0;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.card-valor {
    font-size: 1.9rem;
    font-weight: 700;
    color: #1a1a2e;
    font-family: 'DM Mono', monospace;
    line-height: 1.1;
}
.card-etiqueta {
    font-size: 0.75rem;
    color: #8890a4;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
.card-verde .card-valor { color: #16a34a; }
.card-azul  .card-valor { color: #2563eb; }
.card-rojo  .card-valor { color: #dc2626; }
.card-ambar .card-valor { color: #d97706; }

/* Sección titulo */
.seccion {
    font-size: 1rem;
    font-weight: 600;
    color: #1a1a2e;
    margin-bottom: 0.6rem;
    margin-top: 0.2rem;
}
.seccion-sub {
    font-size: 0.8rem;
    color: #8890a4;
    margin-bottom: 0.8rem;
    margin-top: -0.4rem;
}

/* Tabla */
.stDataFrame {
    border: 1px solid #e8eaf0 !important;
    border-radius: 10px !important;
}
.stDataFrame th {
    background-color: #f8f9fb !important;
    color: #8890a4 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

/* Botones */
.stButton > button {
    background-color: #1a1a2e;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.875rem;
    padding: 0.5rem 1.2rem;
    font-family: 'DM Sans', sans-serif;
}
.stButton > button:hover {
    background-color: #2d2d4e;
}

/* Inputs */
.stTextInput > div > div > input {
    border-radius: 8px !important;
    border: 1px solid #e8eaf0 !important;
    background: #ffffff !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stSelectbox > div > div {
    border-radius: 8px !important;
    border: 1px solid #e8eaf0 !important;
    background: #ffffff !important;
}
.stMultiSelect > div {
    border-radius: 8px !important;
}

/* Card de contacto */
.card-contacto {
    background: #ffffff;
    border: 1px solid #e8eaf0;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    transition: box-shadow 0.2s;
}
.card-contacto:hover {
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.titulo-producto {
    font-size: 0.95rem;
    font-weight: 600;
    color: #1a1a2e;
    line-height: 1.4;
}
.precio-producto {
    font-size: 1.1rem;
    font-weight: 700;
    color: #16a34a;
    font-family: 'DM Mono', monospace;
}
.tel-producto {
    font-family: 'DM Mono', monospace;
    font-size: 0.95rem;
    font-weight: 500;
    color: #2563eb;
}
.meta-producto {
    font-size: 0.8rem;
    color: #8890a4;
    margin-top: 4px;
}

/* Info box */
.info-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    font-size: 0.875rem;
    color: #1e40af;
    margin-bottom: 1rem;
}

/* Divisor */
hr { border: none; border-top: 1px solid #e8eaf0; margin: 1rem 0; }

/* Sidebar stats */
.sidebar-stat {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.35rem 0;
    border-bottom: 1px solid #f0f2f7;
    font-size: 0.82rem;
}
.sidebar-stat-label { color: #8890a4; }
.sidebar-stat-value { font-weight: 600; color: #1a1a2e; font-family: 'DM Mono', monospace; }

/* Badge fuente */
.badge-fuente {
    display: inline-block;
    background: #f0f2f7;
    color: #4a5568;
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 500;
    margin-right: 3px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# DATOS
# ─────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_datos() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    return df


CATEGORIAS = {
    "laptop":      "💻 Laptops",
    "monitor":     "🖥️ Monitores",
    "disco":       "💾 Discos / SSD",
    "ram":         "🧠 Memorias RAM",
    "sonido":      "🔊 Bocinas y Sonido",
    "periferico":  "⌨️ Periféricos",
    "accesorio":   "🔌 Accesorios",
    "modem":       "📡 Modem / WiFi",
    "cpu":         "⚙️ Procesadores",
    "impresora":   "🖨️ Impresoras",
    "chasis":      "🖱️ Chasis y Fuentes",
    "ups":         "🔋 UPS / Energía",
    "dvd":         "💿 Lectores DVD",
    "pc":          "🖥️ PCs Escritorio",
    "cd":          "💿 CD / DVD Virgen",
    "gpu":         "🎮 Tarjetas de Video",
    "motherboard": "🔧 Motherboards",
    "internet":    "🌐 Internet / Nauta",
    "otros":       "📦 Otros",
}

CATEGORIAS_LIMPIO = {k: v.split(" ", 1)[1] for k, v in CATEGORIAS.items()}


# ─────────────────────────────────────────
# SIDEBAR — solo filtros
# ─────────────────────────────────────────
def sidebar(df: pd.DataFrame):
    with st.sidebar:
        # Logo / marca
        st.markdown("""
        <div style='padding: 1rem 0 1.2rem'>
            <div style='font-size:1.5rem; font-weight:700; color:#1a1a2e; letter-spacing:-0.5px;'>
                🖥️ CubaPrecios
            </div>
            <div style='font-size:0.78rem; color:#8890a4; margin-top:3px;'>
                Electrónica en Cuba · Revolico + Facebook
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── CATEGORÍA ──
        st.markdown("<div style='font-size:0.75rem; font-weight:600; color:#8890a4; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:0.4rem;'>Categoría</div>", unsafe_allow_html=True)
        cats_en_db = sorted([c for c in df["categoria"].dropna().unique() if c in CATEGORIAS])
        cat_sel = st.selectbox(
            "cat",
            options=cats_en_db,
            format_func=lambda x: CATEGORIAS.get(x, x),
            label_visibility="collapsed",
        )

        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

        # ── PROVINCIA ──
        provincias = sorted(df["provincia"].dropna().unique())
        prov_sel = None
        if provincias:
            st.markdown("<div style='font-size:0.75rem; font-weight:600; color:#8890a4; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:0.4rem;'>Provincia</div>", unsafe_allow_html=True)
            opciones_prov = ["Todas las provincias"] + provincias
            prov_elegida = st.selectbox("prov", options=opciones_prov, label_visibility="collapsed")
            prov_sel = None if prov_elegida == "Todas las provincias" else prov_elegida

        st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)

        # ── CHECKBOX ──
        solo_tel = st.checkbox("Solo anuncios con teléfono", value=True)

        st.divider()

        # ── ESTADÍSTICAS rápidas de la categoría ──
        df_cat = df[df["categoria"] == cat_sel]
        n_total = len(df_cat)
        n_tel   = int(df_cat["telefono"].notna().sum())
        p_avg   = df_cat["precio_usd"].mean()
        p_min   = df_cat["precio_usd"].min()
        p_max   = df_cat["precio_usd"].max()

        nombre_cat_limpio = CATEGORIAS_LIMPIO.get(cat_sel, cat_sel)
        st.markdown(f"<div style='font-size:0.82rem; font-weight:600; color:#1a1a2e; margin-bottom:0.5rem;'>{nombre_cat_limpio}</div>", unsafe_allow_html=True)

        stats = [
            ("Anuncios", f"{n_total}"),
            ("Con teléfono", f"{n_tel}"),
        ]
        if pd.notna(p_avg): stats.append(("Promedio", f"${p_avg:.0f}"))
        if pd.notna(p_min): stats.append(("Mínimo", f"${p_min:.0f}"))
        if pd.notna(p_max): stats.append(("Máximo", f"${p_max:.0f}"))

        for label, val in stats:
            st.markdown(f"""
            <div class="sidebar-stat">
                <span class="sidebar-stat-label">{label}</span>
                <span class="sidebar-stat-value">{val}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:1.5rem; font-size:0.72rem; color:#c0c4d0; text-align:center;'>Datos actualizados desde Revolico.com</div>", unsafe_allow_html=True)

    return cat_sel, prov_sel, solo_tel


def filtrar(df, cat, prov, solo_tel):
    df_f = df[df["categoria"] == cat].copy()
    if prov:
        df_f = df_f[df_f["provincia"] == prov]
    if solo_tel:
        df_f = df_f[df_f["telefono"].notna()]
    return df_f


# ─────────────────────────────────────────
# PÁGINA: INICIO
# ─────────────────────────────────────────
def pagina_inicio(df: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">{nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Precios actuales en Revolico · Cuba</div>', unsafe_allow_html=True)

    df_cat = df[df["categoria"] == cat].dropna(subset=["precio_usd"])

    if df_cat.empty:
        st.info("No hay anuncios con precio para esta categoría.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="card-metrica">
            <div class="card-valor">{len(df_cat)}</div>
            <div class="card-etiqueta">Anuncios</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="card-metrica card-verde">
            <div class="card-valor">${df_cat["precio_usd"].min():.0f}</div>
            <div class="card-etiqueta">Más barato</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="card-metrica card-rojo">
            <div class="card-valor">${df_cat["precio_usd"].max():.0f}</div>
            <div class="card-etiqueta">Más caro</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="card-metrica card-ambar">
            <div class="card-valor">${df_cat["precio_usd"].mean():.0f}</div>
            <div class="card-etiqueta">Promedio</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_iz, col_der = st.columns([1.4, 1])

    with col_iz:
        st.markdown('<div class="seccion">Distribución de precios</div>', unsafe_allow_html=True)
        st.markdown('<div class="seccion-sub">Cada barra muestra cuántos anuncios tienen ese precio</div>', unsafe_allow_html=True)
        fig = px.histogram(
            df_cat, x="precio_usd", nbins=25,
            color_discrete_sequence=["#2563eb"],
            labels={"precio_usd": "Precio (USD)", "count": "Cantidad"},
        )
        avg = df_cat["precio_usd"].mean()
        fig.add_vline(x=avg, line_dash="dash", line_color="#d97706", line_width=2,
                      annotation_text=f"  Promedio: ${avg:.0f}",
                      annotation_font_color="#d97706", annotation_font_size=12)
        fig.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family="DM Sans", color="#1a1a2e", size=12),
            margin=dict(l=0, r=0, t=10, b=0), height=300,
            bargap=0.08,
            xaxis=dict(gridcolor="#f0f2f7", tickprefix="$", title="Precio (USD)"),
            yaxis=dict(gridcolor="#f0f2f7", title="Anuncios"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        st.markdown('<div class="seccion">Anuncios recientes</div>', unsafe_allow_html=True)
        st.markdown('<div class="seccion-sub">Los últimos publicados</div>', unsafe_allow_html=True)
        col_fecha = "fecha" if "fecha" in df_cat.columns else "fecha_scraping"
        recientes = df_cat.sort_values(col_fecha, ascending=False, na_position="last").head(8)
        for _, row in recientes.iterrows():
            precio = f"${row['precio_usd']:.0f}" if pd.notna(row["precio_usd"]) else "—"
            titulo = str(row["titulo"])[:55] + "..." if len(str(row["titulo"])) > 55 else str(row["titulo"])
            tel = row["telefono"] if pd.notna(row.get("telefono")) else "Sin tel."
            st.markdown(f"""
            <div style='display:flex; justify-content:space-between; align-items:center;
                        padding:0.5rem 0; border-bottom:1px solid #f0f2f7;'>
                <div>
                    <div style='font-size:0.85rem; color:#1a1a2e;'>{titulo}</div>
                    <div style='font-size:0.78rem; color:#8890a4;'>{tel}</div>
                </div>
                <div style='font-weight:700; color:#16a34a; white-space:nowrap;
                            font-family: DM Mono, monospace; font-size:0.95rem; margin-left:1rem;'>
                    {precio}
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# PÁGINA: EXPLORAR
# ─────────────────────────────────────────
def pagina_explorar(df: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Explorar {nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">{len(df)} anuncios disponibles</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("No hay anuncios con los filtros seleccionados.")
        return

    col_busq, col_orden, col_count = st.columns([3, 2, 1])

    with col_busq:
        busqueda = st.text_input("Buscar", placeholder="Buscar por nombre, marca, modelo...", label_visibility="collapsed")

    with col_orden:
        orden = st.selectbox("orden", ["Precio: menor a mayor", "Precio: mayor a menor", "Más recientes"], label_visibility="collapsed")

    df_res = df.copy()
    if busqueda:
        df_res = df_res[df_res["titulo"].str.contains(busqueda, case=False, na=False)]

    if "menor" in orden:
        df_res = df_res.sort_values("precio_usd", ascending=True, na_position="last")
    elif "mayor" in orden:
        df_res = df_res.sort_values("precio_usd", ascending=False, na_position="last")
    else:
        df_res = df_res.sort_values("fecha_scraping", ascending=False, na_position="last")

    with col_count:
        st.markdown(f"<div style='padding:0.6rem 0; font-size:0.85rem; color:#8890a4; text-align:right;'>{len(df_res)} resultados</div>", unsafe_allow_html=True)

    if busqueda and df_res.empty:
        st.info(f'No se encontraron resultados para "{busqueda}".')
        return

    df_tabla = df_res[["titulo", "precio_usd", "telefono", "vendedor", "provincia", "url"]].copy()
    df_tabla["precio_usd"] = df_tabla["precio_usd"].apply(lambda x: f"${x:.0f}" if pd.notna(x) else "Sin precio")
    df_tabla.columns = ["Producto", "Precio", "Teléfono", "Vendedor", "Provincia", "Ver anuncio"]
    df_tabla = df_tabla.fillna("—")

    st.dataframe(
        df_tabla,
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={
            "Ver anuncio": st.column_config.LinkColumn("Ver anuncio"),
            "Precio": st.column_config.TextColumn("Precio"),
        }
    )

    csv_data = df_res[["titulo", "precio_usd", "moneda", "telefono", "whatsapp",
                        "vendedor", "provincia", "url"]].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ Descargar lista en CSV",
        data=csv_data,
        file_name=f"cubaprecios_{cat}.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────
# PÁGINA: COMPARAR
# ─────────────────────────────────────────
def pagina_comparar(df: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Comparar precios — {nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Así están los precios hoy</div>', unsafe_allow_html=True)

    df_p = df.dropna(subset=["precio_usd"])
    if df_p.empty:
        st.info("No hay anuncios con precio para comparar.")
        return

    pmin = df_p["precio_usd"].min()
    pmax = df_p["precio_usd"].max()
    pavg = df_p["precio_usd"].mean()
    pmed = df_p["precio_usd"].median()

    st.markdown(f"""
    <div class="info-box">
        Hay <b>{len(df_p)}</b> anuncios con precio.
        El más barato cuesta <b>${pmin:.0f}</b> y el más caro <b>${pmax:.0f}</b>.
        La mitad de los anuncios están por debajo de <b>${pmed:.0f}</b>.
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card-metrica card-verde">
            <div class="card-valor">${pmin:.0f}</div>
            <div class="card-etiqueta">El más barato</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card-metrica card-rojo">
            <div class="card-valor">${pmax:.0f}</div>
            <div class="card-etiqueta">El más caro</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="card-metrica card-ambar">
            <div class="card-valor">${pavg:.0f}</div>
            <div class="card-etiqueta">Precio promedio</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="card-metrica card-azul">
            <div class="card-valor">${pmed:.0f}</div>
            <div class="card-etiqueta">Precio del medio</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_iz, col_der = st.columns(2)

    with col_iz:
        st.markdown('<div class="seccion">¿Cómo están distribuidos los precios?</div>', unsafe_allow_html=True)
        st.markdown('<div class="seccion-sub">Cada barra muestra cuántos anuncios tienen ese precio</div>', unsafe_allow_html=True)
        fig = px.histogram(
            df_p, x="precio_usd", nbins=20,
            color_discrete_sequence=["#2563eb"],
            labels={"precio_usd": "Precio (USD)", "count": "Anuncios"},
        )
        fig.add_vline(x=pavg, line_dash="dash", line_color="#d97706", line_width=2,
                      annotation_text=f"  Promedio ${pavg:.0f}",
                      annotation_font_color="#d97706", annotation_font_size=11)
        fig.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family="DM Sans", color="#1a1a2e", size=11),
            margin=dict(l=0, r=0, t=10, b=0), height=300,
            bargap=0.08,
            xaxis=dict(gridcolor="#f0f2f7", tickprefix="$", title="Precio (USD)"),
            yaxis=dict(gridcolor="#f0f2f7", title="Cantidad"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        st.markdown('<div class="seccion">¿Qué precio es normal y cuáles son extremos?</div>', unsafe_allow_html=True)
        st.markdown('<div class="seccion-sub">La caja central muestra el rango de precios más comunes</div>', unsafe_allow_html=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Box(
            y=df_p["precio_usd"],
            name=nombre_cat,
            marker_color="#2563eb",
            line_color="#2563eb",
            fillcolor="rgba(37,99,235,0.1)",
            boxpoints="outliers",
            hovertemplate="$%{y:.0f}<extra></extra>",
        ))
        fig2.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family="DM Sans", color="#1a1a2e", size=11),
            margin=dict(l=0, r=0, t=10, b=0), height=300,
            showlegend=False,
            yaxis=dict(gridcolor="#f0f2f7", tickprefix="$", title="Precio (USD)"),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig2, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="seccion">Los 5 más económicos ahora mismo</div>', unsafe_allow_html=True)
        baratos = df_p.nsmallest(5, "precio_usd")[["titulo", "precio_usd", "telefono", "vendedor"]].copy()
        baratos["precio_usd"] = baratos["precio_usd"].apply(lambda x: f"${x:.0f}")
        baratos.columns = ["Producto", "Precio", "Teléfono", "Vendedor"]
        st.dataframe(baratos.fillna("—"), hide_index=True, use_container_width=True)

    with col_b:
        st.markdown('<div class="seccion">Los 5 más caros ahora mismo</div>', unsafe_allow_html=True)
        caros = df_p.nlargest(5, "precio_usd")[["titulo", "precio_usd", "telefono", "vendedor"]].copy()
        caros["precio_usd"] = caros["precio_usd"].apply(lambda x: f"${x:.0f}")
        caros.columns = ["Producto", "Precio", "Teléfono", "Vendedor"]
        st.dataframe(caros.fillna("—"), hide_index=True, use_container_width=True)


# ─────────────────────────────────────────
# PÁGINA: LOS MÁS BARATOS
# ─────────────────────────────────────────
def pagina_ranking(df: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Los más baratos — {nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Ordenados de menor a mayor precio</div>', unsafe_allow_html=True)

    df_p = df.dropna(subset=["precio_usd"]).sort_values("precio_usd")
    if df_p.empty:
        st.info("No hay anuncios con precio.")
        return

    top20 = df_p.head(20).copy()
    top20["label"] = top20["titulo"].str[:38]

    fig = px.bar(
        top20, x="precio_usd", y="label", orientation="h",
        color="precio_usd",
        color_continuous_scale=[[0, "#16a34a"], [0.5, "#d97706"], [1, "#dc2626"]],
        labels={"precio_usd": "Precio (USD)", "label": ""},
        custom_data=["telefono", "vendedor"],
    )
    fig.update_traces(hovertemplate="<b>$%{x:.0f}</b><br>Tel: %{customdata[0]}<extra></extra>")
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="DM Sans", color="#1a1a2e", size=11),
        margin=dict(l=0, r=0, t=10, b=0), height=520,
        coloraxis_showscale=False,
        yaxis=dict(gridcolor="#f0f2f7", autorange="reversed"),
        xaxis=dict(gridcolor="#f0f2f7", tickprefix="$", title="Precio en dólares"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="seccion">Lista completa con contacto</div>', unsafe_allow_html=True)

    df_lista = df_p[["titulo", "precio_usd", "telefono", "whatsapp", "vendedor", "provincia", "url"]].copy()
    df_lista["precio_usd"] = df_lista["precio_usd"].apply(lambda x: f"${x:.0f}")
    df_lista.columns = ["Producto", "Precio", "Teléfono", "WhatsApp", "Vendedor", "Provincia", "Ver anuncio"]
    st.dataframe(
        df_lista.fillna("—"),
        use_container_width=True,
        height=420,
        hide_index=True,
        column_config={"Ver anuncio": st.column_config.LinkColumn("Ver anuncio")}
    )


# ─────────────────────────────────────────
# PÁGINA: CONTACTOS
# ─────────────────────────────────────────
def pagina_contactos(df: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Contactar vendedores — {nombre_cat}</div>', unsafe_allow_html=True)

    df_tel = df[df["telefono"].notna()].sort_values("precio_usd", na_position="last")
    st.markdown(f'<div class="app-subtitulo">{len(df_tel)} vendedores con teléfono disponible</div>', unsafe_allow_html=True)

    if df_tel.empty:
        st.info("No hay vendedores con teléfono en esta selección.")
        return

    busqueda = st.text_input("Buscar", placeholder="Buscar producto por nombre o marca...", label_visibility="collapsed")
    if busqueda:
        df_tel = df_tel[df_tel["titulo"].str.contains(busqueda, case=False, na=False)]
        if df_tel.empty:
            st.info(f'Sin resultados para "{busqueda}".')
            return
        st.markdown(f"**{len(df_tel)}** resultados")

    st.markdown("<br>", unsafe_allow_html=True)

    for _, row in df_tel.head(40).iterrows():
        titulo   = str(row["titulo"])[:80] + "..." if len(str(row["titulo"])) > 80 else str(row["titulo"])
        precio   = f"${row['precio_usd']:.0f} USD" if pd.notna(row["precio_usd"]) else "Precio a consultar"
        tel      = str(row["telefono"]) if pd.notna(row["telefono"]) else None
        whatsapp = str(row["whatsapp"]) if pd.notna(row.get("whatsapp")) else None
        vendedor = str(row["vendedor"]) if pd.notna(row.get("vendedor")) else None
        provincia = str(row["provincia"]) if pd.notna(row.get("provincia")) else None
        url      = str(row["url"]) if pd.notna(row.get("url")) else None

        col_info, col_tel, col_acc = st.columns([3, 1.2, 1])

        with col_info:
            meta = []
            if vendedor:  meta.append(f"Vendedor: {vendedor}")
            if provincia: meta.append(f"Provincia: {provincia}")
            meta_str = " · ".join(meta) if meta else "Sin información adicional"
            st.markdown(f"""
            <div class="card-contacto">
                <div class="titulo-producto">{titulo}</div>
                <div style='margin-top:6px;'>
                    <span class="precio-producto">{precio}</span>
                </div>
                <div class="meta-producto">{meta_str}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_tel:
            if tel:
                st.markdown(f"""
                <div style='padding:1.2rem 0; text-align:center;'>
                    <div class="tel-producto">{tel}</div>
                    <div style='font-size:0.75rem; color:#8890a4; margin-top:2px;'>Llamar o SMS</div>
                </div>
                """, unsafe_allow_html=True)

        with col_acc:
            st.markdown("<div style='padding:0.6rem 0;'>", unsafe_allow_html=True)
            if url:
                st.link_button("Ver anuncio", url, use_container_width=True)
            if whatsapp:
                num_wa = whatsapp.replace("+", "").replace(" ", "")
                if not num_wa.startswith("53"):
                    num_wa = "53" + num_wa
                st.link_button("WhatsApp", f"https://wa.me/{num_wa}", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    if len(df_tel) > 40:
        st.info(f"Mostrando 40 de {len(df_tel)} contactos. Usa el buscador para encontrar algo específico.")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    df = cargar_datos()

    if df.empty:
        st.error("No se encontró la base de datos.")
        st.info("Ejecuta primero: python limpiar_datos.py")
        return

    cat_sel, prov_sel, solo_tel = sidebar(df)
    df_filtrado = filtrar(df, cat_sel, prov_sel, solo_tel)

    # NAVEGACIÓN — tabs horizontales (navbar)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏠  Inicio",
        "🔍  Explorar",
        "📊  Comparar precios",
        "💰  Los más baratos",
        "📞  Contactar vendedores",
    ])

    with tab1:
        pagina_inicio(df, cat_sel)

    with tab2:
        pagina_explorar(df_filtrado, cat_sel)

    with tab3:
        pagina_comparar(df_filtrado, cat_sel)

    with tab4:
        pagina_ranking(df_filtrado, cat_sel)

    with tab5:
        pagina_contactos(df_filtrado, cat_sel)


if __name__ == "__main__":
    main()