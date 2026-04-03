"""
Limpiador Unificado — CubaPrecios v9.2
- Limpieza extrema de títulos (teléfonos, emojis, pagos, envíos, hashtags)
- Lista negra de productos no deseados (power banks, paneles solares, televisores)
- Eliminación de la categoría "otros"
- Forzado de categorías para fuentes, UPS, coolers, tablets, etc.
- Detección prioritaria de laptops (evita que se clasifiquen como CPU/disco)
- Tablets → accesorio (no laptop)
- Periféricos: solo teclados, ratones, auriculares, micrófonos USB
- Accesorios: cables, adaptadores, transformadores, regletas, hubs, tablets
- Kits CPU+board van a motherboard
- Deduplicación mejorada (URL + teléfono/precio/título)
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
# TASAS DE CAMBIO
# ─────────────────────────────────────────
TASA_CUP_USD = 385.0
TASA_MLC_USD = 1.05

# ─────────────────────────────────────────
# PRECIO MÍNIMO/MAXIMO POR CATEGORÍA (USD)
# ─────────────────────────────────────────
PRECIO_MINIMO = {
    "laptop":      100, "pc":          100, "monitor":     40,
    "gpu":         50,  "cpu":         30,  "motherboard": 30,
    "disco":       15,  "ram":         10,  "periferico":  5,
    "accesorio":   2,   "modem":       10,  "impresora":   30,
    "chasis":      15,  "ups":         15,  "dvd":         10,
    "cd":          1,   "internet":    2,   "sonido":      10,
}
PRECIO_MAXIMO = {
    "laptop":      5000, "pc":          5000, "monitor":     2000,
    "gpu":         3000, "cpu":         2000, "motherboard": 1000,
    "disco":       500,  "ram":         500,  "periferico":  500,
    "accesorio":   300,  "modem":       500,  "impresora":   1000,
    "chasis":      500,  "ups":         500,  "dvd":         100,
    "cd":          50,   "internet":    100,  "sonido":      300,
}

# ─────────────────────────────────────────
# LISTA NEGRA DE PRODUCTOS NO DESEADOS (ampliada)
# ─────────────────────────────────────────
PRODUCTOS_EXCLUIDOS = [
    "power bank", "powerbank", "cargador portátil", "batería externa",
    "panel solar", "placa solar", "energía portátil", "oupes", "ecoflow", "bluetti",
    "generador solar", "estación energía", "power station",
    "nauta recarga", "saldo nauta", "internet móvil", "chip nauta",
    "recarga nauta", "tarjeta nauta", "cup nauta", "mlc nauta",
    "televisor", "smart tv", "tv led", "tv 4k", "tv uhd", "tv smart", "led tv", "lcd tv",
]

# ─────────────────────────────────────────
# PALABRAS QUE INDICAN "BUSCA COMPRAR" / TALLER
# ─────────────────────────────────────────
BUSCA_COMPRAR = [
    "desea vender", "quieres vender", "compro ", "compra ",
    "busco ", "busco laptop", "busco pc", "se compra",
    "pago bien", "interesado en comprar", "necesito comprar",
    "quien vende", "alguien vende", "tiene en venta",
    "busco urgente", "busca laptop", "busca pc", "buscando",
    "necesito ", "requiero", "estoy interesado",
]
ES_SERVICIO = [
    "taller", "reparacion", "reparación", "servicio técnico",
    "servicio tecnico", "agenda su cita", "repara tu",
    "mantenimiento", "formateo", "instalacion de windows",
    "instalación de windows", "reparo", "arreglo",
    "diagnostico", "diagnóstico", "servicio a domicilio",
    "reparacion de", "reparación de",
]

# ─────────────────────────────────────────
# LIMPIEZA EXTREMA DE TÍTULOS
# ─────────────────────────────────────────
def limpiar_titulo_extremo(titulo: str) -> str:
    if not titulo:
        return ""
    t = titulo
    # Teléfonos (8 dígitos o 5 seguido de 7)
    t = re.sub(r'\b(5[0-9]{7}|[2-7][0-9]{7})\b', '', t)
    # Emojis (rango amplio)
    t = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FE0F⭐🪷✅🆕💲🪫🔋📱💻🖥️⌨️🖱️🔌💡]', '', t)
    # Hashtags y números de referencia
    t = re.sub(r'#\d+', '', t)
    t = re.sub(r'\b\d{7,8}\s*[-–]\s*', '', t)
    # Frases comunes de pago/envío
    frases = [
        r'(?i)acepto\s+(mlc[-–]cup[-–]usd[-–]eur|cup[-–]usd|mlc|eur)',
        r'(?i)usd[-–]euro[-–]cup[-–]zelle',
        r'(?i)env[ií]o\s+gratis',
        r'(?i)entrega\s+disponible',
        r'(?i)mensajer[ií]a\s+gratis',
        r'(?i)buenos\s+precios',
        r'(?i)garant[ií]a\s+\d+\s+mes',
        r'(?i)⭐\s*todo\s+en\s+laptops\s*⭐',
        r'\|\s*80\s*PLUS\s+ORO\s*\|',
        r'\|\s*[A-Z0-9]+\s*\|',
        r'(?i)vendo\s+', r'(?i)se\s+vende\s+', r'(?i)venta\s+de\s+',
        r'(?i)oferta\s+', r'(?i)ganga\s*[!.]*\s*', r'(?i)nuevo\s+', r'(?i)nueva\s+',
        r'(?i)disponible\s+', r'(?i)tengo\s+', r'(?i)liquido\s+',
        r'(?i)urgente\s+', r'(?i)oportunidad\s+',
        r'[!❗❌✅⚠️💥🔥]+\s*',
    ]
    for pat in frases:
        t = re.sub(pat, '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip(' .,!?;:-')
    return t if len(t) >= 5 else ""

def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    resultado = []
    for char in texto:
        cp = ord(char)
        if (0x1F300 <= cp <= 0x1F9FF or
            0x2600 <= cp <= 0x27BF or
            0xFE00 <= cp <= 0xFE0F or
            cp in (0x200B, 0x200C, 0x200D, 0xFEFF)):
            continue
        resultado.append(char)
    texto = "".join(resultado)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
    return texto

def limpiar_titulo_avanzado(titulo: str) -> str:
    if not titulo:
        return ""
    prefijos = [
        r'^vendo\s+', r'^se vende\s+', r'^venta\s+de\s+', r'^venta\s+',
        r'^oferta\s+', r'^ganga\s*[!.]*\s*', r'^nuevo\s+', r'^nueva\s+',
        r'^disponible\s+', r'^tengo\s+', r'^liquido\s+', r'^urgente\s+',
        r'^oportunidad\s+', r'[!❗❌✅⚠️💥🔥]+\s*',
    ]
    for patron in prefijos:
        titulo = re.sub(patron, '', titulo, flags=re.IGNORECASE).strip()
    titulo = re.sub(r'\s*[-–]\s*Img\s+\d+$', '', titulo, flags=re.IGNORECASE).strip()
    titulo = re.sub(r'\s+\d{7,8}$', '', titulo).strip()
    palabras = titulo.split()
    if len(palabras) > 1 and palabras[0].lower() == palabras[1].lower():
        titulo = ' '.join(palabras[1:])
    return titulo

def limpiar_telefono(tel: str) -> str | None:
    if not tel:
        return None
    solo = re.sub(r'[^0-9]', '', str(tel))
    if solo.startswith("53") and len(solo) == 10:
        solo = solo[2:]
    if len(solo) in [7, 8]:
        return solo
    return None

def mejor_telefono(raw: dict, fuente: str) -> str | None:
    if fuente == "facebook":
        telefonos = raw.get("telefonos")
        if telefonos:
            if isinstance(telefonos, list):
                for t in telefonos:
                    tel = limpiar_telefono(t)
                    if tel:
                        return tel
            elif isinstance(telefonos, str):
                tel = limpiar_telefono(telefonos)
                if tel:
                    return tel
    else:
        for campo in ["telefono", "whatsapp", "telefonos_detectados"]:
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
    if any(x in t for x in ["cup", "peso", "pesos", " mn", "kuki"]):
        return "CUP"
    if "mlc" in t:
        return "MLC"
    return "USD"

def extraer_precio_usd(raw: dict, fuente: str, moneda: str) -> float | None:
    if fuente != "facebook":
        precio_directo = raw.get("precio_usd")
        if precio_directo is not None:
            try:
                valor = float(precio_directo)
                if valor > 1:
                    if moneda == "CUP":
                        return round(valor / TASA_CUP_USD, 2)
                    if moneda == "MLC":
                        return round(valor * TASA_MLC_USD, 2)
                    return valor
            except (ValueError, TypeError):
                pass
    precio_str = (raw.get("precio_texto") or raw.get("precio_raw") or raw.get("precio") or "")
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

def es_producto_excluido(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return any(palabra in t for palabra in PRODUCTOS_EXCLUIDOS)

def normalizar_url(url: str) -> str:
    if not url:
        return ""
    return url.split('?')[0].split('#')[0]

def generar_titulo_limpio(contenido: str) -> str:
    if not contenido:
        return ""
    lineas = [l.strip() for l in contenido.split('\n') if l.strip()]
    if not lineas:
        return ""
    titulo = lineas[0]
    if len(titulo) < 10 and len(lineas) > 1:
        titulo = lineas[0] + " " + lineas[1]
    titulo = limpiar_texto(titulo)
    for patron in [r'^vendo\s+', r'^se vende\s+', r'^venta\s+de\s+']:
        titulo = re.sub(patron, '', titulo, flags=re.IGNORECASE).strip()
    titulo = titulo.strip(" .-,!?")
    if len(titulo) > 100:
        titulo = titulo[:100].rsplit(' ', 1)[0]
    return titulo

# ─────────────────────────────────────────
# FORZAR CATEGORÍA (versión corregida, sin procesador/cpu, incluye tablet)
# ─────────────────────────────────────────
FORZAR_CATEGORIA = {
    "fuente": "chasis", "gabinete": "chasis", "chasis": "chasis", "psu": "chasis",
    "fuente de poder": "chasis", "ups": "ups", "nobreak": "ups", "no break": "ups",
    "regulador": "ups", "backup": "ups", "cooler": "accesorio", "disipador": "accesorio",
    "aire": "accesorio",   # "procesador" y "cpu" eliminados para evitar falsos positivos
    "motherboard": "motherboard", "placa madre": "motherboard",
    "tarjeta de video": "gpu", "gtx": "gpu", "rtx": "gpu",
    "disco duro": "disco", "ssd": "disco", "memoria ram": "ram", "ram ddr": "ram",
    "monitor": "monitor", "laptop": "laptop", "impresora": "impresora",
    "tablet": "accesorio",   # ← NUEVO: tablets van a accesorios
}

PALABRAS_TV = [
    "televisor", "smart tv", "tv led", "tv 4k", "tv uhd",
    "tv smart", "led tv", "lcd tv", "oled tv", "qled",
    "lg tv", "samsung tv", "sony tv", "tcl tv", "hisense",
    "tv 32", "tv 43", "tv 50", "tv 55", "tv 65", "tv 75",
]
PALABRAS_IMPRESORA = [
    "impresora", "multifuncional", "laserjet", "inkjet", "tóner", "toner",
    "tinta continua", "cartucho", "epson", "hp laserjet", "canon pixma",
    "brother", "et-2800", "et-2803", "et-4850", "3 en 1", "3en1",
]

# ─────────────────────────────────────────
# REGLAS DE CATEGORÍA (sin "otros")
# ─────────────────────────────────────────
REGLAS_CATEGORIA = [
    ("pc", {
        "palabras_clave": ["pc gamer", "pc gaming", "pc de escritorio", "computadora de mesa",
                           "desktop", "torre completa", "pc armada", "cpu completo", "aio",
                           "equipo completo", "pc lista", "torre lista", "pc para usar",
                           "mini pc", "optiplex", "nuc", "intel nuc", "pc mini",
                           "computadora completa", "en pc", "vendo pc"],
        "excluir": ["notebook", "monitor", "solo", "disco solo", "ram solo", "procesador solo",
                    "tarjeta video solo", "sin", "falta", "televisor", "smart tv",
                    "impresora", "multifuncional", "tinta", "toner", "epson", "laserjet"],
        "es_equipo_completo": True,
    }),
    ("laptop", {
        "palabras_clave": ["laptop", "notebook", "macbook", "thinkpad", "ideapad", "vivobook",
                           "ultrabook", "chromebook", "portatil", "portátil", "hp envy",
                           "dell inspiron", "lenovo legion", "2 en 1", "horas bateria",
                           "autonomia bateria"],
        "excluir": ["funda", "cargador", "bateria laptop", "cooler", "base", "mouse", "teclado",
                    "monitor", "torre", "gabinete", "disco externo", "memoria usb", "pendrive",
                    "televisor", "smart tv", "impresora", "compatible con", "para laptop",
                    "para pc", "microfono", "micrófono", "bocina", "parlante", "auricular",
                    "rtx", "gtx", "tarjeta de video", "tarjeta grafica", "tablet"],  # ← excluir tablet
        "es_equipo_completo": True,
    }),
    ("monitor", {
        "palabras_clave": ["monitor", "pantalla", "display", "144hz", "165hz", "240hz",
                           "monitor gamer", "monitor gaming", "monitor samsung", "monitor lg",
                           "monitor dell", "monitor hp", "smart tv", "televisor", "tv",
                           "led tv", "lcd tv", "lg tv", "samsung tv", "sony tv", "tcl",
                           "hisense", "curvo", "4k monitor", "monitor 4k"],
        "excluir": ["laptop", "pc", "computadora", "torre", "gabinete", "placa madre",
                    "motherboard", "procesador", "cpu", "memoria ram", "disco duro", "ssd",
                    "tarjeta video", "gpu", "teclado", "mouse", "impresora", "router",
                    "playstation", "ps4", "ps5", "xbox", "nintendo", "chasis", "fuente",
                    "soporte monitor", "brazo monitor", "vesa"],
        "es_equipo_completo": False,
    }),
    ("impresora", {
        "palabras_clave": PALABRAS_IMPRESORA,
        "excluir": ["laptop", "pc", "monitor", "disco", "ssd", "ram", "procesador",
                    "mouse", "teclado", "parlante", "bocina", "televisor", "smart tv"],
        "es_equipo_completo": False,
    }),
    ("gpu", {
        "palabras_clave": ["tarjeta de video", "tarjeta grafica", "tarjeta gráfica",
                           "gtx", "rtx", "radeon", "nvidia", "amd radeon", "video card", "gpu"],
        "excluir": ["laptop", "monitor", "pc completa", "torre completa", "impresora",
                    "teclado", "mouse", "televisor", "smart tv"],
        "es_equipo_completo": False,
    }),
    ("cpu", {
        "palabras_clave": ["procesador", "microprocesador", "intel core", "amd ryzen",
                           "ryzen 3", "ryzen 5", "ryzen 7", "ryzen 9", "cpu intel", "cpu amd",
                           "3200g", "3400g", "4650g", "5600g", "5700g", "14th gen", "13th gen",
                           "12th gen", "11th gen", "10th gen", "14600k", "13600k", "12600k"],
        "excluir": ["laptop", "monitor", "pc completa", "torre", "tarjeta", "disco", "ram",
                    "mouse", "teclado", "impresora", "laptop completa", "pc armada", "kit board",
                    "televisor", "smart tv", "router", "modem", "wifi"],
        "es_equipo_completo": False,
    }),
    ("motherboard", {
        "palabras_clave": ["motherboard", "placa madre", "placa base", "mainboard", "tarjeta madre",
                           "socket", "b450", "b550", "b650", "z690", "z790", "h610", "x570",
                           "a320", "kit board", "board y micro", "kit de board", "a520", "a520m",
                           "b560", "h610m", "b760", "pro de msi", "msi pro", "asus prime"],
        "excluir": ["laptop", "monitor", "pc completa", "mouse", "teclado", "impresora", "televisor"],
        "es_equipo_completo": False,
    }),
    ("ram", {
        "palabras_clave": ["memoria ram", "ram ddr", "ddr3", "ddr4", "ddr5", "sodimm", "dimm",
                           "ram 8gb", "ram 16gb", "ram 32gb"],
        "excluir": ["usb", "pendrive", "flash", "micro sd", "tarjeta memoria", "laptop completa",
                    "pc completa", "disco", "ssd", "memoria usb", "memoria flash", "kit mouse",
                    "kit teclado", "televisor", "smart tv", "dell inspiron", "hp envy", "lenovo"],
        "es_equipo_completo": False,
    }),
    ("disco", {
        "palabras_clave": ["disco duro", "disco ssd", "hdd", "nvme", "m.2", "m2", "disco solido",
                           "disco mecanico", "disco externo", "seagate", "western digital",
                           "toshiba", "adata", "transcend", "disco portatil", "almacenamiento portátil",
                           "wd my passport"],  # ← añadido para capturar discos externos
        "excluir": ["laptop", "notebook", "pc completa", "memoria usb", "pendrive", "teclado",
                    "mouse", "impresora", "monitor", "ram", "televisor", "smart tv"],
        "es_equipo_completo": False,
    }),
    ("chasis", {
        "palabras_clave": ["chasis", "gabinete", "case", "fuente de poder", "fuente corsair",
                           "fuente evga", "psu", "fuente 500w", "fuente 600w", "fuente 750w",
                           "fuente 850w", "fuente atx", "gabinete gamer", "full tower",
                           "mid tower", "fuente certificada", "fuente 80 plus", "montech",
                           "sama", "nzxt", "phanteks", "fractal", "deepcool", "cooler master case",
                           "lian li", "tooq", "fanes rgb", "fan rgb"],
        "excluir": ["laptop", "pc completa", "teclado", "mouse", "impresora", "pantalla", "lcd",
                    "ups", "nobreak", "bateria", "regulador", "led tv", "televisor", "smart tv"],
        "es_equipo_completo": False,
    }),
    ("ups", {
        "palabras_clave": ["ups", "nobreak", "no break", "regulador", "estabilizador", "backup",
                           "bateria 12v", "bateria ups", "mini ups", "apc", "inversor",
                           "estacion energia", "power station", "estación energía"],
        "excluir": ["laptop", "pc", "monitor", "bateria laptop", "fuente de poder", "psu"],
        "es_equipo_completo": False,
    }),
    ("modem", {
        "palabras_clave": ["router", "mikrotik", "tp-link", "tplink", "switch", "access point",
                           "repetidor", "antena wifi", "modem", "nauta", "etecsa", "tarjeta de red",
                           "wifi pci", "extensor wifi", "mesh", "dlink", "d-link", "asus router",
                           "netgear", "ubiquiti", "unifi", "ac750", "ac1200", "ac1750", "ac3000",
                           "ax3000", "ax6000", "wifi 6", "tri-banda", "dual banda"],
        "excluir": ["laptop", "pc", "monitor", "impresora"],
        "es_equipo_completo": False,
    }),
    ("sonido", {
        "palabras_clave": ["bocina", "parlante", "speaker", "subwoofer", "soundbar", "barra sonido",
                           "bafle", "amplificador", "jbl", "home theater", "2.1", "5.1", "7.1",
                           "bocina bluetooth", "parlante bluetooth", "zizo", "anker soundcore",
                           "marshall", "bose", "harman", "microfono", "micrófono", "brazo microfono",
                           "brazo micrófono", "interfaz de audio", "mezclador", "mixer audio"],
        "excluir": ["monitor", "teclado", "mouse", "audifono", "audífonos", "auricular",
                    "headset", "diadema", "microfono usb", "microfono gaming", "fifine",
                    "blue yeti", "hyperx", "pc gamer", "laptop vendo"],
        "es_equipo_completo": False,
    }),
    ("periferico", {
        "palabras_clave": [
            "teclado", "mouse", "raton", "webcam", "camara web",
            "auriculares", "audifonos", "headset", "diadema", "in-ear", "over-ear",
            "earbuds", "tws", "joystick", "gamepad", "control xbox", "control ps4",
            "g502", "logitech", "razer", "corsair", "redragon", "teclado mecanico",
            "teclado gaming", "mouse gaming", "kit mouse", "kit teclado",
            "mouse y teclado", "teclado y mouse", "combo teclado",
            "microfono usb", "micrófono usb", "microfono condensador",
            "micrófono condensador", "microfono gaming", "micrófono gaming",
            "fifine", "blue yeti", "hyperx quadcast",
        ],
        "excluir": ["monitor", "impresora", "disco", "ram", "procesador", "placa", "motherboard",
                    "bocina", "parlante", "soundbar", "micrófono incluido", "pc gamer", "laptop vendo"],
        "es_equipo_completo": False,
    }),
    ("accesorio", {
        "palabras_clave": [
            "cable", "adaptador", "conversor", "hub", "dock", "transformador", "regleta",
            "switch hdmi", "adaptador displayport", "mini displayport", "thundervolt",
            "cooler", "ventilador", "disipador", "base laptop", "cargador", "bateria",
            "power bank", "mouse pad", "alfombrilla", "pendrive", "memoria usb",
            "usb", "micro sd", "tarjeta memoria", "capturadora", "usb 3.0", "usb tipo c",
            "soporte monitor", "soporte laptop", "brazo monitor", "vesa",
            "brazo microfono", "brazo micrófono", "pop filter", "tablet",  # ← tablets aquí
        ],
        "excluir": ["impresora", "disco duro", "memoria ram", "procesador", "teclado", "mouse",
                    "ssd", "hdd", "nvme", "fuente de poder", "pc gamer", "laptop vendo"],
        "es_equipo_completo": False,
    }),
    ("cd", {
        "palabras_clave": ["cd virgen", "dvd virgen", "cd-r", "dvd-r", "bluray virgen", "disco virgen"],
        "excluir": ["quemador", "lector", "unidad"],
        "es_equipo_completo": False,
    }),
    ("dvd", {
        "palabras_clave": ["quemador dvd", "lector dvd", "unidad dvd", "bluray", "dvd externo"],
        "excluir": ["virgen", "cd-r", "dvd-r"],
        "es_equipo_completo": False,
    }),
    ("internet", {
        "palabras_clave": ["nauta", "cuenta nauta", "recarga", "chip nauta", "internet movil", "datos moviles"],
        "excluir": ["router", "modem"],
        "es_equipo_completo": False,
    }),
]

# ─────────────────────────────────────────
# PROVINCIAS NORM (resumida pero funcional)
# ─────────────────────────────────────────
PROVINCIAS_NORM = {
    "habana": "La Habana", "la habana": "La Habana", "ciudad habana": "La Habana",
    "miramar": "La Habana", "vedado": "La Habana", "playa": "La Habana", "marianao": "La Habana",
    "artemisa": "Artemisa", "mayabeque": "Mayabeque", "pinar del rio": "Pinar del Río",
    "pinar del río": "Pinar del Río", "matanzas": "Matanzas", "cienfuegos": "Cienfuegos",
    "villa clara": "Villa Clara", "santa clara": "Villa Clara", "sancti spiritus": "Sancti Spíritus",
    "sancti spíritus": "Sancti Spíritus", "ciego de avila": "Ciego de Ávila", "ciego de ávila": "Ciego de Ávila",
    "camaguey": "Camagüey", "camagüey": "Camagüey", "las tunas": "Las Tunas",
    "holguin": "Holguín", "holguín": "Holguín", "granma": "Granma", "santiago de cuba": "Santiago de Cuba",
    "santiago": "Santiago de Cuba", "guantanamo": "Guantánamo", "guantánamo": "Guantánamo",
    "isla de la juventud": "Isla de la Juventud", "nueva gerona": "Isla de la Juventud",
}

def detectar_provincia(raw: dict, fuente: str, grupo_provincia: str = None) -> str | None:
    if grupo_provincia:
        clave = grupo_provincia.strip().lower()
        norm = PROVINCIAS_NORM.get(clave)
        if norm:
            return norm
        for k, v in PROVINCIAS_NORM.items():
            if k in clave or clave in k:
                return v
        return grupo_provincia
    prov_raw = (raw.get("provincia") or "").strip()
    if prov_raw:
        clave = prov_raw.lower()
        norm = PROVINCIAS_NORM.get(clave)
        if norm:
            return norm
        for k, v in PROVINCIAS_NORM.items():
            if k in clave:
                return v
    texto = (raw.get("contenido") or "") + " " + (raw.get("descripcion_completa") or "") + " " + (raw.get("titulo") or "")
    texto = texto.lower()
    for clave, nombre in PROVINCIAS_NORM.items():
        if clave in texto:
            return nombre
    return None

def es_busca_comprar(texto: str) -> bool:
    t = texto.lower()
    return any(frase in t for frase in BUSCA_COMPRAR)

def es_servicio_taller(texto: str) -> bool:
    t = texto.lower()
    return any(frase in t for frase in ES_SERVICIO)

def _es_tv(texto: str) -> bool:
    return any(p in texto for p in PALABRAS_TV)

def _es_impresora(texto: str) -> bool:
    return any(p in texto for p in PALABRAS_IMPRESORA)

def detectar_categoria_estricta(titulo: str, descripcion: str = "") -> tuple:
    texto = (titulo + " " + descripcion).lower()
    titulo_limpio = limpiar_titulo_avanzado(titulo).lower()

    # ----- REGLA PRIORITARIA: TABLET (antes que laptop) -----
    if re.search(r'\btablet\b', texto):
        return "accesorio", True

    # ----- REGLA PRIORITARIA: LAPTOP -----
    if re.search(r'\b(laptop|notebook|macbook|thinkpad|ideapad|vivobook|chromebook|portatil)\b', texto):
        if not re.search(r'\b(funda|base|enfriador|cooler|disipador|cargador|bateria|teclado|mouse|parlante|bocina|audifono|headset|tablet)\b', texto):
            return "laptop", True

    # Forzar categoría (sin procesador/cpu)
    for palabra, cat in FORZAR_CATEGORIA.items():
        if palabra in titulo_limpio:
            return cat, True

    if _es_tv(texto):
        return "monitor", True

    if _es_impresora(texto):
        es_pc_aio = any(k in texto for k in ["aio pc", "all in one pc", "pc all in one",
                                              "computadora all in one", "desktop all in one"])
        if not es_pc_aio:
            return "impresora", True

    # Equipos completos
    for categoria, reglas in REGLAS_CATEGORIA:
        if not reglas.get("es_equipo_completo", False):
            continue
        palabras_a_buscar = list(reglas["palabras_clave"])
        if categoria == "pc":
            palabras_a_buscar.append("all in one")
        for palabra in palabras_a_buscar:
            if palabra in texto:
                if not any(excluir in texto for excluir in reglas["excluir"]):
                    return categoria, True

    # Kits especiales (board + micro)
    if "kit board" in texto or "kit de board" in texto or "board y micro" in texto:
        return "motherboard", True

    # Kits de CPU + board aunque no diga "board" explícitamente
    if re.search(r'kit\s+(?:de\s+)?(?:procesador|micro|cpu|intel|amd|ryzen|core i\d)', texto) and \
       re.search(r'(ram|disipada|board|placa)', texto):
        return "motherboard", True

    _apu_keywords = ["3200g", "3400g", "4650g", "5600g", "5700g", "ryzen3", "ryzen5", "ryzen7"]
    _board_keywords = ["a520", "b450", "b550", "b650", "a320", "h610", "h510", "b560", "b760"]
    if any(k in texto for k in _apu_keywords) and any(k in texto for k in _board_keywords):
        return "motherboard", True

    _intel_gen = ["14th gen", "13th gen", "12th gen", "11th gen", "10th gen",
                  "14600k", "13600k", "12600k", "13700k", "14700k", "14900k"]
    if any(k in texto for k in _intel_gen):
        return "cpu", True

    if "kit mouse" in texto or "kit teclado" in texto or "mouse y teclado" in texto:
        return "periferico", True

    # Monitores con cuidado (evitar confundir con chasis)
    tiene_chasis = any(k in texto for k in ["chasis", "gabinete", "torre", "case gamer"])
    for categoria, reglas in REGLAS_CATEGORIA:
        if categoria != "monitor":
            continue
        for palabra in reglas["palabras_clave"]:
            if palabra in texto:
                if tiene_chasis and palabra in ["monitor", "pantalla", "display"]:
                    continue
                if not any(excluir in texto for excluir in reglas["excluir"]):
                    return categoria, True

    # Impresoras segunda oportunidad
    for categoria, reglas in REGLAS_CATEGORIA:
        if categoria == "impresora":
            for palabra in reglas["palabras_clave"]:
                if palabra in texto and not any(excluir in texto for excluir in reglas["excluir"]):
                    return categoria, True

    # CPU con i3/i5/i7/i9 (solo si hay contexto técnico)
    cpu_reglas = next((r for c, r in REGLAS_CATEGORIA if c == "cpu"), None)
    if cpu_reglas:
        if not any(excluir in texto for excluir in cpu_reglas["excluir"]):
            for palabra in cpu_reglas["palabras_clave"]:
                if palabra in texto:
                    return "cpu", True
            contexto_cpu = any(c in texto for c in ["procesador", "socket", "ghz", "core", "intel", "amd"])
            if contexto_cpu and re.search(r'\b(i3|i5|i7|i9)\b', texto):
                return "cpu", True

    # Resto de categorías
    saltar = {"pc", "laptop", "monitor", "impresora", "cpu"}
    for categoria, reglas in REGLAS_CATEGORIA:
        if categoria in saltar or reglas.get("es_equipo_completo"):
            continue
        if not reglas["palabras_clave"]:
            continue
        for palabra in reglas["palabras_clave"]:
            if (" " in palabra and palabra in texto) or re.search(r'\b' + re.escape(palabra) + r'\b', texto):
                if not any(excluir in texto for excluir in reglas["excluir"]):
                    return categoria, True

    # No detectada -> None (se descartará)
    return None, False

def precio_valido(precio: float, categoria: str) -> bool:
    if not categoria or categoria not in PRECIO_MINIMO:
        return False
    if not precio or precio < PRECIO_MINIMO[categoria]:
        return False
    if precio > PRECIO_MAXIMO[categoria]:
        return False
    return True

# ─────────────────────────────────────────
# PROCESAR ANUNCIOS
# ─────────────────────────────────────────
def procesar_revolico(raw: dict) -> dict | None:
    titulo = limpiar_texto(raw.get("titulo") or "")
    if not titulo or len(titulo) < 3:
        return None
    descripcion = limpiar_texto(raw.get("descripcion_completa") or "")
    texto_completo = titulo + " " + descripcion

    if es_producto_excluido(texto_completo):
        return None
    if es_busca_comprar(texto_completo) or es_servicio_taller(texto_completo):
        return None

    telefono = mejor_telefono(raw, "revolico")
    if not telefono:
        return None

    precio_texto_raw = (raw.get("precio_texto") or raw.get("precio_raw") or raw.get("precio") or "")
    moneda = detectar_moneda(precio_texto_raw)
    precio_usd = extraer_precio_usd(raw, "revolico", moneda)
    if not precio_usd:
        return None

    categoria_original = raw.get("categoria") or "desconocida"
    categoria, recat = detectar_categoria_estricta(titulo, descripcion)
    if categoria is None or categoria == "internet":
        return None
    if not precio_valido(precio_usd, categoria):
        return None

    provincia = detectar_provincia(raw, "revolico")
    whatsapp = None
    wa_match = re.search(r'wa\.me/\+?53?(\d{7,8})', texto_completo)
    if wa_match:
        whatsapp = limpiar_telefono(wa_match.group(1))

    titulo_limpio = limpiar_titulo_extremo(titulo)
    if not titulo_limpio or len(titulo_limpio) < 5:
        return None

    url = normalizar_url(raw.get("url") or "")
    if not url:
        return None

    imagenes_lista = raw.get("imagenes") or []
    num_imagenes = raw.get("num_imagenes") or len(imagenes_lista)
    imagen_principal = raw.get("imagen_principal") or (imagenes_lista[0] if imagenes_lista else None)

    return {
        "fuente": "revolico",
        "url": url,
        "titulo": titulo_limpio[:100],
        "descripcion": descripcion[:500] if descripcion else None,
        "categoria": categoria,
        "categoria_original": categoria_original,
        "recategorizado": int(recat),
        "precio_usd": precio_usd,
        "moneda": moneda,
        "precio_texto": limpiar_texto(precio_texto_raw)[:50],
        "telefono": telefono,
        "whatsapp": whatsapp,
        "vendedor": limpiar_texto(raw.get("vendedor") or "")[:50] or None,
        "provincia": provincia,
        "municipio": limpiar_texto(raw.get("municipio") or "")[:50] or None,
        "fecha": (raw.get("fecha_exacta") or raw.get("scrapeado_en") or "")[:10] or None,
        "vistas": raw.get("vistas"),
        "num_imagenes": num_imagenes,
        "imagen_principal": imagen_principal,
    }

def procesar_facebook(raw: dict) -> dict | None:
    contenido = raw.get("contenido") or ""
    if not contenido or len(contenido) < 10:
        return None
    if es_producto_excluido(contenido) or es_busca_comprar(contenido) or es_servicio_taller(contenido):
        return None

    titulo = generar_titulo_limpio(contenido)
    if not titulo or len(titulo) < 5:
        return None

    telefono = mejor_telefono(raw, "facebook")
    if not telefono:
        return None

    moneda_raw = raw.get("moneda") or ""
    moneda = detectar_moneda(moneda_raw) if moneda_raw else "USD"
    precio_usd = extraer_precio_usd(raw, "facebook", moneda)
    if not precio_usd:
        return None

    tipo_original = raw.get("tipo_equipo") or "desconocido"
    categoria, recat = detectar_categoria_estricta(titulo, contenido)
    if categoria is None or categoria == "internet":
        return None
    if not precio_valido(precio_usd, categoria):
        return None

    provincia = detectar_provincia(raw, "facebook", raw.get("provincia"))
    whatsapp = None
    wa_match = re.search(r'wa\.me/\+?53?(\d{7,8})', contenido)
    if wa_match:
        whatsapp = limpiar_telefono(wa_match.group(1))

    vendedor = raw.get("autor") or None
    if vendedor and len(vendedor) < 2:
        vendedor = None

    titulo_limpio = limpiar_titulo_extremo(titulo)
    if not titulo_limpio or len(titulo_limpio) < 5:
        return None

    url = normalizar_url(raw.get("url") or "")
    if not url:
        return None

    return {
        "fuente": "facebook",
        "url": url,
        "titulo": titulo_limpio[:100],
        "descripcion": limpiar_texto(contenido)[:500],
        "categoria": categoria,
        "categoria_original": tipo_original,
        "recategorizado": int(recat),
        "precio_usd": precio_usd,
        "moneda": "USD",
        "precio_texto": f"{raw.get('precio')} {raw.get('moneda')}" if raw.get("precio") else "",
        "telefono": telefono,
        "whatsapp": whatsapp,
        "vendedor": vendedor[:50] if vendedor else None,
        "provincia": provincia,
        "municipio": None,
        "fecha": (raw.get("fecha_extraccion") or raw.get("fecha_post") or "")[:10] or None,
        "vistas": None,
        "num_imagenes": 0,
        "imagen_principal": None,
    }

# ─────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────
def cargar_revolico() -> list:
    archivos = sorted(RAW_REVOLICO.glob("*.json"))
    todos = []
    print(f"\n  Revolico: {len(archivos)} archivos")
    for arch in archivos:
        try:
            with open(arch, "r", encoding="utf-8") as f:
                datos = json.load(f)
            procesados = 0
            if isinstance(datos, list):
                for raw in datos:
                    p = procesar_revolico(raw)
                    if p:
                        todos.append(p)
                        procesados += 1
            elif isinstance(datos, dict):
                p = procesar_revolico(datos)
                if p:
                    todos.append(p)
                    procesados += 1
            if procesados > 0:
                print(f"  ✅ {arch.name}: {procesados} anuncios")
            else:
                print(f"  ⚠️ {arch.name}: 0 anuncios (filtrados)")
        except Exception as e:
            print(f"  ❌ {arch.name}: {e}")
    return todos

def cargar_facebook() -> list:
    archivos = list(RAW_FACEBOOK.glob("grupo_*.json")) + list(RAW_FACEBOOK.glob("facebook_ofertas_*.json")) + list(RAW_FACEBOOK.glob("ultimas_ofertas.json"))
    archivos = sorted(set(archivos))
    todos = []
    print(f"\n  Facebook: {len(archivos)} archivos encontrados")
    for arch in archivos:
        try:
            with open(arch, "r", encoding="utf-8") as f:
                datos = json.load(f)
            procesados = 0
            if isinstance(datos, list):
                for raw in datos:
                    p = procesar_facebook(raw)
                    if p:
                        todos.append(p)
                        procesados += 1
            elif isinstance(datos, dict):
                p = procesar_facebook(datos)
                if p:
                    todos.append(p)
                    procesados += 1
            if procesados > 0:
                print(f"  ✅ {arch.name}: {procesados} posts")
            else:
                print(f"  ⚠️ {arch.name}: 0 posts (filtrados)")
        except Exception as e:
            print(f"  ❌ {arch.name}: {e}")
    return todos

# ─────────────────────────────────────────
# GUARDAR RESULTADOS
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

def guardar_sqlite(productos: list) -> int:
    vistos = set()
    unicos = []
    for p in productos:
        clave = (p.get("telefono"), p.get("precio_usd"), p.get("titulo", "")[:50])
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(p)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DROP TABLE IF EXISTS productos")
    defs = [f"{col} {'REAL' if col in COLUMNAS_NUMERICAS else 'TEXT'}" for col in COLUMNAS]
    conn.execute(f"""
        CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(defs)}
        )
    """)
    conn.execute("CREATE INDEX idx_cat ON productos(categoria)")
    conn.execute("CREATE INDEX idx_prov ON productos(provincia)")
    conn.execute("CREATE INDEX idx_prec ON productos(precio_usd)")
    conn.execute("CREATE INDEX idx_tel ON productos(telefono)")
    conn.execute("CREATE INDEX idx_fuent ON productos(fuente)")

    ph = ", ".join(["?" for _ in COLUMNAS])
    sql = f"INSERT OR IGNORE INTO productos ({', '.join(COLUMNAS)}) VALUES ({ph})"
    filas = [tuple(p.get(c) for c in COLUMNAS) for p in unicos]
    conn.executemany(sql, filas)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    conn.close()
    print(f"\n  ✅ SQLite: {total} registros (eliminados {len(productos)-len(unicos)} duplicados)")
    return total

def guardar_csvs(productos: list):
    por_cat = defaultdict(list)
    for p in productos:
        por_cat[p["categoria"]].append(p)
    cols_csv = ["titulo", "precio_usd", "moneda", "telefono", "whatsapp", "vendedor", "provincia", "fuente", "url"]
    for cat, items in por_cat.items():
        items_ord = sorted(items, key=lambda x: x["precio_usd"] or 99999)
        arch = CSV_DIR / f"{cat}.csv"
        with open(arch, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cols_csv, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(items_ord)
    todos_ord = sorted(productos, key=lambda x: (x["categoria"], x["precio_usd"] or 99999))
    arch_maestro = CLEAN_DIR / "todos_los_productos.csv"
    cols_maestro = ["fuente", "categoria", "titulo", "precio_usd", "moneda", "telefono", "whatsapp", "vendedor", "provincia", "url", "fecha"]
    with open(arch_maestro, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols_maestro, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(todos_ord)
    print(f"  ✅ {len(por_cat)} CSVs por categoría + maestro en {CSV_DIR}")

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    print("\n" + "=" * 60)
    print("  CUBA PRECIOS — LIMPIEZA ESTRICTA v9.2")
    print("  + Limpieza extrema de títulos")
    print("  + Lista negra (power banks, televisores, etc.)")
    print("  + Detección prioritaria de laptops y tablets")
    print("  + Tablets → accesorio")
    print("  + Discos externos mejor detectados")
    print("  + Periféricos y accesorios separados")
    print("=" * 60)

    print(f"\n{'─' * 60}")
    print("  CARGANDO DATOS...")
    print(f"{'─' * 60}")

    revolico = cargar_revolico()
    facebook = cargar_facebook()

    todos_raw = revolico + facebook
    print(f"\n  Subtotal: {len(revolico)} Revolico + {len(facebook)} Facebook = {len(todos_raw)}")

    urls_vistas = set()
    todos = []
    for p in todos_raw:
        url = p.get("url") or ""
        if url and url in urls_vistas:
            continue
        if url:
            urls_vistas.add(url)
        todos.append(p)
    print(f"  Duplicados por URL eliminados: {len(todos_raw) - len(todos)}")
    print(f"  Total final: {len(todos)}")

    if not todos:
        print("\n  ❌ Sin datos para guardar")
        return

    print(f"\n{'─' * 60}")
    print("  GUARDANDO...")
    print(f"{'─' * 60}")

    guardar_sqlite(todos)
    guardar_csvs(todos)

    por_cat = defaultdict(int)
    por_prov = defaultdict(int)
    por_fuent = defaultdict(int)
    recat_count = 0
    for p in todos:
        por_cat[p["categoria"]] += 1
        por_prov[p["provincia"] or "Sin provincia"] += 1
        por_fuent[p["fuente"]] += 1
        if p.get("recategorizado"):
            recat_count += 1
    con_tel = sum(1 for p in todos if p["telefono"])
    con_prov = sum(1 for p in todos if p["provincia"])
    precios = [p["precio_usd"] for p in todos if p["precio_usd"]]

    print(f"\n{'=' * 60}")
    print("  RESUMEN FINAL")
    print(f"{'=' * 60}")
    print(f"  Total anuncios     : {len(todos)}")
    for fuente, n in por_fuent.items():
        print(f"  ↳ {fuente:<15} : {n}")
    print(f"  Recategorizados    : {recat_count}")
    print(f"  Con teléfono       : {con_tel} ({round(con_tel/len(todos)*100)}%)")
    print(f"  Con provincia      : {con_prov} ({round(con_prov/len(todos)*100)}%)")
    if precios:
        print(f"  Precio min         : ${min(precios):.0f}")
        print(f"  Precio max         : ${max(precios):.0f}")
        print(f"  Precio promedio    : ${sum(precios)/len(precios):.0f}")
    print(f"\n  POR CATEGORÍA:")
    for cat, n in sorted(por_cat.items(), key=lambda x: -x[1]):
        bar = "█" * min(20, n // 2)
        print(f"    {cat:<15} {n:>4}  {bar}")
    print(f"\n  POR PROVINCIA (top 10):")
    for prov, n in sorted(por_prov.items(), key=lambda x: -x[1])[:10]:
        print(f"    {prov:<30} {n:>4}")
    print(f"\n  💱 Tasa: 1 USD = {TASA_CUP_USD} CUP")
    print(f"  📁 Datos en: {CLEAN_DIR}")
    print("=" * 60)
    print("\n  ✅ Listo. Corre: streamlit run app.py")

if __name__ == "__main__":
    main()