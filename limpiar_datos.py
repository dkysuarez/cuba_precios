"""
Limpiador Unificado — CubaPrecios v8.4
PRIORIDAD DE EQUIPOS COMPLETOS

CORRECCIONES v8.4:
- TELEVISOR / SMART TV → siempre MONITOR (filtro temprano antes de todo)
- "all in one" en impresora NO activa PC (impresoras subieron al Paso 1)
- Router D-Link y variantes → MODEM (añadidos dlink, d-link, ac1200, ac3000, etc.)
- Chasis con fanes RGB/ARGB ya no se autoexcluye ("led" quitado de excluir de chasis)
- "televisor", "smart tv", "tv led", "tv 4k" añadidos a excluir de PC, laptop, cpu, disco, gpu, ram
- "impresora", "epson", "canon", "brother", "hp laserjet", "tinta" añadidos a excluir de PC
- "all in one" sólo activa PC si NO hay palabras de impresora en el texto
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
# PREFIJOS A LIMPIAR DEL TÍTULO
# ─────────────────────────────────────────
PREFIJOS_BASURA = [
    r'^vendo\s+', r'^se vende\s+', r'^venta\s+de\s+',
    r'^venta\s+', r'^oferta\s+', r'^ganga\s*[!.]*\s*',
    r'^nuevo\s+', r'^nueva\s+', r'^disponible\s+',
    r'^tengo\s+', r'^liquido\s+',
    r'^super\s+ganga\s*[!.]*\s*', r'^precio\s+',
    r'^urgente\s+', r'^oportunidad\s+',
    r'[!❗❌✅⚠️💥🔥]+\s*',
]

# ─────────────────────────────────────────
# FIX: palabras que identifican TV/televisor
# Se usan para filtro temprano (Paso 0)
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
# Se usan para proteger PC del "all in one"
# ─────────────────────────────────────────
PALABRAS_IMPRESORA = [
    "impresora", "multifuncional", "laserjet", "inkjet",
    "tóner", "toner", "tinta continua", "cartucho",
    "epson", "hp laserjet", "canon pixma", "brother",
    "et-2800", "et-2803", "et-4850", "3 en 1", "3en1",
    "imprime", "escanea", "fotocopiadora",
]

# ─────────────────────────────────────────
# REGLAS DE CATEGORÍA V8.4
# ORDEN JERÁRQUICO: TV → IMPRESORAS → EQUIPOS COMPLETOS → RESTO
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
        ],
        # FIX: quitado "all in one" de aquí (se maneja con guarda especial)
        # FIX: añadidos televisor, smart tv, impresora y variantes a excluir
        "excluir": [
            "laptop", "notebook", "monitor", "solo", "disco solo",
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
            "hp envy", "dell inspiron", "lenovo legion", "asus rog",
            "2 en 1",
        ],
        # FIX: quitado "touch" y "convertible" (demasiado genéricos)
        # FIX: añadidos televisor y smart tv a excluir
        "excluir": [
            "funda", "cargador", "bateria", "cooler", "base", "mouse",
            "teclado", "monitor", "torre", "gabinete", "disco externo",
            "memoria usb", "pendrive",
            "televisor", "smart tv", "tv led", "tv 4k", "tv uhd",
            "impresora",
        ],
        "es_equipo_completo": True,
    }),

    # ========== 3. MONITORES (incluye Smart TV — pero el Paso 0 ya los atrapa) ==========
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
        ],
        "es_equipo_completo": False,
    }),

    # ========== 4. IMPRESORAS (subidas a posición alta) ==========
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
        # FIX: añadidos televisor y smart tv a excluir
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
            # FIX: i3/i5/i7/i9 se manejan abajo con word boundary SOLO si
            #      no hay contexto de TV (ver lógica especial en detección)
        ],
        # FIX: añadidos televisor y smart tv a excluir
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
        ],
        "excluir": [
            "laptop", "monitor", "pc completa", "ram", "procesador",
            "mouse", "teclado", "impresora",
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
        # FIX: añadidos televisor y smart tv a excluir
        "excluir": [
            "usb", "pendrive", "flash", "micro sd", "tarjeta memoria",
            "laptop completa", "pc completa", "disco", "ssd",
            "memoria usb", "memoria flash", "kit mouse", "kit teclado",
            "televisor", "smart tv",
        ],
        "es_equipo_completo": False,
    }),

    # ========== 9. DISCOS DUROS / SSD ==========
    ("disco", {
        "palabras_clave": [
            "disco duro", "disco ssd", "ssd", "hdd", "nvme",
            "m.2", "m2", "disco solido", "disco mecanico",
            "disco externo", "seagate", "western digital",
            "toshiba", "adata", "transcend", "disco portatil",
        ],
        # FIX: quitado "externo" solo (demasiado genérico), mantenido en frases
        # FIX: añadidos televisor y smart tv a excluir
        "excluir": [
            "laptop", "pc completa", "memoria usb", "pendrive",
            "teclado", "mouse", "impresora", "monitor", "ram",
            "televisor", "smart tv",
        ],
        "es_equipo_completo": False,
    }),

    # ========== 10. CHASIS Y FUENTES ==========
    ("chasis", {
        "palabras_clave": [
            "chasis", "gabinete", "torre", "case", "fuente de poder",
            "fuente corsair", "fuente evga", "psu", "fuente 500w",
            "fuente 600w", "fuente 750w", "fuente 850w",
            "fuente atx", "gabinete gamer", "full tower", "mid tower",
            "fuente certificada", "fuente 80 plus",
            # FIX: añadidos modelos comunes de chasis gaming
            "montech", "sama", "nzxt", "phanteks", "fractal",
            "deepcool", "cooler master case", "lian li",
            "fanes rgb", "fanes argb", "fan rgb", "fan argb",
        ],
        # FIX: quitado "led" de excluir (los chasis gaming mencionan LED/RGB constantemente)
        #      reemplazado por "led tv" y "led monitor" que son más específicos
        "excluir": [
            "laptop", "monitor", "pc completa", "teclado", "mouse",
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
            # FIX: añadidos D-Link y modelos comunes no reconocidos antes
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
        ],
        "excluir": [
            "laptop", "pc", "monitor", "auricular", "audifono",
            "headset", "teclado", "mouse",
        ],
        "es_equipo_completo": False,
    }),

    # ========== 14. PERIFÉRICOS ==========
    ("periferico", {
        "palabras_clave": [
            "teclado", "mouse", "raton", "webcam", "camara web",
            "auriculares", "audifonos", "headset", "microfono",
            "joystick", "gamepad", "control xbox", "control ps4",
            "g502", "logitech", "razer", "corsair", "redragon",
            "teclado mecanico", "teclado gaming", "mouse gaming",
            "mouse gamer", "diadema", "kit mouse", "kit teclado",
            "mouse y teclado", "teclado y mouse", "combo teclado",
        ],
        "excluir": [
            "laptop", "pc", "monitor", "impresora", "disco",
            "ram", "procesador", "placa", "motherboard",
        ],
        "es_equipo_completo": False,
    }),

    # ========== 15. ACCESORIOS ==========
    ("accesorio", {
        "palabras_clave": [
            "cable", "adaptador", "conversor", "hub", "dock",
            "cooler", "ventilador", "disipador", "soporte",
            "base laptop", "cargador", "bateria", "power bank",
            "mouse pad", "alfombrilla", "pendrive", "memoria usb",
            "usb", "micro sd", "tarjeta memoria", "capturadora",
            "usb 3.0", "usb tipo c",
        ],
        "excluir": [
            "laptop", "pc", "monitor", "impresora", "disco duro",
            "memoria ram", "procesador", "teclado", "mouse",
            "ssd", "hdd", "nvme", "fuente de poder",
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
# PROVINCIAS
# ─────────────────────────────────────────
PROVINCIAS_NORM = {
    "habana": "La Habana", "la habana": "La Habana",
    "ciudad habana": "La Habana", "centro habana": "La Habana",
    "habana vieja": "La Habana", "miramar": "La Habana",
    "vedado": "La Habana", "playa": "La Habana",
    "artemisa": "Artemisa", "mayabeque": "Mayabeque",
    "pinar del rio": "Pinar del Río", "pinar del río": "Pinar del Río",
    "matanzas": "Matanzas", "cienfuegos": "Cienfuegos",
    "villa clara": "Villa Clara", "sancti spiritus": "Sancti Spíritus",
    "sancti spíritus": "Sancti Spíritus", "ciego de avila": "Ciego de Ávila",
    "camaguey": "Camagüey", "camagüey": "Camagüey",
    "las tunas": "Las Tunas", "holguin": "Holguín",
    "holguín": "Holguín", "granma": "Granma",
    "santiago de cuba": "Santiago de Cuba", "santiago": "Santiago de Cuba",
    "guantanamo": "Guantánamo", "guantánamo": "Guantánamo",
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
    """Extrae precio y convierte a USD"""
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
        precio_str = raw.get("precio_raw") or raw.get("precio") or ""
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
    """
    FIX v8.4: Detecta si el texto habla de un televisor/smart tv.
    Se llama antes de cualquier otra categorización (Paso 0).
    """
    return any(p in texto for p in PALABRAS_TV)


def _es_impresora(texto: str) -> bool:
    """
    FIX v8.4: Detecta si el texto habla de una impresora.
    Se usa para evitar que "all in one" active la categoría PC.
    """
    return any(p in texto for p in PALABRAS_IMPRESORA)


def detectar_categoria_estricta(titulo: str, descripcion: str = "") -> tuple:
    """
    Detecta categoría con jerarquía estricta v8.4.

    JERARQUÍA:
      Paso 0 — Televisores  → siempre monitor
      Paso 0b — Impresoras  → siempre impresora (evita "all in one" → pc)
      Paso 1 — PC / Laptop  (equipos completos)
      Paso 2 — Kits especiales
      Paso 3 — Monitor
      Paso 4 — Impresora (por si acaso no la atrapó el Paso 0b)
      Paso 5 — Resto de componentes / periféricos
      Paso 6 — Otros
    """
    texto = (titulo + " " + descripcion).lower()

    # ── PASO 0: Televisores — cortocircuito inmediato ──────────────────────
    # Si el texto menciona "televisor", "smart tv" o variantes, es monitor.
    # Esto impide que i3/i5/i7 sueltos, "4k", "pulgadas", etc. lo
    # desvíen a cpu, disco, laptop, etc.
    if _es_tv(texto):
        return "monitor", True

    # ── PASO 0b: Impresoras — cortocircuito antes de PC ───────────────────
    # "all in one", "3 en 1", "epson" etc. deben ser impresora, no PC.
    if _es_impresora(texto):
        # Confirmar que no es un monitor "todo en uno" de verdad
        es_pc_aio = any(k in texto for k in ["aio pc", "all in one pc", "pc all in one",
                                              "computadora all in one", "desktop all in one"])
        if not es_pc_aio:
            return "impresora", True

    # ── PASO 1: Equipos completos (PC, Laptop) ────────────────────────────
    for categoria, reglas in REGLAS_CATEGORIA:
        if not reglas.get("es_equipo_completo", False):
            continue

        # Manejo especial: "all in one" solo activa PC si no es impresora
        palabras_a_buscar = list(reglas["palabras_clave"])
        if categoria == "pc":
            # Añadir "all in one" aquí solo si no es impresora (ya lo descartamos arriba)
            palabras_a_buscar.append("all in one")

        for palabra in palabras_a_buscar:
            if palabra in texto:
                tiene_excluida = any(excluir in texto for excluir in reglas["excluir"])
                if not tiene_excluida:
                    return categoria, True

    # ── PASO 2: Kits especiales ───────────────────────────────────────────
    if "kit board" in texto or "kit de board" in texto or "board y micro" in texto:
        return "motherboard", True

    if ("kit mouse" in texto or "kit teclado" in texto or
            "mouse y teclado" in texto or "teclado y mouse" in texto):
        return "periferico", True

    # ── PASO 3: Monitores ─────────────────────────────────────────────────
    for categoria, reglas in REGLAS_CATEGORIA:
        if categoria != "monitor":
            continue
        for palabra in reglas["palabras_clave"]:
            if palabra in texto:
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
    # Estos modelos son tan cortos que pueden aparecer en cualquier texto.
    # Solo se activan si NO hay contexto de TV, router, chasis o impresora.
    MODELOS_CPU_CORTOS = ["i3", "i5", "i7", "i9"]
    cpu_reglas = next((r for c, r in REGLAS_CATEGORIA if c == "cpu"), None)
    if cpu_reglas:
        tiene_excluida_cpu = any(excluir in texto for excluir in cpu_reglas["excluir"])
        if not tiene_excluida_cpu:
            # Primero verificar keywords largas de cpu (sin ambigüedad)
            for palabra in cpu_reglas["palabras_clave"]:
                if palabra in texto:
                    return "cpu", True
            # Luego, i3/i5/i7/i9 solo si hay contexto claro de CPU/PC
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
    """Verifica que el precio tenga sentido para la categoría"""
    if not precio or precio < PRECIO_MINIMO.get(categoria, 5):
        return False
    if precio > PRECIO_MAXIMO.get(categoria, 5000):
        return False
    return True


def es_busca_comprar(texto: str) -> bool:
    """Detecta si el anuncio busca comprar en lugar de vender"""
    t = texto.lower()
    return any(frase in t for frase in BUSCA_COMPRAR)


def es_servicio_taller(texto: str) -> bool:
    """Detecta si es anuncio de taller o servicio"""
    t = texto.lower()
    return any(frase in t for frase in ES_SERVICIO)


def detectar_provincia(raw: dict, fuente: str, grupo_provincia: str = None) -> str | None:
    """Detecta provincia del anuncio"""
    if grupo_provincia:
        norm = PROVINCIAS_NORM.get(grupo_provincia.lower(), grupo_provincia)
        if norm:
            return norm

    prov = (raw.get("provincia") or "").strip().lower()
    if prov:
        norm = PROVINCIAS_NORM.get(prov)
        if norm:
            return norm

    texto = (
        (raw.get("contenido") or "") + " " +
        (raw.get("descripcion_completa") or "") + " " +
        (raw.get("titulo") or "")
    ).lower()

    for clave, nombre in PROVINCIAS_NORM.items():
        if clave in texto:
            return nombre

    return None


def generar_titulo_limpio(contenido: str) -> str:
    """Genera título limpio desde contenido"""
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
    """Procesa un anuncio de Revolico con reglas estrictas"""

    # Validar título
    titulo = limpiar_texto(raw.get("titulo") or "")
    if not titulo or len(titulo) < 3:
        return None

    descripcion = limpiar_texto(raw.get("descripcion_completa") or "")
    texto_completo = titulo + " " + descripcion

    # 1. Eliminar si busca comprar
    if es_busca_comprar(texto_completo):
        return None

    # 2. Eliminar si es taller/servicio
    if es_servicio_taller(texto_completo):
        return None

    # 3. Validar teléfono
    telefono = mejor_telefono(raw, "revolico")
    if not telefono:
        return None

    # 4. Validar precio
    precio_raw = raw.get("precio_raw") or raw.get("precio") or ""
    moneda = detectar_moneda(precio_raw)
    precio_usd = extraer_precio_usd(raw, "revolico", moneda)

    if not precio_usd:
        return None

    # 5. Categoría estricta
    categoria_original = raw.get("categoria") or "otros"
    categoria, recat = detectar_categoria_estricta(titulo, descripcion)

    # 6. Validar precio por categoría
    if not precio_valido(precio_usd, categoria):
        return None

    # 7. Provincia
    provincia = detectar_provincia(raw, "revolico")

    # 8. WhatsApp
    whatsapp = None
    wa_match = re.search(r'wa\.me/\+?53?(\d{7,8})', texto_completo)
    if wa_match:
        whatsapp = limpiar_telefono(wa_match.group(1))

    # 9. Limpiar título
    titulo_limpio = titulo
    for patron in PREFIJOS_BASURA:
        titulo_limpio = re.sub(patron, '', titulo_limpio, flags=re.IGNORECASE).strip()
    if len(titulo_limpio) < 3:
        titulo_limpio = titulo

    # 10. URL limpia
    url = re.split(r'\?', raw.get("url") or "")[0]

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
        "precio_texto": limpiar_texto(precio_raw)[:50],
        "telefono": telefono,
        "whatsapp": whatsapp,
        "vendedor": limpiar_texto(raw.get("vendedor") or "")[:50] or None,
        "provincia": provincia,
        "municipio": limpiar_texto(raw.get("municipio") or "")[:50] or None,
        "fecha": (raw.get("fecha_exacta") or raw.get("scrapeado_en") or "")[:10] or None,
        "vistas": raw.get("vistas"),
        "num_imagenes": len(raw.get("imagenes") or []),
        "imagen_principal": (raw.get("imagenes") or [None])[0],
    }


def procesar_facebook(raw: dict) -> dict | None:
    """Procesa un post de Facebook con reglas estrictas"""

    contenido = raw.get("contenido") or ""
    if not contenido or len(contenido) < 10:
        return None

    # 1. Eliminar si busca comprar
    if es_busca_comprar(contenido):
        return None

    # 2. Eliminar si es taller/servicio
    if es_servicio_taller(contenido):
        return None

    # 3. Generar título
    titulo = generar_titulo_limpio(contenido)
    if not titulo or len(titulo) < 5:
        return None

    # 4. Validar teléfono
    telefono = mejor_telefono(raw, "facebook")
    if not telefono:
        return None

    # 5. Validar precio
    moneda_raw = raw.get("moneda") or ""
    moneda = detectar_moneda(moneda_raw) if moneda_raw else "USD"
    precio_usd = extraer_precio_usd(raw, "facebook", moneda)

    if not precio_usd:
        return None

    # 6. Categoría estricta
    tipo_original = raw.get("tipo_equipo") or "otros"
    categoria, recat = detectar_categoria_estricta(titulo, contenido)

    # 7. Validar precio por categoría
    if not precio_valido(precio_usd, categoria):
        return None

    # 8. Provincia
    provincia = detectar_provincia(raw, "facebook", raw.get("provincia"))

    # 9. WhatsApp
    whatsapp = None
    wa_match = re.search(r'wa\.me/\+?53?(\d{7,8})', contenido)
    if wa_match:
        whatsapp = limpiar_telefono(wa_match.group(1))

    # 10. Vendedor
    vendedor = raw.get("autor") or None
    if vendedor and len(vendedor) < 2:
        vendedor = None

    return {
        "fuente": "facebook",
        "url": raw.get("url") or "",
        "titulo": titulo[:100],
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
# CARGAR DATOS
# ─────────────────────────────────────────

def cargar_revolico() -> list:
    """Carga todos los archivos de Revolico"""
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
    """Carga todos los archivos de Facebook"""
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
    """Guarda los productos en SQLite"""
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
    conn.execute("CREATE INDEX idx_cat ON productos(categoria)")
    conn.execute("CREATE INDEX idx_prov ON productos(provincia)")
    conn.execute("CREATE INDEX idx_prec ON productos(precio_usd)")
    conn.execute("CREATE INDEX idx_tel ON productos(telefono)")
    conn.execute("CREATE INDEX idx_fuent ON productos(fuente)")

    ph = ", ".join(["?" for _ in COLUMNAS])
    sql = f"INSERT OR IGNORE INTO productos ({', '.join(COLUMNAS)}) VALUES ({ph})"
    filas = [tuple(p.get(c) for c in COLUMNAS) for p in productos]
    conn.executemany(sql, filas)
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    conn.close()

    print(f"\n  ✅ SQLite: {total} registros en {DB_PATH.name}")
    return total


def guardar_csvs(productos: list):
    """Guarda los productos en CSV por categoría"""
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
    print("  CUBA PRECIOS — LIMPIEZA ESTRICTA v8.4")
    print("  JERARQUÍA: TV → IMPRESORA → PC/LAPTOP → COMPONENTES")
    print("=" * 60)
    print("\n  CORRECCIONES v8.4 APLICADAS:")
    print("  ✓ Televisor/Smart TV → MONITOR (filtro prioritario)")
    print("  ✓ Impresora 'all in one' → IMPRESORA (no PC)")
    print("  ✓ Router D-Link/AC3000/AX → MODEM")
    print("  ✓ Chasis gaming con RGB/LED → CHASIS (ya no se autoexcluye)")
    print("  ✓ i3/i5/i7 solo activan CPU con contexto técnico")
    print("  ✓ 'televisor' y 'smart tv' en excluir de pc/laptop/cpu/disco/gpu/ram")
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
        print(f"    {prov:<25} {n:>4}")

    print(f"\n  💱 Tasa: 1 USD = {TASA_CUP_USD} CUP")
    print(f"  📁 Datos en: {CLEAN_DIR}")
    print("=" * 60)
    print("\n  ✅ Listo. Corre: streamlit run app.py")


if __name__ == "__main__":
    main()