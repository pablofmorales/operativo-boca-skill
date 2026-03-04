---
name: operativo-boca
description: "Monitorea los días que juega Boca Juniors y envía un resumen cada 15 minutos de una lista de Twitter específica por Telegram durante el partido."
---

# Operativo Boca ⚽️💙💛💙

Este skill está diseñado para ejecutarse en background (vía cron) cada 15 minutos. 
Su función es detectar si Boca Juniors juega en el día actual, calcular la ventana de tiempo del partido (desde 15 minutos antes hasta el final) y, durante ese período, leer una lista específica de Twitter, resumir la opinión de los tuiteros usando un LLM, y enviarlo por Telegram.

## Configuración Pendiente (Acción Requerida por Pablo)

Para que el scraper de Twitter funcione sin ser bloqueado por la pantalla de login de X.com, necesitamos:

1. **URL de la Lista de Twitter**: Debes crear una "Lista" pública o privada en tu cuenta de X con los tuiteros de Boca que querés seguir y pasarme la URL (ej: `https://x.com/i/lists/123456789`).
2. **Autenticación (Cookies/API)**: Como no tengo acceso a tu Mac para usar tu navegador local, `agent-browser` (que corre en mi contenedor) necesita loguearse. Necesitás extraer tus cookies de sesión de X (el token `auth_token` y `ct0`) y guardarlas, o bien podemos usar una API de scraping externa (como Apify o RapidAPI) que es mucho más estable para Twitter.

## Archivos
- `scripts/monitor.py`: El script principal que verifica el horario del partido y orquesta el scraping y el envío de mensajes.

## Crontab
El script se debe agregar al crontab del sistema o de OpenClaw para que corra cada 15 minutos:
```bash
*/15 * * * * python3 /home/pablo/.openclaw/alfred-workspace/skills/operativo-boca/scripts/monitor.py >> /tmp/operativo-boca.log 2>&1
```
