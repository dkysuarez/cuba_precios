"""
CubaPrecios — App Streamlit v2
Diseño limpio, minimalista, intuitivo para usuarios no técnicos
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
# ESTILOS — limpio, blanco, minimalista
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* Reset general */
html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif;
    background-color: #f8f9fb;
    color: #1a1a2e;
}

/* SIDEBAR - FIX para Streamlit Cloud */
[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    background-color: #ffffff !important;
    border-right: 1px solid #e8eaf0 !important;
    min-width: 300px !important;
    width: 300px !important;
    transform: translateX(0px) !important;
    position: relative !important;
    z-index: 999 !important;
}

/* Forzar que el sidebar no se oculte en modo responsive */
@media (max-width: 2000px) {
    [data-testid="stSidebar"] {
        transform: none !important;
        width: 300px !important;
        min-width: 300px !important;
        margin-left: 0 !important;
        position: relative !important;
    }
}

/* Evitar que el sidebar se colapse automáticamente */
[data-testid="stSidebarCollapsed"] {
    display: none !important;
}

/* Asegurar que el botón de colapsar sea visible */
[data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: fixed !important;
    top: 1rem !important;
    left: 310px !important;
    z-index: 1000 !important;
    background: white !important;
    border-radius: 50% !important;
    width: 32px !important;
    height: 32px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}

/* Estilo del botón de colapsar al hacer hover */
[data-testid="stSidebarCollapseButton"]:hover {
    background: #f0f2f7 !important;
    cursor: pointer !important;
}

/* Asegurar que el botón de colapsar no se oculte en móviles */
@media (max-width: 768px) {
    [data-testid="stSidebarCollapseButton"] {
        left: 10px !important;
        top: 10px !important;
        position: fixed !important;
    }
    
    [data-testid="stSidebar"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        height: 100vh !important;
        overflow-y: auto !important;
        z-index: 1000 !important;
        transform: translateX(0px) !important;
    }
}

/* Contenido principal */
.block-container {
    padding-top: 2rem;
    max-width: 1200px;
}

/* Ocultar elementos de Streamlit */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Titulo de la app */
.app-titulo {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1a1a2e;
    letter-spacing: -0.5px;
}
.app-subtitulo {
    font-size: 0.9rem;
    color: #8890a4;
    margin-top: 2px;
    margin-bottom: 1.5rem;
}

/* Cards de métricas */
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
    font-size: 0.78rem;
    color: #8890a4;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
.card-verde .card-valor { color: #16a34a; }
.card-azul  .card-valor { color: #2563eb; }
.card-rojo  .card-valor { color: #dc2626; }

/* Sección titulo */
.seccion {
    font-size: 1rem;
    font-weight: 600;
    color: #1a1a2e;
    margin-bottom: 0.8rem;
    margin-top: 0.2rem;
}

/* Tabla limpia */
.stDataFrame {
    border: 1px solid #e8eaf0 !important;
    border-radius: 10px !important;
}
.stDataFrame th {
    background-color: #f8f9fb !important;
    color: #8890a4 !important;
    font-size: 0.78rem !important;
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

/* Input de busqueda */
.stTextInput > div > div > input {
    border-radius: 8px !important;
    border: 1px solid #e8eaf0 !important;
    background: #ffffff !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* Selectbox */
.stSelectbox > div > div {
    border-radius: 8px !important;
    border: 1px solid #e8eaf0 !important;
    background: #ffffff !important;
}

/* Multiselect */
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

/* Pill de categoria */
.pill {
    display: inline-block;
    background: #f0f2f7;
    color: #4a5568;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 500;
    margin-right: 4px;
}

/* Divisor suave */
hr { border: none; border-top: 1px solid #e8eaf0; margin: 1rem 0; }

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

/* Precio min/max labels */
.precio-min-label { color: #16a34a; font-weight: 600; }
.precio-max-label { color: #dc2626; font-weight: 600; }
.precio-avg-label { color: #d97706; font-weight: 600; }
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
    "laptop":      "Laptops",
    "monitor":     "Monitores",
    "disco":       "Discos duros / SSD",
    "ram":         "Memorias RAM",
    "teclado":     "Teclados y Mouse",
    "modem":       "Modem / WiFi / Redes",
    "cpu":         "Procesadores",
    "webcam":      "Webcam y Audio",
    "impresora":   "Impresoras",
    "sonido":      "Bocinas y Sonido",
    "chasis":      "Chasis y Fuentes",
    "ups":         "UPS y Reguladores",
    "dvd":         "Lectores DVD",
    "pc":          "PCs de Escritorio",
    "cd":          "CD / DVD Virgen",
    "gpu":         "Tarjetas de Video",
    "motherboard": "Motherboards",
    "internet":    "Internet y Nauta",
    "otros":       "Otros",
}


# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
def sidebar(df: pd.DataFrame):
    with st.sidebar:
        st.markdown("""
        <div style='padding:0.5rem 0 1rem'>
            <div style='font-size:1.4rem; font-weight:700; color:#1a1a2e;'>CubaPrecios</div>
            <div style='font-size:0.8rem; color:#8890a4; margin-top:2px;'>
                Electrónica en Cuba
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Navegacion como links simples
        st.markdown("**Secciones**")
        pagina = st.selectbox(
            "Ir a",
            ["Inicio", "Explorar productos", "Comparar precios",
             "Los más baratos", "Contactar vendedores"],
            label_visibility="collapsed"
        )

        st.divider()

        # Categoria — una sola, no todas
        cats_en_db = sorted([c for c in df["categoria"].dropna().unique() if c in CATEGORIAS])
        st.markdown("**Categoría**")
        cat_sel = st.selectbox(
            "Selecciona una categoría",
            options=cats_en_db,
            format_func=lambda x: CATEGORIAS.get(x, x),
            label_visibility="collapsed",
        )

        # Filtro de provincia (solo si hay datos)
        provincias = sorted(df["provincia"].dropna().unique())
        prov_sel = None
        if provincias:
            st.markdown("**Provincia**")
            opciones_prov = ["Todas"] + provincias
            prov_elegida = st.selectbox(
                "Provincia",
                options=opciones_prov,
                label_visibility="collapsed",
            )
            prov_sel = None if prov_elegida == "Todas" else prov_elegida

        # Solo con telefono
        solo_tel = st.checkbox("Solo anuncios con teléfono", value=True)

        st.divider()

        # Estadistica rapida de la categoria elegida
        df_cat = df[df["categoria"] == cat_sel]
        n_total = len(df_cat)
        n_tel   = df_cat["telefono"].notna().sum()
        p_avg   = df_cat["precio_usd"].mean()

        st.markdown(f"""
        <div style='font-size:0.82rem; color:#8890a4; line-height:2;'>
            <b style='color:#1a1a2e;'>{CATEGORIAS.get(cat_sel, cat_sel)}</b><br>
            {n_total} anuncios en total<br>
            {n_tel} con teléfono<br>
            {"Precio promedio: $" + f"{p_avg:.0f}" if pd.notna(p_avg) else ""}
        </div>
        """, unsafe_allow_html=True)

    return pagina, cat_sel, prov_sel, solo_tel


def filtrar(df, cat, prov, solo_tel):
    df_f = df[df["categoria"] == cat].copy()
    if prov:
        df_f = df_f[df_f["provincia"] == prov]
    if solo_tel:
        df_f = df_f[df_f["telefono"].notna()]
    return df_f


# ─────────────────────────────────────────
# PAGINA: INICIO
# ─────────────────────────────────────────
def pagina_inicio(df: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS.get(cat, cat)

    st.markdown(f'<div class="app-titulo">{nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Precios actuales en Revolico · Cuba</div>',
                unsafe_allow_html=True)

    df_cat = df[df["categoria"] == cat].dropna(subset=["precio_usd"])

    if df_cat.empty:
        st.info("No hay anuncios con precio para esta categoría.")
        return

    # 4 métricas clave
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="card-metrica">
            <div class="card-valor">{len(df_cat)}</div>
            <div class="card-etiqueta">Anuncios encontrados</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="card-metrica card-verde">
            <div class="card-valor">${df_cat["precio_usd"].min():.0f}</div>
            <div class="card-etiqueta">Precio mas bajo</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="card-metrica card-rojo">
            <div class="card-valor">${df_cat["precio_usd"].max():.0f}</div>
            <div class="card-etiqueta">Precio mas alto</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="card-metrica card-azul">
            <div class="card-valor">${df_cat["precio_usd"].mean():.0f}</div>
            <div class="card-etiqueta">Precio promedio</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_iz, col_der = st.columns([1.3, 1])

    # Grafica de distribucion — simple y clara
    with col_iz:
        st.markdown('<div class="seccion">Distribución de precios</div>',
                    unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:0.82rem; color:#8890a4; margin-bottom:0.8rem;'>"
            "Cada barra muestra cuántos anuncios tienen ese precio</div>",
            unsafe_allow_html=True
        )
        fig = px.histogram(
            df_cat,
            x="precio_usd",
            nbins=25,
            color_discrete_sequence=["#2563eb"],
            labels={"precio_usd": "Precio (USD)", "count": "Cantidad de anuncios"},
        )
        avg = df_cat["precio_usd"].mean()
        fig.add_vline(
            x=avg, line_dash="dash", line_color="#d97706", line_width=2,
            annotation_text=f"  Promedio: ${avg:.0f}",
            annotation_font_color="#d97706",
            annotation_font_size=12,
        )
        fig.update_layout(
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(family="DM Sans", color="#1a1a2e", size=12),
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            bargap=0.08,
            xaxis=dict(
                gridcolor="#f0f2f7",
                tickprefix="$",
                title="Precio en dólares (USD)",
            ),
            yaxis=dict(
                gridcolor="#f0f2f7",
                title="Cantidad de anuncios",
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Anuncios recientes
    with col_der:
        st.markdown('<div class="seccion">Anuncios recientes</div>',
                    unsafe_allow_html=True)
        col_fecha = "fecha" if "fecha" in df_cat.columns else "fecha_scraping"
        recientes = df_cat.sort_values(col_fecha, ascending=False, na_position="last").head(8)
        for _, row in recientes.iterrows():
            precio = f"${row['precio_usd']:.0f}" if pd.notna(row["precio_usd"]) else "—"
            titulo = str(row["titulo"])[:55] + "..." if len(str(row["titulo"])) > 55 else str(row["titulo"])
            tel = row["telefono"] if pd.notna(row.get("telefono")) else "Sin tel."
            st.markdown(f"""
            <div style='display:flex; justify-content:space-between;
                        align-items:center; padding:0.5rem 0;
                        border-bottom:1px solid #f0f2f7;'>
                <div>
                    <div style='font-size:0.85rem; color:#1a1a2e;'>{titulo}</div>
                    <div style='font-size:0.78rem; color:#8890a4;'>{tel}</div>
                </div>
                <div style='font-weight:700; color:#16a34a; white-space:nowrap;
                            font-family: DM Mono, monospace; font-size:0.95rem;'>
                    {precio}
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# PAGINA: EXPLORAR
# ─────────────────────────────────────────
def pagina_explorar(df: pd.DataFrame):
    nombre_cat = CATEGORIAS.get(df["categoria"].iloc[0] if not df.empty else "", "")
    st.markdown(f'<div class="app-titulo">Explorar {nombre_cat}</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">{len(df)} anuncios disponibles</div>',
                unsafe_allow_html=True)

    if df.empty:
        st.info("No hay anuncios con los filtros seleccionados.")
        return

    # Barra de busqueda
    busqueda = st.text_input("",
        placeholder="Buscar por nombre, marca, modelo...",
        label_visibility="collapsed"
    )
    if busqueda:
        df = df[df["titulo"].str.contains(busqueda, case=False, na=False)]
        if df.empty:
            st.info(f'No se encontraron resultados para "{busqueda}".')
            return
        st.markdown(f"**{len(df)}** resultados para *{busqueda}*")

    # Ordenar
    col_a, col_b = st.columns([3, 1])
    with col_a:
        orden = st.selectbox("Ordenar por",
            ["Precio: menor a mayor", "Precio: mayor a menor", "Más recientes"],
            label_visibility="collapsed"
        )
    with col_b:
        st.markdown(f"<div style='padding:0.6rem 0; font-size:0.85rem; color:#8890a4;'>"
                    f"{len(df)} resultados</div>", unsafe_allow_html=True)

    if "menor" in orden:
        df = df.sort_values("precio_usd", ascending=True, na_position="last")
    elif "mayor" in orden:
        df = df.sort_values("precio_usd", ascending=False, na_position="last")
    else:
        df = df.sort_values("fecha_scraping", ascending=False, na_position="last")

    # Tabla limpia con columnas relevantes
    df_tabla = df[["titulo", "precio_usd", "telefono", "vendedor", "provincia", "url"]].copy()
    df_tabla["precio_usd"] = df_tabla["precio_usd"].apply(
        lambda x: f"${x:.0f}" if pd.notna(x) else "Sin precio"
    )
    df_tabla.columns = ["Producto", "Precio", "Teléfono", "Vendedor", "Provincia", "Ver anuncio"]
    df_tabla = df_tabla.fillna("—")

    st.dataframe(
        df_tabla,
        use_container_width=True,
        height=480,
        hide_index=True,
        column_config={
            "Ver anuncio": st.column_config.LinkColumn("Ver anuncio"),
            "Precio": st.column_config.TextColumn("Precio"),
        }
    )

    # Descargar
    csv_data = df[["titulo", "precio_usd", "moneda", "telefono", "whatsapp",
                   "vendedor", "provincia", "url"]].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "Descargar lista en Excel/CSV",
        data=csv_data,
        file_name=f"cubaprecios_{df['categoria'].iloc[0]}.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────
# PAGINA: COMPARAR PRECIOS
# ─────────────────────────────────────────
def pagina_comparar(df: pd.DataFrame):
    nombre_cat = CATEGORIAS.get(df["categoria"].iloc[0] if not df.empty else "", "")
    st.markdown(f'<div class="app-titulo">Comparar precios — {nombre_cat}</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Así están los precios hoy</div>',
                unsafe_allow_html=True)

    df_p = df.dropna(subset=["precio_usd"])
    if df_p.empty:
        st.info("No hay anuncios con precio para comparar.")
        return

    pmin = df_p["precio_usd"].min()
    pmax = df_p["precio_usd"].max()
    pavg = df_p["precio_usd"].mean()
    pmed = df_p["precio_usd"].median()

    # Resumen en palabras — para no técnicos
    st.markdown(f"""
    <div class="info-box">
        Hay <b>{len(df_p)}</b> anuncios con precio.
        El más barato cuesta <b>${pmin:.0f}</b> y el más caro <b>${pmax:.0f}</b>.
        La mitad de los anuncios están por debajo de <b>${pmed:.0f}</b>.
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="card-metrica card-verde">
            <div class="card-valor">${pmin:.0f}</div>
            <div class="card-etiqueta">El más barato</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="card-metrica card-rojo">
            <div class="card-valor">${pmax:.0f}</div>
            <div class="card-etiqueta">El más caro</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="card-metrica">
            <div class="card-valor" style="color:#d97706">${pavg:.0f}</div>
            <div class="card-etiqueta">Precio promedio</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="card-metrica card-azul">
            <div class="card-valor">${pmed:.0f}</div>
            <div class="card-etiqueta">Precio del medio</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_iz, col_der = st.columns(2)

    with col_iz:
        st.markdown('<div class="seccion">¿Cómo están distribuidos los precios?</div>',
                    unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:0.82rem; color:#8890a4; margin-bottom:0.5rem;'>"
            "Cada barra muestra cuántos anuncios tienen ese precio</div>",
            unsafe_allow_html=True
        )
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
        st.markdown('<div class="seccion">¿Qué precio es normal y cuáles son extremos?</div>',
                    unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:0.82rem; color:#8890a4; margin-bottom:0.5rem;'>"
            "La caja central muestra el rango de precios más comunes</div>",
            unsafe_allow_html=True
        )
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

    # Tabla los 5 mas baratos y 5 mas caros
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="seccion">Los 5 más económicos ahora mismo</div>',
                    unsafe_allow_html=True)
        baratos = df_p.nsmallest(5, "precio_usd")[
            ["titulo", "precio_usd", "telefono", "vendedor"]
        ].copy()
        baratos["precio_usd"] = baratos["precio_usd"].apply(lambda x: f"${x:.0f}")
        baratos.columns = ["Producto", "Precio", "Teléfono", "Vendedor"]
        baratos = baratos.fillna("—")
        st.dataframe(baratos, hide_index=True, use_container_width=True)

    with col_b:
        st.markdown('<div class="seccion">Los 5 más caros ahora mismo</div>',
                    unsafe_allow_html=True)
        caros = df_p.nlargest(5, "precio_usd")[
            ["titulo", "precio_usd", "telefono", "vendedor"]
        ].copy()
        caros["precio_usd"] = caros["precio_usd"].apply(lambda x: f"${x:.0f}")
        caros.columns = ["Producto", "Precio", "Teléfono", "Vendedor"]
        caros = caros.fillna("—")
        st.dataframe(caros, hide_index=True, use_container_width=True)


# ─────────────────────────────────────────
# PAGINA: LOS MAS BARATOS
# ─────────────────────────────────────────
def pagina_ranking(df: pd.DataFrame):
    nombre_cat = CATEGORIAS.get(df["categoria"].iloc[0] if not df.empty else "", "")
    st.markdown(f'<div class="app-titulo">Los más baratos — {nombre_cat}</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Ordenados de menor a mayor precio</div>',
                unsafe_allow_html=True)

    df_p = df.dropna(subset=["precio_usd"]).sort_values("precio_usd")

    if df_p.empty:
        st.info("No hay anuncios con precio.")
        return

    # Grafica de barras horizontal — los 20 más baratos
    top20 = df_p.head(20).copy()
    top20["titulo_corto"] = top20["titulo"].str[:40] + "..."
    top20["label"] = top20["titulo_corto"].str[:35]

    fig = px.bar(
        top20,
        x="precio_usd",
        y="label",
        orientation="h",
        color="precio_usd",
        color_continuous_scale=[[0, "#16a34a"], [0.5, "#d97706"], [1, "#dc2626"]],
        labels={"precio_usd": "Precio (USD)", "label": ""},
        custom_data=["telefono", "vendedor"],
    )
    fig.update_traces(
        hovertemplate="<b>$%{x:.0f}</b><br>Tel: %{customdata[0]}<extra></extra>"
    )
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="DM Sans", color="#1a1a2e", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
        height=520,
        coloraxis_showscale=False,
        yaxis=dict(gridcolor="#f0f2f7", autorange="reversed"),
        xaxis=dict(gridcolor="#f0f2f7", tickprefix="$", title="Precio en dólares"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Lista completa con telefono
    st.markdown('<div class="seccion">Lista completa con contacto</div>',
                unsafe_allow_html=True)

    df_lista = df_p[["titulo", "precio_usd", "telefono", "whatsapp",
                      "vendedor", "provincia", "url"]].copy()
    df_lista["precio_usd"] = df_lista["precio_usd"].apply(lambda x: f"${x:.0f}")
    df_lista.columns = ["Producto", "Precio", "Teléfono", "WhatsApp",
                        "Vendedor", "Provincia", "Ver anuncio"]
    df_lista = df_lista.fillna("—")

    st.dataframe(
        df_lista,
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={"Ver anuncio": st.column_config.LinkColumn("Ver anuncio")}
    )


# ─────────────────────────────────────────
# PAGINA: CONTACTOS
# ─────────────────────────────────────────
def pagina_contactos(df: pd.DataFrame):
    nombre_cat = CATEGORIAS.get(df["categoria"].iloc[0] if not df.empty else "", "")
    st.markdown(f'<div class="app-titulo">Contactar vendedores — {nombre_cat}</div>',
                unsafe_allow_html=True)

    df_tel = df[df["telefono"].notna()].sort_values("precio_usd", na_position="last")
    st.markdown(f'<div class="app-subtitulo">{len(df_tel)} vendedores con teléfono disponible</div>',
                unsafe_allow_html=True)

    if df_tel.empty:
        st.info("No hay vendedores con teléfono en esta selección.")
        return

    # Buscar
    busqueda = st.text_input("",
        placeholder="Buscar producto por nombre o marca...",
        label_visibility="collapsed"
    )
    if busqueda:
        df_tel = df_tel[df_tel["titulo"].str.contains(busqueda, case=False, na=False)]
        if df_tel.empty:
            st.info(f'Sin resultados para "{busqueda}".')
            return
        st.markdown(f"**{len(df_tel)}** resultados")

    st.markdown("<br>", unsafe_allow_html=True)

    # Cards de contacto
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
                st.link_button("WhatsApp", f"https://wa.me/{num_wa}",
                               use_container_width=True)
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

    pagina, cat_sel, prov_sel, solo_tel = sidebar(df)
    df_filtrado = filtrar(df, cat_sel, prov_sel, solo_tel)

    if "Inicio" in pagina:
        pagina_inicio(df, cat_sel)
    elif "Explorar" in pagina:
        pagina_explorar(df_filtrado)
    elif "Comparar" in pagina:
        pagina_comparar(df_filtrado)
    elif "baratos" in pagina:
        pagina_ranking(df_filtrado)
    elif "Contactar" in pagina:
        pagina_contactos(df_filtrado)


if __name__ == "__main__":
    main()