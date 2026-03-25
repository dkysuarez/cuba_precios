"""
Limpiador de datos — CubaPrecios v2
Lee archivos prov##_Provincia_categoria.detalle.json
Limpia, recategoriza por titulo y guarda en SQLite + CSV
"""

import json
import re
import sqlite3
import csv
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent))
from config import RAW_REVOLICO, CLEAN_DIR, DB_PATH

CSV_DIR = CLEAN_DIR / "csv"
CSV_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────
# TASA DE CAMBIO — TÚ LA CAMBIAS AQUÍ
# ─────────────────────────────────────────
TASA_CUP_USD = 385.0   # 1 USD = 385 CUP (actualiza según El Toque)
TASA_MLC_USD = 1.05    # 1 MLC ≈ 1.05 USD

# ─────────────────────────────────────────
# REGLAS DE CATEGORÍA — por título únicamente
# ─────────────────────────────────────────
REGLAS_CATEGORIA = [
    ("laptop",      ["laptop", "laptops", "notebook", "macbook", "chromebook",
                     "ultrabook", "lenovo ideapad", "hp pavilion", "dell inspiron",
                     "asus vivobook", "acer aspire", "asus laptop", "hp laptop"]),
    ("monitor",     ["monitor", "monitores", "pantalla led", "display",
                     "led 24", "led 27", "led 22", "led 32", "curved", "curvo",
                     "144hz", "75hz", "aoc", "viewsonic", "monitor samsung",
                     "monitor lg", "monitor hp", "monitor lenovo"]),
    ("ram",         ["memoria ram", "ram ddr", "ddr4", "ddr3", "ddr5",
                     "dimm", "sodimm", "memoria flash", "memoria usb",
                     "pendrive", "pen drive", "memoria sd", "microsd",
                     "kingston ram", "crucial ram", "corsair ram"]),
    ("disco",       ["disco duro", "disco ssd", "ssd ", " ssd", "hdd",
                     "nvme", "m.2", "disco externo", "1tb", "2tb",
                     "500gb", "256gb", "512gb", "seagate", "western digital",
                     "wd ", "toshiba disco", "sandisk ssd"]),
    ("cpu",         ["procesador", "microprocesador", "intel core",
                     "amd ryzen", " i3 ", " i5 ", " i7 ", " i9 ",
                     "ryzen 3", "ryzen 5", "ryzen 7", "celeron",
                     "pentium", "xeon", "cpu "]),
    ("gpu",         ["tarjeta de video", "tarjeta grafica", "gpu",
                     " gtx ", " rtx ", "radeon", "nvidia geforce",
                     "rx 580", "rx 6600", "vram"]),
    ("motherboard", ["motherboard", "placa base", "placa madre",
                     "mainboard", "tarjeta madre", "socket am4",
                     "socket 1151", "lga 1200"]),
    ("pc",          ["pc de escritorio", "computadora de mesa", "desktop",
                     "torre pc", "equipo completo", "computador completo",
                     "all in one", "mini pc"]),
    ("impresora",   ["impresora", "impresoras", "toner", "tóner",
                     "cartucho", "cartuchos", "laserjet", "inkjet",
                     "epson", "hp laserjet", "brother impresora"]),
    ("modem",       ["modem", "módem", "router", "wifi router",
                     "tp-link", "mikrotik", "access point",
                     "antena wifi", "repetidor wifi", "switch de red",
                     "cable utp", "cat 6", "fibra optica"]),
    ("teclado",     ["teclado", "mouse ", " mouse", "combo teclado",
                     "teclado gaming", "mouse gaming", "logitech",
                     "redragon teclado"]),
    ("webcam",      ["webcam", "camara web", "microfono", "micrófono",
                     "auricular", "audifonos", "headset", "camara usb"]),
    ("sonido",      ["bocina", "bocinas", "parlante", "parlantes",
                     "speaker", "subwoofer", "amplificador",
                     "tarjeta de sonido", "audio bluetooth"]),
    ("chasis",      ["chasis", "fuente de poder", "fuente atx",
                     "gabinete", "case pc", "tower case",
                     "fuente 500w", "fuente 600w", "cooler cpu",
                     "disipador", "ventilador cpu"]),
    ("ups",         ["ups ", " ups", "no break", "nobreak",
                     "regulador de voltaje", "planta electrica",
                     "inversor", "bateria ups", "apc ups"]),
    ("dvd",         ["quemador dvd", "lector dvd", "unidad dvd",
                     "blu-ray", "bluray", "unidad optica"]),
    ("cd",          ["cd virgen", "dvd virgen", "disco virgen"]),
    ("internet",    ["internet nauta", "cuenta nauta", "correo nauta",
                     "datos moviles", "plan datos"]),
    ("otros",       []),
]


# ─────────────────────────────────────────
# LIMPIEZA
# ─────────────────────────────────────────

def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F9FF"
        "\u2600-\u27BF"
        "\u2702-\u27B0"
        "❎✅⚠️💾📞📍👤🖼📄📊🔄♻️⏭️⏳🍪🔐💬🗑️❤️💙💚💛🧡💜"
        "]+", flags=re.UNICODE
    )
    texto = emoji_pattern.sub("", texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
    return texto


def extraer_precio_usd(precio_raw: str, moneda: str) -> float | None:
    if not precio_raw:
        return None
    match = re.search(r'[\d]+[.,]?[\d]*', precio_raw)
    if not match:
        return None
    try:
        valor = float(match.group(0).replace(",", "."))
        if valor <= 0 or valor > 50000:
            return None
        if moneda == "CUP":
            return round(valor / TASA_CUP_USD, 2)
        if moneda == "MLC":
            return round(valor * TASA_MLC_USD, 2)
        return valor  # USD
    except ValueError:
        return None


def detectar_moneda(precio_raw: str) -> str:
    if not precio_raw:
        return "USD"
    t = precio_raw.lower()
    if any(x in t for x in ["cup", "peso", "pesos", "mn", "kuki", "kukis", "moneda nacional"]):
        return "CUP"
    if any(x in t for x in ["mlc", "tienda"]):
        return "MLC"
    return "USD"


def limpiar_telefono(tel: str) -> str | None:
    if not tel:
        return None
    solo = re.sub(r'[^0-9]', '', tel)
    if solo.startswith("53") and len(solo) == 10:
        solo = solo[2:]
    if len(solo) in [7, 8]:
        return solo
    return None


def detectar_categoria_por_titulo(titulo: str, categoria_original: str) -> tuple[str, bool]:
    """Usa SOLO el titulo para detectar categoria"""
    texto = (titulo or "").lower()
    for categoria, palabras in REGLAS_CATEGORIA:
        if not palabras:
            continue
        for palabra in palabras:
            if palabra in texto:
                return categoria, (categoria != categoria_original)
    return categoria_original, False


# ─────────────────────────────────────────
# PROCESAR ANUNCIO
# ─────────────────────────────────────────

def procesar_anuncio(raw: dict) -> dict | None:
    titulo_limpio = limpiar_texto(raw.get("titulo") or "")
    if not titulo_limpio or len(titulo_limpio) < 3:
        return None

    # Precio
    precio_raw   = limpiar_texto(raw.get("precio_raw") or "")
    moneda       = detectar_moneda(precio_raw)
    precio_usd   = extraer_precio_usd(precio_raw, moneda)

    # Categoria — SOLO por titulo
    cat_original = raw.get("categoria") or "otros"
    categoria, recategorizado = detectar_categoria_por_titulo(titulo_limpio, cat_original)

    # Telefono
    telefono = limpiar_telefono(raw.get("telefono") or "")
    if not telefono:
        for t in (raw.get("telefonos_detectados") or []):
            telefono = limpiar_telefono(t)
            if telefono:
                break

    # WhatsApp
    whatsapp = limpiar_telefono(raw.get("whatsapp") or "")

    # Provincia — garantizada por el scraper v5
    provincia = raw.get("provincia") or None

    # Municipio
    municipio = limpiar_texto(raw.get("municipio") or "") or None

    # Vendedor
    vendedor = limpiar_texto(raw.get("vendedor") or "") or None
    if vendedor and len(vendedor) < 2:
        vendedor = None

    # URL limpia
    url = (raw.get("url") or "").split("?")[0]

    # Descripcion — guardamos pero no usamos para categorizar
    desc = limpiar_texto(raw.get("descripcion_completa") or "")
    desc = desc[:500] if desc else None

    # Fecha
    fecha = (raw.get("fecha_exacta") or raw.get("fecha_publicacion") or
             raw.get("scrapeado_en") or "")[:10] or None

    return {
        "url":                url,
        "fuente":             "revolico",
        "fecha_scraping":     fecha,
        "titulo":             titulo_limpio,
        "descripcion":        desc,
        "categoria":          categoria,
        "categoria_original": cat_original,
        "recategorizado":     recategorizado,
        "precio_usd":         precio_usd,
        "moneda":             moneda,
        "precio_texto":       precio_raw,
        "tasa_cup_usada":     TASA_CUP_USD if moneda == "CUP" else None,
        "telefono":           telefono,
        "whatsapp":           whatsapp,
        "vendedor":           vendedor,
        "provincia":          provincia,
        "municipio":          municipio,
        "vistas":             raw.get("vistas"),
        "tiene_imagen":       len(raw.get("imagenes") or []) > 0,
        "num_imagenes":       len(raw.get("imagenes") or []),
        "imagen_url":         (raw.get("imagenes") or [None])[0],
    }


# ─────────────────────────────────────────
# SQLITE
# ─────────────────────────────────────────

COLUMNAS = [
    "url", "fuente", "fecha_scraping", "titulo", "descripcion",
    "categoria", "categoria_original", "recategorizado",
    "precio_usd", "moneda", "precio_texto", "tasa_cup_usada",
    "telefono", "whatsapp", "vendedor",
    "provincia", "municipio",
    "vistas", "tiene_imagen", "num_imagenes", "imagen_url",
]

def crear_sqlite(conn):
    conn.execute("DROP TABLE IF EXISTS productos")
    conn.execute(f"""
        CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(c + ' TEXT' if c not in ['precio_usd','tasa_cup_usada','vistas','tiene_imagen','num_imagenes','recategorizado'] else c + ' REAL' for c in COLUMNAS)}
        )
    """)
    conn.execute("CREATE INDEX idx_cat      ON productos(categoria)")
    conn.execute("CREATE INDEX idx_prov     ON productos(provincia)")
    conn.execute("CREATE INDEX idx_precio   ON productos(precio_usd)")
    conn.execute("CREATE INDEX idx_tel      ON productos(telefono)")
    conn.execute("CREATE INDEX idx_cat_prov ON productos(categoria, provincia)")
    conn.commit()


def insertar_sqlite(conn, productos: list):
    ph = ", ".join(["?" for _ in COLUMNAS])
    cols = ", ".join(COLUMNAS)
    sql = f"INSERT OR IGNORE INTO productos ({cols}) VALUES ({ph})"
    filas = [
        tuple(int(p[c]) if isinstance(p.get(c), bool) else p.get(c) for c in COLUMNAS)
        for p in productos
    ]
    conn.executemany(sql, filas)
    conn.commit()


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    print("\n" + "="*55)
    print("  CUBA PRECIOS — LIMPIEZA v2")
    print(f"  Tasa CUP/USD: {TASA_CUP_USD} | MLC/USD: {TASA_MLC_USD}")
    print("="*55)

    # Buscar archivos nuevos (prov##_...) y viejos (detalle_...)
    archivos_nuevos = sorted(RAW_REVOLICO.glob("prov??_*.detalle.json"))
    archivos_viejos = sorted(RAW_REVOLICO.glob("detalle_*.json"))
    archivos = archivos_nuevos + archivos_viejos

    if not archivos:
        print("❌ No se encontraron archivos de detalle")
        print(f"   Buscado en: {RAW_REVOLICO}")
        return

    print(f"\n📁 Archivos: {len(archivos)} ({len(archivos_nuevos)} nuevos + {len(archivos_viejos)} viejos)")

    todos = []
    urls_vistas = set()
    stats = {
        "total_raw": 0, "descartados": 0,
        "duplicados": 0, "recategorizados": 0,
        "sin_precio": 0, "sin_telefono": 0, "sin_provincia": 0,
        "por_categoria": {}, "por_provincia": {},
    }

    for archivo in archivos:
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except Exception as e:
            print(f"  ❌ Error leyendo {archivo.name}: {e}")
            continue

        procesados = 0
        for raw in datos:
            stats["total_raw"] += 1
            p = procesar_anuncio(raw)
            if p is None:
                stats["descartados"] += 1
                continue
            url = p["url"]
            if url and url in urls_vistas:
                stats["duplicados"] += 1
                continue
            if url:
                urls_vistas.add(url)

            if not p["precio_usd"]:   stats["sin_precio"] += 1
            if not p["telefono"]:     stats["sin_telefono"] += 1
            if not p["provincia"]:    stats["sin_provincia"] += 1
            if p["recategorizado"]:   stats["recategorizados"] += 1

            cat  = p["categoria"]
            prov = p["provincia"] or "Sin provincia"
            stats["por_categoria"][cat]   = stats["por_categoria"].get(cat, 0) + 1
            stats["por_provincia"][prov]  = stats["por_provincia"].get(prov, 0) + 1

            todos.append(p)
            procesados += 1

        print(f"  ✅ {archivo.name[:50]}: {procesados}/{len(datos)}")

    if not todos:
        print("❌ No hay productos")
        return

    print(f"\n  Total limpio: {len(todos)}")

    # SQLite
    print(f"\n{'─'*55}")
    print("  Guardando SQLite...")
    conn = sqlite3.connect(str(DB_PATH))
    crear_sqlite(conn)
    insertar_sqlite(conn, todos)
    total_db = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    conn.close()
    print(f"  ✅ {DB_PATH.name}: {total_db} registros")

    # CSV por categoria
    print(f"\n{'─'*55}")
    print("  Guardando CSVs...")
    cats = sorted(set(p["categoria"] for p in todos))
    for cat in cats:
        prods = sorted(
            [p for p in todos if p["categoria"] == cat],
            key=lambda x: x["precio_usd"] or 99999
        )
        archivo = CSV_DIR / f"{cat}.csv"
        with open(archivo, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(prods)
        print(f"  💾 {cat}.csv ({len(prods)} filas)")

    # CSV maestro
    maestro = CLEAN_DIR / "todos_los_productos.csv"
    with open(maestro, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(todos, key=lambda x: x["categoria"]))
    print(f"  💾 todos_los_productos.csv ({len(todos)} filas)")

    # Resumen
    stats["total_final"]    = len(todos)
    stats["con_precio"]     = sum(1 for p in todos if p["precio_usd"])
    stats["con_telefono"]   = sum(1 for p in todos if p["telefono"])
    stats["con_provincia"]  = sum(1 for p in todos if p["provincia"])
    stats["con_vendedor"]   = sum(1 for p in todos if p["vendedor"])
    stats["tasa_cup_usd"]   = TASA_CUP_USD
    stats["tasa_mlc_usd"]   = TASA_MLC_USD
    stats["fecha_limpieza"] = datetime.now().isoformat()

    with open(CLEAN_DIR / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print("  RESUMEN FINAL")
    print(f"{'='*55}")
    print(f"  📊 Total limpios   : {stats['total_final']}")
    print(f"  💰 Con precio USD  : {stats['con_precio']}")
    print(f"  📞 Con telefono    : {stats['con_telefono']}")
    print(f"  📍 Con provincia   : {stats['con_provincia']}")
    print(f"  👤 Con vendedor    : {stats['con_vendedor']}")
    print(f"  🔄 Recategorizados : {stats['recategorizados']}")
    print(f"\n  Por categoria:")
    for cat, n in sorted(stats["por_categoria"].items(), key=lambda x: -x[1]):
        print(f"    {cat:<15} {n}")
    print(f"\n  Por provincia:")
    for prov, n in sorted(stats["por_provincia"].items(), key=lambda x: -x[1]):
        print(f"    {prov:<20} {n}")
    print(f"\n  💱 Tasa usada: 1 USD = {TASA_CUP_USD} CUP")
    print(f"  📁 Datos en: {CLEAN_DIR}")
    print("="*55)


if __name__ == "__main__":
    main()