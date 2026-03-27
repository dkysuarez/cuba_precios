"""
Limpiador Unificado — CubaPrecios v4
Lee detalle_*.json (Revolico) + facebook_*.json (Facebook)
Limpia, filtra, recategoriza y guarda en SQLite + CSV

Reglas:
- Sin telefono → descartar
- Precio <= 1 → descartar
- Sin precio → descartar
- Anuncios buscando comprar → descartar
- Anuncios de tiendas/talleres → marcar pero conservar
- Titulo generado desde contenido limpio
- Categoria por titulo unicamente
- Precio minimo por categoria (evita precios absurdos)
"""

import json
import re
import sqlite3
import csv
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.append(str(Path(__file__).resolve().parent))
from config import RAW_REVOLICO, RAW_FACEBOOK, CLEAN_DIR, DB_PATH

CSV_DIR = CLEAN_DIR / "csv"
CSV_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────
# TASAS — CAMBIA AQUI
# ─────────────────────────────────────────
TASA_CUP_USD = 385.0
TASA_MLC_USD = 1.05

# ─────────────────────────────────────────
# PRECIO MINIMO POR CATEGORIA
# Evita precios absurdos tipo $3 para una laptop
# ─────────────────────────────────────────
PRECIO_MINIMO = {
    "laptop":      50,
    "pc":          50,
    "monitor":     20,
    "gpu":         20,
    "cpu":         5,
    "motherboard": 10,
    "disco":       5,
    "ram":         3,
    "teclado":     2,
    "modem":       5,
    "impresora":   10,
    "chasis":      5,
    "ups":         5,
    "webcam":      3,
    "sonido":      3,
    "dvd":         2,
    "cd":          1,
    "internet":    1,
    "otros":       1,
}

PRECIO_MAXIMO = {
    "laptop":      5000,
    "pc":          5000,
    "monitor":     2000,
    "gpu":         3000,
    "cpu":         2000,
    "motherboard": 1000,
    "disco":       500,
    "ram":         500,
    "teclado":     300,
    "modem":       500,
    "impresora":   1000,
    "chasis":      500,
    "ups":         500,
    "webcam":      200,
    "sonido":      500,
    "dvd":         100,
    "cd":          50,
    "internet":    100,
    "otros":       5000,
}

# ─────────────────────────────────────────
# PALABRAS QUE INDICAN BUSCA COMPRAR
# ─────────────────────────────────────────
BUSCA_COMPRAR = [
    "desea vender", "quieres vender", "compro ", "compra ",
    "busco ", "busco laptop", "busco pc", "se compra",
    "pago bien", "interesado en comprar", "necesito comprar",
    "quien vende", "alguien vende", "tiene en venta",
    "busco urgente", "busca laptop", "busca pc",
]

# ─────────────────────────────────────────
# PALABRAS QUE INDICAN ANUNCIO DE TALLER/SERVICIO
# ─────────────────────────────────────────
ES_SERVICIO = [
    "taller", "reparacion", "reparación", "servicio técnico",
    "servicio tecnico", "agenda su cita", "repara tu",
    "mantenimiento", "formateo", "instalacion de windows",
    "instalación de windows",
]

# ─────────────────────────────────────────
# PALABRAS A LIMPIAR DEL INICIO DEL TITULO
# ─────────────────────────────────────────
PREFIJOS_BASURA = [
    r'^vendo\s+', r'^se vende\s+', r'^venta\s+de\s+',
    r'^venta\s+', r'^oferta\s+', r'^ganga\s*[!.]*\s*',
    r'^nuevo\s+', r'^nueva\s+', r'^disponible\s+',
    r'^tengo\s+', r'^liquido\s+', r'^liquido\s+',
    r'^super\s+ganga\s*[!.]*\s*', r'^precio\s+',
    r'^urgente\s+', r'^oportunidad\s+',
    r'[!❗❌✅⚠️💥🔥]+\s*',
]

# ─────────────────────────────────────────
# REGLAS DE CATEGORIA — por titulo
# ─────────────────────────────────────────
REGLAS_CATEGORIA = [
    ("laptop", [
        "laptop", "laptops", "notebook", "macbook", "chromebook",
        "ultrabook", "thinkpad", "ideapad", "vivobook",
        "hp-14", "hp-15", "lenovo laptop", "dell laptop",
        "laptop hp", "laptop lenovo", "laptop dell", "laptop asus",
        "laptop acer", "laptop samsung",
    ]),
    ("monitor", [
        "monitor", "monitores", "pantalla led", "display ",
        "led 24", "led 27", "led 22", "led 32", "led 25", "led 34",
        "curvo", "curved", "144hz", "75hz", "165hz",
        "aoc ", "viewsonic", "monitor samsung", "monitor lg",
        "monitor hp", "monitor lenovo", "monitor acer",
    ]),
    ("ram", [
        "memoria ram", "ram ddr", "ddr4", "ddr3", "ddr5",
        "dimm", "sodimm", "memoria flash", "memoria usb",
        "pendrive", "pen drive", "memoria sd", "microsd",
        "gb ram", "ram 8gb", "ram 16gb", "ram 32gb",
    ]),
    ("disco", [
        "disco duro", "disco ssd", "ssd m.2", "ssd m2",
        " ssd ", "hdd ", " hdd", "nvme", "disco externo",
        "disco interno", "1tb", "2tb", "500gb disco",
        "seagate", "western digital", "wd ", "samsung evo",
        "crucial ssd", "kingston ssd", "m2 ssd",
    ]),
    ("cpu", [
        "procesador", "microprocesador", "intel core i",
        "amd ryzen", " i3 ", " i5 ", " i7 ", " i9 ",
        "ryzen 3", "ryzen 5", "ryzen 7", "ryzen 9",
        "celeron", "pentium", "xeon",
    ]),
    ("gpu", [
        "tarjeta de video", "tarjeta grafica",
        " gtx ", " rtx ", "radeon rx", "nvidia geforce",
        "rx 580", "rx 6600", "rx 6700",
        "gtx 1660", "rtx 3060", "rtx 4060", "rtx 3080",
    ]),
    ("motherboard", [
        "motherboard", "placa base", "placa madre",
        "mainboard", "tarjeta madre", "socket am4", "socket am5",
        "lga 1200", "lga 1700", "board b450", "board b550",
        "board z690", "board h370", "board b365",
    ]),
    ("pc", [
        "pc de escritorio", "computadora de mesa", "desktop",
        "torre pc", "equipo completo", "pc gamer", "pc gaming",
        "all in one", "mini pc", "torre gamer",
        "vendo pc", "computadora completa",
    ]),
    ("impresora", [
        "impresora", "impresoras", "toner", "tóner",
        "cartucho", "cartuchos", "laserjet", "inkjet",
        "epson l32", "epson l31", "epson l38",
        "hp laserjet", "hp inkjet", "brother impresora",
        "tinta impresora",
    ]),
    ("modem", [
        "modem", "módem", "router", "wifi router",
        "tp-link", "mikrotik", "access point",
        "antena wifi", "repetidor wifi",
        "cable utp", "cat 6", "cat6",
    ]),
    ("teclado", [
        "teclado mecanico", "teclado mecánico", "teclado gaming",
        "teclado inalambrico", "mouse gaming", "combo teclado",
        "teclado rgb", "mouse rgb", "teclado tkl",
    ]),
    ("webcam", [
        "webcam", "camara web", "microfono externo",
        "auricular", "audifonos", "headset gaming",
        "camara usb",
    ]),
    ("sonido", [
        "bocina", "bocinas", "parlante", "parlantes",
        "speaker", "subwoofer", "amplificador audio",
        "tarjeta de sonido",
    ]),
    ("chasis", [
        "chasis", "gabinete pc", "case pc", "torre case",
        "fuente de poder", "fuente atx", "fuente 500w",
        "fuente 600w", "fuente 750w", "cooler cpu",
        "disipador cpu", "disipacion liquida",
    ]),
    ("ups", [
        "ups ", " ups", "no break", "nobreak",
        "regulador de voltaje", "planta electrica",
        "inversor", "bateria ups", "estabilizador",
    ]),
    ("dvd", [
        "quemador dvd", "lector dvd", "unidad dvd",
        "blu-ray", "bluray", "unidad optica",
    ]),
    ("cd", [
        "cd virgen", "dvd virgen", "disco virgen",
    ]),
    ("internet", [
        "internet nauta", "cuenta nauta", "correo nauta",
        "saldo nauta", "datos moviles",
    ]),
    ("otros", []),
]

# ─────────────────────────────────────────
# PROVINCIAS
# ─────────────────────────────────────────
PROVINCIAS_NORM = {
    "habana":            "La Habana",
    "la habana":         "La Habana",
    "ciudad habana":     "La Habana",
    "centro habana":     "La Habana",
    "habana vieja":      "La Habana",
    "miramar":           "La Habana",
    "vedado":            "La Habana",
    "playa":             "La Habana",
    "marianao":          "La Habana",
    "artemisa":          "Artemisa",
    "mayabeque":         "Mayabeque",
    "pinar del rio":     "Pinar del Río",
    "pinar del río":     "Pinar del Río",
    "matanzas":          "Matanzas",
    "cienfuegos":        "Cienfuegos",
    "villa clara":       "Villa Clara",
    "sancti spiritus":   "Sancti Spíritus",
    "sancti spíritus":   "Sancti Spíritus",
    "ciego de avila":    "Ciego de Ávila",
    "camaguey":          "Camagüey",
    "camagüey":          "Camagüey",
    "las tunas":         "Las Tunas",
    "holguin":           "Holguín",
    "holguín":           "Holguín",
    "granma":            "Granma",
    "bayamo":            "Granma",
    "santiago de cuba":  "Santiago de Cuba",
    "santiago":          "Santiago de Cuba",
    "guantanamo":        "Guantánamo",
    "guantánamo":        "Guantánamo",
    "isla de la juventud": "Isla de la Juventud",
}


# ─────────────────────────────────────────
# FUNCIONES DE LIMPIEZA
# ─────────────────────────────────────────

def limpiar_texto(texto: str) -> str:
    """Elimina emojis y caracteres raros"""
    if not texto:
        return ""
    resultado = []
    for char in texto:
        cp = ord(char)
        if (0x1F300 <= cp <= 0x1F9FF or
            0x2600  <= cp <= 0x27BF or
            0xFE00  <= cp <= 0xFE0F or
            cp in (0x200B, 0x200C, 0x200D, 0xFEFF)):
            continue
        resultado.append(char)
    texto = "".join(resultado)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
    return texto


def generar_titulo_desde_contenido(contenido: str, tipo_equipo: str) -> str:
    """
    Genera un titulo limpio desde el contenido del post de Facebook.
    Toma las primeras palabras significativas, sin prefijos de venta.
    """
    if not contenido:
        return ""

    # Tomar primera linea no vacia
    lineas = [l.strip() for l in contenido.split('\n') if l.strip()]
    if not lineas:
        return ""

    titulo = lineas[0]

    # Si la primera linea es muy corta o solo tiene precio, usar las dos primeras
    if len(titulo) < 10 and len(lineas) > 1:
        titulo = lineas[0] + " " + lineas[1]

    # Limpiar emojis y simbolos
    titulo = limpiar_texto(titulo)

    # Quitar prefijos de venta del inicio
    for patron in PREFIJOS_BASURA:
        titulo = re.sub(patron, '', titulo, flags=re.IGNORECASE).strip()

    # Si quedo muy corto, intentar con la segunda linea
    if len(titulo) < 8 and len(lineas) > 1:
        titulo2 = limpiar_texto(lineas[1])
        for patron in PREFIJOS_BASURA:
            titulo2 = re.sub(patron, '', titulo2, flags=re.IGNORECASE).strip()
        if len(titulo2) > len(titulo):
            titulo = titulo2

    # Capitalizar correctamente
    titulo = titulo.strip(" .-,!?")

    # Limitar longitud
    if len(titulo) > 100:
        titulo = titulo[:100].rsplit(' ', 1)[0]

    return titulo


def limpiar_telefono(tel: str) -> str | None:
    """Normaliza telefono a 8 digitos cubanos"""
    if not tel:
        return None
    solo = re.sub(r'[^0-9]', '', str(tel))
    if solo.startswith("53") and len(solo) == 10:
        solo = solo[2:]
    if len(solo) in [7, 8]:
        return solo
    return None


def mejor_telefono(raw: dict, fuente: str) -> str | None:
    """Extrae el mejor telefono segun la fuente"""
    if fuente == "facebook":
        # Facebook guarda en lista "telefonos"
        for t in (raw.get("telefonos") or []):
            tel = limpiar_telefono(t)
            if tel:
                return tel
    else:
        # Revolico guarda en campos individuales
        for campo in ["telefono", "whatsapp", "telefonos_detectados", "telefonos_listado"]:
            valor = raw.get(campo)
            if isinstance(valor, list):
                for v in valor:
                    tel = limpiar_telefono(v)
                    if tel:
                        return tel
            elif valor:
                tel = limpiar_telefono(valor)
                if tel:
                    return tel
    return None


def detectar_moneda(texto: str) -> str:
    if not texto:
        return "USD"
    t = str(texto).lower()
    if any(x in t for x in ["cup", "peso", "pesos", " mn", "kuki", "kukis"]):
        return "CUP"
    if "mlc" in t:
        return "MLC"
    return "USD"


def extraer_precio_usd(raw: dict, fuente: str, moneda: str) -> float | None:
    """Extrae precio segun la fuente"""
    if fuente == "facebook":
        precio = raw.get("precio")
        if precio and float(precio) > 1:
            if moneda == "CUP":
                return round(float(precio) / TASA_CUP_USD, 2)
            if moneda == "MLC":
                return round(float(precio) * TASA_MLC_USD, 2)
            return float(precio)
    else:
        precio_str = raw.get("precio_raw") or ""
        match = re.search(r'\b(\d{1,6}(?:[.,]\d{1,2})?)\b', precio_str)
        if match:
            try:
                valor = float(match.group(1).replace(",", "."))
                if valor > 1:
                    if moneda == "CUP":
                        return round(valor / TASA_CUP_USD, 2)
                    if moneda == "MLC":
                        return round(valor * TASA_MLC_USD, 2)
                    return valor
            except ValueError:
                pass
    return None


def detectar_categoria(titulo: str, cat_original: str) -> tuple:
    """Categoriza SOLO por titulo"""
    texto = (titulo or "").lower()
    for categoria, palabras in REGLAS_CATEGORIA:
        if not palabras:
            continue
        for palabra in palabras:
            if palabra in texto:
                return categoria, (categoria != cat_original)
    return cat_original or "otros", False


def detectar_provincia(raw: dict, fuente: str, grupo_provincia: str = None) -> str | None:
    """Detecta provincia con fallback inteligente"""
    # 1. Provincia del grupo (Facebook — garantizada)
    if grupo_provincia:
        return PROVINCIAS_NORM.get(grupo_provincia.lower(), grupo_provincia)

    # 2. Campo provincia del raw
    prov = (raw.get("provincia") or "").strip().lower()
    if prov and len(prov) > 2:
        norm = PROVINCIAS_NORM.get(prov)
        if norm:
            return norm

    # 3. Buscar en contenido/descripcion
    texto = (
        (raw.get("contenido") or "") + " " +
        (raw.get("descripcion_completa") or "") + " " +
        (raw.get("titulo") or "")
    ).lower()

    for clave, nombre in PROVINCIAS_NORM.items():
        if len(clave) > 5 and clave in texto:
            return nombre

    return None


def es_busca_comprar(texto: str) -> bool:
    """Detecta si el anuncio busca comprar, no vender"""
    t = texto.lower()
    return any(frase in t for frase in BUSCA_COMPRAR)


def es_servicio_taller(texto: str) -> bool:
    """Detecta si es un anuncio de taller o servicio"""
    t = texto.lower()
    return any(frase in t for frase in ES_SERVICIO)


def precio_valido(precio: float, categoria: str) -> bool:
    """Verifica que el precio tenga sentido para la categoria"""
    if not precio or precio <= 1:
        return False
    pmin = PRECIO_MINIMO.get(categoria, 1)
    pmax = PRECIO_MAXIMO.get(categoria, 5000)
    return pmin <= precio <= pmax


# ─────────────────────────────────────────
# PROCESAR ANUNCIOS
# ─────────────────────────────────────────

def procesar_revolico(raw: dict) -> dict | None:
    titulo = limpiar_texto(raw.get("titulo") or "")
    if not titulo or len(titulo) < 3:
        return None

    # Limpiar prefijos del titulo
    titulo_limpio = titulo
    for patron in PREFIJOS_BASURA:
        titulo_limpio = re.sub(patron, '', titulo_limpio, flags=re.IGNORECASE).strip()
    if len(titulo_limpio) < 3:
        titulo_limpio = titulo

    # Descartar si busca comprar
    if es_busca_comprar(titulo + " " + (raw.get("descripcion_completa") or "")):
        return None

    telefono = mejor_telefono(raw, "revolico")
    if not telefono:
        return None

    precio_raw = raw.get("precio_raw") or ""
    moneda = detectar_moneda(precio_raw)
    precio_usd = extraer_precio_usd(raw, "revolico", moneda)

    cat_original = raw.get("categoria") or "otros"
    categoria, recat = detectar_categoria(titulo_limpio, cat_original)

    if not precio_valido(precio_usd, categoria):
        return None

    provincia = detectar_provincia(raw, "revolico")
    whatsapp = limpiar_telefono(raw.get("whatsapp") or "")
    vendedor = limpiar_texto(raw.get("vendedor") or "") or None
    if vendedor and len(vendedor) < 2:
        vendedor = None

    url = re.split(r'\?', raw.get("url") or "")[0]
    desc = limpiar_texto(raw.get("descripcion_completa") or "")
    desc = desc[:500] if desc else None
    fecha = (raw.get("fecha_exacta") or raw.get("scrapeado_en") or "")[:10] or None

    return {
        "fuente":             "revolico",
        "url":                url,
        "titulo":             titulo_limpio,
        "descripcion":        desc,
        "categoria":          categoria,
        "categoria_original": cat_original,
        "recategorizado":     int(recat),
        "precio_usd":         precio_usd,
        "moneda":             moneda,
        "precio_texto":       limpiar_texto(precio_raw),
        "telefono":           telefono,
        "whatsapp":           whatsapp,
        "vendedor":           vendedor,
        "provincia":          provincia,
        "municipio":          limpiar_texto(raw.get("municipio") or "") or None,
        "fecha":              fecha,
        "vistas":             raw.get("vistas"),
        "num_imagenes":       len(raw.get("imagenes") or []),
        "imagen_principal":   (raw.get("imagenes") or [None])[0],
    }


def procesar_facebook(raw: dict) -> dict | None:
    contenido = raw.get("contenido") or ""
    if not contenido or len(contenido) < 10:
        return None

    # Descartar si busca comprar
    if es_busca_comprar(contenido):
        return None

    # Descartar talleres/servicios (no tienen precio de producto especifico)
    if es_servicio_taller(contenido):
        return None

    tipo_original = raw.get("tipo_equipo") or "otros"

    # Generar titulo limpio desde el contenido
    titulo = generar_titulo_desde_contenido(contenido, tipo_original)
    if not titulo or len(titulo) < 5:
        return None

    telefono = mejor_telefono(raw, "facebook")
    if not telefono:
        return None

    moneda_raw = raw.get("moneda") or ""
    moneda = detectar_moneda(moneda_raw) if moneda_raw else "USD"
    precio_usd = extraer_precio_usd(raw, "facebook", moneda)

    categoria, recat = detectar_categoria(titulo, tipo_original)

    if not precio_valido(precio_usd, categoria):
        return None

    # Provincia: usar la del grupo si esta disponible
    provincia = detectar_provincia(raw, "facebook")

    whatsapp = None
    # Extraer WhatsApp de links wa.me en el contenido
    wa_match = re.search(r'wa\.me/\+?53?(\d{7,8})', contenido)
    if wa_match:
        whatsapp = limpiar_telefono(wa_match.group(1))

    # Vendedor: no disponible en Facebook directamente
    vendedor = raw.get("marca") or None

    url = raw.get("url") or ""
    desc = limpiar_texto(contenido)
    desc = desc[:500] if desc else None
    fecha = (raw.get("fecha_extraccion") or "")[:10] or None

    return {
        "fuente":             "facebook",
        "url":                url,
        "titulo":             titulo,
        "descripcion":        desc,
        "categoria":          categoria,
        "categoria_original": tipo_original,
        "recategorizado":     int(recat),
        "precio_usd":         precio_usd,
        "moneda":             "USD",
        "precio_texto":       f"{raw.get('precio')} USD" if raw.get("precio") else "",
        "telefono":           telefono,
        "whatsapp":           whatsapp,
        "vendedor":           vendedor,
        "provincia":          provincia,
        "municipio":          None,
        "fecha":              fecha,
        "vistas":             None,
        "num_imagenes":       0,
        "imagen_principal":   None,
    }


# ─────────────────────────────────────────
# CARGAR DATOS
# ─────────────────────────────────────────

def cargar_revolico() -> list:
    archivos = sorted(RAW_REVOLICO.glob("detalle_*.json"))
    todos = []
    print(f"\n  Revolico: {len(archivos)} archivos")
    for arch in archivos:
        try:
            with open(arch, "r", encoding="utf-8") as f:
                datos = json.load(f)
            procesados = 0
            for raw in datos:
                p = procesar_revolico(raw)
                if p:
                    todos.append(p)
                    procesados += 1
            print(f"  ✅ {arch.name}: {procesados}/{len(datos)}")
        except Exception as e:
            print(f"  ❌ {arch.name}: {e}")
    return todos


def cargar_facebook() -> list:
    archivos = list(RAW_FACEBOOK.glob("facebook_ofertas_*.json"))
    archivos += list(RAW_FACEBOOK.glob("ultimas_ofertas.json"))
    archivos = sorted(set(archivos))

    todos = []
    print(f"\n  Facebook: {len(archivos)} archivos")
    for arch in archivos:
        try:
            with open(arch, "r", encoding="utf-8") as f:
                datos = json.load(f)
            procesados = 0
            for raw in datos:
                p = procesar_facebook(raw)
                if p:
                    todos.append(p)
                    procesados += 1
            print(f"  ✅ {arch.name}: {procesados}/{len(datos)}")
        except Exception as e:
            print(f"  ❌ {arch.name}: {e}")
    return todos


# ─────────────────────────────────────────
# GUARDAR
# ─────────────────────────────────────────

COLUMNAS = [
    "fuente", "url", "titulo", "descripcion",
    "categoria", "categoria_original", "recategorizado",
    "precio_usd", "moneda", "precio_texto",
    "telefono", "whatsapp", "vendedor",
    "provincia", "municipio", "fecha",
    "vistas", "num_imagenes", "imagen_principal",
]

COLUMNAS_NUMERICAS = {"precio_usd", "recategorizado", "vistas", "num_imagenes"}


def guardar_sqlite(productos: list):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DROP TABLE IF EXISTS productos")

    defs = []
    for col in COLUMNAS:
        tipo = "REAL" if col in COLUMNAS_NUMERICAS else "TEXT"
        defs.append(f"{col} {tipo}")

    conn.execute(f"""
        CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(defs)}
        )
    """)
    conn.execute("CREATE INDEX idx_cat   ON productos(categoria)")
    conn.execute("CREATE INDEX idx_prov  ON productos(provincia)")
    conn.execute("CREATE INDEX idx_prec  ON productos(precio_usd)")
    conn.execute("CREATE INDEX idx_tel   ON productos(telefono)")
    conn.execute("CREATE INDEX idx_fuent ON productos(fuente)")
    conn.execute("CREATE INDEX idx_catprov ON productos(categoria, provincia)")

    ph  = ", ".join(["?" for _ in COLUMNAS])
    sql = f"INSERT OR IGNORE INTO productos ({', '.join(COLUMNAS)}) VALUES ({ph})"
    filas = [tuple(p.get(c) for c in COLUMNAS) for p in productos]
    conn.executemany(sql, filas)
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    conn.close()
    print(f"\n  ✅ SQLite: {total} registros en {DB_PATH.name}")
    return total


def guardar_csvs(productos: list):
    # Por categoria
    por_cat = defaultdict(list)
    for p in productos:
        por_cat[p["categoria"]].append(p)

    cols_csv = ["titulo", "precio_usd", "moneda", "telefono", "whatsapp",
                "vendedor", "provincia", "fuente", "url"]

    for cat, items in por_cat.items():
        items_ord = sorted(items, key=lambda x: x["precio_usd"] or 99999)
        arch = CSV_DIR / f"{cat}.csv"
        with open(arch, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cols_csv, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(items_ord)

    # Maestro
    todos_ord = sorted(productos, key=lambda x: (x["categoria"], x["precio_usd"] or 99999))
    arch_maestro = CLEAN_DIR / "todos_los_productos.csv"
    cols_maestro = ["fuente", "categoria", "titulo", "precio_usd", "moneda",
                    "telefono", "whatsapp", "vendedor", "provincia", "url", "fecha"]
    with open(arch_maestro, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols_maestro, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(todos_ord)

    print(f"  ✅ {len(por_cat)} CSVs + maestro en {CSV_DIR}")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    print("\n" + "="*55)
    print("  CUBA PRECIOS — LIMPIEZA UNIFICADA v4")
    print(f"  Tasa CUP: {TASA_CUP_USD} | MLC: {TASA_MLC_USD}")
    print("="*55)
    print("\n  Reglas activas:")
    print("  ✓ Sin telefono        → descartado")
    print("  ✓ Precio <= 1 USD     → descartado")
    print("  ✓ Precio imposible    → descartado (por categoria)")
    print("  ✓ Busca comprar       → descartado")
    print("  ✓ Taller/servicio     → descartado")
    print("  ✓ Titulo limpio       → sin 'Vendo', emojis, etc.")
    print("  ✓ Categoria por titulo → no por descripcion")

    print(f"\n{'─'*55}")
    print("  Cargando datos...")
    print(f"{'─'*55}")

    revolico = cargar_revolico()
    facebook = cargar_facebook()

    todos_raw = revolico + facebook
    print(f"\n  Subtotal: {len(revolico)} Revolico + {len(facebook)} Facebook = {len(todos_raw)}")

    # Deduplicar por URL
    urls_vistas = set()
    todos = []
    for p in todos_raw:
        url = p.get("url") or ""
        if url and url in urls_vistas:
            continue
        if url:
            urls_vistas.add(url)
        todos.append(p)

    print(f"  Duplicados eliminados: {len(todos_raw) - len(todos)}")
    print(f"  Total final: {len(todos)}")

    if not todos:
        print("\n❌ Sin datos para guardar")
        return

    # Guardar
    print(f"\n{'─'*55}")
    print("  Guardando...")
    print(f"{'─'*55}")
    guardar_sqlite(todos)
    guardar_csvs(todos)

    # Resumen
    por_cat   = defaultdict(int)
    por_prov  = defaultdict(int)
    por_fuent = defaultdict(int)
    for p in todos:
        por_cat[p["categoria"]] += 1
        por_prov[p["provincia"] or "Sin provincia"] += 1
        por_fuent[p["fuente"]] += 1

    con_tel  = sum(1 for p in todos if p["telefono"])
    con_prov = sum(1 for p in todos if p["provincia"])
    precios  = [p["precio_usd"] for p in todos if p["precio_usd"]]

    print(f"\n{'='*55}")
    print("  RESUMEN FINAL")
    print(f"{'='*55}")
    print(f"  Total anuncios    : {len(todos)}")
    for fuente, n in por_fuent.items():
        print(f"  ↳ {fuente:<15} : {n}")
    print(f"  Con telefono      : {con_tel} ({round(con_tel/len(todos)*100)}%)")
    print(f"  Con provincia     : {con_prov} ({round(con_prov/len(todos)*100)}%)")
    if precios:
        print(f"  Precio min        : ${min(precios):.0f}")
        print(f"  Precio max        : ${max(precios):.0f}")
        print(f"  Precio promedio   : ${sum(precios)/len(precios):.0f}")

    print(f"\n  Por categoria:")
    for cat, n in sorted(por_cat.items(), key=lambda x: -x[1]):
        bar = "█" * min(20, n // 3)
        print(f"    {cat:<15} {n:>4}  {bar}")

    print(f"\n  Por provincia:")
    for prov, n in sorted(por_prov.items(), key=lambda x: -x[1])[:12]:
        print(f"    {prov:<25} {n:>4}")

    print(f"\n  💱 Tasa: 1 USD = {TASA_CUP_USD} CUP")
    print(f"  📁 Datos en: {CLEAN_DIR}")
    print("="*55)
    print("\n  ✅ Listo. Corre: streamlit run app/app.py")


if __name__ == "__main__":
    main()