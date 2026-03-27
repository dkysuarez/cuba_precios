"""
Scraper Facebook — CubaPrecios v3 MEJORADO
- Login manual con espera infinita hasta que confirmes verificación
- El browser NO se cierra hasta que termines manualmente
- Detecta automáticamente cuando la sesión está lista
"""

import json
import re
import time
import random
import sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Playwright, TimeoutError
from loguru import logger

sys.path.append(str(Path(__file__).resolve().parent))
from cuba_precios.config import RAW_FACEBOOK, LOGS_DIR, BASE_DIR, crear_estructura

# ─────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)
RAW_FACEBOOK.mkdir(parents=True, exist_ok=True)

logger.add(
    str(LOGS_DIR / "scraper_facebook.log"),
    rotation="10 MB", retention="7 days",
    level="INFO", encoding="utf-8"
)

COOKIES_FILE    = BASE_DIR / "facebook_cookies.json"
PROGRESO_FILE   = RAW_FACEBOOK / "progreso_grupos.json"

# ─────────────────────────────────────────
# GRUPOS — los 15 que tienes
# ─────────────────────────────────────────
GRUPOS = [
    {"id": "297240078588766",   "nombre": "PC Habana compra venta",           "provincia": "La Habana"},
    {"id": "1111660586685813",  "nombre": "Cuba Laptop",                       "provincia": "La Habana"},
    {"id": "1182752842088373",  "nombre": "Cuba PC",                           "provincia": "La Habana"},
    {"id": "947838842958500",   "nombre": "Laptop Gaming Habana",              "provincia": "La Habana"},
    {"id": "292258926111708",   "nombre": "Piezas PC Moviles Laptop Habana",   "provincia": "La Habana"},
    {"id": "910742393258328",   "nombre": "Piezas y Accesorios PC Laptop",     "provincia": "La Habana"},
    {"id": "3214321075381359",  "nombre": "Ventas PC Cuba Habana",             "provincia": "La Habana"},
    {"id": "407361857472194",   "nombre": "Compra Venta PC La Habana",         "provincia": "La Habana"},
    {"id": "1020254828028432",  "nombre": "Cuba PC Gamer",                     "provincia": "La Habana"},
    {"id": "443378673477491",   "nombre": "Habana PC Componentes",             "provincia": "La Habana"},
    {"id": "403415329280846",   "nombre": "Compra Venta Laptop PC La Habana",  "provincia": "La Habana"},
    {"id": "738418240391571",   "nombre": "Venta PC Hardware Villa Clara",     "provincia": "Villa Clara"},
    {"id": "709671433013368",   "nombre": "Computadoras PC Las Tunas",         "provincia": "Las Tunas"},
    {"id": "379380940360093",   "nombre": "Santiago Cuba Comprar Vender PC",   "provincia": "Santiago de Cuba"},
    {"id": "157544866178244",   "nombre": "Todo PC Santiago de Cuba",          "provincia": "Santiago de Cuba"},
]


# ─────────────────────────────────────────
# SESION / COOKIES
# ─────────────────────────────────────────

def guardar_cookies(context):
    cookies = context.cookies()
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print("✅ Sesion de Facebook guardada")
    logger.info("Cookies guardadas")


def cargar_cookies(context) -> bool:
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        logger.info("Cookies cargadas")
        return True
    return False


def sesion_existe() -> bool:
    return COOKIES_FILE.exists()


def borrar_sesion():
    if COOKIES_FILE.exists():
        COOKIES_FILE.unlink()
        logger.info("Sesion borrada")


# ─────────────────────────────────────────
# PROGRESO — para reanudar si se corta
# ─────────────────────────────────────────

def cargar_progreso() -> dict:
    if PROGRESO_FILE.exists():
        with open(PROGRESO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_progreso(progreso: dict):
    with open(PROGRESO_FILE, "w", encoding="utf-8") as f:
        json.dump(progreso, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────
# BROWSER
# ─────────────────────────────────────────

def nuevo_browser(p: Playwright, headless=True):
    browser = p.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
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
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = {runtime: {}};
    """)
    return browser, context


# ─────────────────────────────────────────
# LOGIN MANUAL MEJORADO — CON ESPERA Y SIN ERRORES
# ─────────────────────────────────────────

def hacer_login(p: Playwright) -> bool:
    """
    Abre browser visible para que el usuario haga login.
    Espera hasta que el usuario presione ENTER y luego espera que la página se estabilice.
    """
    print("\n" + "="*55)
    print("  INICIA SESION EN FACEBOOK")
    print("="*55)
    print("  1. Se abre el browser ahora")
    print("  2. Escribe tu usuario y contrasena")
    print("  3. Si te pide verificación (teléfono/correo), confírmala")
    print("  4. Espera a ver tu feed de Facebook")
    print("  5. Presiona ENTER cuando termines")
    print("="*55 + "\n")

    browser, context = nuevo_browser(p, headless=False)
    page = context.new_page()

    try:
        # Ir a la página de login
        page.goto("https://www.facebook.com/login", timeout=60000)
        print("✅ Login page abierta")
        print("📱 Completa el login en el browser...")
        print("   Si te pide verificar con tu teléfono, hazlo ahora.")
        print("   Espera a ver tu feed de Facebook.\n")

        # ESPERA INFINITA hasta que el usuario presione ENTER
        input("🔐 Cuando hayas terminado el login, PRESIONA ENTER para continuar...\n")

        # Esperar a que la página termine de cargar/estabilizarse
        print("⏳ Esperando a que la página se estabilice...")

        # Intentar esperar hasta que la navegación termine
        try:
            # Esperar hasta que no haya navegación activa
            page.wait_for_load_state("networkidle", timeout=30000)
            print("✅ Página completamente cargada")
        except Exception:
            print("⚠️  Timeout esperando carga, pero continuamos...")

        # Esperar un poco extra para asegurar
        time.sleep(3)

        # Verificar que estamos en una página válida y logueada
        try:
            current_url = page.url
            print(f"📍 URL actual: {current_url[:80]}")

            # Verificar si estamos en una página de checkpoint (verificación)
            if "checkpoint" in current_url:
                print("⚠️  Aún hay verificación pendiente. Espera más tiempo...")
                input("Presiona ENTER cuando hayas completado la verificación...")
                # Esperar de nuevo
                time.sleep(2)
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
                except:
                    pass

            # Verificar si aún estamos en login
            if "/login" in page.url:
                print("⚠️  Parece que sigues en la página de login.")
                respuesta = input("¿Quieres esperar más? (s/n): ").lower()
                if respuesta == 's':
                    input("Presiona ENTER cuando hayas terminado...")
                    time.sleep(3)
                else:
                    print("❌ Login no completado")
                    context.close()
                    browser.close()
                    return False

        except Exception as e:
            print(f"⚠️  Error verificando URL: {e}")
            # Continuamos de todos modos, puede que la página esté en medio de una redirección

        # Intentar obtener el contenido sin errores
        print("✅ Login completado — guardando sesion...")
        time.sleep(2)  # Pequeña pausa extra

        # Guardar cookies
        guardar_cookies(context)
        print("💾 Cookies guardadas exitosamente")

        # Mantener el browser abierto un momento más
        print("✅ Todo listo. Cerrando browser...")

        context.close()
        browser.close()
        return True

    except Exception as e:
        logger.error(f"Error login: {e}")
        print(f"❌ Error: {e}")
        print("   Esto puede ocurrir si la página se cerró antes de tiempo.")
        try:
            context.close()
            browser.close()
        except:
            pass
        return False


# ─────────────────────────────────────────
# DETECCION
# ─────────────────────────────────────────

def esta_logueado(page) -> bool:
    try:
        url = page.url
        if "/login" in url or "checkpoint" in url:
            return False
        # Buscar elementos que solo aparecen logueado
        for sel in ["[aria-label='Facebook']", "div[role='feed']", "[aria-label='Tu perfil']"]:
            try:
                if page.query_selector(sel):
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def tiene_captcha_o_bloqueo(page) -> bool:
    try:
        url = page.url
        contenido = page.content().lower()
        return (
            "checkpoint" in url or
            "security" in url or
            "esta cuenta fue bloqueada" in contenido or
            "your account has been locked" in contenido or
            "confirma tu identidad" in contenido
        )
    except Exception:
        return False


# ─────────────────────────────────────────
# EXTRACCION DE POSTS
# ─────────────────────────────────────────

def extraer_telefonos(texto: str) -> list:
    """Extrae numeros de telefono cubanos del texto"""
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


def extraer_precio(texto: str) -> tuple:
    """Extrae precio y moneda del texto del post"""
    if not texto:
        return None, None

    t = texto.lower()

    patrones = [
        (r'[\$]?\s*(\d{2,6})\s*(?:usd|dolar|dolares|dólares|fula|divisa)', "usd"),
        (r'(\d{2,6})\s*(?:mlc)', "mlc"),
        (r'(\d{3,7})\s*(?:cup|pesos?|mn\b|kukis?|moneda nacional)', "cup"),
        (r'(?:en|precio|a|por)\s*[\$]?\s*(\d{2,6})\s*(?:usd|dolar|dolares)?', "usd"),
        (r'(\d{2,6})\s*(?:usd|dolar)', "usd"),
    ]

    for patron, moneda in patrones:
        match = re.search(patron, t)
        if match:
            try:
                valor = float(match.group(1))
                if 1 < valor < 100000:
                    return valor, moneda
            except (ValueError, IndexError):
                continue

    return None, None


def detectar_tipo_equipo(texto: str) -> str:
    """Detecta el tipo de equipo mencionado en el post"""
    t = texto.lower()
    tipos = [
        ("laptop",      ["laptop", "laptops", "notebook", "macbook"]),
        ("pc",          ["pc gamer", "pc gaming", "torre pc", "computadora", "desktop"]),
        ("monitor",     ["monitor", "pantalla led", "pantalla curva"]),
        ("ram",         ["memoria ram", "ram ddr", "ddr4", "ddr3", "ddr5"]),
        ("disco",       ["disco duro", "disco ssd", "ssd ", " ssd", "nvme", "hdd"]),
        ("cpu",         ["procesador", "microprocesador", "intel core", "ryzen", " i5 ", " i7 ", " i3 "]),
        ("gpu",         ["tarjeta de video", "tarjeta grafica", "gtx", "rtx", "radeon"]),
        ("motherboard", ["motherboard", "placa madre", "placa base"]),
        ("teclado",     ["teclado", "mouse ", " mouse", "combo teclado"]),
        ("modem",       ["router", "modem", "wifi", "tp-link", "mikrotik"]),
        ("impresora",   ["impresora", "toner", "cartucho", "laserjet"]),
        ("chasis",      ["chasis", "fuente de poder", "gabinete", "disipador"]),
        ("ups",         ["ups ", " ups", "no break", "regulador"]),
        ("webcam",      ["webcam", "camara web", "audifonos", "headset"]),
        ("sonido",      ["bocina", "parlante", "speaker", "subwoofer"]),
    ]
    for tipo, palabras in tipos:
        for palabra in palabras:
            if palabra in t:
                return tipo
    return "otros"


def extraer_posts_de_pagina(page, grupo: dict) -> list:
    """Extrae todos los posts visibles en la pagina actual del grupo."""
    posts = []

    selectores_post = [
        "div[data-pagelet^='GroupFeed'] div[role='article']",
        "div[role='feed'] > div",
        "div[data-testid='fbfeed_story']",
        "div[role='article']",
    ]

    elementos = []
    for sel in selectores_post:
        try:
            elementos = page.query_selector_all(sel)
            if len(elementos) > 2:
                logger.info(f"Selector '{sel}': {len(elementos)} posts")
                break
        except Exception:
            continue

    if not elementos:
        try:
            debug = RAW_FACEBOOK / f"debug_{grupo['id']}_{datetime.now().strftime('%H%M%S')}.html"
            debug.write_text(page.content(), encoding="utf-8")
            print(f"  ⚠️  Sin posts detectados. HTML guardado: {debug.name}")
        except Exception:
            pass
        return posts

    for elem in elementos:
        try:
            texto = ""
            for sel_texto in [
                "div[data-ad-preview='message']",
                "div[dir='auto']",
                "div[data-testid='post_message']",
                "span[dir='auto']",
            ]:
                try:
                    e = elem.query_selector(sel_texto)
                    if e:
                        t = e.inner_text().strip()
                        if len(t) > len(texto):
                            texto = t
                except Exception:
                    continue

            if not texto or len(texto) < 10:
                try:
                    texto = elem.inner_text().strip()
                except Exception:
                    continue

            if len(texto) < 10:
                continue

            url_post = None
            try:
                links = elem.query_selector_all("a[href*='/posts/'], a[href*='/permalink/']")
                for link in links:
                    href = link.get_attribute("href") or ""
                    if "/posts/" in href or "/permalink/" in href:
                        url_post = href.split("?")[0]
                        if not url_post.startswith("http"):
                            url_post = "https://www.facebook.com" + url_post
                        break
            except Exception:
                pass

            fecha_post = None
            try:
                for sel_fecha in ["abbr[data-utime]", "a[role='link'] span", "span[id*='jsc']"]:
                    e = elem.query_selector(sel_fecha)
                    if e:
                        fecha_post = e.get_attribute("data-utime") or e.inner_text().strip()
                        if fecha_post:
                            break
            except Exception:
                pass

            autor = None
            try:
                for sel_autor in [
                    "h2 a", "h3 a", "strong a",
                    "span[dir='auto'] a", "a[aria-label]"
                ]:
                    e = elem.query_selector(sel_autor)
                    if e:
                        texto_autor = e.inner_text().strip()
                        if texto_autor and len(texto_autor) > 1 and len(texto_autor) < 80:
                            autor = texto_autor
                            break
            except Exception:
                pass

            telefonos = extraer_telefonos(texto)
            precio, moneda = extraer_precio(texto)
            tipo_equipo = detectar_tipo_equipo(texto)

            post = {
                "url":             url_post or f"https://www.facebook.com/groups/{grupo['id']}",
                "contenido":       texto[:2000],
                "autor":           autor,
                "fecha_post":      fecha_post,
                "telefonos":       telefonos,
                "precio":          precio,
                "moneda":          moneda,
                "tipo_equipo":     tipo_equipo,
                "provincia":       grupo["provincia"],
                "grupo_nombre":    grupo["nombre"],
                "grupo_id":        grupo["id"],
                "fecha_extraccion": datetime.now().isoformat(),
            }

            if telefonos or precio:
                posts.append(post)

        except Exception as e:
            logger.warning(f"Error extrayendo post: {e}")
            continue

    return posts


def scroll_y_extraer(page, grupo: dict, max_scrolls: int = 50) -> list:
    """Hace scroll infinito en el grupo y extrae posts progresivamente."""
    todos_posts = []
    urls_vistas = set()
    sin_nuevos_count = 0

    print(f"  Iniciando scroll en: {grupo['nombre']}")

    for scroll_num in range(max_scrolls):
        posts_pagina = extraer_posts_de_pagina(page, grupo)

        posts_nuevos = []
        for p in posts_pagina:
            url = p.get("url", "")
            clave = url or p.get("contenido", "")[:100]
            if clave not in urls_vistas:
                urls_vistas.add(clave)
                posts_nuevos.append(p)

        if posts_nuevos:
            todos_posts.extend(posts_nuevos)
            sin_nuevos_count = 0
            print(f"  Scroll {scroll_num+1}/{max_scrolls} — "
                  f"+{len(posts_nuevos)} posts nuevos "
                  f"(total: {len(todos_posts)})")
        else:
            sin_nuevos_count += 1
            print(f"  Scroll {scroll_num+1}/{max_scrolls} — sin posts nuevos ({sin_nuevos_count}/5)")

        if sin_nuevos_count >= 5:
            print(f"  ✅ Sin contenido nuevo — terminando grupo")
            break

        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(random.uniform(2.5, 4.0))

            for sel in [
                "div[role='button']:has-text('Ver más publicaciones')",
                "div[role='button']:has-text('Ver más')",
                "a:has-text('Ver más publicaciones')",
            ]:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click()
                        time.sleep(2)
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Error scroll: {e}")
            break

        if (scroll_num + 1) % 10 == 0:
            guardar_json_grupo(todos_posts, grupo)
            print(f"  💾 Guardado parcial: {len(todos_posts)} posts")

    return todos_posts


def guardar_json_grupo(posts: list, grupo: dict):
    """Guarda los posts de un grupo en JSON"""
    if not posts:
        return

    nombre_limpio = re.sub(r'[^a-z0-9]', '_', grupo['nombre'].lower())
    archivo = RAW_FACEBOOK / f"grupo_{grupo['id']}_{nombre_limpio}.json"

    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    logger.info(f"Guardado: {archivo.name} ({len(posts)} posts)")


def scrape_grupo(grupo: dict, page, p: Playwright) -> list:
    """Scrapea un grupo completo"""
    url_grupo = f"https://www.facebook.com/groups/{grupo['id']}"
    print(f"\n{'─'*55}")
    print(f"  Grupo: {grupo['nombre']}")
    print(f"  Provincia: {grupo['provincia']}")
    print(f"  URL: {url_grupo}")
    print(f"{'─'*55}")

    for intento in range(3):
        try:
            page.goto(url_grupo, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            time.sleep(3)
            break
        except Exception as e:
            if intento < 2:
                print(f"  ⚠️  Red inestable, reintentando ({intento+1}/3)...")
                time.sleep(5)
            else:
                print(f"  ❌ No se pudo cargar el grupo")
                return []

    if not esta_logueado(page):
        print("  ⚠️  Sesion expirada")
        return []

    if tiene_captcha_o_bloqueo(page):
        print("  ⚠️  Bloqueo detectado — pausa larga...")
        time.sleep(60)
        return []

    contenido = page.content().lower()
    if "unirse al grupo" in contenido or "join group" in contenido:
        print("  ⚠️  No eres miembro de este grupo — saltando")
        return []

    posts = scroll_y_extraer(page, grupo, max_scrolls=100)
    guardar_json_grupo(posts, grupo)

    print(f"\n  ✅ {grupo['nombre']}: {len(posts)} posts con datos")
    return posts


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    crear_estructura()

    print("\n" + "="*55)
    print("  CUBA PRECIOS — SCRAPER FACEBOOK v3")
    print("  Login manual + extraccion completa")
    print("="*55)
    print(f"  Grupos: {len(GRUPOS)}")
    print(f"  Datos en: {RAW_FACEBOOK}")
    print("="*55)

    progreso = cargar_progreso()
    grupos_completados = set(progreso.get("completados", []))

    if grupos_completados:
        print(f"\n  ♻️  Grupos ya procesados: {len(grupos_completados)}")
        print(f"  Pendientes: {len(GRUPOS) - len(grupos_completados)}")

    with sync_playwright() as p:

        # ── Login MEJORADO con espera manual ────────────
        if not sesion_existe():
            print("\n🔐 Necesitas iniciar sesion en Facebook")
            print("   Cuando te pida verificar con tu teléfono, hazlo desde el browser")
            print("   El browser NO se cerrará hasta que presiones ENTER\n")

            ok = hacer_login(p)
            if not ok:
                print("❌ Login fallido. Vuelve a intentarlo.")
                return
        else:
            print("\n✅ Sesion existente encontrada")
            # Verificar que la sesión sigue siendo válida
            browser, context = nuevo_browser(p, headless=False)
            if cargar_cookies(context):
                page = context.new_page()
                try:
                    page.goto("https://www.facebook.com", timeout=30000)
                    time.sleep(3)
                    if not esta_logueado(page):
                        print("⚠️  Sesión expirada, necesitas hacer login de nuevo")
                        borrar_sesion()
                        context.close()
                        browser.close()
                        ok = hacer_login(p)
                        if not ok:
                            return
                    else:
                        print("✅ Sesión válida")
                        context.close()
                        browser.close()
                except:
                    context.close()
                    browser.close()
            else:
                browser.close()

        # ── Browser headless con cookies ─────
        browser, context = nuevo_browser(p, headless=True)
        if not cargar_cookies(context):
            print("❌ No se pudieron cargar las cookies")
            browser.close()
            return

        page = context.new_page()

        # Verificar que el login sigue activo
        print("\n🔄 Verificando sesion...")
        try:
            page.goto("https://www.facebook.com", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            time.sleep(3)

            if not esta_logueado(page):
                print("⚠️  Sesion expirada — necesitas hacer login de nuevo")
                context.close()
                browser.close()
                borrar_sesion()
                ok = hacer_login(p)
                if not ok:
                    return
                browser, context = nuevo_browser(p, headless=True)
                cargar_cookies(context)
                page = context.new_page()
            else:
                print("✅ Sesion activa")

        except Exception as e:
            print(f"❌ Error verificando sesion: {e}")
            browser.close()
            return

        # ── Scrapear grupos ──────────────────
        resultados_totales = {}
        total_posts = 0

        for idx, grupo in enumerate(GRUPOS):
            grupo_id = grupo["id"]

            if grupo_id in grupos_completados:
                print(f"\n  ⏭️  Ya procesado: {grupo['nombre']}")
                continue

            try:
                posts = scrape_grupo(grupo, page, p)
                resultados_totales[grupo_id] = len(posts)
                total_posts += len(posts)

                grupos_completados.add(grupo_id)
                progreso["completados"] = list(grupos_completados)
                progreso["ultima_actualizacion"] = datetime.now().isoformat()
                guardar_progreso(progreso)

            except Exception as e:
                logger.error(f"Error en grupo {grupo['nombre']}: {e}")
                print(f"  ❌ Error: {e}")

            if idx < len(GRUPOS) - 1:
                pausa = random.uniform(8, 15)
                print(f"\n  ⏳ Pausa entre grupos: {pausa:.0f}s")
                time.sleep(pausa)

        try:
            context.close()
            browser.close()
        except Exception:
            pass

        # ── Resumen ──────────────────────────
        print("\n" + "="*55)
        print("  RESUMEN FINAL")
        print("="*55)
        print(f"  Total posts extraidos: {total_posts}")
        print(f"\n  Por grupo:")
        for grupo in GRUPOS:
            n = resultados_totales.get(grupo["id"], "ya procesado")
            print(f"    {grupo['nombre'][:40]:<42} {n}")
        print(f"\n  📁 Datos en: {RAW_FACEBOOK}")
        print("="*55)
        print("\n  ✅ Listo. Ahora corre: python limpiar_datos.py")


if __name__ == "__main__":
    main()