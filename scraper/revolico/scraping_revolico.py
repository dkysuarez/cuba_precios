"""
Scraper Revolico.com — Version 5
- Scrapea por PROVINCIA + CATEGORIA garantizando provincia en cada anuncio
- Extrae listado + detalle completo (telefono, vendedor, descripcion)
- Reanuda automaticamente si se interrumpe
- Maneja captcha y red inestable
"""

import json
import re
import time
import random
import sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Playwright
from loguru import logger

sys.path.append(str(Path(__file__).resolve().parent))
from config import (
    RAW_REVOLICO, LOGS_DIR, BASE_DIR,
    REVOLICO_BASE_URL, REVOLICO_CATEGORIAS,
    SCRAPER_CONFIG, crear_estructura
)

# ─────────────────────────────────────────
# LOGS
# ─────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logger.add(
    str(LOGS_DIR / "scraper_revolico.log"),
    rotation="10 MB", retention="7 days",
    level="INFO", encoding="utf-8"
)

COOKIES_FILE = BASE_DIR / "session_cookies.json"

# ─────────────────────────────────────────
# PROVINCIAS DE CUBA — ID de Revolico
# ─────────────────────────────────────────
PROVINCIAS = {
    "la-habana":        1,
    "artemisa":         2,
    "mayabeque":        3,
    "pinar-del-rio":    4,
    "isla-juventud":    5,
    "matanzas":         6,
    "cienfuegos":       7,
    "villa-clara":      8,
    "sancti-spiritus":  9,
    "ciego-de-avila":   10,
    "camaguey":         11,
    "las-tunas":        12,
    "holguin":          13,
    "granma":           14,
    "santiago-de-cuba": 15,
    "guantanamo":       16,
}

NOMBRE_PROVINCIA = {
    1:  "La Habana",
    2:  "Artemisa",
    3:  "Mayabeque",
    4:  "Pinar del Río",
    5:  "Isla de la Juventud",
    6:  "Matanzas",
    7:  "Cienfuegos",
    8:  "Villa Clara",
    9:  "Sancti Spíritus",
    10: "Ciego de Ávila",
    11: "Camagüey",
    12: "Las Tunas",
    13: "Holguín",
    14: "Granma",
    15: "Santiago de Cuba",
    16: "Guantánamo",
}


# ─────────────────────────────────────────
# SESION
# ─────────────────────────────────────────

def guardar_cookies(context):
    cookies = context.cookies()
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print("✅ Sesion guardada")

def cargar_cookies(context) -> bool:
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    return False

def sesion_existe() -> bool:
    return COOKIES_FILE.exists()

def borrar_sesion():
    if COOKIES_FILE.exists():
        COOKIES_FILE.unlink()


# ─────────────────────────────────────────
# BROWSER
# ─────────────────────────────────────────

def nuevo_browser(p: Playwright, headless=True):
    browser = p.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="es-ES",
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
    """)
    return browser, context


# ─────────────────────────────────────────
# DETECCION
# ─────────────────────────────────────────

def tiene_captcha(page) -> bool:
    try:
        c = page.content().lower()
        return "turnstile" in c or "cf-challenge" in c
    except Exception:
        return False

def tiene_anuncios(page) -> bool:
    for sel in ["article", "[class*='adCard']", "[class*='AdCard']"]:
        try:
            if len(page.query_selector_all(sel)) > 2:
                return True
        except Exception:
            continue
    return False


# ─────────────────────────────────────────
# NAVEGACION
# ─────────────────────────────────────────

def navegar(page, url: str, intentos: int = 3) -> bool:
    for i in range(intentos):
        try:
            page.goto(url, timeout=90000)
            page.wait_for_load_state("domcontentloaded", timeout=90000)
            return True
        except Exception as e:
            if i < intentos - 1:
                espera = (i + 1) * 5
                print(f"  ⚠️  Red inestable, reintentando en {espera}s...")
                time.sleep(espera)
            else:
                logger.error(f"Fallo: {url}: {e}")
                return False
    return False


# ─────────────────────────────────────────
# CAPTCHA
# ─────────────────────────────────────────

def resolver_captcha(p: Playwright, url: str) -> bool:
    print("\n" + "="*55)
    print("  RESUELVE EL CAPTCHA EN EL BROWSER")
    print("="*55)
    browser, context = nuevo_browser(p, headless=False)
    page = context.new_page()
    resultado = False
    try:
        page.goto(url, timeout=90000)
        print("⏳ Resuelve el captcha (2 min max)...")
        for i in range(24):
            time.sleep(5)
            if not tiene_captcha(page) and len(page.content()) > 5000:
                print("✅ Captcha resuelto")
                guardar_cookies(context)
                resultado = True
                break
            print(f"  Esperando... ({(i+1)*5}s)")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        try:
            context.close()
            browser.close()
        except Exception:
            pass
    return resultado


# ─────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────

def extraer_telefonos(texto: str) -> list:
    if not texto:
        return []
    patrones = [
        r'\b5[0-9]{7}\b',
        r'\+53\s?[0-9]{8}',
        r'\b53[0-9]{8}\b',
        r'\b[2-7][0-9]{6,7}\b',
    ]
    encontrados = []
    for p in patrones:
        encontrados.extend(re.findall(p, texto))
    return list(set([t.replace(" ", "") for t in encontrados]))


def archivo_provincia_categoria(categoria: str, provincia_id: int) -> Path:
    """Ruta del archivo raw para una combinacion provincia+categoria"""
    nombre_prov = NOMBRE_PROVINCIA[provincia_id].replace(" ", "_").replace("í", "i").replace("é", "e").replace("ú", "u").replace("á", "a").replace("ó", "o")
    return RAW_REVOLICO / f"prov{provincia_id:02d}_{nombre_prov}_{categoria}.json"


def cargar_urls_procesadas_detalle(categoria: str, provincia_id: int) -> set:
    archivo = archivo_provincia_categoria(categoria, provincia_id).with_suffix(".detalle.json")
    if not archivo.exists():
        return set()
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return {d.get("url") for d in datos if d.get("url")}
    except Exception:
        return set()


def cargar_detalle_existente(categoria: str, provincia_id: int) -> list:
    archivo = archivo_provincia_categoria(categoria, provincia_id).with_suffix(".detalle.json")
    if archivo.exists():
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_detalle(detalles: list, categoria: str, provincia_id: int):
    if not detalles:
        return
    archivo = archivo_provincia_categoria(categoria, provincia_id).with_suffix(".detalle.json")
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(detalles, f, ensure_ascii=False, indent=2)


def guardar_progreso_general(progreso: dict):
    """Guarda que combinaciones provincia+categoria ya fueron procesadas"""
    archivo = RAW_REVOLICO / "progreso_scraping.json"
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(progreso, f, ensure_ascii=False, indent=2)


def cargar_progreso_general() -> dict:
    archivo = RAW_REVOLICO / "progreso_scraping.json"
    if archivo.exists():
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ─────────────────────────────────────────
# PASO 1 — LISTADO CON URLs
# ─────────────────────────────────────────

def extraer_cards(page, provincia_id: int, categoria: str) -> list:
    """Extrae todos los cards de la pagina actual"""
    anuncios = []

    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
    except Exception:
        pass

    elementos = []
    for selector in ["article", "[class*='adCard']", "[class*='AdCard']", "[class*='ad-card']"]:
        try:
            elementos = page.query_selector_all(selector)
            if elementos:
                break
        except Exception:
            continue

    if not elementos:
        try:
            debug = RAW_REVOLICO / f"debug_{datetime.now().strftime('%H%M%S')}.html"
            debug.write_text(page.content(), encoding="utf-8")
            print(f"  ⚠️  Sin cards. HTML: {debug.name}")
        except Exception:
            pass
        return anuncios

    for elem in elementos:
        try:
            anuncio = {}

            # ── URL ──────────────────────────────
            url = None
            try:
                links = elem.query_selector_all("a")
                for link in links:
                    href = link.get_attribute("href") or ""
                    if href and len(href) > 10 and "/" in href:
                        es_cat = any(x in href for x in [
                            "/computadoras/pc-de", "/computadoras/laptop",
                            "/computadoras/memoria", "/computadoras/disco",
                            "/computadoras/monitor", "/computadoras/micro",
                            "/computadoras/mother", "/computadoras/tarjeta",
                            "/computadoras/modem", "/computadoras/teclado",
                            "/computadoras/impres", "/computadoras/webcam",
                            "/computadoras/backup", "/computadoras/chasis",
                            "/computadoras/quema", "/computadoras/cd-dvd",
                            "/computadoras/inter", "/computadoras/otros",
                            "/computadoras/sonido", "?", "#",
                        ])
                        if not es_cat:
                            url = href if href.startswith("http") else REVOLICO_BASE_URL + href
                            break
            except Exception:
                pass

            if not url:
                for attr in ["data-href", "data-url", "data-link"]:
                    try:
                        val = elem.get_attribute(attr)
                        if val:
                            url = val if val.startswith("http") else REVOLICO_BASE_URL + val
                            break
                    except Exception:
                        continue

            if not url:
                try:
                    href = elem.get_attribute("href")
                    if href:
                        url = href if href.startswith("http") else REVOLICO_BASE_URL + href
                except Exception:
                    pass

            anuncio["url"] = url

            # ── Titulo (solo el titulo, no descripcion) ──
            for sel in ["h2", "h3", "[class*='title']", "[class*='Title']"]:
                try:
                    e = elem.query_selector(sel)
                    if e:
                        texto = e.inner_text().strip()
                        if len(texto) > 3:
                            anuncio["titulo"] = texto
                            break
                except Exception:
                    continue

            # ── Precio ──────────────────────────
            for sel in ["[class*='price']", "[class*='Price']", "[class*='precio']"]:
                try:
                    e = elem.query_selector(sel)
                    if e:
                        anuncio["precio_raw"] = e.inner_text().strip()
                        break
                except Exception:
                    continue

            # ── Fecha ────────────────────────────
            for sel in ["[class*='date']", "[class*='Date']", "time", "[class*='ago']"]:
                try:
                    e = elem.query_selector(sel)
                    if e:
                        anuncio["fecha_publicacion"] = e.inner_text().strip()
                        break
                except Exception:
                    continue

            # ── Telefono en titulo ───────────────
            tels = extraer_telefonos(anuncio.get("titulo") or "")
            if tels:
                anuncio["telefonos_titulo"] = tels

            # ── Metadata garantizada ─────────────
            anuncio["categoria"]    = categoria
            anuncio["provincia"]    = NOMBRE_PROVINCIA[provincia_id]
            anuncio["provincia_id"] = provincia_id
            anuncio["fuente"]       = "revolico"
            anuncio["scrapeado_en"] = datetime.now().isoformat()

            if anuncio.get("titulo"):
                anuncios.append(anuncio)

        except Exception as e:
            logger.warning(f"Error card: {e}")
            continue

    return anuncios


def scrape_listado(categoria: str, provincia_id: int, page, p: Playwright, max_paginas: int = 2) -> list:
    """Scrapea listado de una categoria+provincia"""
    url_base = (
        REVOLICO_BASE_URL
        + REVOLICO_CATEGORIAS[categoria]
        + f"?province={provincia_id}"
    )

    if not navegar(page, url_base):
        return []

    time.sleep(3)

    if tiene_captcha(page) and not tiene_anuncios(page):
        print(f"  ⚠️  Captcha en listado")
        borrar_sesion()
        if not resolver_captcha(p, url_base):
            return None
        cargar_cookies(page.context)
        if not navegar(page, url_base):
            return []
        time.sleep(3)

    todos = []
    pagina = 1

    while pagina <= max_paginas:
        print(f"  📄 Pag {pagina}/{max_paginas} | {NOMBRE_PROVINCIA[provincia_id]} | {categoria}...")
        anuncios = extraer_cards(page, provincia_id, categoria)
        con_url = sum(1 for a in anuncios if a.get("url"))
        print(f"     → {len(anuncios)} anuncios | {con_url} con URL")

        for a in anuncios:
            a["pagina_listado"] = pagina
        todos.extend(anuncios)

        # Siguiente pagina
        siguiente = None
        for sel in ["a[rel='next']", "[class*='next'] a", "a:has-text('Siguiente')"]:
            try:
                e = page.query_selector(sel)
                if e:
                    siguiente = e
                    break
            except Exception:
                continue

        if not siguiente:
            break

        try:
            time.sleep(random.uniform(2, 4))
            siguiente.click()
            page.wait_for_load_state("domcontentloaded", timeout=90000)
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Error siguiente: {e}")
            break

        pagina += 1

    return todos


# ─────────────────────────────────────────
# PASO 2 — DETALLE DE CADA ANUNCIO
# ─────────────────────────────────────────

def extraer_detalle(page, anuncio_base: dict) -> dict:
    """Extrae detalle completo — usa titulo como referencia principal"""
    detalle = {
        **anuncio_base,
        "descripcion_completa":  None,
        "telefono":              None,
        "whatsapp":              None,
        "vendedor":              None,
        "municipio":             None,
        "fecha_exacta":          None,
        "vistas":                None,
        "imagenes":              [],
        "telefonos_detectados":  list(anuncio_base.get("telefonos_titulo") or []),
        "detalle_scrapeado_en":  datetime.now().isoformat(),
    }

    try:
        # Descripcion completa (guardamos pero no usamos para recategorizar)
        for sel in [
            "[class*='description']", "[class*='Description']",
            "[class*='adDescription']", "[class*='detail']",
            "[class*='body']", "section p",
        ]:
            try:
                e = page.query_selector(sel)
                if e:
                    texto = e.inner_text().strip()
                    if len(texto) > 20:
                        detalle["descripcion_completa"] = texto
                        # Telefonos en descripcion
                        tels = extraer_telefonos(texto)
                        detalle["telefonos_detectados"] = list(
                            set(detalle["telefonos_detectados"] + tels)
                        )
                        break
            except Exception:
                continue

        # Telefono via link tel:
        try:
            for link in page.query_selector_all("a[href^='tel:'], a[href^='callto:']"):
                href = link.get_attribute("href") or ""
                numero = re.sub(r'[^0-9+]', '', href)
                if len(numero) >= 7:
                    detalle["telefono"] = numero
                    break
        except Exception:
            pass

        # Telefono via clases
        if not detalle["telefono"]:
            for sel in [
                "[class*='phone']", "[class*='Phone']",
                "[class*='telefono']", "[class*='contact']", "[class*='call']",
            ]:
                try:
                    e = page.query_selector(sel)
                    if e:
                        texto = e.inner_text().strip()
                        nums = extraer_telefonos(texto)
                        if nums:
                            detalle["telefono"] = nums[0]
                            break
                        elif re.search(r'\d{7,}', texto):
                            detalle["telefono"] = re.sub(r'[^0-9]', '', texto)
                            break
                except Exception:
                    continue

        # Fallback: primer telefono en texto
        if not detalle["telefono"] and detalle["telefonos_detectados"]:
            detalle["telefono"] = detalle["telefonos_detectados"][0]

        # WhatsApp
        for sel in ["a[href*='whatsapp.com']", "a[href*='wa.me']", "[class*='whatsapp']"]:
            try:
                e = page.query_selector(sel)
                if e:
                    href = e.get_attribute("href") or ""
                    match = re.search(r'(\d{8,15})', href)
                    if match:
                        detalle["whatsapp"] = match.group(1)
                    break
            except Exception:
                continue

        # Vendedor
        for sel in [
            "[class*='seller']", "[class*='Seller']",
            "[class*='user']", "[class*='User']",
            "[class*='author']", "[class*='owner']",
        ]:
            try:
                e = page.query_selector(sel)
                if e:
                    texto = e.inner_text().strip()
                    if 2 < len(texto) < 60:
                        detalle["vendedor"] = texto
                        break
            except Exception:
                continue

        # Municipio (provincia ya la tenemos garantizada)
        for sel in ["[class*='location']", "[class*='Location']", "[class*='address']"]:
            try:
                e = page.query_selector(sel)
                if e:
                    texto = e.inner_text().strip()
                    if texto:
                        partes = [x.strip() for x in texto.split(",")]
                        # Si tiene 2 partes, la segunda es municipio
                        if len(partes) > 1:
                            detalle["municipio"] = partes[1]
                        break
            except Exception:
                continue

        # Fecha exacta
        for sel in ["[class*='date']", "time[datetime]", "[class*='published']"]:
            try:
                e = page.query_selector(sel)
                if e:
                    dt = e.get_attribute("datetime") or e.inner_text().strip()
                    if dt:
                        detalle["fecha_exacta"] = dt
                        break
            except Exception:
                continue

        # Vistas
        for sel in ["[class*='view']", "[class*='visit']", "[class*='seen']"]:
            try:
                e = page.query_selector(sel)
                if e:
                    nums = re.findall(r'\d+', e.inner_text())
                    if nums:
                        detalle["vistas"] = int(nums[0])
                        break
            except Exception:
                continue

        # Imagenes
        imagenes = []
        for sel in [
            "[class*='gallery'] img", "[class*='carousel'] img",
            "[class*='photo'] img", "[class*='slider'] img", "figure img",
        ]:
            try:
                for img in page.query_selector_all(sel):
                    src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                    if src.startswith("http") and src not in imagenes:
                        if not any(x in src.lower() for x in ["icon", "logo", "avatar", "banner"]):
                            imagenes.append(src)
            except Exception:
                continue

        detalle["imagenes"] = imagenes[:10]

    except Exception as e:
        logger.warning(f"Error detalle {detalle.get('url')}: {e}")

    return detalle


# ─────────────────────────────────────────
# PIPELINE POR PROVINCIA + CATEGORIA
# ─────────────────────────────────────────

def procesar(categoria: str, provincia_id: int, p: Playwright, max_paginas: int = 2) -> int:
    nombre_prov = NOMBRE_PROVINCIA[provincia_id]

    procesados   = cargar_urls_procesadas_detalle(categoria, provincia_id)
    existentes   = cargar_detalle_existente(categoria, provincia_id)
    nuevos       = []
    errores      = 0

    browser, context = nuevo_browser(p, headless=True)
    if cargar_cookies(context):
        pass
    else:
        pass
    page = context.new_page()

    try:
        # PASO 1: Listado
        resultado = scrape_listado(categoria, provincia_id, page, p, max_paginas)

        if resultado is None:
            return 0

        if not resultado:
            return 0

        pendientes = [
            a for a in resultado
            if a.get("url") and a.get("url") not in procesados
        ]

        sin_url = sum(1 for a in resultado if not a.get("url"))
        if sin_url > 0:
            print(f"  ⚠️  {sin_url} anuncios sin URL descartados")

        if not pendientes:
            return len(existentes)

        print(f"  [2/2] Detalle: {len(pendientes)} anuncios...")

        for i, anuncio in enumerate(pendientes):
            url = anuncio["url"]
            titulo_corto = (anuncio.get("titulo") or "")[:40]
            print(f"  [{i+1}/{len(pendientes)}] {titulo_corto}...")

            ok = navegar(page, url)
            if not ok:
                errores += 1
                if errores > 5:
                    time.sleep(30)
                    errores = 0
                continue

            time.sleep(1.5)

            if tiene_captcha(page):
                print("  ⚠️  Captcha — guardando progreso...")
                guardar_detalle(existentes + nuevos, categoria, provincia_id)
                borrar_sesion()
                if resolver_captcha(p, url):
                    try:
                        context.close()
                        browser.close()
                    except Exception:
                        pass
                    browser, context = nuevo_browser(p, headless=True)
                    cargar_cookies(context)
                    page = context.new_page()
                    navegar(page, url)
                    time.sleep(2)
                else:
                    return len(existentes) + len(nuevos)

            detalle = extraer_detalle(page, anuncio)
            nuevos.append(detalle)
            errores = 0

            tel  = detalle.get("telefono") or "—"
            vend = detalle.get("vendedor") or "—"
            mun  = detalle.get("municipio") or "—"
            print(f"    📞 {tel}  👤 {vend}  🏙 {mun}")

            if (i + 1) % 30 == 0:
                guardar_detalle(existentes + nuevos, categoria, provincia_id)
                print(f"  💾 Guardado parcial: {len(existentes)+len(nuevos)}")

            time.sleep(random.uniform(1.5, 3.0))

    except Exception as e:
        logger.error(f"Error {categoria}/{nombre_prov}: {e}")
        print(f"  ❌ Error: {e}")
    finally:
        try:
            context.close()
            browser.close()
        except Exception:
            pass

    todos = existentes + nuevos
    guardar_detalle(todos, categoria, provincia_id)

    con_tel = sum(1 for d in todos if d.get("telefono"))
    print(f"  ✅ {nombre_prov} / {categoria}: {len(todos)} anuncios | 📞 {con_tel} con tel")
    return len(todos)


# ─────────────────────────────────────────
# MENU
# ─────────────────────────────────────────

def preguntar_accion(categoria: str, provincia_id: int) -> str:
    archivo = archivo_provincia_categoria(categoria, provincia_id).with_suffix(".detalle.json")
    if not archivo.exists():
        return "procesar"
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return "procesar"

    nombre_prov = NOMBRE_PROVINCIA[provincia_id]
    con_tel = sum(1 for d in datos if d.get("telefono"))
    print(f"\n  ⚠️  Ya existe: {nombre_prov} / {categoria} ({len(datos)} anuncios, {con_tel} tel)")
    print("  [1] Actualizar  [2] Continuar  [3] Saltar  [4] Salir")

    while True:
        op = input("  Eleccion (1/2/3/4): ").strip()
        if op == "1":
            archivo.unlink()
            return "procesar"
        elif op == "2":
            return "procesar"
        elif op == "3":
            return "saltar"
        elif op == "4":
            return "salir"
        else:
            print("  ❌ Escribe 1, 2, 3 o 4")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    crear_estructura()

    # ── Que categorias scrapear ──────────
    CATEGORIAS = [
        "ram", "disco", "monitor", "laptop", "pc",
        "cpu", "gpu", "modem", "motherboard", "chasis",
        "impresora", "teclado", "webcam", "sonido",
        "ups", "dvd", "cd", "internet", "otros"
    ]

    # ── Que provincias scrapear ──────────
    # Por defecto todas — comenta las que no quieras
    PROVINCIAS_SCRAPEAR = list(PROVINCIAS.values())
    # Para probar solo La Habana:
    # PROVINCIAS_SCRAPEAR = [1]

    # ── Paginas por combinacion ──────────
    # 1 pagina  ≈ 20-30 anuncios por provincia/categoria
    # 2 paginas ≈ 40-60 anuncios
    MAX_PAGINAS = 2

    # ── Modo interactivo o automatico ────
    # True  = pregunta que hacer si ya existe
    # False = salta automaticamente los ya procesados
    MODO_INTERACTIVO = False

    total_combinaciones = len(CATEGORIAS) * len(PROVINCIAS_SCRAPEAR)

    print("\n" + "="*55)
    print("  CUBA PRECIOS — SCRAPER v5 CON PROVINCIAS")
    print("="*55)
    print(f"  Categorias  : {len(CATEGORIAS)}")
    print(f"  Provincias  : {len(PROVINCIAS_SCRAPEAR)}")
    print(f"  Combinaciones: {total_combinaciones}")
    print(f"  Paginas/combo: {MAX_PAGINAS} (~{MAX_PAGINAS*25} anuncios)")
    print(f"  Total estimado: ~{total_combinaciones * MAX_PAGINAS * 25} anuncios")
    print("="*55)

    progreso = cargar_progreso_general()

    with sync_playwright() as p:

        # Verificar sesion
        if not sesion_existe():
            print("\n🔄 Verificando acceso...")
            url_prueba = REVOLICO_BASE_URL + REVOLICO_CATEGORIAS["ram"] + "?province=1"
            browser, context = nuevo_browser(p, headless=True)
            page = context.new_page()
            try:
                if navegar(page, url_prueba):
                    time.sleep(3)
                    if tiene_anuncios(page):
                        print("✅ Acceso OK — sin captcha")
                        guardar_cookies(context)
                    elif tiene_captcha(page):
                        context.close()
                        browser.close()
                        resolver_captcha(p, url_prueba)
                    else:
                        guardar_cookies(context)
            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass
        else:
            print("✅ Sesion existente")

        resultados = {}
        combo_actual = 0

        for provincia_id in PROVINCIAS_SCRAPEAR:
            nombre_prov = NOMBRE_PROVINCIA[provincia_id]

            for categoria in CATEGORIAS:
                combo_actual += 1
                clave = f"{provincia_id}_{categoria}"

                print(f"\n{'='*55}")
                print(f"  [{combo_actual}/{total_combinaciones}] {nombre_prov} / {categoria.upper()}")
                print(f"{'='*55}")

                # Verificar si ya fue procesado
                if clave in progreso and progreso[clave] == "completado":
                    if not MODO_INTERACTIVO:
                        print(f"  ⏭️  Ya procesado — saltando")
                        continue

                if MODO_INTERACTIVO:
                    accion = preguntar_accion(categoria, provincia_id)
                    if accion == "saltar":
                        continue
                    elif accion == "salir":
                        print("\n👋 Saliendo...")
                        guardar_progreso_general(progreso)
                        break
                else:
                    # Automatico: saltar si ya existe con datos
                    archivo = archivo_provincia_categoria(categoria, provincia_id).with_suffix(".detalle.json")
                    if archivo.exists():
                        print(f"  ⏭️  Archivo existe — saltando")
                        progreso[clave] = "completado"
                        continue

                cantidad = procesar(categoria, provincia_id, p, max_paginas=MAX_PAGINAS)
                resultados[clave] = cantidad
                progreso[clave] = "completado"
                guardar_progreso_general(progreso)

                # Pausa entre combinaciones
                pausa = random.uniform(3, 6)
                time.sleep(pausa)

            else:
                continue
            break  # Si hubo "salir" en el loop interno

    # Resumen
    print("\n" + "="*55)
    print("  RESUMEN FINAL")
    print("="*55)
    total = sum(resultados.values())
    print(f"  📊 Combinaciones procesadas : {len(resultados)}")
    print(f"  📊 Total anuncios           : {total}")
    print(f"  📁 Archivos en: data/raw/revolico/")
    print(f"     prov##_Provincia_categoria.detalle.json")
    print("="*55)
    print("\n  ✅ Cuando termine corre: python limpiar_datos.py")