"""
Configuración central del proyecto CubaPrecios
Rutas dinámicas - Funciona tanto localmente como en Streamlit Cloud
"""

from pathlib import Path
import os

# ─────────────────────────────────────────
# RAÍZ DEL PROYECTO
# ─────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

# ─────────────────────────────────────────
# RUTAS DE DATOS
# ─────────────────────────────────────────
DATA_DIR    = BASE_DIR / "data"
RAW_DIR     = DATA_DIR / "raw"
CLEAN_DIR   = DATA_DIR / "clean"
BACKUPS_DIR = DATA_DIR / "backups"

# Raw por fuente
RAW_REVOLICO = RAW_DIR / "revolico"
RAW_FACEBOOK = RAW_DIR / "facebook_selenium"
RAW_TELEGRAM = RAW_DIR / "telegram"

# Logs
LOGS_DIR = BASE_DIR / "logs"

# ─────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────
DB_PATH       = CLEAN_DIR / "cubaprecios.db"
CSV_PRODUCTOS = CLEAN_DIR / "productos.csv"

# ─────────────────────────────────────────
# PLAYWRIGHT — browsers en el mismo disco
# ─────────────────────────────────────────
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BASE_DIR / ".browsers")

# ─────────────────────────────────────────
# REVOLICO — URLs y categorías
# ─────────────────────────────────────────
REVOLICO_BASE_URL = "https://www.revolico.com"

REVOLICO_CATEGORIAS = {
    "pc":          "/computadoras/pc-de-escritorio/",
    "laptop":      "/computadoras/laptop/",
    "cpu":         "/computadoras/microprocesador/",
    "monitor":     "/computadoras/monitor/",
    "motherboard": "/computadoras/motherboard/",
    "ram":         "/computadoras/memoria-ram-flash/",
    "disco":       "/computadoras/disco-duro-interno-externo/",
    "chasis":      "/computadoras/chasis-fuente/",
    "gpu":         "/computadoras/tarjeta-de-video/",
    "sonido":      "/computadoras/tarjeta-de-sonido-bocinas/",
    "dvd":         "/computadoras/quemador-lector-dvd-cd/",
    "ups":         "/computadoras/backup-ups/",
    "impresora":   "/computadoras/impresora-cartuchos/",
    "modem":       "/computadoras/modem-wifi-red/",
    "webcam":      "/computadoras/webcam-microf-audifono/",
    "teclado":     "/computadoras/teclado-mouse/",
    "internet":    "/computadoras/internet-email/",
    "cd":          "/computadoras/cd-dvd-virgen/",
    "otros":       "/computadoras/otros/",
}

# ─────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────
SCRAPER_CONFIG = {
    "headless":    True,
    "timeout":     90000,
    "delay_min":   2,
    "delay_max":   5,
    "max_paginas": 10,
    "reintentos":  3,
}

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
    """Crea todas las carpetas necesarias si no existen"""
    carpetas = [
        RAW_REVOLICO, RAW_FACEBOOK, RAW_TELEGRAM,
        CLEAN_DIR, BACKUPS_DIR, LOGS_DIR,
    ]
    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)
    print("✅ Estructura de carpetas verificada correctamente.")
    print(f"📁 Base de datos: {DB_PATH}")


if __name__ == "__main__":
    crear_estructura()