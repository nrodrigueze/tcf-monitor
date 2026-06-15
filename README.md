# TCF Canada Monitor 🇨🇦

Revisa automáticamente la disponibilidad de cupos para el examen **TCF Canada** en 7 centros acreditados de Canadá, cada 2 horas. Envía un email de alerta cuando detecta un cupo nuevo y mantiene un calendario `.ics` actualizado automáticamente.

## Centros monitoreados

| Centro | Ciudad |
|--------|--------|
| Alliance Française Vancouver | Vancouver, BC |
| Alliance Française Victoria | Victoria, BC |
| Alliance Française Toronto | Toronto / N.York / Mississauga / Oakville, ON |
| Alliance Française Calgary | Calgary, AB |
| Alliance Française Edmonton | Edmonton, AB |
| Ashton Testing Services | Vancouver, BC |
| GB Language Centre | North York (Toronto), ON |

---

## Calendario en vivo (ICS)

El archivo `TCF_Canada_2026.ics` se actualiza automáticamente en cada corrida. Suscríbete con esta URL fija:

```
webcal://raw.githubusercontent.com/nrodrigueze/tcf-monitor/main/TCF_Canada_2026.ics
```

**iPhone:** Safari → pegar URL → "Subscribe to Calendar"  
**Google Calendar:** Otros calendarios → `+` → Desde URL → pegar URL  

El calendario incluye:
- 🟢 Un evento por sesión disponible (en la fecha exacta del examen)
- 🔴 Sesiones agotadas (para referencia)
- 🕐 Sesiones próximas a abrir registro
- ⏰ Fecha exacta en que abre el registro de cada sesión
- 📅 Aperturas de registro trimestrales (Toronto, Vancouver)

---

## Configuración (5 minutos)

### Paso 1 — Repositorio en GitHub
El repositorio debe ser **público** para que la URL del ICS funcione sin autenticación.

### Paso 2 — Archivos requeridos
```
tcf-monitor/
├── tcf_monitor.py          ← scraper principal
├── generar_ics.py          ← generador de calendario
├── README.md
└── .github/
    └── workflows/
        └── monitor.yml     ← automatización cada 2 horas
```

### Paso 3 — Gmail App Password
1. Ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Crea una App Password con nombre "TCF Monitor"
3. Copia las 16 letras (sin espacios)

### Paso 4 — Secrets en GitHub
Settings → Secrets and variables → Actions → New repository secret

| Nombre | Valor |
|--------|-------|
| `EMAIL_TO` | email donde llegan las alertas |
| `EMAIL_FROM` | cuenta Gmail que manda el email |
| `EMAIL_PASSWORD` | App Password de 16 letras |

### Paso 5 — Correr manualmente
Actions → TCF Canada Monitor → Run workflow → Run workflow (verde)

---

## Horario de ejecución

Corre cada 2 horas automáticamente (UTC):

| UTC | PDT (Surrey, BC) |
|-----|-----------------|
| 00:00 | 17:00 |
| 02:00 | 19:00 |
| 04:00 | 21:00 |
| 06:00 | 23:00 |
| 08:00 | 01:00 |
| 10:00 | 03:00 |
| 12:00 | 05:00 |
| 14:00 | 07:00 |
| 16:00 | 09:00 |
| 18:00 | 11:00 |
| 20:00 | 13:00 |
| 22:00 | 15:00 |

---

## Email de alerta

Solo se envía cuando un centro cambia de cualquier estado → **DISPONIBLE**:

```
Asunto: 🚨 TCF Canada — ¡Cupo disponible!

🎉 TCF Canada — Cupos detectados

• AF Vancouver (Vancouver, BC)
  Estado: DISPONIBLE
  Fechas: September 9, 2026
  👉 Registrarse ahora → https://www.alliancefrancaise.ca/...
```

---

## Ver resultados

Actions → último run de "TCF Canada Monitor" → descargar artefacto `tcf-log-N`

---

## Costos

**Gratis.** GitHub Actions incluye 2,000 min/mes en repos privados (o ilimitado en repos públicos).  
Este workflow usa ~2 min × 12 veces/día × 30 días = ~720 min/mes.
