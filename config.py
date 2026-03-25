"""
Configuración central del proyecto CubaPrecios
Todas las rutas, constantes y settings en un solo lugar
"""

from pathlib import Path
import os

# ─────────────────────────────────────────
# RAÍZ DEL PROYECTO
# ─────────────────────────────────────────
BASE_DIR = Path("D:/CubaPrecios")

# ─────────────────────────────────────────
# RUTAS DE DATOS
# ─────────────────────────────────────────
DATA_DIR        = BASE_DIR / "data"
RAW_DIR         = DATA_DIR / "raw"
CLEAN_DIR       = DATA_DIR / "clean"
BACKUPS_DIR     = DATA_DIR / "backups"

RAW_REVOLICO    = RAW_DIR / "revolico"
RAW_TELEGRAM    = RAW_DIR / "telegram"
RAW_FACEBOOK    = RAW_DIR / "facebook"

# ─────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────
DB_PATH         = CLEAN_DIR / "cubaprecios.db"
CSV_PRODUCTOS   = CLEAN_DIR / "productos.csv"

# ─────────────────────────────────────────
# PLAYWRIGHT
# ─────────────────────────────────────────
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BASE_DIR / ".browsers")

# ─────────────────────────────────────────
# REVOLICO — TODAS LAS CATEGORÍAS REALES
# ─────────────────────────────────────────
REVOLICO_BASE_URL = "https://www.revolico.com"

REVOLICO_CATEGORIAS = {
    "pc":           "/computadoras/pc-de-escritorio/",
    "laptop":       "/computadoras/laptop/",
    "cpu":          "/computadoras/microprocesador/",
    "monitor":      "/computadoras/monitor/",
    "motherboard":  "/computadoras/motherboard/",
    "ram":          "/computadoras/memoria-ram-flash/",
    "disco":        "/computadoras/disco-duro-interno-externo/",
    "chasis":       "/computadoras/chasis-fuente/",
    "gpu":          "/computadoras/tarjeta-de-video/",
    "sonido":       "/computadoras/tarjeta-de-sonido-bocinas/",
    "dvd":          "/computadoras/quemador-lector-dvd-cd/",
    "ups":          "/computadoras/backup-ups/",
    "impresora":    "/computadoras/impresora-cartuchos/",
    "modem":        "/computadoras/modem-wifi-red/",
    "webcam":       "/computadoras/webcam-microf-audifono/",
    "teclado":      "/computadoras/teclado-mouse/",
    "internet":     "/computadoras/internet-email/",
    "cd":           "/computadoras/cd-dvd-virgen/",
    "otros":        "/computadoras/otros/",
}

# ─────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────
SCRAPER_CONFIG = {
    "headless":     True,
    "timeout":      90000,
    "delay_min":    2,
    "delay_max":    5,
    "max_paginas":  10,
    "reintentos":   3,
}

# ─────────────────────────────────────────
# LOGS
# ─────────────────────────────────────────
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "scraper.log"

# ─────────────────────────────────────────
# MONEDAS
# ─────────────────────────────────────────
MONEDAS_KEYWORDS = {
    "USD": ["usd", "dolar", "dólares", "dollar", "fula", "verde", "divisa"],
    "MLC": ["mlc", "tienda", "saldo"],
    "CUP": ["cup", "peso", "pesos", "mn", "moneda nacional", "kuki", "kukis"],
}

# ─────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────
def crear_estructura():
    carpetas = [
        RAW_REVOLICO, RAW_TELEGRAM, RAW_FACEBOOK,
        CLEAN_DIR, BACKUPS_DIR, LOGS_DIR
    ]
    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)
    print("✅ Estructura de carpetas verificada en D:/CubaPrecios")

if __name__ == "__main__":
    crear_estructura()