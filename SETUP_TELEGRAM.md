# Configuracion del Bot de Telegram

Para que las notificaciones de Telegram funcionen, necesitas añadir dos secrets en GitHub.

## Pasos

1. Ve a tu repositorio en GitHub
2. Click en **Settings** (esquina superior derecha)
3. En el menu izquierdo: **Secrets and variables** → **Actions**
4. Click en **New repository secret** y añade:

### Secret 1: TELEGRAM_TOKEN
- **Name**: `TELEGRAM_TOKEN`
- **Value**: El token de tu bot (formato: `1234567890:ABCdef...`)

### Secret 2: TELEGRAM_CHAT_ID  
- **Name**: `TELEGRAM_CHAT_ID`
- **Value**: Tu Chat ID numerico (ejemplo: `1704096490`)

5. Click en **Add secret** para cada uno

## Verificacion

Una vez añadidos los secrets:
1. Ve a **Actions** → **Revision Semanal Arritmias**
2. Click en **Run workflow**
3. En ~2 minutos recibirás un mensaje en Telegram con el resumen

## Mensaje de ejemplo

```
📊 Reporte Semanal Arritmias

📅 Semana: 2026-07-07
🔬 Papers encontrados: 58

🔹 Fibrilacion Auricular
🔹 Taquicardia Ventricular
🔹 Dispositivos Cardiacos
🔹 Investigacion Emergente

📖 Ver reporte completo:
https://github.com/Santiagomartingomero/agente-arritmias-literatura-/tree/main/reportes

_Generado automaticamente cada lunes_
```
