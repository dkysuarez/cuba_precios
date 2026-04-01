"""
Limpiador Unificado — CubaPrecios v8.6
PRIORIDAD DE EQUIPOS COMPLETOS + LIMPIEZA AVANZADA DE TÍTULOS + FORZADO DE CATEGORÍA

CAMBIOS v8.6 (fixes):
- FIX CRÍTICO: procesar_revolico() ahora lee precio_usd directamente del JSON
  cuando el scraper ya lo calculó (campo "precio_usd"), evitando que todos los
  anuncios sean descartados por precio nulo.
- FIX: precio_texto lee "precio_texto" además de "precio_raw" / "precio".
- FIX: num_imagenes lee "num_imagenes" del JSON además de contar lista "imagenes".
- FIX: imagen_principal lee "imagen_principal" del JSON además de "imagenes[0]".
- FIX PROVINCIAS: PROVINCIAS_NORM ampliado con todas las variantes con/sin tilde,
  abreviaturas coloquiales y municipios que Revolico usa como provincia.
- FIX: detectar_provincia() ahora intenta coincidencia parcial (subcadena) como
  último recurso antes de devolver None, para cubrir valores como
  "Pinar del Río (ciudad)" o "La Habana - Playa".
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
# PRECIO MÍNIMO POR CATEGORÍA (USD)
# ─────────────────────────────────────────
PRECIO_MINIMO = {
    "laptop":      100,
    "pc":          100,
    "monitor":     40,
    "gpu":         50,
    "cpu":         30,
    "motherboard": 30,
    "disco":       15,
    "ram":         10,
    "periferico":  5,
    "accesorio":   2,
    "modem":       10,
    "impresora":   30,
    "chasis":      15,
    "ups":         15,
    "dvd":         10,
    "cd":          1,
    "internet":    2,
    "sonido":      10,
    "otros":       5,
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
    "periferico":  500,
    "accesorio":   300,
    "modem":       500,
    "impresora":   1000,
    "chasis":      500,
    "ups":         500,
    "dvd":         100,
    "cd":          50,
    "internet":    100,
    "sonido":      300,
    "otros":       5000,
}

# ─────────────────────────────────────────
# PALABRAS QUE INDICAN "BUSCA COMPRAR"
# ─────────────────────────────────────────
BUSCA_COMPRAR = [
    "desea vender", "quieres vender", "compro ", "compra ",
    "busco ", "busco laptop", "busco pc", "se compra",
    "pago bien", "interesado en comprar", "necesito comprar",
    "quien vende", "alguien vende", "tiene en venta",
    "busco urgente", "busca laptop", "busca pc", "buscando",
    "necesito ", "requiero", "estoy interesado",
]

# ─────────────────────────────────────────
# PALABRAS QUE INDICAN TALLER/SERVICIO
# ─────────────────────────────────────────
ES_SERVICIO = [
    "taller", "reparacion", "reparación", "servicio técnico",
    "servicio tecnico", "agenda su cita", "repara tu",
    "mantenimiento", "formateo", "instalacion de windows",
    "instalación de windows", "reparo", "arreglo",
    "diagnostico", "diagnóstico", "servicio a domicilio",
    "reparacion de", "reparación de",
]

# ─────────────────────────────────────────
# PREFIJOS A LIMPIAR DEL TÍTULO (versión extendida)
# ─────────────────────────────────────────
PREFIJOS_BASURA = [
    r'^vendo\s+', r'^se vende\s+', r'^venta\s+de\s+',
    r'^venta\s+', r'^oferta\s+', r'^ganga\s*[!.]*\s*',
    r'^nuevo\s+', r'^nueva\s+', r'^disponible\s+',
    r'^tengo\s+', r'^liquido\s+',
    r'^super\s+ganga\s*[!.]*\s*', r'^precio\s+',
    r'^urgente\s+', r'^oportunidad\s+',
    r'[!❗❌✅⚠️💥🔥]+\s*',
    # Nuevos patrones para ruido común
    r'^cañón[\s_]+', r'^cañon[\s_]+', r'^nos fuimos[\s_]+', r'^gaming[\s_]+',
    r'^chasis[\s_]+', r'^fuente[\s_]+', r'^memoria[\s_]+', r'^procesador[\s_]+',
    r'^tarjeta[\s_]+', r'^laptop[\s_]+', r'^pc[\s_]+', r'^monitor[\s_]+',
    r'^cargador[\s_]+', r'^bateria[\s_]+', r'^accesorio[\s_]+',
    r'^venta[\s_]+', r'^oferta[\s_]+', r'^nuevo[\s_]+', r'^original[\s_]+',
    r'^[A-ZÁÉÍÓÚÑ]{2,}[\s_]+',  # Palabras en mayúsculas seguidas de espacio (ej: "CAÑÓN ")
]

# ─────────────────────────────────────────
# FIX: palabras que identifican TV/televisor
# ─────────────────────────────────────────
PALABRAS_TV = [
    "televisor", "smart tv", "tv led", "tv 4k", "tv uhd",
    "tv smart", "led tv", "lcd tv", "oled tv", "qled",
    "lg tv", "samsung tv", "sony tv", "tcl tv", "hisense",
    "tv 32", "tv 43", "tv 50", "tv 55", "tv 65", "tv 75",
    "pulgadas smart", "uhd 4k tv",
]

# ─────────────────────────────────────────
# FIX: palabras que identifican impresoras
# ─────────────────────────────────────────
PALABRAS_IMPRESORA = [
    "impresora", "multifuncional", "laserjet", "inkjet",
    "tóner", "toner", "tinta continua", "cartucho",
    "epson", "hp laserjet", "canon pixma", "brother",
    "et-2800", "et-2803", "et-4850", "3 en 1", "3en1",
    "imprime", "escanea", "fotocopiadora",
]

# ─────────────────────────────────────────
# FORZAR CATEGORÍA POR PALABRAS CLAVE (título limpio)
# ─────────────────────────────────────────
FORZAR_CATEGORIA = {
    "fuente": "chasis",
    "gabinete": "chasis",
    "chasis": "chasis",
    "psu": "chasis",
    "ups": "ups",
    "nobreak": "ups",
    "regulador": "ups",
    "procesador": "cpu",
    "cpu": "cpu",
    "motherboard": "motherboard",
    "placa madre": "motherboard",
    "tarjeta de video": "gpu",
    "gtx": "gpu",
    "rtx": "gpu",
    "disco duro": "disco",
    "ssd": "disco",
    "memoria ram": "ram",
    "ram ddr": "ram",
    "monitor": "monitor",
    "laptop": "laptop",
    "impresora": "impresora",
}

# ─────────────────────────────────────────
# REGLAS DE CATEGORÍA V8.6 (misma jerarquía que antes)
# ─────────────────────────────────────────
EQUIPOS_COMPLETOS = ["pc", "laptop"]

REGLAS_CATEGORIA = [
    # ========== 1. PC COMPLETAS ==========
    ("pc", {
        "palabras_clave": [
            "pc gamer", "pc gaming", "pc de escritorio", "computadora de mesa",
            "desktop", "torre completa", "pc armada", "cpu completo",
            "aio", "equipo completo", "pc lista",
            "torre lista", "pc para usar", "mini pc", "optiplex",
            "nuc", "intel nuc", "pc mini", "computadora completa",
            "en pc", "vendo pc", "pc y laptop", "pc y laptops",
            "laptops y pc", "pcs y laptops",
        ],
        "excluir": [
            "notebook", "monitor", "solo", "disco solo",
            "ram solo", "procesador solo", "tarjeta video solo",
            "sin", "falta",
            "televisor", "smart tv", "tv led", "tv 4k", "tv uhd",
            "impresora", "multifuncional", "tinta", "toner", "tóner",
            "epson", "laserjet", "inkjet", "et-2800", "et-2803",
        ],
        "es_equipo_completo": True,
    }),
    # ========== 2. LAPTOPS ==========
    ("laptop", {
        "palabras_clave": [
            "laptop", "notebook", "macbook", "thinkpad", "ideapad",
            "vivobook", "ultrabook", "chromebook", "portatil", "portátil",
            "hp envy", "dell inspiron", "lenovo legion",
            "2 en 1",
            "horas bateria", "horas batería", "horas de bateria", "horas de batería",
            "autonomia bateria", "autonomía batería",
        ],
        "excluir": [
            "funda", "cargador", "bateria laptop", "cooler", "base", "mouse",
            "teclado", "monitor", "torre", "gabinete", "disco externo",
            "memoria usb", "pendrive",
            "televisor", "smart tv", "tv led", "tv 4k", "tv uhd",
            "impresora",
            "compatible con", "para laptop", "para pc", "microfono",
            "micrófono", "bocina", "parlante", "auricular",
            "rtx", "gtx", "tarjeta de video", "tarjeta grafica", "tarjeta gráfica",
        ],
        "es_equipo_completo": True,
    }),
    # ========== 3. MONITORES ==========
    ("monitor", {
        "palabras_clave": [
            "monitor", "pantalla", "display", "144hz", "165hz", "240hz",
            "monitor gamer", "monitor gaming", "monitor samsung",
            "monitor lg", "monitor dell", "monitor hp",
            "smart tv", "televisor", "tv", "led tv", "lcd tv",
            "lg tv", "samsung tv", "sony tv", "tcl", "hisense",
            "curvo", "4k monitor", "monitor 4k",
        ],
        "excluir": [
            "laptop", "pc", "computadora", "torre", "gabinete",
            "placa madre", "motherboard", "procesador", "cpu",
            "memoria ram", "disco duro", "ssd", "tarjeta video",
            "gpu", "teclado", "mouse", "impresora", "router",
            "playstation", "ps4", "ps5", "xbox", "nintendo",
            "chasis", "fuente", "case",
            "soporte monitor", "soporte para monitor", "brazo monitor",
            "bracket monitor", "vesa",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 4. IMPRESORAS ==========
    ("impresora", {
        "palabras_clave": [
            "impresora", "multifuncional", "laserjet", "inkjet", "plotter",
            "tóner", "toner", "cartucho", "tinta continua",
            "epson", "canon", "brother", "hp laserjet",
            "impresora epson", "impresora hp", "impresora canon",
            "et-2800", "et-2803", "et-4850", "tinta original",
            "cartucho tinta", "3 en 1", "3en1", "all in one impresora",
        ],
        "excluir": [
            "laptop", "pc", "monitor", "disco", "ssd", "ram",
            "procesador", "mouse", "teclado", "parlante", "bocina",
            "televisor", "smart tv",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 5. TARJETAS DE VIDEO (GPU) ==========
    ("gpu", {
        "palabras_clave": [
            "tarjeta de video", "tarjeta grafica", "tarjeta gráfica",
            "gtx", "rtx", "radeon", "nvidia", "amd radeon",
            "video card", "gpu", "geforce",
        ],
        "excluir": [
            "laptop", "monitor", "pc completa", "torre completa",
            "impresora", "teclado", "mouse",
            "televisor", "smart tv",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 6. PROCESADORES (CPU) ==========
    ("cpu", {
        "palabras_clave": [
            "procesador", "microprocesador", "intel core",
            "amd ryzen", "ryzen 3", "ryzen 5", "ryzen 7", "ryzen 9",
            "cpu intel", "cpu amd",
            "ryzen3", "ryzen5", "ryzen7", "ryzen9",
            "3200g", "3400g", "4650g", "5600g", "5700g",
            "14th gen", "13th gen", "12th gen", "11th gen", "10th gen",
            "14600k", "13600k", "12600k", "13700k", "14700k",
            "14900k", "13900k", "12900k",
        ],
        "excluir": [
            "laptop", "monitor", "pc completa", "torre", "tarjeta",
            "disco", "ram", "mouse", "teclado", "impresora",
            "laptop completa", "pc armada", "kit board",
            "televisor", "smart tv", "tv led", "tv 4k",
            "router", "modem", "wifi",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 7. MOTHERBOARDS ==========
    ("motherboard", {
        "palabras_clave": [
            "motherboard", "placa madre", "placa base", "mainboard",
            "tarjeta madre", "socket", "b450", "b550", "b650",
            "z690", "z790", "h610", "x570", "a320",
            "kit board", "board y micro", "kit de board",
            "a520", "a520m", "b560", "h610m", "b760",
            "pro de msi", "msi pro", "asus prime", "gigabyte b",
            "asrock b", "asrock h",
        ],
        "excluir": [
            "laptop", "monitor", "pc completa", "mouse", "teclado", "impresora",
            "televisor", "smart tv",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 8. MEMORIAS RAM ==========
    ("ram", {
        "palabras_clave": [
            "memoria ram", "ram ddr", "ddr3", "ddr4", "ddr5",
            "sodimm", "dimm", "ram 8gb", "ram 16gb", "ram 32gb",
        ],
        "excluir": [
            "usb", "pendrive", "flash", "micro sd", "tarjeta memoria",
            "laptop completa", "pc completa", "disco", "ssd",
            "memoria usb", "memoria flash", "kit mouse", "kit teclado",
            "televisor", "smart tv",
            "dell inspiron", "hp envy", "lenovo", "thinkpad", "macbook",
            "ideapad", "vivobook", "notebook",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 9. DISCOS DUROS / SSD ==========
    ("disco", {
        "palabras_clave": [
            "disco duro", "disco ssd", "hdd", "nvme",
            "m.2", "m2", "disco solido", "disco mecanico",
            "disco externo", "seagate", "western digital",
            "toshiba", "adata", "transcend", "disco portatil",
        ],
        "excluir": [
            "laptop", "notebook", "pc completa", "memoria usb", "pendrive",
            "teclado", "mouse", "impresora", "monitor", "ram",
            "televisor", "smart tv",
            "dell inspiron", "hp envy", "lenovo", "thinkpad", "macbook",
            "ideapad", "vivobook", "asus rog laptop",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 10. CHASIS Y FUENTES ==========
    ("chasis", {
        "palabras_clave": [
            "chasis", "gabinete", "case", "fuente de poder",
            "fuente corsair", "fuente evga", "psu", "fuente 500w",
            "fuente 600w", "fuente 750w", "fuente 850w",
            "fuente atx", "gabinete gamer", "full tower", "mid tower",
            "fuente certificada", "fuente 80 plus",
            "montech", "sama", "nzxt", "phanteks", "fractal",
            "deepcool", "cooler master case", "lian li", "tooq",
            "fanes rgb", "fanes argb", "fan rgb", "fan argb",
        ],
        "excluir": [
            "laptop", "pc completa", "teclado", "mouse",
            "impresora", "pantalla", "lcd", "ups", "nobreak",
            "bateria", "regulador", "led tv", "led monitor",
            "televisor", "smart tv",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 11. UPS Y BATERÍAS ==========
    ("ups", {
        "palabras_clave": [
            "ups", "nobreak", "no break", "regulador", "estabilizador",
            "backup", "bateria 12v", "bateria ups", "mini ups",
            "apc", "inversor", "estacion energia", "power station",
            "estación energía", "planta electrica", "generador",
        ],
        "excluir": [
            "laptop", "pc", "monitor", "bateria laptop", "fuente de poder",
            "psu", "fuente atx",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 12. ROUTERS Y REDES ==========
    ("modem", {
        "palabras_clave": [
            "router", "mikrotik", "tp-link", "tplink", "switch",
            "access point", "repetidor", "antena wifi", "modem",
            "nauta", "etecsa", "tarjeta de red", "wifi pci",
            "extensor wifi", "mesh",
            "dlink", "d-link", "d link", "asus router", "netgear",
            "ubiquiti", "unifi", "ac750", "ac1200", "ac1750",
            "ac3000", "ax3000", "ax6000", "wifi 6", "wifi6",
            "tri-banda", "tribanda", "dual banda", "dualbanda",
        ],
        "excluir": [
            "laptop", "pc", "monitor", "impresora",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 13. BOCINAS Y SONIDO ==========
    ("sonido", {
        "palabras_clave": [
            "bocina", "parlante", "speaker", "subwoofer",
            "soundbar", "barra sonido", "bafle", "amplificador",
            "jbl", "home theater", "2.1", "5.1", "7.1",
            "bocina bluetooth", "parlante bluetooth",
            "zizo", "anker soundcore", "marshall", "bose", "harman",
            "microfono", "micrófono", "brazo microfono", "brazo micrófono",
            "brazo ajustable", "arm microfono", "pop filter",
            "interfaz de audio", "interfaz audio", "mezclador",
            "mixer audio", "audio interface",
        ],
        "excluir": [
            "monitor", "teclado", "mouse",
            "audifono", "audífonos", "auricular", "auriculares",
            "headset", "diadema", "in-ear", "over-ear",
            "microfono usb", "micrófono usb",
            "microfono gaming", "micrófono gaming",
            "fifine", "blue yeti", "hyperx",
            "pc gamer", "pc gaming", "laptop vendo", "vendo laptop",
            "notebook vendo", "vendo notebook",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 14. PERIFÉRICOS ==========
    ("periferico", {
        "palabras_clave": [
            "teclado", "mouse", "raton", "webcam", "camara web",
            "auriculares", "audifonos", "audífonos", "headset", "diadema",
            "in-ear", "over-ear", "earbuds", "tws",
            "joystick", "gamepad", "control xbox", "control ps4",
            "g502", "logitech", "razer", "corsair", "redragon",
            "teclado mecanico", "teclado gaming", "mouse gaming",
            "mouse gamer", "kit mouse", "kit teclado",
            "mouse y teclado", "teclado y mouse", "combo teclado",
            "microfono usb", "micrófono usb", "microfono condensador",
            "micrófono condensador", "microfono gaming", "micrófono gaming",
            "fifine", "blue yeti", "hyperx quadcast",
            "jbl live", "jbl tune", "jbl free", "jbl reflect", "jbl endurance",
            "sony wh", "sony wf", "sony xm", "bose quietcomfort", "jabra",
            "sennheiser", "anker soundcore auricular", "beats",
        ],
        "excluir": [
            "monitor", "impresora", "disco",
            "ram", "procesador", "placa", "motherboard",
            "bocina", "parlante", "speaker", "subwoofer", "soundbar",
            "micrófono incluido", "microfono incluido",
            "micrófono integrado", "microfono integrado",
            "pc gamer", "pc gaming", "laptop vendo", "vendo laptop",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 15. ACCESORIOS ==========
    ("accesorio", {
        "palabras_clave": [
            "cable", "adaptador", "conversor", "hub", "dock",
            "cooler", "ventilador", "disipador",
            "base laptop", "cargador", "bateria", "power bank",
            "mouse pad", "alfombrilla", "pendrive", "memoria usb",
            "usb", "micro sd", "tarjeta memoria", "capturadora",
            "usb 3.0", "usb tipo c",
            "soporte monitor", "soporte para monitor",
            "soporte laptop", "soporte para laptop",
            "soporte escritorio", "brazo monitor",
            "bracket monitor", "vesa",
        ],
        "excluir": [
            "impresora", "disco duro",
            "memoria ram", "procesador", "teclado", "mouse",
            "ssd", "hdd", "nvme", "fuente de poder",
            "pc gamer", "laptop vendo",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 16. CD / DVD VIRGEN ==========
    ("cd", {
        "palabras_clave": [
            "cd virgen", "dvd virgen", "cd-r", "dvd-r",
            "bluray virgen", "disco virgen", "cd virgenes",
        ],
        "excluir": [
            "quemador", "lector", "unidad",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 17. LECTORES DVD ==========
    ("dvd", {
        "palabras_clave": [
            "quemador dvd", "lector dvd", "unidad dvd",
            "bluray", "dvd externo", "unidad optica",
        ],
        "excluir": [
            "virgen", "cd-r", "dvd-r",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 18. INTERNET Y NAUTA ==========
    ("internet", {
        "palabras_clave": [
            "nauta", "cuenta nauta", "recarga", "chip nauta",
            "internet movil", "datos moviles", "saldo nauta",
        ],
        "excluir": [
            "router", "modem",
        ],
        "es_equipo_completo": False,
    }),
    # ========== 19. OTROS ==========
    ("otros", {
        "palabras_clave": [],
        "excluir": [],
        "es_equipo_completo": False,
    }),
]

# ─────────────────────────────────────────
# PROVINCIAS — v8.6: cobertura total
# Se incluyen: nombre oficial, sin tilde, abreviaturas coloquiales,
# municipios que Revolico pone en el campo provincia, y variantes mixtas.
# ─────────────────────────────────────────
PROVINCIAS_NORM = {
    # ── La Habana ──────────────────────────────────────────────────────────
    "habana":              "La Habana",
    "la habana":           "La Habana",
    "ciudad habana":       "La Habana",
    "ciudad de la habana": "La Habana",
    "centro habana":       "La Habana",
    "habana vieja":        "La Habana",
    "miramar":             "La Habana",
    "vedado":              "La Habana",
    "playa":               "La Habana",
    "marianao":            "La Habana",
    "boyeros":             "La Habana",
    "arroyo naranjo":      "La Habana",
    "cotorro":             "La Habana",
    "san miguel del padron": "La Habana",
    "san miguel del padrón": "La Habana",
    "diez de octubre":     "La Habana",
    "10 de octubre":       "La Habana",
    "cerro":               "La Habana",
    "regla":               "La Habana",
    "guanabacoa":          "La Habana",
    "la lisa":             "La Habana",
    "plaza":               "La Habana",
    "plaza de la revolución": "La Habana",
    "plaza de la revolucion": "La Habana",

    # ── Artemisa ──────────────────────────────────────────────────────────
    "artemisa":            "Artemisa",
    "san antonio de los baños": "Artemisa",
    "san antonio de los banos": "Artemisa",
    "bauta":               "Artemisa",
    "güira de melena":     "Artemisa",
    "guira de melena":     "Artemisa",
    "alquizar":            "Artemisa",
    "alquízar":            "Artemisa",
    "caimito":             "Artemisa",
    "mariel":              "Artemisa",
    "guanajay":            "Artemisa",

    # ── Mayabeque ─────────────────────────────────────────────────────────
    "mayabeque":           "Mayabeque",
    "san jose de las lajas": "Mayabeque",
    "san josé de las lajas": "Mayabeque",
    "jaruco":              "Mayabeque",
    "santa cruz del norte": "Mayabeque",
    "madruga":             "Mayabeque",
    "bejucal":             "Mayabeque",
    "nueva paz":           "Mayabeque",
    "guines":              "Mayabeque",
    "güines":              "Mayabeque",
    "melena del sur":      "Mayabeque",

    # ── Pinar del Río ─────────────────────────────────────────────────────
    "pinar del rio":       "Pinar del Río",
    "pinar del río":       "Pinar del Río",
    "pinar":               "Pinar del Río",
    "vinales":             "Pinar del Río",
    "viñales":             "Pinar del Río",
    "consolacion del sur": "Pinar del Río",
    "consolación del sur": "Pinar del Río",
    "san cristobal":       "Pinar del Río",
    "san cristóbal":       "Pinar del Río",
    "los palacios":        "Pinar del Río",
    "la palma":            "Pinar del Río",
    "bahia honda":         "Pinar del Río",
    "bahía honda":         "Pinar del Río",
    "minas de matahambre": "Pinar del Río",

    # ── Matanzas ──────────────────────────────────────────────────────────
    "matanzas":            "Matanzas",
    "varadero":            "Matanzas",
    "cardenas":            "Matanzas",
    "cárdenas":            "Matanzas",
    "colon":               "Matanzas",
    "colón":               "Matanzas",
    "jovellanos":          "Matanzas",
    "perico":              "Matanzas",
    "limonar":             "Matanzas",
    "union de reyes":      "Matanzas",
    "unión de reyes":      "Matanzas",

    # ── Cienfuegos ────────────────────────────────────────────────────────
    "cienfuegos":          "Cienfuegos",
    "palmira":             "Cienfuegos",
    "rodas":               "Cienfuegos",
    "cruces":              "Cienfuegos",
    "lajas":               "Cienfuegos",
    "cumanayagua":         "Cienfuegos",

    # ── Villa Clara ───────────────────────────────────────────────────────
    "villa clara":         "Villa Clara",
    "santa clara":         "Villa Clara",
    "caibarien":           "Villa Clara",
    "caibarién":           "Villa Clara",
    "sagua la grande":     "Villa Clara",
    "remedios":            "Villa Clara",
    "placetas":            "Villa Clara",
    "camajuani":           "Villa Clara",
    "camajuaní":           "Villa Clara",
    "ranchuelo":           "Villa Clara",
    "manicaragua":         "Villa Clara",
    "cifuentes":           "Villa Clara",

    # ── Sancti Spíritus ───────────────────────────────────────────────────
    "sancti spiritus":     "Sancti Spíritus",
    "sancti spíritus":     "Sancti Spíritus",
    "spiritus":            "Sancti Spíritus",
    "spíritus":            "Sancti Spíritus",
    "trinidad":            "Sancti Spíritus",
    "yaguajay":            "Sancti Spíritus",
    "jatibonico":          "Sancti Spíritus",
    "cabaiguan":           "Sancti Spíritus",
    "cabaiguán":           "Sancti Spíritus",
    "fomento":             "Sancti Spíritus",
    "la sierpe":           "Sancti Spíritus",
    "taguasco":            "Sancti Spíritus",

    # ── Ciego de Ávila ────────────────────────────────────────────────────
    "ciego de avila":      "Ciego de Ávila",
    "ciego de ávila":      "Ciego de Ávila",
    "ciego":               "Ciego de Ávila",
    "moron":               "Ciego de Ávila",
    "morón":               "Ciego de Ávila",
    "chambas":             "Ciego de Ávila",
    "florencia":           "Ciego de Ávila",
    "venezuela":           "Ciego de Ávila",
    "baraguá":             "Ciego de Ávila",
    "balagua":             "Ciego de Ávila",
    "primero de enero":    "Ciego de Ávila",

    # ── Camagüey ──────────────────────────────────────────────────────────
    "camaguey":            "Camagüey",
    "camagüey":            "Camagüey",
    "nuevitas":            "Camagüey",
    "guaimaro":            "Camagüey",
    "guáimaro":            "Camagüey",
    "esmeralda":           "Camagüey",
    "florida":             "Camagüey",
    "minas":               "Camagüey",
    "vertientes":          "Camagüey",
    "jimaguayu":           "Camagüey",

    # ── Las Tunas ─────────────────────────────────────────────────────────
    "las tunas":           "Las Tunas",
    "tunas":               "Las Tunas",
    "victoria de las tunas": "Las Tunas",
    "puerto padre":        "Las Tunas",
    "jobabo":              "Las Tunas",
    "amancio":             "Las Tunas",
    "colombia":            "Las Tunas",
    "manatí":              "Las Tunas",
    "manati":              "Las Tunas",

    # ── Holguín ───────────────────────────────────────────────────────────
    "holguin":             "Holguín",
    "holguín":             "Holguín",
    "banes":               "Holguín",
    "bayan":               "Holguín",
    "gibara":              "Holguín",
    "moa":                 "Holguín",
    "mayari":              "Holguín",
    "mayarí":              "Holguín",
    "niquero":             "Holguín",
    "sagua de tanamo":     "Holguín",
    "sagua de tánamo":     "Holguín",
    "cueto":               "Holguín",
    "cacocum":             "Holguín",
    "urbano noris":        "Holguín",
    "antilla":             "Holguín",

    # ── Granma ────────────────────────────────────────────────────────────
    "granma":              "Granma",
    "bayamo":              "Granma",
    "manzanillo":          "Granma",
    "media luna":          "Granma",
    "niquero":             "Granma",
    "campechuela":         "Granma",
    "yara":                "Granma",
    "jiguani":             "Granma",
    "jiguaní":             "Granma",
    "buey arriba":         "Granma",
    "bartolome maso":      "Granma",
    "bartolomé masó":      "Granma",
    "guisa":               "Granma",
    "rio cauto":           "Granma",
    "río cauto":           "Granma",
    "cauto cristo":        "Granma",

    # ── Santiago de Cuba ─────────────────────────────────────────────────
    "santiago de cuba":    "Santiago de Cuba",
    "santiago":            "Santiago de Cuba",
    "palma soriano":       "Santiago de Cuba",
    "contramaestre":       "Santiago de Cuba",
    "mella":               "Santiago de Cuba",
    "san luis":            "Santiago de Cuba",
    "songo la maya":       "Santiago de Cuba",
    "songo-la maya":       "Santiago de Cuba",
    "segundo frente":      "Santiago de Cuba",
    "guama":               "Santiago de Cuba",
    "tercer frente":       "Santiago de Cuba",

    # ── Guantánamo ────────────────────────────────────────────────────────
    "guantanamo":          "Guantánamo",
    "guantánamo":          "Guantánamo",
    "baracoa":             "Guantánamo",
    "yateras":             "Guantánamo",
    "maisi":               "Guantánamo",
    "maisí":               "Guantánamo",
    "niceto perez":        "Guantánamo",
    "el salvador":         "Guantánamo",
    "imias":               "Guantánamo",
    "imías":               "Guantánamo",
    "san antonio del sur": "Guantánamo",
    "caimanera":           "Guantánamo",

    # ── Isla de la Juventud ───────────────────────────────────────────────
    "isla de la juventud": "Isla de la Juventud",
    "isla juventud":       "Isla de la Juventud",
    "isla de la juventud": "Isla de la Juventud",
    "la isla":             "Isla de la Juventud",
    "nueva gerona":        "Isla de la Juventud",
    "isla":                "Isla de la Juventud",
}


# ─────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────

def limpiar_texto(texto: str) -> str:
    """Elimina emojis y caracteres raros"""
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
    """Limpia título eliminando ruido al inicio y final"""
    if not titulo:
        return ""
    for patron in PREFIJOS_BASURA:
        titulo = re.sub(patron, '', titulo, flags=re.IGNORECASE).strip()
    titulo = re.sub(r'\s*[-–]\s*Img\s+\d+$', '', titulo, flags=re.IGNORECASE).strip()
    titulo = re.sub(r'\s+\d{7,8}$', '', titulo).strip()
    palabras = titulo.split()
    if len(palabras) > 1 and palabras[0].lower() == palabras[1].lower():
        titulo = ' '.join(palabras[1:])
    return titulo


def limpiar_telefono(tel: str) -> str | None:
    """Normaliza teléfono a 8 dígitos cubanos"""
    if not tel:
        return None
    solo = re.sub(r'[^0-9]', '', str(tel))
    if solo.startswith("53") and len(solo) == 10:
        solo = solo[2:]
    if len(solo) in [7, 8]:
        return solo
    return None


def mejor_telefono(raw: dict, fuente: str) -> str | None:
    """Extrae el mejor teléfono según la fuente"""
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
    """Detecta moneda en el texto"""
    if not texto:
        return "USD"
    t = str(texto).lower()
    if any(x in t for x in ["cup", "peso", "pesos", " mn", "kuki"]):
        return "CUP"
    if "mlc" in t:
        return "MLC"
    return "USD"


def extraer_precio_usd(raw: dict, fuente: str, moneda: str) -> float | None:
    """
    Extrae precio y convierte a USD.
    v8.6: para Revolico, primero intenta leer precio_usd directo del JSON
    (el scraper ya lo calculó), luego precio_texto, precio_raw, precio.
    """
    if fuente == "facebook":
        precio = raw.get("precio")
        if precio:
            try:
                valor = float(precio)
                if valor > 1:
                    if moneda == "CUP":
                        return round(valor / TASA_CUP_USD, 2)
                    if moneda == "MLC":
                        return round(valor * TASA_MLC_USD, 2)
                    return valor
            except (ValueError, TypeError):
                pass
    else:
        # ── FIX v8.6: leer precio_usd ya calculado por el scraper ──────────
        precio_directo = raw.get("precio_usd")
        if precio_directo is not None:
            try:
                valor = float(precio_directo)
                if valor > 1:
                    # El scraper ya entrega USD; igual aplicamos conversión
                    # si la moneda detectada en precio_texto fuera CUP/MLC
                    # (situación rara, pero la cubrimos por seguridad)
                    if moneda == "CUP":
                        return round(valor / TASA_CUP_USD, 2)
                    if moneda == "MLC":
                        return round(valor * TASA_MLC_USD, 2)
                    return valor
            except (ValueError, TypeError):
                pass

        # ── Fallback: parsear desde texto ───────────────────────────────────
        precio_str = (
            raw.get("precio_raw") or
            raw.get("precio_texto") or   # FIX v8.6: añadido precio_texto
            raw.get("precio") or
            ""
        )
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


def _es_tv(texto: str) -> bool:
    return any(p in texto for p in PALABRAS_TV)


def _es_impresora(texto: str) -> bool:
    return any(p in texto for p in PALABRAS_IMPRESORA)


def detectar_categoria_estricta(titulo: str, descripcion: str = "") -> tuple:
    """
    Detecta categoría con jerarquía estricta v8.6.
    Incluye forzado por palabras clave en título limpio.
    """
    texto = (titulo + " " + descripcion).lower()
    titulo_limpio = limpiar_titulo_avanzado(titulo).lower()

    # ── PASO 0: Forzar categoría por palabras clave en título limpio ──
    for palabra, cat in FORZAR_CATEGORIA.items():
        if palabra in titulo_limpio:
            return cat, True

    # ── PASO 0: Televisores ──────────────────────────────────────
    if _es_tv(texto):
        return "monitor", True

    # ── PASO 0b: Impresoras ───────────────────────────────────────────
    if _es_impresora(texto):
        es_pc_aio = any(k in texto for k in ["aio pc", "all in one pc", "pc all in one",
                                              "computadora all in one", "desktop all in one"])
        if not es_pc_aio:
            return "impresora", True

    # ── PASO 1: Equipos completos (PC, Laptop) ────────────────────────────
    for categoria, reglas in REGLAS_CATEGORIA:
        if not reglas.get("es_equipo_completo", False):
            continue

        palabras_a_buscar = list(reglas["palabras_clave"])
        if categoria == "pc":
            palabras_a_buscar.append("all in one")

        for palabra in palabras_a_buscar:
            if palabra in texto:
                tiene_excluida = any(excluir in texto for excluir in reglas["excluir"])
                if not tiene_excluida:
                    return categoria, True

    # ── PASO 2: Kits especiales ───────────────────────────────────────────
    if "kit board" in texto or "kit de board" in texto or "board y micro" in texto:
        return "motherboard", True

    _apu_keywords = ["3200g", "3400g", "4650g", "5600g", "5700g", "ryzen3", "ryzen5", "ryzen7"]
    _board_keywords = ["a520", "b450", "b550", "b650", "a320", "h610", "h510", "b560", "b760",
                       "pro de msi", "asus prime", "asrock"]
    _tiene_apu = any(k in texto for k in _apu_keywords)
    _tiene_board = any(k in texto for k in _board_keywords)
    if _tiene_apu and _tiene_board:
        return "motherboard", True

    _intel_gen_kw = ["14th gen", "13th gen", "12th gen", "11th gen", "10th gen",
                     "14600k", "13600k", "12600k", "13700k", "14700k", "14900k", "13900k"]
    if any(k in texto for k in _intel_gen_kw):
        return "cpu", True

    if ("kit mouse" in texto or "kit teclado" in texto or
            "mouse y teclado" in texto or "teclado y mouse" in texto):
        return "periferico", True

    # ── PASO 3: Monitores ─────────────────────────────────────────────────
    _tiene_chasis_combo = any(k in texto for k in ["chasis", "gabinete", "torre", "case gamer",
                                                    "mid tower", "full tower"])
    for categoria, reglas in REGLAS_CATEGORIA:
        if categoria != "monitor":
            continue
        for palabra in reglas["palabras_clave"]:
            if palabra in texto:
                if _tiene_chasis_combo and palabra in ["monitor", "pulgadas", "display", "pantalla"]:
                    continue
                tiene_excluida = any(excluir in texto for excluir in reglas["excluir"])
                if not tiene_excluida:
                    return categoria, True

    # ── PASO 4: Impresoras (segunda oportunidad) ──────────────────────────
    for categoria, reglas in REGLAS_CATEGORIA:
        if categoria != "impresora":
            continue
        for palabra in reglas["palabras_clave"]:
            if palabra in texto:
                tiene_excluida = any(excluir in texto for excluir in reglas["excluir"])
                if not tiene_excluida:
                    return categoria, True

    # ── PASO 5: CPU — manejo especial para i3/i5/i7/i9 ───────────────────
    MODELOS_CPU_CORTOS = ["i3", "i5", "i7", "i9"]
    cpu_reglas = next((r for c, r in REGLAS_CATEGORIA if c == "cpu"), None)
    if cpu_reglas:
        tiene_excluida_cpu = any(excluir in texto for excluir in cpu_reglas["excluir"])
        if not tiene_excluida_cpu:
            for palabra in cpu_reglas["palabras_clave"]:
                if palabra in texto:
                    return "cpu", True
            contexto_cpu = any(c in texto for c in [
                "procesador", "socket", "ghz", "núcleo", "nucleo", "core",
                "intel", "amd", "generacion", "generación", "lga", "am4", "am5",
            ])
            if contexto_cpu:
                for modelo in MODELOS_CPU_CORTOS:
                    patron = r'\b' + re.escape(modelo) + r'\b'
                    if re.search(patron, texto):
                        return "cpu", True

    # ── PASO 6: Resto de categorías (en orden) ────────────────────────────
    CATEGORIAS_RESTANTES_SKIP = {"pc", "laptop", "monitor", "impresora", "cpu", "otros"}

    for categoria, reglas in REGLAS_CATEGORIA:
        if categoria in CATEGORIAS_RESTANTES_SKIP:
            continue
        if reglas.get("es_equipo_completo", False):
            continue

        palabras_clave = reglas["palabras_clave"]
        palabras_excluir = reglas["excluir"]

        if not palabras_clave:
            continue

        tiene_clave = False
        for palabra in palabras_clave:
            if " " in palabra:
                if palabra in texto:
                    tiene_clave = True
                    break
            else:
                patron = r'\b' + re.escape(palabra) + r'\b'
                if re.search(patron, texto):
                    tiene_clave = True
                    break

        if tiene_clave:
            tiene_excluida = any(excluir in texto for excluir in palabras_excluir)
            if not tiene_excluida:
                return categoria, True

    # ── PASO 7: Sin categoría detectada ──────────────────────────────────
    return "otros", False


def precio_valido(precio: float, categoria: str) -> bool:
    if not precio or precio < PRECIO_MINIMO.get(categoria, 5):
        return False
    if precio > PRECIO_MAXIMO.get(categoria, 5000):
        return False
    return True


def es_busca_comprar(texto: str) -> bool:
    t = texto.lower()
    return any(frase in t for frase in BUSCA_COMPRAR)


def es_servicio_taller(texto: str) -> bool:
    t = texto.lower()
    return any(frase in t for frase in ES_SERVICIO)


def detectar_provincia(raw: dict, fuente: str, grupo_provincia: str = None) -> str | None:
    """
    Detecta y normaliza provincia.
    v8.6: tres niveles de búsqueda:
      1. grupo_provincia (Facebook groups con provincia fija)
      2. campo "provincia" del raw — búsqueda exacta en PROVINCIAS_NORM
      3. campo "provincia" del raw — búsqueda parcial (subcadena) como fallback
      4. texto libre (descripcion + titulo) — búsqueda por subcadena
    """
    # ── Nivel 1: provincia del grupo (Facebook) ───────────────────────────
    if grupo_provincia:
        clave = grupo_provincia.strip().lower()
        norm = PROVINCIAS_NORM.get(clave)
        if norm:
            return norm
        # Fallback parcial para grupo_provincia
        for k, v in PROVINCIAS_NORM.items():
            if k in clave or clave in k:
                return v
        return grupo_provincia  # devolver tal cual si no se reconoce

    # ── Nivel 2: campo "provincia" — búsqueda exacta ──────────────────────
    prov_raw = (raw.get("provincia") or "").strip()
    if prov_raw:
        clave = prov_raw.lower()
        norm = PROVINCIAS_NORM.get(clave)
        if norm:
            return norm

        # ── Nivel 3: búsqueda parcial sobre el campo provincia ────────────
        # Cubre casos como "Pinar del Río (ciudad)", "La Habana - Vedado", etc.
        for k, v in PROVINCIAS_NORM.items():
            if k in clave:
                return v

    # ── Nivel 4: búsqueda en texto libre ─────────────────────────────────
    texto = (
        (raw.get("contenido") or "") + " " +
        (raw.get("descripcion_completa") or "") + " " +
        (raw.get("titulo") or "")
    ).lower()

    if texto.strip():
        for clave, nombre in PROVINCIAS_NORM.items():
            if clave in texto:
                return nombre

    return None


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
    for patron in PREFIJOS_BASURA:
        titulo = re.sub(patron, '', titulo, flags=re.IGNORECASE).strip()
    titulo = titulo.strip(" .-,!?")
    if len(titulo) > 100:
        titulo = titulo[:100].rsplit(' ', 1)[0]
    return titulo


# ─────────────────────────────────────────
# PROCESAR ANUNCIOS
# ─────────────────────────────────────────

def procesar_revolico(raw: dict) -> dict | None:
    """
    Procesa un anuncio de Revolico.
    v8.6 fixes:
    - precio_usd leído directamente del JSON si el scraper ya lo calculó
    - precio_texto incluido en la cadena de lectura de precio
    - num_imagenes leído del campo homónimo además de contar lista "imagenes"
    - imagen_principal leída del campo homónimo además de imagenes[0]
    """
    titulo = limpiar_texto(raw.get("titulo") or "")
    if not titulo or len(titulo) < 3:
        return None

    descripcion = limpiar_texto(raw.get("descripcion_completa") or "")
    texto_completo = titulo + " " + descripcion

    if es_busca_comprar(texto_completo):
        return None
    if es_servicio_taller(texto_completo):
        return None

    telefono = mejor_telefono(raw, "revolico")
    if not telefono:
        return None

    # ── Precio ───────────────────────────────────────────────────────────
    # Moneda: leer de precio_texto o precio_raw (no de precio_usd que ya es float)
    precio_texto_raw = (
        raw.get("precio_texto") or
        raw.get("precio_raw") or
        raw.get("precio") or
        ""
    )
    moneda = detectar_moneda(precio_texto_raw)
    precio_usd = extraer_precio_usd(raw, "revolico", moneda)
    if not precio_usd:
        return None

    # ── Categoría ─────────────────────────────────────────────────────────
    categoria_original = raw.get("categoria") or "otros"
    categoria, recat = detectar_categoria_estricta(titulo, descripcion)

    if not precio_valido(precio_usd, categoria):
        return None

    # ── Provincia ─────────────────────────────────────────────────────────
    provincia = detectar_provincia(raw, "revolico")

    # ── WhatsApp desde texto ──────────────────────────────────────────────
    whatsapp = None
    wa_match = re.search(r'wa\.me/\+?53?(\d{7,8})', texto_completo)
    if wa_match:
        whatsapp = limpiar_telefono(wa_match.group(1))

    # ── Limpiar título ────────────────────────────────────────────────────
    titulo_limpio = titulo
    for patron in PREFIJOS_BASURA:
        titulo_limpio = re.sub(patron, '', titulo_limpio, flags=re.IGNORECASE).strip()
    if len(titulo_limpio) < 3:
        titulo_limpio = titulo
    titulo_limpio = limpiar_titulo_avanzado(titulo_limpio)

    url = re.split(r'\?', raw.get("url") or "")[0]

    # ── FIX v8.6: num_imagenes e imagen_principal ─────────────────────────
    # El scraper guarda num_imagenes como int e imagen_principal como str,
    # no como lista "imagenes". Leemos ambos formatos.
    imagenes_lista = raw.get("imagenes") or []
    num_imagenes = raw.get("num_imagenes") or len(imagenes_lista)
    imagen_principal = (
        raw.get("imagen_principal") or
        (imagenes_lista[0] if imagenes_lista else None)
    )

    return {
        "fuente":            "revolico",
        "url":               url,
        "titulo":            titulo_limpio[:100],
        "descripcion":       descripcion[:500] if descripcion else None,
        "categoria":         categoria,
        "categoria_original": categoria_original,
        "recategorizado":    int(recat),
        "precio_usd":        precio_usd,
        "moneda":            moneda,
        "precio_texto":      limpiar_texto(precio_texto_raw)[:50],
        "telefono":          telefono,
        "whatsapp":          whatsapp,
        "vendedor":          limpiar_texto(raw.get("vendedor") or "")[:50] or None,
        "provincia":         provincia,
        "municipio":         limpiar_texto(raw.get("municipio") or "")[:50] or None,
        "fecha":             (raw.get("fecha_exacta") or raw.get("scrapeado_en") or "")[:10] or None,
        "vistas":            raw.get("vistas"),
        "num_imagenes":      num_imagenes,
        "imagen_principal":  imagen_principal,
    }


def procesar_facebook(raw: dict) -> dict | None:
    """Procesa un post de Facebook con reglas estrictas"""
    contenido = raw.get("contenido") or ""
    if not contenido or len(contenido) < 10:
        return None

    if es_busca_comprar(contenido):
        return None
    if es_servicio_taller(contenido):
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

    tipo_original = raw.get("tipo_equipo") or "otros"
    categoria, recat = detectar_categoria_estricta(titulo, contenido)

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

    return {
        "fuente":            "facebook",
        "url":               raw.get("url") or "",
        "titulo":            titulo[:100],
        "descripcion":       limpiar_texto(contenido)[:500],
        "categoria":         categoria,
        "categoria_original": tipo_original,
        "recategorizado":    int(recat),
        "precio_usd":        precio_usd,
        "moneda":            "USD",
        "precio_texto":      f"{raw.get('precio')} {raw.get('moneda')}" if raw.get("precio") else "",
        "telefono":          telefono,
        "whatsapp":          whatsapp,
        "vendedor":          vendedor[:50] if vendedor else None,
        "provincia":         provincia,
        "municipio":         None,
        "fecha":             (raw.get("fecha_extraccion") or raw.get("fecha_post") or "")[:10] or None,
        "vistas":            None,
        "num_imagenes":      0,
        "imagen_principal":  None,
    }


# ─────────────────────────────────────────
# CARGAR DATOS
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

        except json.JSONDecodeError as e:
            print(f"  ❌ {arch.name}: Error JSON - {e}")
        except Exception as e:
            print(f"  ❌ {arch.name}: {e}")

    return todos


def cargar_facebook() -> list:
    archivos_grupos = list(RAW_FACEBOOK.glob("grupo_*.json"))
    archivos_viejos = list(RAW_FACEBOOK.glob("facebook_ofertas_*.json"))
    archivos_viejos += list(RAW_FACEBOOK.glob("ultimas_ofertas.json"))
    archivos = list(set(archivos_grupos + archivos_viejos))
    archivos = sorted(archivos)

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

        except json.JSONDecodeError as e:
            print(f"  ❌ {arch.name}: Error JSON - {e}")
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

    todos_ord = sorted(productos, key=lambda x: (x["categoria"], x["precio_usd"] or 99999))
    arch_maestro = CLEAN_DIR / "todos_los_productos.csv"
    cols_maestro = ["fuente", "categoria", "titulo", "precio_usd", "moneda",
                    "telefono", "whatsapp", "vendedor", "provincia", "url", "fecha"]
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
    print("  CUBA PRECIOS — LIMPIEZA ESTRICTA v8.6")
    print("  JERARQUÍA: TV → IMPRESORA → PC/LAPTOP → COMPONENTES")
    print("  + FIXES: precio_usd directo, provincias completas")
    print("=" * 60)
    print("\n  CORRECCIONES v8.6 APLICADAS:")
    print("  ✓ precio_usd leído directamente del JSON del scraper")
    print("  ✓ precio_texto incluido en cadena de lectura de precio")
    print("  ✓ num_imagenes e imagen_principal leídos del campo homónimo")
    print("  ✓ PROVINCIAS_NORM: cobertura total (>120 entradas)")
    print("  ✓ detectar_provincia(): 4 niveles (exacto, parcial, fallback texto)")
    print("  ✓ Televisor/Smart TV → MONITOR (filtro prioritario)")
    print("  ✓ Impresora 'all in one' → IMPRESORA (no PC)")
    print("  ✓ Router D-Link/AC3000/AX → MODEM")
    print("  ✓ Chasis gaming con RGB/LED → CHASIS")
    print("  ✓ i3/i5/i7 solo activan CPU con contexto técnico")
    print(f"\n  Tasa CUP: {TASA_CUP_USD} | MLC: {TASA_MLC_USD}")
    print("=" * 60)

    print(f"\n{'─' * 60}")
    print("  CARGANDO DATOS...")
    print(f"{'─' * 60}")

    revolico = cargar_revolico()
    facebook = cargar_facebook()

    todos_raw = revolico + facebook
    print(f"\n  Subtotal: {len(revolico)} Revolico + {len(facebook)} Facebook = {len(todos_raw)}")

    # Eliminar duplicados por URL
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
        print("\n  ❌ Sin datos para guardar")
        return

    print(f"\n{'─' * 60}")
    print("  GUARDANDO...")
    print(f"{'─' * 60}")

    guardar_sqlite(todos)
    guardar_csvs(todos)

    # Estadísticas
    por_cat   = defaultdict(int)
    por_prov  = defaultdict(int)
    por_fuent = defaultdict(int)
    recat_count = 0

    for p in todos:
        por_cat[p["categoria"]] += 1
        por_prov[p["provincia"] or "Sin provincia"] += 1
        por_fuent[p["fuente"]] += 1
        if p.get("recategorizado"):
            recat_count += 1

    con_tel  = sum(1 for p in todos if p["telefono"])
    con_prov = sum(1 for p in todos if p["provincia"])
    precios  = [p["precio_usd"] for p in todos if p["precio_usd"]]

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