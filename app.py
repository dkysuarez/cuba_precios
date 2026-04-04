"""
CubaPrecios — App Streamlit v8
Mejoras UI/UX:
- Cards en grid HTML real (2 columnas simétricas, misma altura)
- Filtros y selector de orden con contraste visual claro
- Sidebar rediseñada con secciones bien delimitadas
- Toda la lógica original intacta
"""

import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

from config import DB_PATH

st.set_page_config(
    page_title="CubaPrecios — Electrónica en Cuba",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# ESTILOS GLOBALES
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=DM+Mono:wght@400;500&display=swap');

/* ── Base ── */
html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif;
    background-color: #f0f2f6 !important;
    color: #1a1a2e;
}
#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container {
    padding-top: 1.2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1340px !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 2px solid #e2e8f0 !important;
    min-width: 290px !important;
    width: 290px !important;
}
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* Selectbox dentro de sidebar — fondo blanco con borde visible */
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child {
    background-color: #f8fafc !important;
    border: 2px solid #94a3b8 !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child:hover {
    border-color: #475569 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] svg { color: #475569 !important; }

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #ffffff;
    border-bottom: 2px solid #e2e8f0;
    padding: 0 0.5rem;
    margin-bottom: 1.5rem;
    border-radius: 10px 10px 0 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.stTabs [data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.88rem;
    font-weight: 500;
    color: #64748b;
    padding: 0.75rem 1.1rem;
    border-bottom: 3px solid transparent;
    margin-bottom: -2px;
    border-radius: 0;
    background: transparent !important;
    transition: color 0.15s;
}
.stTabs [aria-selected="true"] {
    color: #1e3a5f !important;
    border-bottom: 3px solid #1e3a5f !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #1e3a5f !important; }

/* ── Buscador con borde visible ── */
[data-testid="stMain"] [data-testid="stTextInput"] input {
    border: 2px solid #94a3b8 !important;
    border-radius: 8px !important;
    background-color: #ffffff !important;
    padding: 0.45rem 0.75rem !important;
}
[data-testid="stMain"] [data-testid="stTextInput"] input:focus {
    border-color: #1e3a5f !important;
    box-shadow: 0 0 0 3px rgba(30,58,95,0.1) !important;
}

/* ── Selector de orden — tono suave, letras oscuras ── */
[data-testid="stMain"] [data-baseweb="select"] > div:first-child {
    background-color: #f1f5f9 !important;
    border: 2px solid #94a3b8 !important;
    border-radius: 8px !important;
}
[data-testid="stMain"] [data-baseweb="select"] > div:first-child:hover {
    border-color: #475569 !important;
    background-color: #e8edf3 !important;
}
[data-testid="stMain"] [data-baseweb="select"] svg { color: #475569 !important; }
[data-testid="stMain"] [data-baseweb="select"] [data-baseweb="select-placeholder"],
[data-testid="stMain"] [data-baseweb="select"] [class*="singleValue"] {
    color: #334155 !important;
    font-weight: 600 !important;
}

/* ── Cabecera ── */
.app-titulo {
    font-size: 1.75rem;
    font-weight: 800;
    color: #1a1a2e;
    letter-spacing: -0.5px;
    line-height: 1.2;
}
.app-subtitulo {
    font-size: 0.88rem;
    color: #475569;
    font-weight: 400;
    margin-top: 3px;
    margin-bottom: 1.2rem;
}

/* ── Cards de métricas ── */
.card-metrica {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.card-valor {
    font-size: 1.85rem;
    font-weight: 700;
    color: #1a1a2e;
    font-family: 'DM Mono', monospace;
    line-height: 1.1;
}
.card-etiqueta {
    font-size: 0.72rem;
    color: #64748b;
    margin-top: 5px;
    text-transform: uppercase;
    letter-spacing: 0.9px;
    font-weight: 600;
}
.card-verde .card-valor { color: #15803d; }
.card-azul  .card-valor { color: #1d4ed8; }
.card-rojo  .card-valor { color: #dc2626; }
.card-ambar .card-valor { color: #b45309; }

/* ── GRID DE CARDS DE PRODUCTOS ── */
/*
   Clave del fix de alineación:
   Usamos un contenedor CSS Grid real con 2 columnas.
   Cada card usa flex-direction:column y justify-content:space-between
   para empujar la zona de teléfono siempre al fondo,
   haciendo que todas las cards tengan la misma altura visual.
*/
.cards-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    align-items: stretch;   /* todas las celdas tienen la misma altura */
    margin-bottom: 1rem;
}
.cards-grid-1col {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.65rem;
    margin-bottom: 1rem;
}

/* Card individual */
.card-producto {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.15rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: box-shadow 0.18s, border-color 0.18s;
    min-height: 130px;        /* altura mínima para evitar cards enanas */
}
.card-producto:hover {
    box-shadow: 0 5px 16px rgba(0,0,0,0.07);
    border-color: #cbd5e1;
}

/* Zona superior de la card */
.card-top { flex: 1; }

.badge-top {
    display: inline-block;
    background: #15803d;
    color: #fff;
    font-size: 0.63rem;
    font-family: 'DM Mono', monospace;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    margin-bottom: 0.45rem;
    letter-spacing: 0.3px;
}
.precio-card {
    font-size: 1.25rem;
    font-weight: 700;
    color: #15803d;
    font-family: 'DM Mono', monospace;
    margin-bottom: 0.2rem;
}
.titulo-card {
    font-size: 0.9rem;
    font-weight: 600;
    color: #1a1a2e;
    line-height: 1.4;
    /* Truncar a 3 líneas máximo para uniformidad */
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 0.2rem;
}
.meta-card {
    font-size: 0.77rem;
    color: #64748b;
    margin-top: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.badge-fuente {
    display: inline-block;
    background: #f1f5f9;
    color: #475569;
    border-radius: 20px;
    padding: 1px 7px;
    font-size: 0.67rem;
    font-weight: 600;
    margin-left: 5px;
    vertical-align: middle;
    border: 1px solid #e2e8f0;
}

/* Zona inferior de la card (teléfono) — siempre al fondo */
.card-bottom {
    border-top: 1px solid #f1f5f9;
    margin-top: 0.65rem;
    padding-top: 0.55rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.35rem;
}
.tel-numero {
    font-family: 'DM Mono', monospace;
    font-size: 0.97rem;
    font-weight: 600;
    color: #1d4ed8;
}
.tel-sub {
    font-size: 0.7rem;
    color: #64748b;
    margin-top: 1px;
}
.wa-link {
    color: #15803d;
    text-decoration: none;
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    font-weight: 600;
}
.wa-link:hover { text-decoration: underline; }
.ver-link {
    font-size: 0.76rem;
    color: #64748b;
    text-decoration: none;
    border: 1px solid #e2e8f0;
    border-radius: 5px;
    padding: 0.22rem 0.6rem;
    white-space: nowrap;
    background: #f8fafc;
    transition: background 0.15s;
}
.ver-link:hover { background: #e2e8f0; color: #1a1a2e; }

/* ── Etiqueta de sección ── */
.section-label {
    font-size: 0.95rem;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 0.1rem;
}
.section-sub {
    font-size: 0.8rem;
    color: #64748b;
    margin-bottom: 0.8rem;
}

/* ── Info box ── */
.info-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    font-size: 0.875rem;
    color: #1e40af;
    margin-bottom: 1rem;
}

/* ── Resultados counter ── */
.results-count {
    text-align: right;
    font-size: 0.82rem;
    color: #64748b;
    margin-bottom: 0.75rem;
}

/* ── Filtros en sidebar — labels ── */
.sidebar-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #334155;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.4rem;
    display: block;
}
.sidebar-stat-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.84rem;
    padding: 0.22rem 0;
    border-bottom: 1px solid #f1f5f9;
}
.sidebar-stat-row:last-child { border-bottom: none; }
.sidebar-stat-label { color: #64748b; }
.sidebar-stat-val { font-weight: 700; font-family: 'DM Mono', monospace; color: #1a1a2e; }
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
    if "fecha_scraping" not in df.columns and "fecha" in df.columns:
        df["fecha_scraping"] = df["fecha"]
    return df


CATEGORIAS = {
    "laptop":      ("💻", "Laptops"),
    "monitor":     ("🖥️", "Monitores"),
    "disco":       ("💾", "Discos / SSD"),
    "ram":         ("🧠", "Memorias RAM"),
    "sonido":      ("🔊", "Bocinas y Sonido"),
    "periferico":  ("⌨️", "Periféricos"),
    "accesorio":   ("🔌", "Accesorios"),
    "modem":       ("📡", "Modem / WiFi"),
    "cpu":         ("⚙️", "Procesadores"),
    "impresora":   ("🖨️", "Impresoras"),
    "chasis":      ("🖱️", "Chasis y Fuentes"),
    "ups":         ("🔋", "UPS / Energía"),
    "dvd":         ("💿", "Lectores DVD"),
    "pc":          ("🖥️", "PCs Escritorio"),
    "cd":          ("💿", "CD / DVD Virgen"),
    "gpu":         ("🎮", "Tarjetas de Video"),
    "motherboard": ("🔧", "Motherboards"),
    "internet":    ("🌐", "Internet / Nauta"),
    "otros":       ("📦", "Otros"),
}
CATEGORIAS_LIMPIO = {k: v[1] for k, v in CATEGORIAS.items()}


def fmt_precio(v):
    if pd.isna(v):
        return "—"
    return f"${v:,.0f}"


def filtrar(df, cat, prov):
    df_f = df[df["categoria"] == cat].copy()
    if prov:
        df_f = df_f[df_f["provincia"] == prov]
    return df_f


# ─────────────────────────────────────────
# TARJETA DE PRODUCTO (HTML puro, grid-friendly)
# ─────────────────────────────────────────
def render_card(row, es_top=False) -> str:
    """
    Devuelve HTML de una card SIN el div.card-producto exterior,
    para que el grid los envuelva. Llamar desde render_cards_grid().
    """
    titulo = str(row.get("titulo", "Sin título"))
    if len(titulo) > 100:
        titulo = titulo[:97] + "…"

    precio = fmt_precio(row.get("precio_usd"))
    fuente = str(row.get("fuente", "")).strip()
    telefono = str(row["telefono"]) if pd.notna(row.get("telefono")) else None
    whatsapp = str(row["whatsapp"]) if pd.notna(row.get("whatsapp")) else None
    url = str(row["url"]) if pd.notna(row.get("url")) else None

    # Meta: provincia · vendedor
    meta_parts = []
    if pd.notna(row.get("provincia")):
        meta_parts.append(str(row["provincia"]))
    if pd.notna(row.get("vendedor")) and str(row.get("vendedor")) not in ("nan", ""):
        meta_parts.append(str(row["vendedor"])[:28])
    meta = " · ".join(meta_parts) if meta_parts else "Sin información"

    badge_top = '<div class="badge-top">🔥 Mejor precio</div>' if es_top else ""
    badge_fuente = f'<span class="badge-fuente">{fuente}</span>' if fuente else ""

    # WhatsApp
    wa_html = ""
    if whatsapp:
        num = whatsapp.replace("+", "").replace(" ", "")
        if not num.startswith("53"):
            num = "53" + num
        wa_html = f' &nbsp;·&nbsp; <a class="wa-link" href="https://wa.me/{num}" target="_blank">WhatsApp ↗</a>'

    # Ver anuncio
    ver_html = ""
    if url:
        ver_html = f'<a class="ver-link" href="{url}" target="_blank">Ver anuncio →</a>'

    # Zona teléfono — solo si hay teléfono
    bottom_html = ""
    if telefono:
        bottom_html = f"""
        <div class="card-bottom">
            <div>
                <div class="tel-numero">📞 {telefono}</div>
                <div class="tel-sub">Llamar o SMS{wa_html}</div>
            </div>
            {ver_html}
        </div>"""
    elif url:
        # Sin teléfono pero con URL: mostrar link abajo igual para simetría
        bottom_html = f"""
        <div class="card-bottom" style="justify-content:flex-end;">
            {ver_html}
        </div>"""

    return f"""
    <div class="card-producto">
        <div class="card-top">
            {badge_top}
            <div class="precio-card">{precio}</div>
            <div class="titulo-card">{titulo}{badge_fuente}</div>
            <div class="meta-card">{meta}</div>
        </div>
        {bottom_html}
    </div>"""


def render_cards_grid(rows_iter, cols=2) -> str:
    """
    Recibe un iterable de rows y devuelve HTML con grid de N columnas.
    Así todas las cards viven en el mismo DOM y CSS Grid las alinea.
    """
    css_class = "cards-grid" if cols == 2 else "cards-grid-1col"
    cards_html = "\n".join(render_card(row, es_top=es_top) for es_top, row in rows_iter)
    return f'<div class="{css_class}">{cards_html}</div>'


# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
def sidebar(df: pd.DataFrame):
    with st.sidebar:
        # Logo
        st.markdown("""
        <div style="padding: 1.1rem 0 1rem;">
            <div style="font-size:1.45rem; font-weight:800; color:#1a1a2e; letter-spacing:-0.5px;">
                🖥️ CubaPrecios
            </div>
            <div style="font-size:0.76rem; color:#94a3b8; margin-top:2px;">
                Electrónica en Cuba · Revolico + Facebook
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── Filtro Categoría ──
        st.markdown('<span class="sidebar-label">📁 Categoría</span>', unsafe_allow_html=True)
        cats_en_db = sorted([c for c in df["categoria"].dropna().unique() if c in CATEGORIAS])
        cat_sel = st.selectbox(
            "cat",
            options=cats_en_db,
            format_func=lambda x: f"{CATEGORIAS[x][0]}  {CATEGORIAS[x][1]}",
            label_visibility="collapsed",
        )

        st.markdown("<div style='margin-top:1.1rem;'></div>", unsafe_allow_html=True)

        # ── Filtro Provincia ──
        provincias = sorted(df["provincia"].dropna().unique())
        prov_sel = None
        if provincias:
            st.markdown('<span class="sidebar-label">📍 Provincia</span>', unsafe_allow_html=True)
            opciones_prov = ["Todas las provincias"] + provincias
            prov_elegida = st.selectbox("prov", options=opciones_prov, label_visibility="collapsed")
            prov_sel = None if prov_elegida == "Todas las provincias" else prov_elegida

        st.markdown("<div style='margin-top:1.2rem;'></div>", unsafe_allow_html=True)
        st.divider()

        # ── Estadísticas rápidas ──
        df_cat = df[df["categoria"] == cat_sel]
        n_total = len(df_cat)
        n_tel   = int(df_cat["telefono"].notna().sum())
        p_avg   = df_cat["precio_usd"].mean()
        p_min   = df_cat["precio_usd"].min()
        p_max   = df_cat["precio_usd"].max()

        nombre_cat_limpio = CATEGORIAS_LIMPIO.get(cat_sel, cat_sel)
        st.markdown(
            f"<div style='font-size:0.82rem; font-weight:700; color:#1a1a2e; margin-bottom:0.55rem;'>"
            f"Resumen · {nombre_cat_limpio}</div>",
            unsafe_allow_html=True
        )

        stats = [("Anuncios", f"{n_total}"), ("Con teléfono", f"{n_tel}")]
        if pd.notna(p_avg): stats.append(("Promedio", fmt_precio(p_avg)))
        if pd.notna(p_min): stats.append(("Mínimo", fmt_precio(p_min)))
        if pd.notna(p_max): stats.append(("Máximo", fmt_precio(p_max)))

        rows_html = "".join(
            f'<div class="sidebar-stat-row">'
            f'<span class="sidebar-stat-label">{lbl}</span>'
            f'<span class="sidebar-stat-val">{val}</span>'
            f'</div>'
            for lbl, val in stats
        )
        st.markdown(
            f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:0.6rem 0.9rem;">'
            f'{rows_html}</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            "<div style='margin-top:1.4rem; font-size:0.68rem; color:#cbd5e1; text-align:center;'>"
            "Datos desde Revolico.com + Facebook</div>",
            unsafe_allow_html=True
        )

    return cat_sel, prov_sel


# ─────────────────────────────────────────
# PÁGINAS
# ─────────────────────────────────────────
def pagina_inicio(df: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">{nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Precios actuales en Revolico · Cuba</div>', unsafe_allow_html=True)

    df_cat = df[df["categoria"] == cat].dropna(subset=["precio_usd"])

    if df_cat.empty:
        st.info("No hay anuncios con precio para esta categoría.")
        return

    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    metricas = [
        (c1, "", f"{len(df_cat)}", "Anuncios"),
        (c2, "card-verde", fmt_precio(df_cat["precio_usd"].min()), "Más barato"),
        (c3, "card-rojo",  fmt_precio(df_cat["precio_usd"].max()), "Más caro"),
        (c4, "card-ambar", fmt_precio(df_cat["precio_usd"].mean()), "Promedio"),
    ]
    for col, cls, val, lbl in metricas:
        with col:
            st.markdown(
                f'<div class="card-metrica {cls}">'
                f'<div class="card-valor">{val}</div>'
                f'<div class="card-etiqueta">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Anuncios recientes</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Los últimos publicados</div>', unsafe_allow_html=True)

    col_fecha = "fecha" if "fecha" in df_cat.columns else "fecha_scraping"
    recientes = df_cat.sort_values(col_fecha, ascending=False, na_position="last").head(8)

    # Grid de 1 columna en inicio (lectura más cómoda)
    rows_iter = ((False, row) for _, row in recientes.iterrows())
    st.html(render_cards_grid(rows_iter, cols=1))


def pagina_explorar(df_filtrado: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Explorar {nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="app-subtitulo">{len(df_filtrado)} anuncios disponibles</div>',
        unsafe_allow_html=True
    )

    if df_filtrado.empty:
        st.info("No hay anuncios con los filtros seleccionados. Prueba cambiando la provincia.")
        return

    # ── Búsqueda + Orden ──
    # El selectbox de orden tiene clase CSS especial via container
    col_busq, col_orden = st.columns([3, 1])
    with col_busq:
        busqueda = st.text_input(
            "Buscar",
            placeholder="🔍  Buscar por nombre, marca, modelo...",
            label_visibility="collapsed"
        )
    with col_orden:
        orden = st.selectbox(
            "Ordenar por",
            ["Precio: menor a mayor", "Precio: mayor a menor", "Más recientes"],
            label_visibility="collapsed"
        )

    df_res = df_filtrado.copy()
    if busqueda:
        df_res = df_res[df_res["titulo"].str.contains(busqueda, case=False, na=False)]

    if "menor" in orden:
        df_res = df_res.sort_values("precio_usd", ascending=True, na_position="last")
    elif "mayor" in orden:
        df_res = df_res.sort_values("precio_usd", ascending=False, na_position="last")
    else:
        col_fecha = "fecha" if "fecha" in df_res.columns else "fecha_scraping"
        df_res = df_res.sort_values(col_fecha, ascending=False, na_position="last")

    if busqueda and df_res.empty:
        st.info(f'No se encontraron resultados para "{busqueda}".')
        return

    st.markdown(
        f'<div class="results-count">{len(df_res)} resultado{"s" if len(df_res) != 1 else ""}</div>',
        unsafe_allow_html=True
    )

    # ── Grid de 2 columnas (CSS Grid real, no st.columns) ──
    top3_idx = set(df_res.head(3).index) if not df_res.empty else set()
    items = list(df_res.head(60).iterrows())

    rows_iter = ((idx in top3_idx, row) for idx, row in items)
    st.html(render_cards_grid(rows_iter, cols=2))

    if len(df_res) > 60:
        st.info(f"Mostrando 60 de {len(df_res)} anuncios. Usa el buscador para afinar.")

    # Descarga CSV
    cols_csv = [c for c in ["titulo", "precio_usd", "moneda", "telefono", "whatsapp", "vendedor", "provincia", "url"] if c in df_res.columns]
    csv_data = df_res[cols_csv].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ Descargar lista CSV",
        data=csv_data,
        file_name=f"cubaprecios_{cat}.csv",
        mime="text/csv"
    )


def pagina_ranking(df_filtrado: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Los más baratos — {nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Ordenados de menor a mayor precio</div>', unsafe_allow_html=True)

    df_p = df_filtrado.dropna(subset=["precio_usd"]).sort_values("precio_usd")
    if df_p.empty:
        st.info("No hay anuncios con precio.")
        return

    df_tabla = df_p[["titulo", "precio_usd", "telefono", "whatsapp", "vendedor", "provincia", "url"]].copy()
    df_tabla["precio_usd"] = df_tabla["precio_usd"].apply(fmt_precio)
    df_tabla = df_tabla.fillna("—")
    df_tabla.columns = ["Producto", "Precio", "Teléfono", "WhatsApp", "Vendedor", "Provincia", "Ver anuncio"]
    st.dataframe(
        df_tabla,
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={"Ver anuncio": st.column_config.LinkColumn("Ver anuncio")}
    )


def pagina_comparar(df_filtrado: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Comparar precios — {nombre_cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitulo">Resumen estadístico de precios</div>', unsafe_allow_html=True)

    df_p = df_filtrado.dropna(subset=["precio_usd"])
    if df_p.empty:
        st.info("No hay anuncios con precio para comparar.")
        return

    pmin = df_p["precio_usd"].min()
    pmax = df_p["precio_usd"].max()
    pavg = df_p["precio_usd"].mean()
    pmed = df_p["precio_usd"].median()

    st.markdown(
        f'<div class="info-box">Hay <b>{len(df_p)}</b> anuncios con precio. '
        f'El más barato cuesta <b>{fmt_precio(pmin)}</b> y el más caro <b>{fmt_precio(pmax)}</b>. '
        f'La mitad de los anuncios están por debajo de <b>{fmt_precio(pmed)}</b>.</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)
    metricas = [
        (c1, "card-verde", fmt_precio(pmin), "El más barato"),
        (c2, "card-rojo",  fmt_precio(pmax), "El más caro"),
        (c3, "card-ambar", fmt_precio(pavg), "Precio promedio"),
        (c4, "card-azul",  fmt_precio(pmed), "Precio mediano"),
    ]
    for col, cls, val, lbl in metricas:
        with col:
            st.markdown(
                f'<div class="card-metrica {cls}">'
                f'<div class="card-valor">{val}</div>'
                f'<div class="card-etiqueta">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True
            )


def pagina_contactos(df_filtrado: pd.DataFrame, cat: str):
    nombre_cat = CATEGORIAS_LIMPIO.get(cat, cat)
    st.markdown(f'<div class="app-titulo">Contactar vendedores — {nombre_cat}</div>', unsafe_allow_html=True)

    df_tel = df_filtrado[df_filtrado["telefono"].notna()].sort_values("precio_usd", na_position="last")
    st.markdown(
        f'<div class="app-subtitulo">{len(df_tel)} vendedores con teléfono disponible</div>',
        unsafe_allow_html=True
    )

    if df_tel.empty:
        st.info("No hay vendedores con teléfono en esta selección.")
        return

    busqueda = st.text_input(
        "Buscar",
        placeholder="🔍  Buscar producto por nombre o marca...",
        label_visibility="collapsed"
    )
    if busqueda:
        df_tel = df_tel[df_tel["titulo"].str.contains(busqueda, case=False, na=False)]
        if df_tel.empty:
            st.info(f'Sin resultados para "{busqueda}".')
            return

    rows_iter = ((False, row) for _, row in df_tel.head(40).iterrows())
    st.html(render_cards_grid(rows_iter, cols=1))

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

    cat_sel, prov_sel = sidebar(df)
    df_filtrado = filtrar(df, cat_sel, prov_sel)

    # Header principal
    emoji, nombre_cat = CATEGORIAS.get(cat_sel, ("📦", cat_sel))
    st.markdown(
        f"<div style='font-size:1.65rem; font-weight:800; color:#1a1a2e; letter-spacing:-0.5px; margin-bottom:0.1rem;'>"
        f"{emoji} {nombre_cat}</div>"
        f"<div style='font-size:0.8rem; color:#64748b; margin-bottom:1.2rem;'>Precios actuales · Revolico · Cuba</div>",
        unsafe_allow_html=True
    )

    # Pestañas
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏠  Inicio",
        "🔍  Explorar",
        "💰  Los más baratos",
        "📊  Comparar precios",
        "📞  Contactar vendedores",
    ])

    with tab1: pagina_inicio(df, cat_sel)
    with tab2: pagina_explorar(df_filtrado, cat_sel)
    with tab3: pagina_ranking(df_filtrado, cat_sel)
    with tab4: pagina_comparar(df_filtrado, cat_sel)
    with tab5: pagina_contactos(df_filtrado, cat_sel)


if __name__ == "__main__":
    main()