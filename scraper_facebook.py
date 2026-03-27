"""
Scraper de Facebook usando Selenium - VERSIÓN CORREGIDA CON BEAUTIFULSOUP
"""

import json
import time
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup  # <--- ESTA ES LA IMPORTACIÓN QUE FALTABA

# Configuración
BASE_DIR = Path(__file__).resolve().parent
RAW_FACEBOOK = BASE_DIR / "data" / "raw" / "facebook_selenium"
LOGS_DIR = BASE_DIR / "logs"

RAW_FACEBOOK.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────

EQUIPOS = [
    "laptop", "pc", "computadora", "torre", "cpu", "monitor",
    "teclado", "mouse", "ram", "disco duro", "ssd", "tarjeta gráfica",
    "gpu", "laptop lenovo", "laptop hp", "pc gamer"
]

PROVINCIAS = [
    "La Habana", "Habana", "Artemisa", "Mayabeque", "Matanzas",
    "Cienfuegos", "Villa Clara", "Sancti Spíritus", "Ciego de Ávila",
    "Camagüey", "Las Tunas", "Holguín", "Granma", "Santiago de Cuba",
    "Guantánamo", "Pinar del Río"
]

# ─────────────────────────────────────────────────────────────

class FacebookSeleniumScraper:
    def __init__(self):
        self.driver = None
        self.urls_procesadas = self.cargar_urls_procesadas()

    def iniciar_navegador(self):
        """Iniciar Chrome con opciones anti-detección"""
        chrome_options = Options()

        # Opciones para evitar detección
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Opciones de rendimiento
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        # User agent real
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # Tamaño de ventana
        chrome_options.add_argument("--window-size=1366,768")

        self.driver = webdriver.Chrome(options=chrome_options)

        # Ejecutar script para ocultar webdriver
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        return self.driver

    def cargar_urls_procesadas(self):
        archivo = RAW_FACEBOOK / "urls_procesadas.json"
        if archivo.exists():
            try:
                with open(archivo, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except:
                return set()
        return set()

    def guardar_url_procesada(self, url):
        self.urls_procesadas.add(url)
        archivo = RAW_FACEBOOK / "urls_procesadas.json"
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(list(self.urls_procesadas), f, ensure_ascii=False, indent=2)

    def extraer_urls_facebook_de_pagina(self) -> List[str]:
        """Extraer URLs de Facebook de la página actual de Google"""
        urls = []

        try:
            # Buscar todos los enlaces en la página
            enlaces = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'facebook.com/groups')]")

            for elem in enlaces:
                try:
                    href = elem.get_attribute("href")
                    if href and "facebook.com/groups" in href:
                        # Limpiar URL
                        if "&" in href:
                            href = href.split("&")[0]
                        if "?" in href:
                            href = href.split("?")[0]
                        # Ignorar URLs de Google
                        if "google.com" not in href and href not in urls:
                            urls.append(href)
                except StaleElementReferenceException:
                    continue

        except Exception as e:
            print(f"      Error extrayendo URLs: {e}")

        return urls

    def buscar_en_google(self, query: str, max_resultados: int = 10) -> List[str]:
        """
        Buscar en Google usando Selenium (navegador real)
        """
        urls = []

        try:
            # Ir a Google
            self.driver.get("https://www.google.com")
            time.sleep(random.uniform(2, 3))

            # Buscar el campo de búsqueda
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )

            # Limpiar y escribir la consulta
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)

            time.sleep(random.uniform(3, 5))

            # Recoger URLs de resultados
            for pagina in range(2):  # Máximo 2 páginas
                # Extraer URLs de la página actual
                nuevas_urls = self.extraer_urls_facebook_de_pagina()

                for url in nuevas_urls:
                    if url not in urls:
                        urls.append(url)

                print(f"      Encontradas {len(urls)} URLs de Facebook hasta ahora")

                if len(urls) >= max_resultados:
                    break

                # Intentar ir a la siguiente página
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, "a#pnnext")
                    if next_button.is_enabled():
                        next_button.click()
                        time.sleep(random.uniform(3, 5))
                    else:
                        break
                except:
                    break

        except Exception as e:
            print(f"      ❌ Error en búsqueda: {e}")

        return urls[:max_resultados]

    def extraer_contenido_post(self, url: str) -> str:
        """Extraer el contenido de un post de Facebook"""
        try:
            self.driver.get(url)
            time.sleep(random.uniform(3, 5))

            # Obtener el HTML
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # Extraer texto de la página
            page_text = soup.get_text()

            # Intentar encontrar el contenido del post
            post_content = ""

            # Buscar diferentes selectores de contenido
            selectores = [
                'div[data-ad-preview="message"]',
                'div[data-testid="post_message"]',
                'div[class*="x1lliihq"]',
                'div[dir="auto"]'
            ]

            for selector in selectores:
                elementos = soup.select(selector)
                for elem in elementos:
                    texto = elem.get_text().strip()
                    if len(texto) > 20:
                        post_content = texto
                        break
                if post_content:
                    break

            # Si no encontró, usar el texto completo pero limitado
            if not post_content:
                # Intentar encontrar en el HTML con regex
                post_match = re.search(r'<div[^>]*data-testid="post_message"[^>]*>(.*?)</div>', html, re.DOTALL)
                if post_match:
                    post_content = re.sub(r'<[^>]+>', '', post_match.group(1)).strip()
                else:
                    post_content = page_text[:1500]

            return post_content

        except Exception as e:
            print(f"      Error cargando post: {e}")
            return ""

    def extraer_datos_post(self, url: str) -> Dict:
        """
        Extraer datos de un post de Facebook
        """
        try:
            # Obtener el contenido del post
            contenido = self.extraer_contenido_post(url)

            if not contenido:
                return {"error": "No se pudo extraer contenido", "url": url}

            # ── EXTRACCIÓN DE DATOS ──
            texto_completo = contenido.lower()

            # Teléfonos
            telefonos = self.extraer_telefonos(texto_completo)

            # Precio
            precio_info = self.extraer_precio(texto_completo)

            # Modelo/Marca
            modelo_info = self.extraer_modelo(texto_completo)

            # Provincia
            provincia = self.extraer_provincia(texto_completo)

            # Tipo de equipo
            tipo_equipo = self.extraer_tipo_equipo(texto_completo)

            # Especificaciones
            especificaciones = self.extraer_especificaciones(texto_completo)

            resultado = {
                "url": url,
                "contenido": contenido[:800],
                "telefonos": telefonos,
                "precio": precio_info["precio"],
                "moneda": precio_info["moneda"],
                "modelo": modelo_info["modelo"],
                "marca": modelo_info["marca"],
                "provincia": provincia,
                "tipo_equipo": tipo_equipo,
                "especificaciones": especificaciones,
                "fecha_extraccion": datetime.now().isoformat()
            }

            return resultado

        except Exception as e:
            return {"error": str(e), "url": url}

    def extraer_telefonos(self, texto: str) -> List[str]:
        """Extraer números de teléfono cubanos"""
        patrones = [
            r'\b5[0-9]{7}\b',
            r'\b[2-7][0-9]{6,7}\b',
            r'\+53\s?[0-9]{8}',
            r'\b53[0-9]{8}\b',
            r'(?:tel|whatsapp|wa|contacto)[:\s]*([0-9\s]{7,15})',
        ]

        numeros = []
        for patron in patrones:
            matches = re.findall(patron, texto, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                n_clean = re.sub(r'[\s\-\(\)]', '', str(match))
                if n_clean and len(n_clean) >= 7 and n_clean not in numeros:
                    numeros.append(n_clean)

        return numeros[:3]

    def extraer_precio(self, texto: str) -> Dict:
        """Extraer precio y moneda"""
        patrones = [
            (r'(\d+[\.,]?\d*)\s*(cup|mn|pesos?)', "cup"),
            (r'(\d+[\.,]?\d*)\s*(mlc)', "mlc"),
            (r'(\d+[\.,]?\d*)\s*(usd|dólar|dolar|\$)', "usd"),
            (r'precio[:;]\s*(\d+[\.,]?\d*)', "cup"),
            (r'(\d+[\.,]?\d*)\s*(cuc)', "cup"),
        ]

        for patron, moneda_default in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                precio_str = match.group(1).replace(',', '.')
                try:
                    precio = float(precio_str)
                    moneda = moneda_default
                    if len(match.groups()) > 1 and match.group(2):
                        moneda_raw = match.group(2).lower()
                        if "mlc" in moneda_raw:
                            moneda = "mlc"
                        elif "usd" in moneda_raw or "$" in moneda_raw:
                            moneda = "usd"
                    return {"precio": precio, "moneda": moneda}
                except:
                    continue

        return {"precio": None, "moneda": None}

    def extraer_modelo(self, texto: str) -> Dict:
        """Extraer modelo y marca"""
        modelo = None
        marca = None

        marcas = ["lenovo", "hp", "dell", "asus", "acer", "macbook", "thinkpad",
                  "ideapad", "pavilion", "inspiron", "vivobook", "ryzen", "intel",
                  "nvidia", "gtx", "rtx", "radeon"]

        for m in marcas:
            if m in texto:
                marca = m.upper()
                break

        patrones_modelo = [
            r'(thinkpad|ideapad|pavilion|inspiron|vivobook)\s*(\w*\d*)',
            r'(ryzen\s*\d+)',
            r'(core\s*i\d+)',
            r'(gtx|rtx)\s*(\d+)',
        ]

        for patron in patrones_modelo:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                modelo = match.group(0).upper()
                break

        return {"modelo": modelo, "marca": marca}

    def extraer_provincia(self, texto: str) -> Optional[str]:
        for provincia in PROVINCIAS:
            if provincia.lower() in texto:
                return provincia
        return None

    def extraer_tipo_equipo(self, texto: str) -> Optional[str]:
        tipos = {
            "laptop": ["laptop", "notebook", "portátil", "lenovo", "hp", "dell"],
            "pc": ["pc", "computadora", "torre", "cpu", "gabinete"],
            "monitor": ["monitor", "pantalla", "led"],
            "gpu": ["tarjeta gráfica", "tarjeta de video", "gpu", "gtx", "rtx"],
            "ram": ["memoria ram", "ram", "ddr"],
            "disco": ["disco duro", "ssd", "hdd"],
            "periferico": ["teclado", "mouse", "ratón"],
        }

        for tipo, palabras in tipos.items():
            for palabra in palabras:
                if palabra in texto:
                    return tipo
        return "otros"

    def extraer_especificaciones(self, texto: str) -> Dict:
        specs = {}

        ram_match = re.search(r'(\d+)\s*gb\s*ram', texto)
        if ram_match:
            specs["ram"] = f"{ram_match.group(1)}GB"

        proc_match = re.search(r'(i\d|ryzen\s*\d+|core\s*i\d)', texto, re.IGNORECASE)
        if proc_match:
            specs["procesador"] = proc_match.group(0).upper()

        disco_match = re.search(r'(\d+)\s*(gb|tb)\s*(ssd|hdd)?', texto)
        if disco_match:
            specs["disco"] = f"{disco_match.group(1)}{disco_match.group(2).upper()}"
            if disco_match.group(3):
                specs["disco"] += f" {disco_match.group(3).upper()}"

        return specs

    def buscar_todos_equipos(self, dias: int = 7, max_por_equipo: int = 8):
        """Buscar todos los equipos"""
        todos_resultados = []

        print(f"\n{'='*55}")
        print(f"  🔍 BUSCANDO EQUIPOS (últimos {dias} días)")
        print(f"{'='*55}")

        fecha_after = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")

        for idx, equipo in enumerate(EQUIPOS):
            print(f"\n📌 [{idx+1}/{len(EQUIPOS)}] Buscando: {equipo.upper()}")

            # Construir consulta
            query = f'"{equipo}" site:facebook.com/groups (venta OR vendo OR oferta) after:{fecha_after} -buscando -busco'
            print(f"   Query: {query[:80]}...")

            # Buscar en Google
            urls = self.buscar_en_google(query, max_resultados=max_por_equipo)

            # Filtrar URLs que son de Facebook
            urls_facebook = [u for u in urls if "facebook.com/groups" in u]
            print(f"   📊 URLs de Facebook: {len(urls_facebook)}")

            # Filtrar URLs nuevas
            urls_nuevas = [u for u in urls_facebook if u not in self.urls_procesadas]
            print(f"   🆕 Nuevas: {len(urls_nuevas)}")

            # Procesar cada URL
            for url_idx, url in enumerate(urls_nuevas[:max_por_equipo]):
                try:
                    print(f"      [{url_idx+1}] Extrayendo...")

                    datos = self.extraer_datos_post(url)

                    if datos and "error" not in datos:
                        if datos.get("telefonos") or datos.get("precio"):
                            datos["equipo_buscado"] = equipo
                            todos_resultados.append(datos)
                            self.guardar_url_procesada(url)

                            # Mostrar resumen
                            precio_str = f"{datos['precio']} {datos['moneda']}" if datos.get('precio') else "sin precio"
                            telefono_str = datos['telefonos'][0] if datos.get('telefonos') else "sin teléfono"
                            print(f"         ✅ {datos['tipo_equipo']} - {precio_str} - 📞 {telefono_str}")
                        else:
                            print(f"         ⚠️  Sin datos relevantes")
                    else:
                        error_msg = datos.get('error', 'desconocido') if datos else 'sin datos'
                        print(f"         ❌ Error: {error_msg}")

                    time.sleep(random.uniform(2, 3))

                except Exception as e:
                    print(f"         ❌ Error procesando: {e}")
                    continue

            # Guardar progreso cada 3 equipos
            if (idx + 1) % 3 == 0 and todos_resultados:
                self.guardar_progreso(todos_resultados)

            # Pausa entre equipos
            if idx < len(EQUIPOS) - 1:
                pausa = random.uniform(5, 8)
                print(f"   ⏳ Pausa de {pausa:.0f}s...")
                time.sleep(pausa)

        return todos_resultados

    def guardar_progreso(self, resultados):
        """Guardar progreso parcial"""
        archivo = RAW_FACEBOOK / "progreso_parcial.json"
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Progreso guardado: {len(resultados)} resultados")

    def cerrar(self):
        if self.driver:
            self.driver.quit()

# ─────────────────────────────────────────────────────────────
# FUNCIONES DE GUARDADO
# ─────────────────────────────────────────────────────────

def guardar_resultados(resultados: List[Dict]):
    """Guardar resultados en JSON"""
    if not resultados:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_nuevo = RAW_FACEBOOK / f"facebook_ofertas_{timestamp}.json"

    with open(archivo_nuevo, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Guardados {len(resultados)} resultados en {archivo_nuevo.name}")

    archivo_ultimo = RAW_FACEBOOK / "ultimas_ofertas.json"
    with open(archivo_ultimo, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"💾 Actualizado: ultimas_ofertas.json")

def generar_reporte(resultados: List[Dict]):
    """Generar reporte con mejores ofertas"""
    if not resultados:
        print("\n❌ No se encontraron resultados")
        return

    print("\n" + "="*55)
    print("  📊 REPORTE DE OFERTAS RECIENTES")
    print("="*55)

    # Separar por tipo
    por_tipo = {}
    for r in resultados:
        tipo = r.get("tipo_equipo", "otros")
        if tipo not in por_tipo:
            por_tipo[tipo] = []
        por_tipo[tipo].append(r)

    print(f"\n📈 Resumen por tipo:")
    for tipo, items in por_tipo.items():
        print(f"   • {tipo}: {len(items)} publicaciones")

    # Mejores precios
    print(f"\n💰 MEJORES PRECIOS ENCONTRADOS:")

    for tipo, items in por_tipo.items():
        con_precio = [i for i in items if i.get("precio")]
        if con_precio:
            ordenados = sorted(con_precio, key=lambda x: x["precio"])
            mejor = ordenados[0]
            moneda = mejor.get('moneda', 'CUP').upper()
            print(f"\n📌 {tipo.upper()} - {mejor['precio']} {moneda}")
            print(f"   📝 {mejor.get('contenido', '')[:100]}...")
            if mejor.get('telefonos'):
                print(f"   📞 Teléfono: {mejor['telefonos'][0]}")
            if mejor.get('provincia'):
                print(f"   📍 Provincia: {mejor['provincia']}")
            print(f"   🔗 URL: {mejor.get('url', '')}")

    print(f"\n{'='*55}")

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def main():
    print("\n" + "="*55)
    print("  🚀 SCRAPER FACEBOOK CON SELENIUM")
    print("  Extrae ofertas RECIENTES sin login")
    print("="*55)

    # Configuración
    DIAS = 7
    MAX_POR_EQUIPO = 8

    print(f"\n⚙️  Configuración:")
    print(f"   • Días a buscar: {DIAS}")
    print(f"   • Máximo por equipo: {MAX_POR_EQUIPO}")
    print(f"   • Equipos a buscar: {len(EQUIPOS)}")

    scraper = None

    try:
        scraper = FacebookSeleniumScraper()
        scraper.iniciar_navegador()

        print("\n⚠️  Se abrirá el navegador. Por favor:")
        print("   1. Si Google pide captcha, resuélvelo manualmente")
        print("   2. Espera a que el script continúe")
        print("\n⏳ Iniciando en 3 segundos...")
        time.sleep(3)

        # Buscar todos los equipos
        resultados = scraper.buscar_todos_equipos(
            dias=DIAS,
            max_por_equipo=MAX_POR_EQUIPO
        )

        # Guardar y mostrar reporte
        if resultados:
            guardar_resultados(resultados)
            generar_reporte(resultados)
            print(f"\n✅ Proceso completado!")
            print(f"📁 Datos guardados en: {RAW_FACEBOOK}")
            print(f"📊 Total de ofertas: {len(resultados)}")
        else:
            print("\n❌ No se encontraron resultados")

    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if scraper:
            scraper.cerrar()

if __name__ == "__main__":
    main()