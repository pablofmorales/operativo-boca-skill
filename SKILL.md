---
name: operativo-boca
description: "Monitorea redes sociales (Twitter/X y Reddit) durante eventos deportivos y envía resúmenes en tiempo real vía Telegram."
---

# Operativo Boca (Match Monitor) ⚽️💬

Este skill está diseñado para ejecutarse en background (vía cron) cada 15 minutos. 
Su función principal es detectar si hay un partido programado en el día actual, calcular la ventana de tiempo del evento y, durante ese período:
1. Extraer los últimos tweets de referentes seleccionados en X/Twitter.
2. Extraer los comentarios más calientes del "Match Thread" activo en un subreddit (ej: `r/BocaJuniors`).
3. Resumir el "termómetro" o la opinión general usando un modelo LLM.
4. Enviar un reporte en tiempo real vía Telegram.

A pesar de su nombre y configuración por defecto, **el skill es completamente genérico y personalizable** para cualquier equipo o evento.

## ⚙️ Instalación y Configuración

1. Crea tu archivo de configuración basándote en el ejemplo provisto:
```bash
cd config
cp settings.example.json settings.json
```

2. Edita `config/settings.json` con tus parámetros:
- `telegram_chat_id`: El ID de Telegram a donde el bot enviará los mensajes.
- `twitter_accounts`: Lista de cuentas de Twitter (sin el @) a monitorear.
- `reddit_subreddit`: El subreddit a leer (ej: `BocaJuniors`, `soccer`, `formula1`).
- `reddit_keywords`: Palabras clave que el script buscará en los títulos para identificar cuál es el "Match Thread" activo.
- `fixture_path`: Ruta al archivo JSON con el calendario de partidos.

### Autenticación en Twitter / X
Para leer Twitter de manera automatizada necesitas proveer credenciales de una sesión válida. El script buscará las siguientes variables de entorno:
- `TWITTER_AUTH_TOKEN` (cookie `auth_token`)
- `TWITTER_CT0` (cookie `ct0`)

*Nota: Para entornos locales, el script también tiene un fallback para leer desde el gestor de contraseñas Unix `pass` (`pass show x-twitter/bird`), pero se recomienda usar variables de entorno para despliegues portables.*

### ¿Qué se necesita para leer Reddit?
Para leer un subreddit público **NO se necesita ninguna API Key ni cuenta de Reddit**. 
El script utiliza el endpoint público agregando `.json` a la URL (ej: `https://www.reddit.com/r/BocaJuniors/new.json`). Lo único obligatorio que implementa el código internamente es enviar una cabecera `User-Agent` personalizada, ya que Reddit bloquea peticiones anónimas de bots genéricos (como las de la librería `urllib` por defecto). Si planeas escalar este script a muchas peticiones por minuto, deberías crear una App en Reddit y usar la librería `praw` con OAuth, pero para el volumen de este cron, el endpoint público es perfecto.

## 📅 Archivo de Calendario (Fixture)
Debes proveer un JSON con las fechas de los eventos (configurado en `fixture_path`). Ejemplo:
```json
{
  "2026-03-10": {
    "opponent": "River Plate",
    "time": "17:00",
    "competition": "Liga Profesional"
  }
}
```

## ⏱️ Crontab
El script se debe agregar al crontab del sistema o de OpenClaw para que corra cada 15 minutos:
```bash
*/15 * * * * python3 /ruta/a/operativo-boca/scripts/monitor.py >> /tmp/operativo-boca.log 2>&1
```

*(Para probarlo manualmente forzando la ejecución fuera de horario de partido, usa `python3 scripts/monitor.py --force`)*
