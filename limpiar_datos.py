"""
Limpiador de datos — CubaPrecios v4.1 (Corregido + Robusto)
- Maneja tanto listas como diccionarios sueltos
- Sistema inteligente de categorías
- Descarta sin precio y sin teléfono
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
# TASA DE CAMBIO
# ─────────────────────────────────────────
TASA_CUP_USD = 385.0
TASA_MLC_USD = 1.05

# ─────────────────────────────────────────
# SISTEMA INTELIGENTE DE CATEGORÍAS
# ─────────────────────────────────────────
CATEGORIAS_REGLAS = {
    "laptop": {"fuertes": ["laptop", "laptops", "notebook", "macbook", "chromebook", "ultrabook"],
               "debiles": ["ideapad", "pavilion", "inspiron", "vivobook", "aspire", "thinkpad"]},
    "monitor": {"fuertes": ["monitor", "monitores", "pantalla led", "display"],
                "debiles": ["led 24", "led 27", "led 22", "led 32", "144hz", "75hz", "curvo", "aoc", "viewsonic"]},
    "ram": {"fuertes": ["memoria ram", "ram ddr", "ddr4", "ddr3", "ddr5", "dimm", "sodimm"],
            "debiles": ["kingston", "crucial", "corsair", "hyperx", "gb ram", "memoria usb", "memorias usb", "pendrive", "pen drive", "usb flash"]},
    "disco": {"fuertes": ["disco duro", "disco ssd", "ssd ", "hdd", "nvme", "m.2"],
              "debiles": ["1tb", "2tb", "500gb", "256gb", "512gb", "seagate", "western digital", "wd "]},
    "cpu": {"fuertes": ["procesador", "microprocesador", "intel core", "amd ryzen"],
            "debiles": ["i3", "i5", "i7", "i9", "ryzen 3", "ryzen 5", "ryzen 7", "celeron", "pentium"]},
    "gpu": {"fuertes": ["tarjeta de video", "tarjeta grafica", "gpu ", " gtx ", " rtx ", "radeon"],
            "debiles": ["rx 580", "rx 6600", "vram"]},
    "motherboard": {"fuertes": ["motherboard", "placa base", "placa madre"],
                    "debiles": ["socket am4", "socket am5", "lga 1200", "lga 1700"]},
    "pc": {"fuertes": ["pc de escritorio", "torre pc", "computadora de mesa", "equipo completo"],
           "debiles": ["all in one", "mini pc", "pc gaming"]},
    "impresora": {"fuertes": ["impresora", "impresoras"],
                  "debiles": ["toner", "cartucho", "laserjet", "inkjet", "epson", "brother"]},
    "modem": {"fuertes": ["modem", "módem", "router", "wifi router"],
              "debiles": ["tp-link", "mikrotik", "access point", "antena wifi"]},
    "teclado": {"fuertes": ["teclado", "mouse", "raton"],
                "debiles": ["combo teclado", "gaming", "logitech", "redragon"]},
    "webcam": {"fuertes": ["webcam", "camara web"],
               "debiles": ["microfono", "auricular", "audifonos", "headset"]},
    "sonido": {"fuertes": ["bocina", "parlante", "speaker", "subwoofer"],
               "debiles": ["amplificador", "tarjeta de sonido"]},
    "chasis": {"fuertes": ["chasis", "gabinete", "case pc", "fuente de poder"],
               "debiles": ["tower case", "fuente atx"]},
    "ups": {"fuertes": ["ups", "no break", "nobreak"],
            "debiles": ["regulador de voltaje"]},
    "dvd": {"fuertes": ["quemador dvd", "lector dvd", "unidad dvd", "bluray"],
            "debiles": ["dvd rw"]},
    "cd": {"fuertes": ["cd virgen", "dvd virgen", "disco virgen", "cd-r", "dvd-r", "cd r", "dvd r"],
           "debiles": []},
    "internet": {"fuertes": ["nauta", "cuenta nauta", "correo nauta"],
                 "debiles": ["datos moviles", "plan datos"]}
}

# ─────────────────────────────────────────
# FUNCIONES DE LIMPIEZA
# ─────────────────────────────────────────
def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    resultado = [char for char in texto if not (0x1F300 <= ord(char) <= 0x1F9FF or
                                               0x2600 <= ord(char) <= 0x27BF or
                                               0x2702 <= ord(char) <= 0x27B0)]
    texto = "".join(resultado)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
    return texto

def limpiar_telefono(tel: str) -> str | None:
    if not tel:
        return None
    solo = re.sub(r'[^0-9]', '', str(tel))
    if solo.startswith("53") and len(solo) == 10:
        solo = solo[2:]
    return solo if len(solo) in [7, 8] else None

def mejor_telefono(raw: dict) -> str | None:
    for campo in ["telefono", "whatsapp", "telefonos_detectados", "telefonos_titulo", "telefonos_en_texto"]:
        valor = raw.get(campo)
        if isinstance(valor, list):
            for t in valor:
                if tel := limpiar_telefono(t):
                    return tel
        elif valor:
            if tel := limpiar_telefono(valor):
                return tel
    return None

def detectar_moneda(precio_raw: str) -> str:
    if not precio_raw:
        return "USD"
    t = precio_raw.lower()
    if any(x in t for x in ["cup", "peso", "pesos", "mn", "kuki"]):
        return "CUP"
    if any(x in t for x in ["mlc", "tienda"]):
        return "MLC"
    return "USD"

def extraer_precio_usd(precio_raw: str, moneda: str) -> float | None:
    if not precio_raw:
        return None
    match = re.search(r'\b(\d{1,6}(?:[.,]\d{1,2})?)\b', precio_raw)
    if not match:
        return None
    try:
        valor = float(match.group(1).replace(",", "."))
        if valor <= 0 or valor > 99999:
            return None
        if moneda == "CUP":
            return round(valor / TASA_CUP_USD, 2)
        if moneda == "MLC":
            return round(valor * TASA_MLC_USD, 2)
        return valor
    except:
        return None

def detectar_categoria(titulo: str, categoria_original: str) -> tuple[str, bool]:
    if not titulo:
        return categoria_original, False
    texto = titulo.lower()
    mejor_categoria = categoria_original
    mejor_puntaje = 0

    for cat, reglas in CATEGORIAS_REGLAS.items():
        puntaje = 0
        for kw in reglas.get("fuertes", []):
            if kw in texto:
                puntaje += 3
                break
        for kw in reglas.get("debiles", []):
            if kw in texto:
                puntaje += 1
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_categoria = cat

    if mejor_puntaje < 2:
        mejor_categoria = "otros"

    return mejor_categoria, (mejor_categoria != categoria_original)

# ─────────────────────────────────────────
# PROCESAR ANUNCIO
# ─────────────────────────────────────────
def procesar_anuncio(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None

    titulo = limpiar_texto(raw.get("titulo") or "")
    if not titulo or len(titulo) < 5:
        return None

    precio_raw = limpiar_texto(raw.get("precio_raw") or "")
    moneda = detectar_moneda(precio_raw)
    precio_usd = extraer_precio_usd(precio_raw, moneda)

    if precio_usd is None:          # SIN PRECIO → DESCARTAR
        return None

    telefono = mejor_telefono(raw)
    if not telefono:                # SIN TELÉFONO → DESCARTAR
        return None

    cat_original = raw.get("categoria") or "otros"
    categoria, recat = detectar_categoria(titulo, cat_original)

    whatsapp = limpiar_telefono(raw.get("whatsapp") or "")

    provincia = raw.get("provincia") or None
    municipio = limpiar_texto(raw.get("municipio") or "") or None
    vendedor = limpiar_texto(raw.get("vendedor") or "") or None
    if vendedor and len(vendedor) < 2:
        vendedor = None

    url = re.split(r'\?', raw.get("url") or "")[0]
    desc = limpiar_texto(raw.get("descripcion_completa") or raw.get("descripcion") or "")
    desc = desc[:600] if desc else None

    fecha = (raw.get("fecha_exacta") or raw.get("fecha_publicacion") or
             raw.get("scrapeado_en") or "")[:10] or None

    return {
        "url": url,
        "fuente": "revolico",
        "fecha_scraping": fecha,
        "titulo": titulo,
        "descripcion": desc,
        "categoria": categoria,
        "categoria_original": cat_original,
        "recategorizado": int(recat),
        "precio_usd": precio_usd,
        "moneda": moneda,
        "precio_texto": precio_raw,
        "tasa_cup_usada": TASA_CUP_USD if moneda == "CUP" else None,
        "telefono": telefono,
        "whatsapp": whatsapp,
        "vendedor": vendedor,
        "provincia": provincia,
        "municipio": municipio,
        "vistas": raw.get("vistas"),
        "tiene_imagen": int(len(raw.get("imagenes") or []) > 0),
        "num_imagenes": len(raw.get("imagenes") or []),
        "imagen_url": (raw.get("imagenes") or [None])[0],
    }

# ─────────────────────────────────────────
# SQLITE y CSV (sin cambios importantes)
# ─────────────────────────────────────────
COLUMNAS = ["url", "fuente", "fecha_scraping", "titulo", "descripcion", "categoria",
            "categoria_original", "recategorizado", "precio_usd", "moneda", "precio_texto",
            "tasa_cup_usada", "telefono", "whatsapp", "vendedor", "provincia", "municipio",
            "vistas", "tiene_imagen", "num_imagenes", "imagen_url"]

def crear_sqlite(conn):
    conn.execute("DROP TABLE IF EXISTS productos")
    definiciones = [f"{col} REAL" if col in ["precio_usd","tasa_cup_usada","vistas","recategorizado","tiene_imagen","num_imagenes"] else f"{col} TEXT" for col in COLUMNAS]
    conn.execute(f"CREATE TABLE productos (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(definiciones)})")
    for idx in ["categoria", "provincia", "precio_usd", "telefono"]:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{idx} ON productos({idx})")
    conn.commit()

def insertar_sqlite(conn, productos):
    ph = ", ".join(["?"] * len(COLUMNAS))
    sql = f"INSERT OR IGNORE INTO productos ({', '.join(COLUMNAS)}) VALUES ({ph})"
    filas = [tuple(p.get(c) for c in COLUMNAS) for p in productos]
    conn.executemany(sql, filas)
    conn.commit()

def guardar_csv(productos, nombre):
    if not productos:
        return
    archivo = CSV_DIR / f"{nombre}.csv"
    cols_csv = ["url","titulo","categoria","precio_usd","moneda","precio_texto","telefono",
                "whatsapp","vendedor","provincia","municipio","descripcion","vistas",
                "tiene_imagen","imagen_url","recategorizado","categoria_original","fecha_scraping"]
    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols_csv, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(productos)
    print(f"  💾 {nombre}.csv — {len(productos)} filas")

# ─────────────────────────────────────────
# MAIN - Manejo robusto de JSON
# ─────────────────────────────────────────
def main():
    print("\n" + "="*65)
    print("  CUBA PRECIOS — LIMPIADOR v4.1 (ROBUSTO)")
    print("="*65)

    archivos = sorted(RAW_REVOLICO.glob("*.json"))
    if not archivos:
        print("❌ No hay archivos JSON")
        return

    todos = []
    urls_vistas = set()
    stats = {"total_raw":0, "descartados":0, "duplicados":0, "recategorizados":0,
             "por_categoria":{}, "por_provincia":{}}

    for archivo in archivos:
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  ❌ Error JSON {archivo.name}: {e}")
            continue

        # Normalizar: convertir a lista si es un solo dict
        if isinstance(data, dict):
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            print(f"  ⚠️  Formato desconocido en {archivo.name}")
            continue

        procesados = 0
        for raw in items:
            stats["total_raw"] += 1
            producto = procesar_anuncio(raw)
            if not producto:
                stats["descartados"] += 1
                continue

            url = producto["url"]
            if url and url in urls_vistas:
                stats["duplicados"] += 1
                continue
            if url:
                urls_vistas.add(url)

            if producto.get("recategorizado"):
                stats["recategorizados"] += 1

            cat = producto["categoria"]
            prov = producto.get("provincia") or "Sin provincia"
            stats["por_categoria"][cat] = stats["por_categoria"].get(cat, 0) + 1
            stats["por_provincia"][prov] = stats["por_provincia"].get(prov, 0) + 1

            todos.append(producto)
            procesados += 1

        print(f"  ✅ {archivo.name:<45} → {procesados}/{len(items)}")

    if not todos:
        print("\n❌ No quedaron productos válidos.")
        return

    print(f"\n{'─'*65}")
    print(f"  Total válidos: {len(todos)}")
    print(f"  Descartados:   {stats['descartados']}")
    print(f"  Duplicados:    {stats['duplicados']}")

    # Guardar
    conn = sqlite3.connect(str(DB_PATH))
    crear_sqlite(conn)
    insertar_sqlite(conn, todos)
    total_db = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    conn.close()
    print(f"  ✅ Base de datos: {total_db} registros")

    print("\n  Guardando CSVs...")
    for cat in sorted(stats["por_categoria"].keys()):
        prods = [p for p in todos if p["categoria"] == cat]
        prods.sort(key=lambda x: x["precio_usd"] or 99999)
        guardar_csv(prods, cat)

    guardar_csv(sorted(todos, key=lambda x: (x["categoria"], x.get("precio_usd") or 99999)),
                "todos_los_productos")

    print(f"\n{'='*65}")
    print("  RESUMEN FINAL")
    print("="*65)
    print(f"  Por categoría:")
    for cat, n in sorted(stats["por_categoria"].items(), key=lambda x: -x[1]):
        print(f"    {cat:<15} {n:>5}")
    print(f"\n  📁 Datos en: {CLEAN_DIR}")
    print("  ✅ Ahora puedes correr: streamlit run app.py")
    print("="*65)

if __name__ == "__main__":
    main()