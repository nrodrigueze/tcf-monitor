#!/usr/bin/env python3
"""
TCF Canada — Monitor de Disponibilidad
Alliance Française de Canadá + Ashton Testing Services + GB Language Centre

Diseñado para correr en GitHub Actions cada 6 horas.
Manda email cuando detecta un cupo nuevo.

Variables de entorno requeridas (GitHub Secrets):
    EMAIL_TO       — tu email donde llegan las alertas
    EMAIL_FROM     — email Gmail que manda las alertas
    EMAIL_PASSWORD — App Password de Gmail (myaccount.google.com/apppasswords)

Correr localmente:
    pip install requests beautifulsoup4 lxml
    EMAIL_TO=tu@email.com EMAIL_FROM=tu@gmail.com EMAIL_PASSWORD=xxxx \
        python tcf_monitor.py --check-once
"""

import requests
import time
import json
import re
import argparse
import logging
import sys
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Intentar importar smtplib (siempre disponible en Python estándar)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────────────────────
#  CONFIGURACIÓN  ←  EDITA AQUÍ
# ─────────────────────────────────────────────────────────
# Credenciales leídas desde variables de entorno (GitHub Secrets)
_email_to       = os.environ.get("EMAIL_TO", "")
_email_from     = os.environ.get("EMAIL_FROM", "")
_email_password = os.environ.get("EMAIL_PASSWORD", "")

CONFIG = {
    "intervalo_segundos": 21600,
    "log_file":    "tcf_monitor.log",
    "estado_file": "tcf_estado.json",

    # Se activa automáticamente si EMAIL_TO está definido en el entorno
    "send_email":      bool(_email_to and _email_from and _email_password),
    "email_from":      _email_from,
    "email_to":        _email_to,
    "email_password":  _email_password,
    "smtp_server":     "smtp.gmail.com",
    "smtp_port":       587,

    # Sin notificación de escritorio en servidor
    "notif_escritorio": False,
}

# ─────────────────────────────────────────────────────────
#  CENTROS A MONITOREAR
# ─────────────────────────────────────────────────────────
CENTROS = [
    {
        "nombre": "AF Vancouver",
        "ciudad": "Vancouver, BC",
        "url_check": "https://www.alliancefrancaise.ca/en/language/exams/tcf-canada/",
        "url_registro": "https://www.alliancefrancaise.ca/products/ciep-tcf-canada-full-exam/",
        "url_tabla": "https://www.alliancefrancaise.ca/en/language/exams/tcf-canada/",
        "tipo": "vancouver",
        "notas": "Sep 2: SOLD OUT | Sep 4: SOLD OUT | Sep 9: abre Jun 17 12pm | $390 CAD",
    },
    {
        "nombre": "AF Victoria",
        "ciudad": "Victoria, BC",
        "url_check": "https://www.afvictoria.ca/exams/tcf/",
        "url_registro": "https://www.afvictoria.ca/exams/tcf/",
        "tipo": "victoria",
        "notas": "1B-1218 Langley Street, Victoria BC. Sin sesiones verano 2026. Reanudan oct 2026. info@afvictoria.ca",
    },
    {
        "nombre": "AF Toronto",
        "ciudad": "Toronto / N.York / Mississauga / Oakville, ON",
        "url_check": "https://www.alliance-francaise.ca/en/exams/tests/informations-about-tcf-canada/tcf-canada",
        "url_registro": "https://www.alliance-francaise.ca/en/exams/tests/informations-about-tcf-canada/tcf-canada",
        "tipo": "toronto",
        "notas": "Q3 abierto desde mayo 20. Q4 abre ago 15. $390 CAD. 4 campus.",
    },


    {
        "nombre": "AF Calgary",
        "ciudad": "Calgary, AB",
        "url_check": "https://www.afcalgary.ca/exams/tcf/registration-process/",
        "url_registro": "https://www.afcalgary.ca/exams/tcf/registration-process/",
        "tipo": "calgary",
        "notas": "$400 CAD. Primer llegado, primer servido.",
    },
    {
        "nombre": "AF Edmonton",
        "ciudad": "Edmonton, AB",
        "url_check": "https://www.afedmonton.com/en/exams/tcf/",
        "url_registro": "https://www.afedmonton.com/en/exams/tcf/",
        "tipo": "edmonton",
        "notas": "$400 CAD. Registro mínimo 10 días antes.",
    },

    {
        "nombre": "Ashton Testing Services",
        "ciudad": "Vancouver, BC",
        "url_check": "https://ashtontesting.ca/tcf-canada-test/",
        "url_registro": "https://ashtontesting.ca/tcf-canada-test/",
        "tipo": "ashton",
        "notas": "$410 CAD. testcentre@ashtontesting.ca · (604) 628-5783. 410-1190 Melville St, Vancouver. Sin reembolsos ni cambios de fecha.",
    },
    {
        "nombre": "GB Language Centre",
        "ciudad": "North York, ON (Toronto)",
        "url_check": "https://gblc.ca/en",
        "url_registro": "https://gblc.ca/en/tests/tcf-canada",
        "tipo": "gblc",
        "notas": "Sep 2026 abierto. admin@gblc.ca · 416-704-1940. 716 Gordon Baker Rd, Suite 211, North York.",
    },
]

# ─────────────────────────────────────────────────────────
#  COLORES ANSI (deshabilitados en Windows si no soporta)
# ─────────────────────────────────────────────────────────
_use_color = sys.stdout.isatty() and platform.system() != "Windows" or (
    platform.system() == "Windows" and os.environ.get("TERM_PROGRAM") is not None
)

class C:
    VERDE    = "\033[92m"  if _use_color else ""
    ROJO     = "\033[91m"  if _use_color else ""
    AMARILLO = "\033[93m"  if _use_color else ""
    AZUL     = "\033[94m"  if _use_color else ""
    CYAN     = "\033[96m"  if _use_color else ""
    BOLD     = "\033[1m"   if _use_color else ""
    RESET    = "\033[0m"   if _use_color else ""
    GRIS     = "\033[90m"  if _use_color else ""

# Habilitar colores ANSI en Windows
if platform.system() == "Windows":
    os.system("color")  # activa ANSI en cmd.exe

# ─────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────
_log_path = Path(__file__).parent / CONFIG["log_file"]
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tcf_monitor")

# ─────────────────────────────────────────────────────────
#  HTTP HEADERS — imitar navegador real
# ─────────────────────────────────────────────────────────
# Rotación de User-Agents para evitar bloqueos
USER_AGENTS = [
    # Chrome 125 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome 125 Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Firefox 126 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Safari 17 Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge 125 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

_ua_index = 0

def get_headers(referer: str = "https://www.google.com/") -> dict:
    global _ua_index
    ua = USER_AGENTS[_ua_index % len(USER_AGENTS)]
    _ua_index += 1
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9,fr-CA;q=0.8,fr;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Referer": referer,
        "DNT": "1",
        "Cache-Control": "no-cache",
    }

# ─────────────────────────────────────────────────────────
#  FETCH CON RETRY
# ─────────────────────────────────────────────────────────
def fetch_page(url: str, intentos: int = 3, pausa: float = 4.0):
    """Descarga una página con reintentos y User-Agent rotatorio."""
    session = requests.Session()
    for intento in range(1, intentos + 1):
        try:
            headers = get_headers()
            # Primera solicitud a la raíz del dominio para obtener cookies
            from urllib.parse import urlparse
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
            try:
                session.get(base, headers=get_headers(), timeout=10)
                time.sleep(1)
            except Exception:
                pass
            r = session.get(url, headers=headers, timeout=20, allow_redirects=True)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "lxml")
            elif r.status_code == 403:
                log.warning(f"403 Forbidden en intento {intento}/{intentos}: {url}")
            elif r.status_code == 429:
                espera = pausa * (intento * 2)
                log.warning(f"429 Rate limit. Esperando {espera}s...")
                time.sleep(espera)
            else:
                log.warning(f"HTTP {r.status_code} en {url}")
        except requests.exceptions.ConnectionError as e:
            log.warning(f"Conexión fallida (intento {intento}): {e}")
        except requests.exceptions.Timeout:
            log.warning(f"Timeout (intento {intento}): {url}")
        except Exception as e:
            log.warning(f"Error inesperado (intento {intento}): {e}")

        if intento < intentos:
            time.sleep(pausa * intento)

    return None


# ─────────────────────────────────────────────────────────
#  DETECCIÓN DE FECHAS  (ES/FR/EN)
# ─────────────────────────────────────────────────────────
_MESES = (
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december"
    r"|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
    r"|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
)
_RE_FECHA = re.compile(
    rf"\b{_MESES}[\s\-]+(?:\d{{1,2}}[\s,\-]+)?\d{{4}}\b|\b\d{{4}}[\-/]\d{{2}}[\-/]\d{{2}}\b",
    re.IGNORECASE,
)

def extraer_fechas(texto: str) -> list[str]:
    return list(dict.fromkeys(_RE_FECHA.findall(texto)))  # sin duplicados, orden preservado


# ─────────────────────────────────────────────────────────
#  LÓGICA DE ANÁLISIS POR CENTRO
# ─────────────────────────────────────────────────────────

def _resultado_base(nombre, ciudad, url_r, url_c, notas) -> dict:
    return {
        "nombre": nombre,
        "ciudad": ciudad,
        "url_registro": url_r,
        "url_check": url_c,
        "notas": notas,
        "estado": "VERIFICAR",
        "fechas": [],
        "detalle": "",
        "timestamp": datetime.now().isoformat(),
    }


def check_vancouver(centro: dict) -> dict:
    """
    AF Vancouver usa la plataforma Oncord con una tabla de sesiones que muestra:
      - Exam name (TCF-Canada September 2, 2026)
      - Schedules (Wed 02 Sep 2026 9am-4pm)
      - Registration Dates (Jun 15 2026 12:00pm - Jun 30 2026 4:00pm)
      - Location, Spots left, Price, Bookings (Full / Opens in Xd Xh / Book Now)
    Parseamos esa tabla para extraer sesiones disponibles, próximas y agotadas.
    """
    r = _resultado_base(centro["nombre"], centro["ciudad"],
                        centro["url_registro"], centro["url_check"], centro["notas"])
    soup = fetch_page(centro["url_check"])
    if not soup:
        r["estado"] = "BLOQUEADO"
        r["detalle"] = "Sitio bloqueó el acceso. Verificar manualmente en alliancefrancaise.ca"
        return r

    texto = soup.get_text(" ", strip=True)
    sesiones_disponibles = []
    sesiones_proximas = []
    sesiones_llenas = []
    sesiones_raw = []   # lista de dicts con info completa para el ICS

    # La tabla Oncord tiene filas con clase "event-row" o similar
    # Cada fila contiene: nombre examen, schedules, registration dates, spots, precio, botón
    filas = soup.find_all("tr")
    if not filas:
        # Fallback: buscar divs con clase de evento
        filas = soup.find_all(class_=re.compile(r"event|session|row", re.I))

    for fila in filas:
        texto_fila = fila.get_text(" ", strip=True)
        if "TCF" not in texto_fila.upper():
            continue

        info = {"texto": texto_fila}

        # Extraer fecha del examen (ej: "September 2, 2026" o "02 Sep 2026")
        m_fecha = re.search(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
            r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})",
            texto_fila, re.IGNORECASE
        )
        if m_fecha:
            info["fecha_examen"] = m_fecha.group(1).strip()

        # Extraer spots disponibles
        m_spots = re.search(r"(\d+)\s*(?:spots?|cupos?|places?)\s*(?:left|remaining|available)?",
                            texto_fila, re.IGNORECASE)
        if m_spots:
            info["spots"] = int(m_spots.group(1))

        # Detectar estado del botón
        texto_low = texto_fila.lower()
        if "full" in texto_low and "spots" not in texto_low:
            info["estado_boton"] = "FULL"
            sesiones_llenas.append(info.get("fecha_examen", texto_fila[:40]))
        elif re.search(r"opens?\s+in\s+\d+", texto_low):
            m_opens = re.search(r"(opens?\s+in\s+[\d\w\s]+)", texto_fila, re.IGNORECASE)
            info["estado_boton"] = m_opens.group(1).strip() if m_opens else "PRÓXIMO"
            # Extraer fecha de apertura de registro
            m_reg = re.search(
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
                r"\s+\d{1,2}:\d{2}(?:am|pm))",
                texto_fila, re.IGNORECASE
            )
            if m_reg:
                info["abre_registro"] = m_reg.group(1).strip()
            sesiones_proximas.append(info)
        elif "book now" in texto_low or ("spots" in texto_low and info.get("spots", 0) > 0):
            info["estado_boton"] = "DISPONIBLE"
            sesiones_disponibles.append(info)

        sesiones_raw.append(info)

    # Guardar sesiones completas para el ICS
    r["sesiones"] = sesiones_raw

    if sesiones_disponibles:
        r["estado"] = "DISPONIBLE"
        r["fechas"] = [s.get("fecha_examen", "?") for s in sesiones_disponibles]
        spots_total = sum(s.get("spots", 0) for s in sesiones_disponibles)
        r["detalle"] = f"{len(sesiones_disponibles)} sesión(es) disponible(s) — {spots_total} cupos totales"
    elif sesiones_proximas:
        r["estado"] = "PRÓXIMO"
        proxima = sesiones_proximas[0]
        abre = proxima.get("abre_registro", proxima.get("estado_boton", "próximamente"))
        r["fechas"] = [s.get("fecha_examen", "?") for s in sesiones_proximas]
        r["detalle"] = f"Registro abre: {abre}"
    elif sesiones_llenas:
        r["estado"] = "AGOTADO"
        r["fechas"] = sesiones_llenas[:5]
        r["detalle"] = f"{len(sesiones_llenas)} sesión(es) FULL"
    else:
        # Fallback a texto plano si no se parseó tabla
        if "sold out" in texto.lower() or "full" in texto.lower():
            r["estado"] = "AGOTADO"
            r["detalle"] = "Sesiones marcadas como FULL/SOLD OUT"
        elif "opens in" in texto.lower():
            r["estado"] = "PRÓXIMO"
            m = re.search(r"opens?\s+in\s+([\d\w\s]+)", texto, re.IGNORECASE)
            r["detalle"] = f"Registro abre en: {m.group(1).strip() if m else 'próximamente'}"
        else:
            r["estado"] = "VERIFICAR"
            r["detalle"] = "Sin tabla de sesiones detectada — verificar manualmente"

    return r


def check_toronto(centro: dict) -> dict:
    r = _resultado_base(centro["nombre"], centro["ciudad"],
                        centro["url_registro"], centro["url_check"], centro["notas"])
    soup = fetch_page(centro["url_check"])
    if not soup:
        r["estado"] = "BLOQUEADO"
        r["detalle"] = "Sitio bloqueó el acceso. Verificar manualmente."
        return r

    texto = soup.get_text(" ", strip=True)
    fechas = extraer_fechas(texto)

    # Toronto muestra "Dates & Times" como enlace cuando hay cupos
    # y "sessions remain open while spots are available"
    if "if a session is not listed, it is full" in texto.lower():
        # Si aparecen fechas E-TCF / P-TCF = hay cupos
        etcf = soup.find(text=re.compile(r"E-TCF|P-TCF", re.I))
        if etcf:
            r["estado"] = "DISPONIBLE"
            r["fechas"] = fechas[:8]
            r["detalle"] = "Sesiones E-TCF/P-TCF listadas (ver sitio para fechas exactas)"
        else:
            r["estado"] = "AGOTADO"
            r["detalle"] = "Sin sesiones listadas (todas llenas)"
    elif fechas:
        r["estado"] = "VERIFICAR"
        r["fechas"] = fechas[:8]
        r["detalle"] = f"{len(fechas)} fecha(s) mencionadas — verificar disponibilidad"
    else:
        r["estado"] = "VERIFICAR"
        r["detalle"] = "Sin fechas detectadas — verificar manualmente"

    return r


def check_generico(centro: dict,
                   kw_agotado: list[str],
                   kw_disponible: list[str]) -> dict:
    r = _resultado_base(centro["nombre"], centro["ciudad"],
                        centro["url_registro"], centro["url_check"], centro["notas"])
    soup = fetch_page(centro["url_check"])
    if not soup:
        r["estado"] = "BLOQUEADO"
        r["detalle"] = "Sitio bloqueó el acceso. Verificar manualmente."
        return r

    texto_low = soup.get_text(" ", strip=True).lower()
    fechas = extraer_fechas(soup.get_text(" "))

    agotado = any(k in texto_low for k in kw_agotado)
    disponible = any(k in texto_low for k in kw_disponible)

    if agotado and not disponible:
        r["estado"] = "AGOTADO"
        r["detalle"] = "Indicadores de cupos agotados detectados"
    elif disponible:
        r["estado"] = "DISPONIBLE"
        r["fechas"] = fechas[:8]
        r["detalle"] = "Indicadores de registro abierto detectados"
        if fechas:
            r["detalle"] += f" | {len(fechas)} fecha(s) mencionada(s)"
    elif fechas:
        r["estado"] = "VERIFICAR"
        r["fechas"] = fechas[:8]
        r["detalle"] = f"{len(fechas)} fecha(s) encontrada(s) — verificar manualmente"
    else:
        r["estado"] = "VERIFICAR"
        r["detalle"] = "Sin señales claras — verificar manualmente"

    return r


def check_calgary(centro: dict) -> dict:
    return check_generico(
        centro,
        kw_agotado=["sold out", "no dates", "no sessions available", "full",
                    "working with our partners"],
        kw_disponible=["choose your date", "click on the link", "book your spot",
                       "register", "available"],
    )


def check_edmonton(centro: dict) -> dict:
    return check_generico(
        centro,
        kw_agotado=["sold out", "no available"],
        kw_disponible=["click here to fill", "fill out the form", "next sessions",
                       "register", "available"],
    )


def check_ashton(centro: dict) -> dict:
    """
    Ashton Testing Services (Vancouver).
    Lista fechas como 'July 05th 9.00 am (FULL)' o sin (FULL) si hay cupo.
    """
    r = _resultado_base(centro["nombre"], centro["ciudad"],
                        centro["url_registro"], centro["url_check"], centro["notas"])
    soup = fetch_page(centro["url_check"])
    if not soup:
        r["estado"] = "BLOQUEADO"
        r["detalle"] = "Sitio bloqueó el acceso. Verificar manualmente."
        return r

    texto = soup.get_text(" ", strip=True)

    patron_sesion = re.compile(
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{1,2}[:.:]\d{2}\s*(?:am|pm))"
        r"(\s*\(FULL\))?",
        re.IGNORECASE,
    )
    sesiones = patron_sesion.findall(texto)
    disponibles = [s[0].strip() for s in sesiones if not s[1]]
    llenas      = [s[0].strip() for s in sesiones if s[1]]

    alta_demanda = (
        "demand is higher than normal" in texto.lower()
        or "adding more sessions" in texto.lower()
        or "share updates as soon as new dates" in texto.lower()
    )

    if disponibles:
        r["estado"] = "DISPONIBLE"
        r["fechas"] = disponibles
        r["detalle"] = (
            f"{len(disponibles)} fecha(s) disponible(s)"
            + (f" | {len(llenas)} llena(s)" if llenas else "")
        )
    elif llenas and not disponibles:
        r["estado"] = "AGOTADO"
        r["detalle"] = f"Todas las sesiones listadas están FULL ({len(llenas)})"
    elif alta_demanda:
        r["estado"] = "AGOTADO"
        r["detalle"] = "Aviso de alta demanda — sin nuevas fechas publicadas aún"
    else:
        r["estado"] = "VERIFICAR"
        r["detalle"] = "Sin sesiones detectadas — verificar manualmente"

    return r


def check_gblc(centro: dict) -> dict:
    """
    GB Language Centre (North York, Toronto).
    Detecta el banner de apertura: 'September 2026 test dates are now open for registration'.
    """
    r = _resultado_base(centro["nombre"], centro["ciudad"],
                        centro["url_registro"], centro["url_check"], centro["notas"])
    soup = fetch_page(centro["url_check"])
    if not soup:
        soup = fetch_page(centro["url_registro"])
    if not soup:
        r["estado"] = "BLOQUEADO"
        r["detalle"] = "Sitio bloqueó el acceso. Verificar manualmente en gblc.ca"
        return r

    texto = soup.get_text(" ", strip=True)
    texto_low = texto.lower()
    fechas = extraer_fechas(texto)

    kw_open = ["now open for registration", "open for registration", "book now",
               "dates are now open", "register now"]
    kw_sold = ["sold out", "fully booked", "no dates available", "check back soon"]

    m_banner = re.search(
        r"(\w+ \d{4}\s+test dates?\s+are\s+now\s+open[^.]*)",
        texto, re.IGNORECASE,
    )

    if m_banner:
        r["estado"] = "DISPONIBLE"
        r["fechas"] = [m_banner.group(1).strip()] + fechas[:4]
        r["detalle"] = f"Banner detectado: '{m_banner.group(1).strip()}'"
    elif any(k in texto_low for k in kw_open):
        r["estado"] = "DISPONIBLE"
        r["fechas"] = fechas[:6]
        r["detalle"] = "Indicadores de registro abierto detectados"
    elif any(k in texto_low for k in kw_sold):
        r["estado"] = "AGOTADO"
        r["detalle"] = "Indicadores de cupos agotados detectados"
    elif fechas:
        r["estado"] = "VERIFICAR"
        r["fechas"] = fechas[:6]
        r["detalle"] = f"{len(fechas)} fecha(s) mencionada(s) — verificar manualmente"
    else:
        r["estado"] = "VERIFICAR"
        r["detalle"] = "Página renderiza con JS; verificar manualmente en gblc.ca"

    return r


# ─────────────────────────────────────────────────────────
#  DESPACHO
# ─────────────────────────────────────────────────────────
def check_victoria(centro: dict) -> dict:
    """
    AF Victoria usa la misma plataforma Oncord que Vancouver.
    Parsea tabla de sesiones: si no hay fechas = agotado.
    Nota: sin sesiones verano 2026, reanudan octubre 2026.
    """
    r = _resultado_base(centro["nombre"], centro["ciudad"],
                        centro["url_registro"], centro["url_check"], centro["notas"])
    soup = fetch_page(centro["url_check"])
    if not soup:
        r["estado"] = "BLOQUEADO"
        r["detalle"] = "Sitio bloqueó el acceso. Verificar en afvictoria.ca/exams/tcf/"
        return r

    texto = soup.get_text(" ", strip=True)
    texto_low = texto.lower()
    sesiones_raw = []

    # Buscar tabla Oncord
    filas = soup.find_all("tr")
    sesiones_disponibles = []
    sesiones_proximas = []
    sesiones_llenas = []

    for fila in filas:
        texto_fila = fila.get_text(" ", strip=True)
        if "TCF" not in texto_fila.upper():
            continue
        info = {"texto": texto_fila}

        m_fecha = re.search(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
            r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})",
            texto_fila, re.IGNORECASE
        )
        if m_fecha:
            info["fecha_examen"] = m_fecha.group(1).strip()

        m_spots = re.search(r"(\d+)\s*(?:spots?|cupos?|places?)\s*(?:left|remaining|available)?",
                            texto_fila, re.IGNORECASE)
        if m_spots:
            info["spots"] = int(m_spots.group(1))

        texto_fila_low = texto_fila.lower()
        if "full" in texto_fila_low and "spots" not in texto_fila_low:
            info["estado_boton"] = "FULL"
            sesiones_llenas.append(info.get("fecha_examen", texto_fila[:40]))
        elif re.search(r"opens?\s+in\s+\d+", texto_fila_low):
            m_opens = re.search(r"(opens?\s+in\s+[\d\w\s]+)", texto_fila, re.IGNORECASE)
            info["estado_boton"] = m_opens.group(1).strip() if m_opens else "PRÓXIMO"
            m_reg = re.search(
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\s+\d{1,2}:\d{2}(?:am|pm))",
                texto_fila, re.IGNORECASE
            )
            if m_reg:
                info["abre_registro"] = m_reg.group(1).strip()
            sesiones_proximas.append(info)
        elif "book now" in texto_fila_low or ("spots" in texto_fila_low and info.get("spots", 0) > 0):
            info["estado_boton"] = "DISPONIBLE"
            sesiones_disponibles.append(info)

        sesiones_raw.append(info)

    r["sesiones"] = sesiones_raw

    if sesiones_disponibles:
        r["estado"] = "DISPONIBLE"
        r["fechas"] = [s.get("fecha_examen", "?") for s in sesiones_disponibles]
        spots_total = sum(s.get("spots", 0) for s in sesiones_disponibles)
        r["detalle"] = f"{len(sesiones_disponibles)} sesión(es) disponible(s) — {spots_total} cupos"
    elif sesiones_proximas:
        r["estado"] = "PRÓXIMO"
        proxima = sesiones_proximas[0]
        abre = proxima.get("abre_registro", proxima.get("estado_boton", "próximamente"))
        r["fechas"] = [s.get("fecha_examen", "?") for s in sesiones_proximas]
        r["detalle"] = f"Registro abre: {abre}"
    elif sesiones_llenas:
        r["estado"] = "AGOTADO"
        r["fechas"] = sesiones_llenas[:5]
        r["detalle"] = f"{len(sesiones_llenas)} sesión(es) FULL"
    else:
        # Fallback texto plano
        kw_sold = ["sold out", "no dates available", "check back", "check our website regularly"]
        kw_summer = ["no tcf-canada session will be held during summer", "resume in october",
                     "check back on this page", "sold out at the moment"]
        if any(k in texto_low for k in kw_summer):
            r["estado"] = "AGOTADO"
            r["detalle"] = "Sin sesiones verano 2026 — reanudan octubre 2026"
        elif any(k in texto_low for k in kw_sold):
            r["estado"] = "AGOTADO"
            r["detalle"] = "Agotado — revisar regularmente"
        else:
            r["estado"] = "VERIFICAR"
            r["detalle"] = "Sin fechas detectadas — verificar en afvictoria.ca/exams/tcf/"

    return r


CHECKERS = {
    "vancouver": check_vancouver,
    "victoria":  check_victoria,
    "toronto":   check_toronto,

    "calgary":   check_calgary,
    "edmonton":  check_edmonton,
    "ashton":    check_ashton,
    "gblc":      check_gblc,
}

def verificar_centro(centro: dict) -> dict:
    fn = CHECKERS.get(centro["tipo"])
    if fn:
        return fn(centro)
    r = _resultado_base(centro["nombre"], centro["ciudad"],
                        centro.get("url_registro",""), centro.get("url_check",""),
                        centro.get("notas",""))
    r["estado"] = "ERROR"
    r["detalle"] = f"Tipo desconocido: {centro['tipo']}"
    return r


# ─────────────────────────────────────────────────────────
#  CONSOLA
# ─────────────────────────────────────────────────────────
ICONOS = {
    "DISPONIBLE": f"{C.VERDE}✅ DISPONIBLE{C.RESET}",
    "AGOTADO":    f"{C.ROJO}❌ AGOTADO{C.RESET}",
    "PRÓXIMO":    f"{C.AMARILLO}🕐 PRÓXIMO{C.RESET}",
    "VERIFICAR":  f"{C.AMARILLO}⚠️  VERIFICAR{C.RESET}",
    "BLOQUEADO":  f"{C.GRIS}🔒 BLOQUEADO (WAF){C.RESET}",
    "ERROR":      f"{C.GRIS}💤 ERROR{C.RESET}",
}

def imprimir_resultado(r: dict):
    icono = ICONOS.get(r["estado"], r["estado"])
    print(f"\n  {C.BOLD}{r['nombre']}{C.RESET}  {C.GRIS}({r['ciudad']}){C.RESET}")
    print(f"  Estado  : {icono}")
    if r.get("fechas"):
        for f in r["fechas"][:5]:
            print(f"  {C.VERDE}  → {f}{C.RESET}")
    if r.get("detalle"):
        print(f"  {C.GRIS}Detalle : {r['detalle']}{C.RESET}")
    print(f"  {C.AZUL}Registro: {r['url_registro']}{C.RESET}")


# ─────────────────────────────────────────────────────────
#  NOTIFICACIÓN DE ESCRITORIO
# ─────────────────────────────────────────────────────────
def notif_escritorio(titulo: str, mensaje: str):
    if not CONFIG.get("notif_escritorio"):
        return
    sistema = platform.system()
    try:
        if sistema == "Windows":
            # Usar PowerShell (no requiere librerías extra)
            ps_script = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
                f"$t = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime]::New();"
                f"$t.LoadXml('<toast><visual><binding template=\"ToastGeneric\"><text>{titulo}</text><text>{mensaje}</text></binding></visual></toast>');"
                f"$n = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('TCF Monitor');"
                f"$n.Show([Windows.UI.Notifications.ToastNotification]::New($t));"
            )
            subprocess.run(["powershell", "-Command", ps_script],
                           capture_output=True, timeout=10)
        elif sistema == "Darwin":  # macOS
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{mensaje}" with title "{titulo}" sound name "Glass"'],
                capture_output=True, timeout=10,
            )
        elif sistema == "Linux":
            subprocess.run(
                ["notify-send", titulo, mensaje, "--urgency=critical"],
                capture_output=True, timeout=10,
            )
    except Exception as e:
        log.debug(f"Notificación de escritorio falló: {e}")


# ─────────────────────────────────────────────────────────
#  EMAIL
# ─────────────────────────────────────────────────────────
def enviar_email(cambios: list[dict]):
    if not CONFIG["send_email"] or not cambios:
        return
    try:
        cuerpo = "<h2>🎉 TCF Canada — Cupos detectados</h2><ul>\n"
        for r in cambios:
            fechas_str = ", ".join(r.get("fechas", [])) or "—"
            cuerpo += (
                f"<li><b>{r['nombre']}</b> ({r['ciudad']})<br>"
                f"Estado: <b>{r['estado']}</b><br>"
                f"Fechas: {fechas_str}<br>"
                f"<a href='{r['url_registro']}'>👉 Registrarse ahora</a></li>\n"
            )
        cuerpo += f"</ul><p><i>Revisión: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i></p>"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚨 TCF Canada — ¡Cupo disponible!"
        msg["From"]    = CONFIG["email_from"]
        msg["To"]      = CONFIG["email_to"]
        msg.attach(MIMEText(cuerpo, "html"))

        with smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"]) as s:
            s.starttls()
            s.login(CONFIG["email_from"], CONFIG["email_password"])
            s.send_message(msg)
        log.info(f"📧 Email enviado a {CONFIG['email_to']}")
    except Exception as e:
        log.error(f"Error al enviar email: {e}")


# ─────────────────────────────────────────────────────────
#  ESTADO PERSISTENTE
# ─────────────────────────────────────────────────────────
_estado_path = Path(__file__).parent / CONFIG["estado_file"]

def cargar_estado() -> dict:
    if _estado_path.exists():
        try:
            return json.loads(_estado_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def guardar_estado(resultados: list[dict]):
    estado = {
        r["nombre"]: {
            "estado": r["estado"],
            "fechas": r.get("fechas", []),
            "detalle": r.get("detalle", ""),
            "ts": r.get("timestamp", ""),
        }
        for r in resultados
    }
    _estado_path.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")

def detectar_cambios(resultados: list[dict], anterior: dict) -> list[dict]:
    cambios = []
    for r in resultados:
        est_ant = anterior.get(r["nombre"], {}).get("estado", "")
        if r["estado"] == "DISPONIBLE" and est_ant != "DISPONIBLE":
            cambios.append(r)
            log.info(f"🔔 CAMBIO: {r['nombre']} → {est_ant or 'desconocido'} → DISPONIBLE")
    return cambios


# ─────────────────────────────────────────────────────────
#  CICLO PRINCIPAL
# ─────────────────────────────────────────────────────────
def revisar_todos() -> list[dict]:
    resultados = []
    for i, centro in enumerate(CENTROS):
        log.info(f"  [{i+1}/{len(CENTROS)}] Revisando {centro['nombre']}...")
        r = verificar_centro(centro)
        resultados.append(r)
        imprimir_resultado(r)
        time.sleep(3)  # pausa cortés entre peticiones
    return resultados


def run(una_vez: bool = False):
    print(f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗
║   TCF Canada — Monitor de Disponibilidad               ║
║   Alliance Française de Canadá | Intervalo: 6 horas   ║
╚══════════════════════════════════════════════════════════╝{C.RESET}
Log: {_log_path}
Estado: {_estado_path}
""")

    while True:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{C.BOLD}{'─'*58}{C.RESET}")
        print(f"{C.BOLD}  🔍 Revisión: {ahora}{C.RESET}")
        print(f"{C.BOLD}{'─'*58}{C.RESET}")

        anterior = cargar_estado()
        resultados = revisar_todos()
        guardar_estado(resultados)

        cambios = detectar_cambios(resultados, anterior)
        if cambios:
            nombres = ", ".join(c["nombre"] for c in cambios)
            print(f"\n{C.VERDE}{C.BOLD}  🚨 ¡NUEVOS CUPOS! → Registrarse YA{C.RESET}")
            for c in cambios:
                print(f"  ✅ {c['nombre']} → {c['url_registro']}")
            notif_escritorio(
                "🎉 TCF Canada — Cupo disponible",
                f"{nombres} — ¡Regístrate ahora!"
            )
            enviar_email(cambios)
        else:
            bloqueados = sum(1 for r in resultados if r["estado"] == "BLOQUEADO")
            if bloqueados == len(CENTROS):
                print(f"\n{C.AMARILLO}  ⚠️  Todos los sitios bloquearon el scraping desde este equipo.{C.RESET}")
                print(f"{C.AMARILLO}  Prueba con una VPN residencial o revisa manualmente los sitios.{C.RESET}")
            else:
                print(f"\n{C.GRIS}  Sin nuevos cupos en esta revisión.{C.RESET}")

        if una_vez:
            break

        prox = datetime.fromtimestamp(time.time() + CONFIG["intervalo_segundos"])
        print(f"\n{C.GRIS}  Próxima revisión: {prox.strftime('%H:%M:%S')} "
              f"(en {CONFIG['intervalo_segundos']//3600}h). Ctrl+C para detener.{C.RESET}\n")
        time.sleep(CONFIG["intervalo_segundos"])


# ─────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Monitor de disponibilidad TCF Canada — Alliance Française de Canadá",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python tcf_monitor.py                  # Loop cada 6 horas
  python tcf_monitor.py --check-once     # Una revisión y sale

Programar en Windows (Task Scheduler cada 6h):
  1. Abrir Task Scheduler → "Create Basic Task"
  2. Trigger: Daily, repetir cada 6 horas
  3. Action: Start a program
     Programa: C:\\Users\\TU_USUARIO\\AppData\\Local\\Python\\bin\\python.exe
     Argumentos: "C:\\ruta\\a\\tcf_monitor.py" --check-once
  4. Marcar "Run whether user is logged on or not"

Programar en macOS/Linux (cron):
  crontab -e
  0 */6 * * * /usr/bin/python3 /ruta/a/tcf_monitor.py --check-once >> /tmp/tcf.log 2>&1
        """
    )
    parser.add_argument(
        "--check-once", action="store_true",
        help="Revisa una sola vez y sale (ideal para Task Scheduler / cron)"
    )
    args = parser.parse_args()
    run(una_vez=args.check_once)
