"""
Scraper de DETALLE de Revolico.com
Lee las URLs de los JSON raw ya descargados,
entra a cada anuncio individual y extrae:
- Telefono / WhatsApp
- Nombre del vendedor
- Descripcion completa
- Fecha exacta
- Provincia / Ciudad
- Imagenes (URLs)
- Vistas del anuncio
- Precio completo

Guarda en: data/raw/revolico/detalle_CATEGORIA.json
Permite reanudar si se interrumpe (no repite URLs ya procesadas)
"""

import json
import time
import random
import sys
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from loguru import logger

sys.path.append(str(Path(__file__).resolve().parents[2]))
from config import (
    RAW_REVOLICO, LOGS_DIR, BASE_DIR,
    REVOLICO_BASE_URL, SCRAPER_CONFIG, crear_estructura
)

# ─────────────────────────────────────────
# LOGS
# ─────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logger.add(
    str(LOGS_DIR / "detalle_revolico.log"),
    rotation="10 MB", retention="7 days",
    level="INFO", encoding="utf-8"
)

COOKIES_FILE = BASE_DIR / "session_cookies.json"


# ─────────────────────────────────────────
# SESIÓN
# ─────────────────────────────────────────

def cargar_cookies(context) -> bool:
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        logger.info("Cookies cargadas")
        return True
    return False


def guardar_cookies(context):
    cookies = context.cookies()
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    logger.info("Cookies guardadas")
    print("✅ Sesion guardada")


def borrar_sesion():
    if COOKIES_FILE.exists():
        COOKIES_FILE.unlink()


# ─────────────────────────────────────────
# BROWSER
# ─────────────────────────────────────────

def get_browser_context(playwright, headless: bool = True):
    browser = playwright.chromium.launch(
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
# CAPTCHA
# ─────────────────────────────────────────

def tiene_captcha(page) -> bool:
    c = page.content().lower()
    return "turnstile" in c or "cf-challenge" in c or "challenge" in c


def resolver_captcha_manual(url: str) -> bool:
    print("\n" + "="*55)
    print("  RESUELVE EL CAPTCHA EN EL BROWSER QUE SE ABRE")
    print("="*55)

    resultado = False
    with sync_playwright() as p:
        browser, context = get_browser_context(p, headless=False)
        page = context.new_page()
        try:
            page.goto(url, timeout=90000)
            print("⏳ Esperando captcha (2 minutos max)...")
            for i in range(24):
                time.sleep(5)
                contenido = page.content()
                # En pagina de detalle buscamos el titulo del anuncio
                if not tiene_captcha(page) and len(contenido) > 5000:
                    print("✅ Captcha resuelto")
                    guardar_cookies(context)
                    time.sleep(2)
                    resultado = True
                    break
                print(f"  Esperando... ({(i+1)*5}s / 120s)")
            if not resultado:
                print("⚠️  Tiempo agotado.")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            browser.close()
    return resultado


# ─────────────────────────────────────────
# CARGAR URLs DESDE JSONs RAW
# ─────────────────────────────────────────

def cargar_urls_categoria(categoria: str) -> list:
    """
    Lee el JSON raw mas reciente de una categoria
    y retorna lista de dicts con {url, titulo, precio_raw, categoria}
    """
    archivos = sorted(RAW_REVOLICO.glob(f"*_{categoria}.json"), reverse=True)
    if not archivos:
        print(f"  ❌ No hay JSON raw para: {categoria}")
        return []

    archivo = archivos[0]
    print(f"  📄 Leyendo: {archivo.name}")

    with open(archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)

    # Filtrar solo los que tienen URL
    con_url = [d for d in datos if d.get("url")]
    sin_url = len(datos) - len(con_url)

    print(f"  📊 Total: {len(datos)} | Con URL: {len(con_url)} | Sin URL: {sin_url}")
    return con_url


def cargar_urls_procesadas(categoria: str) -> set:
    """
    Lee el archivo de detalle existente y retorna
    el set de URLs ya procesadas (para no repetir)
    """
    archivo_detalle = RAW_REVOLICO / f"detalle_{categoria}.json"
    if not archivo_detalle.exists():
        return set()

    with open(archivo_detalle, "r", encoding="utf-8") as f:
        datos = json.load(f)

    urls = {d.get("url") for d in datos if d.get("url")}
    print(f"  ♻️  Ya procesadas: {len(urls)} URLs — continuando desde donde quedó")
    return urls


def cargar_detalle_existente(categoria: str) -> list:
    archivo_detalle = RAW_REVOLICO / f"detalle_{categoria}.json"
    if archivo_detalle.exists():
        with open(archivo_detalle, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ─────────────────────────────────────────
# EXTRACCIÓN DE DETALLE DE UN ANUNCIO
# ─────────────────────────────────────────

def extraer_telefono_texto(texto: str) -> list:
    """Extrae números de teléfono cubanos de cualquier texto"""
    if not texto:
        return []
    patrones = [
        r'\b5[0-9]{7}\b',           # Movil cubano: 5XXXXXXX
        r'\b[2-7][0-9]{6,7}\b',     # Fijo cubano
        r'\+53\s?[0-9]{8}',         # Con codigo de pais
        r'\b53[0-9]{8}\b',          # Con 53 pegado
    ]
    encontrados = []
    for patron in patrones:
        matches = re.findall(patron, texto)
        encontrados.extend(matches)
    # Limpiar duplicados y espacios
    return list(set([t.replace(" ", "").replace("+", "") for t in encontrados]))


def extraer_detalle_anuncio(page, url_base: dict) -> dict:
    """
    Extrae todos los datos de la pagina de detalle de un anuncio.
    url_base: dict con los datos del listado (titulo, precio_raw, etc.)
    """
    detalle = {
        # Heredar datos del listado
        "url":          url_base.get("url"),
        "titulo":       url_base.get("titulo"),
        "precio_raw":   url_base.get("precio_raw"),
        "categoria":    url_base.get("categoria"),
        "fuente":       "revolico",
        "scrapeado_en": datetime.now().isoformat(),

        # Campos nuevos del detalle
        "descripcion_completa": None,
        "telefono":             None,
        "whatsapp":             None,
        "vendedor":             None,
        "provincia":            None,
        "municipio":            None,
        "fecha_publicacion":    None,
        "vistas":               None,
        "imagenes":             [],
        "telefonos_en_texto":   [],
    }

    try:
        contenido = page.content()

        # ── Descripción completa ──────────────
        for sel in [
            "[class*='description']", "[class*='Description']",
            "[class*='adDescription']", "[class*='body']",
            "[class*='detail']", "section p", "article p",
            "[class*='text']", ".description"
        ]:
            e = page.query_selector(sel)
            if e:
                texto = e.inner_text().strip()
                if len(texto) > 20:
                    detalle["descripcion_completa"] = texto
                    # Buscar teléfonos en la descripción
                    detalle["telefonos_en_texto"] = extraer_telefono_texto(texto)
                    break

        # ── Teléfono oficial ──────────────────
        for sel in [
            "[class*='phone']", "[class*='Phone']",
            "[class*='telefono']", "[class*='Telefono']",
            "[class*='contact']", "[class*='Contact']",
            "a[href^='tel:']", "a[href^='callto:']",
            "[class*='call']", "[class*='whatsapp']",
            "[data-testid*='phone']", "[data-testid*='contact']",
        ]:
            e = page.query_selector(sel)
            if e:
                texto = e.inner_text().strip()
                href = e.get_attribute("href") or ""
                numero = texto or href.replace("tel:", "").replace("callto:", "")
                if numero and len(numero) >= 7:
                    detalle["telefono"] = numero.strip()
                    break

        # Si no encontró teléfono con selectores, buscar en todo el HTML
        if not detalle["telefono"]:
            # Buscar en href de links tipo tel:
            links_tel = page.query_selector_all("a[href^='tel:'], a[href^='callto:']")
            for link in links_tel:
                href = link.get_attribute("href") or ""
                numero = href.replace("tel:", "").replace("callto:", "").strip()
                if numero:
                    detalle["telefono"] = numero
                    break

        # ── WhatsApp ──────────────────────────
        for sel in [
            "a[href*='whatsapp']", "a[href*='wa.me']",
            "[class*='whatsapp']", "[class*='WhatsApp']"
        ]:
            e = page.query_selector(sel)
            if e:
                href = e.get_attribute("href") or e.inner_text().strip()
                if href:
                    # Extraer número de URL de WhatsApp
                    match = re.search(r'(\d{8,15})', href)
                    if match:
                        detalle["whatsapp"] = match.group(1)
                    else:
                        detalle["whatsapp"] = href
                    break

        # ── Vendedor / Nombre ─────────────────
        for sel in [
            "[class*='seller']", "[class*='Seller']",
            "[class*='user']", "[class*='User']",
            "[class*='author']", "[class*='Author']",
            "[class*='name']", "[class*='vendor']",
            "[data-testid*='user']", "[data-testid*='seller']",
        ]:
            e = page.query_selector(sel)
            if e:
                texto = e.inner_text().strip()
                if texto and len(texto) > 1 and len(texto) < 60:
                    detalle["vendedor"] = texto
                    break

        # ── Provincia / Ubicación ─────────────
        for sel in [
            "[class*='location']", "[class*='Location']",
            "[class*='province']", "[class*='Province']",
            "[class*='ciudad']", "[class*='address']",
            "[class*='ubicacion']", "[data-testid*='location']",
        ]:
            e = page.query_selector(sel)
            if e:
                texto = e.inner_text().strip()
                if texto:
                    # Separar provincia y municipio si viene junto
                    partes = texto.split(",")
                    detalle["provincia"] = partes[0].strip()
                    if len(partes) > 1:
                        detalle["municipio"] = partes[1].strip()
                    break

        # ── Fecha publicación ─────────────────
        for sel in [
            "[class*='date']", "[class*='Date']",
            "time", "[class*='published']",
            "[class*='created']", "[class*='ago']",
            "[datetime]",
        ]:
            e = page.query_selector(sel)
            if e:
                # Intentar atributo datetime primero (mas preciso)
                dt = e.get_attribute("datetime")
                texto = dt or e.inner_text().strip()
                if texto:
                    detalle["fecha_publicacion"] = texto
                    break

        # ── Vistas ────────────────────────────
        for sel in [
            "[class*='view']", "[class*='View']",
            "[class*='visit']", "[class*='seen']",
            "[class*='vista']", "[class*='contador']",
        ]:
            e = page.query_selector(sel)
            if e:
                texto = e.inner_text().strip()
                # Extraer solo el número
                nums = re.findall(r'\d+', texto)
                if nums:
                    detalle["vistas"] = int(nums[0])
                    break

        # ── Imágenes ──────────────────────────
        imagenes = []
        for sel in [
            "img[class*='photo']", "img[class*='Photo']",
            "img[class*='image']", "img[class*='gallery']",
            "[class*='gallery'] img", "[class*='carousel'] img",
            "[class*='slider'] img", "figure img",
        ]:
            imgs = page.query_selector_all(sel)
            for img in imgs:
                src = img.get_attribute("src") or img.get_attribute("data-src")
                if src and src.startswith("http") and src not in imagenes:
                    # Filtrar iconos y logos pequeños
                    if not any(x in src for x in ["icon", "logo", "avatar", "flag"]):
                        imagenes.append(src)

        detalle["imagenes"] = imagenes[:10]  # max 10 imagenes

        # ── Buscar teléfonos en título también ──
        telefonos_titulo = extraer_telefono_texto(detalle.get("titulo", ""))
        todos_telefonos = list(set(
            detalle.get("telefonos_en_texto", []) + telefonos_titulo
        ))
        detalle["telefonos_en_texto"] = todos_telefonos

        # Si no encontró teléfono oficial pero hay en texto, usar ese
        if not detalle["telefono"] and todos_telefonos:
            detalle["telefono"] = todos_telefonos[0]

    except Exception as e:
        logger.warning(f"Error extrayendo detalle: {e}")

    return detalle


# ─────────────────────────────────────────
# SCRAPER DE DETALLE PRINCIPAL
# ─────────────────────────────────────────

def scrape_detalles_categoria(categoria: str, max_anuncios: int = None):
    """
    Entra a cada anuncio de una categoria y extrae el detalle completo.
    Reanuda automaticamente si se interrumpe.
    """
    print(f"\n{'='*55}")
    print(f"  DETALLE: {categoria.upper()}")
    print(f"{'='*55}")

    # Cargar URLs del raw
    anuncios_raw = cargar_urls_categoria(categoria)
    if not anuncios_raw:
        return 0

    # Ver cuales ya procesamos (para reanudar)
    urls_procesadas = cargar_urls_procesadas(categoria)
    detalles_existentes = cargar_detalle_existente(categoria)

    # Filtrar solo los pendientes
    pendientes = [a for a in anuncios_raw if a.get("url") not in urls_procesadas]

    if max_anuncios:
        pendientes = pendientes[:max_anuncios]

    print(f"  ⏳ Pendientes: {len(pendientes)} anuncios")

    if not pendientes:
        print("  ✅ Todos los anuncios ya tienen detalle")
        return len(detalles_existentes)

    detalles_nuevos = []
    errores = 0

    with sync_playwright() as p:
        browser, context = get_browser_context(p, headless=True)

        if cargar_cookies(context):
            print("  🍪 Sesion cargada")

        page = context.new_page()

        for i, anuncio in enumerate(pendientes):
            url = anuncio.get("url")
            if not url:
                continue

            # Asegurar URL completa
            if not url.startswith("http"):
                url = REVOLICO_BASE_URL + url

            print(f"  [{i+1}/{len(pendientes)}] {anuncio.get('titulo', '')[:50]}...")

            try:
                # Navegar al anuncio
                ok = False
                for intento in range(3):
                    try:
                        page.goto(url, timeout=90000)
                        page.wait_for_load_state("domcontentloaded", timeout=90000)
                        ok = True
                        break
                    except Exception as e:
                        if intento < 2:
                            print(f"    ⚠️  Red inestable, reintentando... ({intento+1}/3)")
                            time.sleep((intento + 1) * 5)
                        else:
                            raise e

                if not ok:
                    errores += 1
                    continue

                time.sleep(1.5)

                # Verificar captcha
                if tiene_captcha(page):
                    print("  ⚠️  Captcha detectado — guardando progreso...")
                    logger.warning("Captcha en detalle — guardando y pausando")

                    # Guardar lo que llevamos
                    _guardar_detalles(detalles_existentes + detalles_nuevos, categoria)

                    browser.close()
                    borrar_sesion()

                    # Resolver captcha
                    ok_c = resolver_captcha_manual(url)
                    if not ok_c:
                        print("❌ No se pudo resolver captcha")
                        return len(detalles_existentes) + len(detalles_nuevos)

                    # Reiniciar browser con nueva sesion
                    browser2, context2 = get_browser_context(p, headless=True)
                    cargar_cookies(context2)
                    page = context2.new_page()
                    page.goto(url, timeout=90000)
                    page.wait_for_load_state("domcontentloaded", timeout=90000)
                    time.sleep(2)

                # Extraer detalle
                detalle = extraer_detalle_anuncio(page, anuncio)
                detalles_nuevos.append(detalle)

                # Mostrar lo que encontramos
                tel = detalle.get("telefono") or (detalle.get("telefonos_en_texto") or ["—"])[0]
                prov = detalle.get("provincia") or "—"
                vend = detalle.get("vendedor") or "—"
                print(f"    📞 {tel}  📍 {prov}  👤 {vend}")

                # Guardar cada 50 anuncios por si se interrumpe
                if (i + 1) % 50 == 0:
                    _guardar_detalles(detalles_existentes + detalles_nuevos, categoria)
                    print(f"  💾 Progreso guardado: {len(detalles_existentes) + len(detalles_nuevos)} total")

                # Pausa entre requests
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)

            except Exception as e:
                logger.warning(f"Error en {url}: {e}")
                print(f"    ❌ Error: {str(e)[:60]}")
                errores += 1

                # Si hay muchos errores seguidos, pausar
                if errores > 10:
                    print("  ⚠️  Muchos errores seguidos, pausando 30s...")
                    time.sleep(30)
                    errores = 0

        try:
            context.close()
            browser.close()
        except:
            pass

    # Guardar resultado final
    todos = detalles_existentes + detalles_nuevos
    _guardar_detalles(todos, categoria)

    print(f"\n  ✅ Detalle completado: {len(todos)} anuncios con detalle")
    return len(todos)


def _guardar_detalles(detalles: list, categoria: str):
    """Guarda el archivo de detalle de una categoria"""
    if not detalles:
        return

    archivo = RAW_REVOLICO / f"detalle_{categoria}.json"
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(detalles, f, ensure_ascii=False, indent=2)
    logger.info(f"Detalle guardado: {archivo} ({len(detalles)} anuncios)")


# ─────────────────────────────────────────
# RESUMEN
# ─────────────────────────────────────────

def mostrar_resumen(resultados: dict):
    print("\n" + "="*55)
    print("  RESUMEN — SCRAPER DE DETALLE")
    print("="*55)
    total = 0
    for cat, cantidad in resultados.items():
        icono = "✅" if cantidad > 0 else "⏭️ "
        print(f"  {icono} {cat:<15} {cantidad} anuncios con detalle")
        total += cantidad
    print(f"{'─'*55}")
    print(f"  📊 TOTAL: {total} anuncios procesados")
    print("="*55)
    print(f"\n  📁 Archivos guardados en:")
    print(f"  {RAW_REVOLICO}")
    print(f"  Busca los archivos: detalle_CATEGORIA.json")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    crear_estructura()

    # ← Pon aqui las categorias que quieres procesar
    # Empieza con una para probar, luego agrega el resto
    CATEGORIAS = [
        "ram", "disco", "monitor", "laptop", "pc",
        "cpu", "gpu", "modem", "motherboard", "chasis",
        "impresora", "teclado", "webcam", "sonido",
        "ups", "dvd", "cd", "internet", "otros"
    ]

    # MAX_ANUNCIOS = None  ← procesa todos
    # MAX_ANUNCIOS = 100   ← para probar rapido
    MAX_ANUNCIOS = 20

    print("\n" + "="*55)
    print("  CUBA PRECIOS — SCRAPER DE DETALLE")
    print("="*55)
    print(f"  Categorias: {len(CATEGORIAS)}")
    print(f"  Modo: {'COMPLETO' if not MAX_ANUNCIOS else f'PRUEBA ({MAX_ANUNCIOS} por cat)'}")
    print("="*55)

    resultados = {}

    for cat in CATEGORIAS:
        # Verificar que existe el raw
        archivos_raw = list(RAW_REVOLICO.glob(f"*_{cat}.json"))
        archivos_raw = [a for a in archivos_raw if "detalle" not in a.name]

        if not archivos_raw:
            print(f"\n⚠️  Sin datos raw para '{cat}' — ejecuta primero scraping_revolico.py")
            resultados[cat] = 0
            continue

        cantidad = scrape_detalles_categoria(cat, max_anuncios=MAX_ANUNCIOS)
        resultados[cat] = cantidad

        # Pausa entre categorias
        if cat != CATEGORIAS[-1]:
            pausa = random.uniform(5, 10)
            print(f"\n⏳ Pausa entre categorias: {pausa:.1f}s")
            time.sleep(pausa)

    mostrar_resumen(resultados)