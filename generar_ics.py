#!/usr/bin/env python3
"""
Genera TCF_Canada_2026.ics con el estado actual de cada centro.
Lee tcf_estado.json (producido por tcf_monitor.py) y combina:
  - Fechas fijas conocidas (apertura de registro, cierres FEI, sesiones Ashton)
  - Estado dinámico de cada centro en tiempo real
Se corre automáticamente por GitHub Actions después de cada revisión.
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────
#  HELPERS ICS
# ─────────────────────────────────────────────────────────
def ics_date(d: date) -> str:
    return d.strftime("%Y%m%d")

def ics_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def fold(line: str) -> str:
    """RFC 5545: líneas > 75 chars se parten con CRLF + espacio."""
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

def make_event(
    uid: str,
    summary: str,
    dtstart: date,
    dtend: date,
    description: str,
    location: str = "",
    url: str = "",
    all_day: bool = True,
    confirmed: bool = True,
) -> list[str]:
    now = ics_now()
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}@tcf-monitor-nrodrigueze",
        f"DTSTAMP:{now}",
        f"LAST-MODIFIED:{now}",
    ]
    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{ics_date(dtstart)}")
        lines.append(f"DTEND;VALUE=DATE:{ics_date(dtend + timedelta(days=1))}")
    else:
        lines.append(f"DTSTART;VALUE=DATE:{ics_date(dtstart)}")
        lines.append(f"DTEND;VALUE=DATE:{ics_date(dtend + timedelta(days=1))}")

    lines.append(fold(f"SUMMARY:{escape(summary)}"))

    if description:
        lines.append(fold(f"DESCRIPTION:{escape(description)}"))
    if location:
        lines.append(fold(f"LOCATION:{escape(location)}"))
    if url:
        lines.append(fold(f"URL:{url}"))

    lines.append(f"STATUS:{'CONFIRMED' if confirmed else 'TENTATIVE'}")
    lines.append("END:VEVENT")
    return lines


# ─────────────────────────────────────────────────────────
#  FECHAS FIJAS 2026
# ─────────────────────────────────────────────────────────
EVENTOS_FIJOS = [

    # ── ASHTON TESTING SERVICES — sesiones julio (todas FULL por ahora) ──
    dict(uid="ashton-jul05", summary="🔴 TCF Canada — Ashton Vancouver 9:00 AM [FULL]",
         dtstart=date(2026,7,5), dtend=date(2026,7,5), confirmed=True,
         location="410-1190 Melville Street, Vancouver, BC V6E 3W1",
         url="https://ashtontesting.ca/tcf-canada-test/",
         description="Ashton Testing Services — Sesión COMPLETA\nHora: 9:00 AM\nCosto: $410 CAD\ntestcentre@ashtontesting.ca | (604) 628-5783"),

    dict(uid="ashton-jul12", summary="🔴 TCF Canada — Ashton Vancouver 9:00 AM [FULL]",
         dtstart=date(2026,7,12), dtend=date(2026,7,12), confirmed=True,
         location="410-1190 Melville Street, Vancouver, BC V6E 3W1",
         url="https://ashtontesting.ca/tcf-canada-test/",
         description="Ashton Testing Services — Sesión COMPLETA\nHora: 9:00 AM\nCosto: $410 CAD"),

    dict(uid="ashton-jul17", summary="🔴 TCF Canada — Ashton Vancouver 5:00 PM [FULL]",
         dtstart=date(2026,7,17), dtend=date(2026,7,17), confirmed=True,
         location="410-1190 Melville Street, Vancouver, BC V6E 3W1",
         url="https://ashtontesting.ca/tcf-canada-test/",
         description="Ashton Testing Services — Sesión COMPLETA\nHora: 5:00 PM\nCosto: $410 CAD"),

    dict(uid="ashton-jul24", summary="🔴 TCF Canada — Ashton Vancouver 5:00 PM [FULL]",
         dtstart=date(2026,7,24), dtend=date(2026,7,24), confirmed=True,
         location="410-1190 Melville Street, Vancouver, BC V6E 3W1",
         url="https://ashtontesting.ca/tcf-canada-test/",
         description="Ashton Testing Services — Sesión COMPLETA\nHora: 5:00 PM\nCosto: $410 CAD"),

    dict(uid="ashton-jul30", summary="🔴 TCF Canada — Ashton Vancouver 5:00 PM [FULL]",
         dtstart=date(2026,7,30), dtend=date(2026,7,30), confirmed=True,
         location="410-1190 Melville Street, Vancouver, BC V6E 3W1",
         url="https://ashtontesting.ca/tcf-canada-test/",
         description="Ashton Testing Services — Sesión COMPLETA\nHora: 5:00 PM\nCosto: $410 CAD"),

    # ── AF TORONTO — aperturas de registro ──
    dict(uid="toronto-q3-open", summary="📅 REGISTRO ABRE — AF Toronto Q3 (Jul–Sep 2026) 10:00 AM",
         dtstart=date(2026,5,20), dtend=date(2026,5,20), confirmed=True,
         location="Alliance Française Toronto — 4 campus en GTA",
         url="https://www.alliance-francaise.ca/en/exams/tests/informations-about-tcf-canada/tcf-canada",
         description="AF Toronto — Apertura de registro Q3 (Julio–Septiembre 2026)\nHora: 10:00 AM\nCosto: $390 CAD\nFormatos: E-TCF y P-TCF\nCampus: Downtown Toronto, North York, Mississauga, Oakville"),

    dict(uid="toronto-q4-open", summary="📅 REGISTRO ABRE — AF Toronto Q4 (Oct–Dic 2026) 10:00 AM",
         dtstart=date(2026,8,15), dtend=date(2026,8,15), confirmed=True,
         location="Alliance Française Toronto — 4 campus en GTA",
         url="https://www.alliance-francaise.ca/en/exams/tests/informations-about-tcf-canada/tcf-canada",
         description="AF Toronto — Apertura de registro Q4 (Octubre–Diciembre 2026)\nHora: 10:00 AM\nCosto: $390 CAD"),

    # ── AF VANCOUVER — aperturas de registro ──
    dict(uid="van-sep-open", summary="📅 REGISTRO ABRE — AF Vancouver Septiembre 2026",
         dtstart=date(2026,6,15), dtend=date(2026,6,15), confirmed=False,
         location="Alliance Française Vancouver — 6161 Cambie Street, Vancouver, BC",
         url="https://www.alliancefrancaise.ca/products/ciep-tcf-canada-full-exam/",
         description="AF Vancouver — Registro para septiembre 2026 abre a mediados de junio\nCosto: $390 CAD\ntef.tcf@alliancefrancaise.ca | (604) 327-0201"),

    dict(uid="van-q4-open", summary="📅 REGISTRO ABRE — AF Vancouver Oct–Dic 2026",
         dtstart=date(2026,9,1), dtend=date(2026,9,1), confirmed=False,
         location="Alliance Française Vancouver — 6161 Cambie Street, Vancouver, BC",
         url="https://www.alliancefrancaise.ca/products/ciep-tcf-canada-full-exam/",
         description="AF Vancouver — Registro para Oct–Dic 2026 abre en septiembre\nCosto: $390 CAD"),

    # ── FEI CIERRE AGOSTO ──
    dict(uid="fei-cierre-ago", summary="⛔ SIN EXÁMENES TCF — Cierre FEI (todos los centros)",
         dtstart=date(2026,8,3), dtend=date(2026,8,16), confirmed=True,
         location="",
         url="https://www.france-education-international.fr",
         description="France Éducation International (FEI) cierra del 3 al 16 de agosto 2026.\nNingún centro en Canadá puede ofrecer TCF durante este período.\nResultados de exámenes de finales de julio pueden llegar con retraso."),

    dict(uid="ottawa-reanuda", summary="🟢 REANUDAN EXÁMENES TCF — AF Ottawa",
         dtstart=date(2026,8,18), dtend=date(2026,8,18), confirmed=True,
         location="Alliance Française Ottawa — 352 MacLaren Street, Ottawa ON",
         url="https://af.ca/ottawa/en/tests_et_examens/tcf/",
         description="AF Ottawa — Sesiones TCF reanudan después del cierre de verano de FEI."),

    # ── GB LANGUAGE CENTRE ──
    dict(uid="gblc-sep-open", summary="🟢 TCF Canada — GB Language Centre Septiembre 2026 ABIERTO",
         dtstart=date(2026,9,1), dtend=date(2026,9,30), confirmed=True,
         location="GB Language Centre — 716 Gordon Baker Rd, Suite 211, North York, ON",
         url="https://gblc.ca/en/tests/tcf-canada",
         description="GB Language Centre — Sesiones de septiembre 2026 abiertas.\nadmin@gblc.ca | 416-704-1940"),
]

# ─────────────────────────────────────────────────────────
#  EVENTOS DINÁMICOS desde tcf_estado.json
# ─────────────────────────────────────────────────────────
EMOJIS_ESTADO = {
    "DISPONIBLE": "🟢",
    "AGOTADO":    "🔴",
    "PRÓXIMO":    "🕐",
    "VERIFICAR":  "⚠️",
    "BLOQUEADO":  "🔒",
    "ERROR":      "💤",
}

URLS_REGISTRO = {
    "AF Vancouver":           "https://www.alliancefrancaise.ca/products/ciep-tcf-canada-full-exam/",
    "AF Toronto":             "https://www.alliance-francaise.ca/en/exams/tests/informations-about-tcf-canada/tcf-canada",
    "AF Ottawa":              "https://af.ca/ottawa/en/tests_et_examens/tcf/",
    "AF Montréal":            "https://www.afmontreal.ca/tcf/",
    "AF Calgary":             "https://www.afcalgary.ca/exams/tcf/registration-process/",
    "AF Edmonton":            "https://www.afedmonton.com/en/exams/tcf/",
    "AF Halifax":             "https://afhalifax.ca/test-your-french/tcf/",
    "Ashton Testing Services":"https://ashtontesting.ca/tcf-canada-test/",
    "GB Language Centre":     "https://gblc.ca/en/tests/tcf-canada",
}

def eventos_dinamicos(estado: dict, hoy: date) -> list[list[str]]:
    """Genera un evento por centro con su estado actual."""
    resultado = []
    for nombre, datos in estado.items():
        est = datos.get("estado", "VERIFICAR")
        fechas = datos.get("fechas", [])
        detalle = datos.get("detalle", "")
        ts = datos.get("ts", "")[:16].replace("T", " ")
        emoji = EMOJIS_ESTADO.get(est, "❓")
        url = URLS_REGISTRO.get(nombre, "")

        # Descripción
        desc_parts = [f"Estado: {est}", f"Revisión: {ts}"]
        if detalle:
            desc_parts.append(f"Detalle: {detalle}")
        if fechas:
            desc_parts.append("Fechas detectadas:\n" + "\n".join(f"  • {f}" for f in fechas))
        if url:
            desc_parts.append(f"Registrarse: {url}")
        description = "\n".join(desc_parts)

        summary = f"{emoji} TCF Canada — {nombre} [{est}]"

        ev = make_event(
            uid=f"estado-{nombre.lower().replace(' ','-')}",
            summary=summary,
            dtstart=hoy,
            dtend=hoy,
            description=description,
            url=url,
            confirmed=(est == "DISPONIBLE"),
        )
        resultado.append(ev)
    return resultado


# ─────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────
def generar(estado_path: str = "tcf_estado.json",
            output_path: str = "TCF_Canada_2026.ics") -> None:

    hoy = date.today()

    # Leer estado actual
    estado = {}
    p = Path(estado_path)
    if p.exists():
        try:
            estado = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  No se pudo leer {estado_path}: {e}")

    # Construir líneas del calendario
    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TCF Canada Monitor//nrodrigueze//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        fold("X-WR-CALNAME:TCF Canada 2026 — Monitor"),
        "X-WR-TIMEZONE:America/Vancouver",
        fold(f"X-WR-CALDESC:Actualizado {hoy.isoformat()} — 9 centros en Canadá. Estado en tiempo real + fechas fijas."),
        "REFRESH-INTERVAL;VALUE=DURATION:PT2H",
        fold(f"SOURCE:https://raw.githubusercontent.com/nrodrigueze/tcf-monitor/main/{output_path}"),
    ]

    # Eventos de estado dinámico
    if estado:
        for ev_lines in eventos_dinamicos(estado, hoy):
            cal.extend(ev_lines)
    else:
        print("ℹ️  Sin estado previo — solo eventos fijos")

    # Eventos fijos
    for ef in EVENTOS_FIJOS:
        ev_lines = make_event(
            uid=ef["uid"],
            summary=ef["summary"],
            dtstart=ef["dtstart"],
            dtend=ef["dtend"],
            description=ef.get("description", ""),
            location=ef.get("location", ""),
            url=ef.get("url", ""),
            confirmed=ef.get("confirmed", True),
        )
        cal.extend(ev_lines)

    cal.append("END:VCALENDAR")

    content = "\r\n".join(cal) + "\r\n"
    Path(output_path).write_text(content, encoding="utf-8")

    total = len(estado) + len(EVENTOS_FIJOS)
    print(f"✅ {output_path} generado — {total} eventos ({len(estado)} dinámicos + {len(EVENTOS_FIJOS)} fijos)")
    print(f"   Suscripción: https://raw.githubusercontent.com/nrodrigueze/tcf-monitor/main/{output_path}")


if __name__ == "__main__":
    generar()
