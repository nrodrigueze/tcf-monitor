#!/usr/bin/env python3
"""
Genera TCF_Canada_2026.ics — SOLO eventos de apertura de registro.

Filosofía: el calendario debe estar vacío de ruido. Un evento se crea
ÚNICAMENTE cuando tcf_monitor.py extrajo, con confianza, la fecha y hora
exacta en que abre el registro de una sesión específica (columna
"Registration Dates" de la tabla Oncord, o equivalente en otros centros).

Si un centro no tiene ninguna apertura de registro detectada (sea porque
está bloqueado, todo está FULL, todo ya está abierto para reservar, o el
scraper no pudo parsear la tabla con certeza) — NO se genera ningún evento
para ese centro. Nada de "VERIFICAR" ni "BLOQUEADO" en el calendario.

Cada evento:
  - Ocurre a la hora EXACTA de apertura (no todo el día)
  - Tiene un VALARM 30 minutos antes
  - Incluye el link directo para registrarse
"""

import json
import re
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────
#  HELPERS ICS
# ─────────────────────────────────────────────────────────
def ics_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def fold(line: str) -> str:
    """RFC 5545: líneas > 75 octetos se parten con CRLF + espacio."""
    result, chunk = [], line
    while len(chunk.encode("utf-8")) > 75:
        cut = 75
        while len(chunk[:cut].encode("utf-8")) > 75:
            cut -= 1
        result.append(chunk[:cut])
        chunk = " " + chunk[cut:]
    result.append(chunk)
    return "\r\n".join(result)

def escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def make_event_datetime(
    uid: str,
    summary: str,
    dt: datetime,
    description: str,
    url: str = "",
    location: str = "",
    duration_minutes: int = 30,
    alarm_minutes_before: int = 30,
) -> list[str]:
    """
    Evento puntual (no de día completo) a una hora exacta, con recordatorio.
    dt debe estar en hora local de Vancouver (America/Vancouver) — se asume
    naive y se etiqueta con TZID para que cada calendario lo ajuste bien.
    """
    now = ics_now()
    dtstart = dt.strftime("%Y%m%dT%H%M%S")
    dtend = (dt + timedelta(minutes=duration_minutes)).strftime("%Y%m%dT%H%M%S")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}@tcf-monitor-nrodrigueze",
        f"DTSTAMP:{now}",
        f"DTSTART;TZID=America/Vancouver:{dtstart}",
        f"DTEND;TZID=America/Vancouver:{dtend}",
        fold(f"SUMMARY:{escape(summary)}"),
    ]
    if description:
        lines.append(fold(f"DESCRIPTION:{escape(description)}"))
    if location:
        lines.append(fold(f"LOCATION:{escape(location)}"))
    if url:
        lines.append(fold(f"URL:{url}"))
    lines.append("STATUS:CONFIRMED")

    # Recordatorio antes de la apertura
    lines += [
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        fold(f"DESCRIPTION:{escape(summary)}"),
        f"TRIGGER:-PT{alarm_minutes_before}M",
        "END:VALARM",
    ]

    lines.append("END:VEVENT")
    return lines


# ─────────────────────────────────────────────────────────
#  PARSEO DE FECHA+HORA  ("Jun 17 2026 3:00pm")
# ─────────────────────────────────────────────────────────
_MESES = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
    "january":1,"february":2,"march":3,"april":4,"june":6,"july":7,
    "august":8,"september":9,"october":10,"november":11,"december":12,
}

def parse_apertura(texto: str) -> datetime | None:
    """
    Parsea 'Jun 17 2026 3:00pm' o 'June 17, 2026 3:00 pm' a datetime naive
    (hora local del centro, asumida Pacific salvo que se indique otra).
    Retorna None si no logra parsear con confianza — nunca inventa una fecha.
    """
    if not texto:
        return None
    m = re.search(
        r"(\w+)\.?\s+(\d{1,2}),?\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*(am|pm)",
        texto.strip(), re.IGNORECASE
    )
    if not m:
        return None
    mes_txt, dia, anio, hora, minuto, ampm = m.groups()
    mes = _MESES.get(mes_txt.lower()[:3])
    if not mes:
        return None
    hora = int(hora)
    if ampm.lower() == "pm" and hora != 12:
        hora += 12
    elif ampm.lower() == "am" and hora == 12:
        hora = 0
    try:
        return datetime(int(anio), mes, int(dia), hora, int(minuto))
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────
#  URLs de registro por centro (para el link en el evento)
# ─────────────────────────────────────────────────────────
URLS_REGISTRO = {
    "AF Vancouver":            "https://www.alliancefrancaise.ca/en/language/exams/tcf-canada/",
    "AF Victoria":             "https://www.afvictoria.ca/exams/tcf/",
    "AF Toronto":              "https://www.alliance-francaise.ca/en/exams/tests/informations-about-tcf-canada/tcf-canada",
    "AF Calgary":              "https://www.afcalgary.ca/exams/tcf/registration-process/",
    "AF Edmonton":             "https://www.afedmonton.com/en/exams/tcf/",
    "Ashton Testing Services": "https://ashtontesting.ca/tcf-canada-test/",
    "GB Language Centre":      "https://gblc.ca/en/tests/tcf-canada",
}

UBICACIONES = {
    "AF Vancouver": "6161 Cambie Street, Vancouver, BC",
    "AF Victoria":  "1B-1218 Langley Street, Victoria, BC",
    "AF Toronto":   "Alliance Française Toronto — 4 campus en GTA",
    "AF Calgary":   "Alliance Française Calgary",
    "AF Edmonton":  "Alliance Française Edmonton",
    "Ashton Testing Services": "410-1190 Melville Street, Vancouver, BC",
    "GB Language Centre": "716 Gordon Baker Rd, Suite 211, North York, ON",
}


# ─────────────────────────────────────────────────────────
#  EVENTOS A PARTIR DEL ESTADO
# ─────────────────────────────────────────────────────────
def eventos_desde_estado(estado: dict) -> list[list[str]]:
    """
    Recorre cada centro. Solo genera evento por sesión cuya fecha de
    apertura de registro se haya extraído con éxito (campo 'abre_registro'
    dentro de r['sesiones']). Todo lo demás se ignora silenciosamente.
    """
    eventos = []
    for nombre, datos in estado.items():
        sesiones = datos.get("sesiones", [])
        if not sesiones:
            continue  # nada confiable para este centro — no se genera ruido

        url = URLS_REGISTRO.get(nombre, "")
        location = UBICACIONES.get(nombre, "")

        for i, ses in enumerate(sesiones):
            abre_txt = ses.get("abre_registro", "")
            dt_abre = parse_apertura(abre_txt)
            if not dt_abre:
                continue  # sin fecha parseable con confianza — se descarta

            fecha_examen = ses.get("fecha_examen", "")
            spots = ses.get("spots")

            summary = f"⏰ Registro abre — {nombre}"
            if fecha_examen and fecha_examen != "?":
                summary += f" (examen {fecha_examen})"

            desc_parts = [f"Centro: {nombre}"]
            if fecha_examen and fecha_examen != "?":
                desc_parts.append(f"Fecha del examen: {fecha_examen}")
            desc_parts.append(f"Apertura de registro: {abre_txt}")
            if spots:
                desc_parts.append(f"Cupos disponibles al momento de la revisión: {spots}")
            if url:
                desc_parts.append(f"Registrarse aquí: {url}")
            description = "\n".join(desc_parts)

            uid_base = f"{nombre.lower().replace(' ','-')}-{i}-{dt_abre.strftime('%Y%m%d%H%M')}"

            ev = make_event_datetime(
                uid=f"apertura-{uid_base}",
                summary=summary,
                dt=dt_abre,
                description=description,
                url=url,
                location=location,
                alarm_minutes_before=30,
            )
            eventos.append(ev)

    return eventos


# ─────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────
def generar(estado_path: str = "tcf_estado.json",
            output_path: str = "TCF_Canada_2026.ics") -> None:

    estado = {}
    p = Path(estado_path)
    if p.exists():
        try:
            estado = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  No se pudo leer {estado_path}: {e}")

    eventos = eventos_desde_estado(estado)

    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TCF Canada Monitor//nrodrigueze//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        fold("X-WR-CALNAME:TCF Canada — Aperturas de registro"),
        "X-WR-TIMEZONE:America/Vancouver",
        fold(f"X-WR-CALDESC:Actualizado {date.today().isoformat()} — avisos de apertura de registro con 30 min de anticipación."),
        "REFRESH-INTERVAL;VALUE=DURATION:PT2H",
        fold(f"SOURCE:https://raw.githubusercontent.com/nrodrigueze/tcf-monitor/main/{output_path}"),
        # VTIMEZONE estándar para America/Vancouver (Pacific Time, con DST)
        "BEGIN:VTIMEZONE",
        "TZID:America/Vancouver",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:-0800",
        "TZOFFSETTO:-0700",
        "TZNAME:PDT",
        "DTSTART:19700308T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:-0700",
        "TZOFFSETTO:-0800",
        "TZNAME:PST",
        "DTSTART:19701101T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    for ev_lines in eventos:
        cal.extend(ev_lines)

    cal.append("END:VCALENDAR")

    content = "\r\n".join(cal) + "\r\n"
    Path(output_path).write_text(content, encoding="utf-8")

    print(f"✅ {output_path} generado — {len(eventos)} evento(s) de apertura de registro")
    if not eventos:
        print("   (sin aperturas detectadas en esta revisión — calendario vacío, sin ruido)")
    print(f"   Suscripción: https://raw.githubusercontent.com/nrodrigueze/tcf-monitor/main/{output_path}")


if __name__ == "__main__":
    generar()
