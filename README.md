# TCF Canada Monitor 🇨🇦

Revisa automáticamente la disponibilidad de cupos para el examen **TCF Canada** en los 9 centros acreditados de Canadá, cada 6 horas. Envía un email de alerta cuando detecta un cupo nuevo.

## Centros monitoreados

| Centro | Ciudad |
|--------|--------|
| Alliance Française Vancouver | Vancouver, BC |
| Alliance Française Toronto | Toronto / N.York / Mississauga / Oakville, ON |
| Alliance Française Ottawa | Ottawa, ON |
| Alliance Française Montréal | Montréal, QC |
| Alliance Française Calgary | Calgary, AB |
| Alliance Française Edmonton | Edmonton, AB |
| Alliance Française Halifax | Halifax, NS |
| Ashton Testing Services | Vancouver, BC |
| GB Language Centre | North York (Toronto), ON |

---

## Configuración (5 minutos)

### Paso 1 — Crear el repositorio en GitHub

1. Ve a [github.com](https://github.com) e inicia sesión (o crea una cuenta gratis)
2. Haz clic en **"New repository"** (botón verde arriba a la derecha)
3. Nombre: `tcf-monitor`
4. Marca **Private** (para que nadie más vea tus credenciales)
5. Haz clic en **"Create repository"**

### Paso 2 — Subir los archivos

En la página de tu nuevo repositorio vacío:

1. Haz clic en **"uploading an existing file"**
2. Sube los dos archivos:
   - `tcf_monitor.py`
   - `.github/workflows/monitor.yml` ← primero crea la carpeta `.github/workflows/` manualmente en la interfaz
3. Haz clic en **"Commit changes"**

> **Alternativa más fácil:** usa [github.dev](https://github.dev) — abre el repo y arrastra los archivos.

### Paso 3 — Configurar el email (Gmail App Password)

1. Ve a tu cuenta Gmail → [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Crea una App Password con nombre "TCF Monitor"
3. Copia las 16 letras que te da (ej: `abcd efgh ijkl mnop`)

### Paso 4 — Agregar los Secrets en GitHub

En tu repositorio → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Agrega estos 3 secrets:

| Nombre | Valor |
|--------|-------|
| `EMAIL_TO` | tu email donde quieres recibir alertas |
| `EMAIL_FROM` | tu cuenta Gmail que manda el email |
| `EMAIL_PASSWORD` | la App Password de 16 letras del paso anterior |

### Paso 5 — Activar GitHub Actions

1. Ve a la pestaña **Actions** en tu repositorio
2. Si pide confirmación, haz clic en **"I understand my workflows, enable them"**
3. Para probar inmediatamente: clic en **"TCF Canada Monitor"** → **"Run workflow"** → **"Run workflow"**

---

## Horario de ejecución

El monitor corre automáticamente 4 veces al día:

| UTC | Hora PDT (Surrey, BC) |
|-----|----------------------|
| 00:00 | 17:00 (5 PM) |
| 06:00 | 23:00 (11 PM) |
| 12:00 | 05:00 (5 AM) |
| 18:00 | 11:00 (11 AM) |

---

## Cómo funciona

- Cada 6 horas GitHub corre el script en sus servidores (gratis)
- El script visita cada sitio y detecta si hay cupos disponibles
- Si detecta un cupo **nuevo** (que no existía en la revisión anterior), manda un email de alerta inmediato
- El log completo queda disponible en la pestaña **Actions** → selecciona el run → descarga el artefacto `tcf-log-N`

---

## Email de alerta

Cuando hay un cupo nuevo recibes un email como este:

```
Asunto: 🚨 TCF Canada — ¡Cupo disponible!

🎉 TCF Canada — Cupos detectados

• Ashton Testing Services (Vancouver, BC)
  Estado: DISPONIBLE
  Fechas: August 14th 9.00 am
  👉 Registrarse ahora → https://ashtontesting.ca/tcf-canada-test/

Revisión: 2026-06-15 18:00
```

---

## Ver resultados manualmente

1. Ve a tu repositorio en GitHub
2. Pestaña **Actions**
3. Haz clic en el último run de "TCF Canada Monitor"
4. Descarga el artefacto **tcf-log-N** para ver el log completo y el estado JSON

---

## Costos

**Gratis.** GitHub Actions incluye 2,000 minutos/mes en repositorios privados.
Este workflow usa ~2 minutos por ejecución × 4 veces al día × 30 días = ~240 minutos/mes.
Bien dentro del límite gratuito.
