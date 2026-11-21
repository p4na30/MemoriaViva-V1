# Guía de Despliegue en GCP y Switch Demo / Producción (`MV_APP_MODE`)

Esta guía está pensada para quien opera **Google Cloud Shell / Cloud Run** y necesita desplegar, verificar o alternar entre las dos ediciones de **MemoriaViva RISE v3.0** sin riesgo de mezclar datos ni colisionar bots de Telegram.

---

## 1. Arquitectura Dual (2 Servicios · 2 Buckets · 2 Bots · 2 APKs)

| Concepto | Edición **Demo (Pitch / Jurado)** | Edición **Producción (Limpia / Usuarios Nuevos)** |
| :--- | :--- | :--- |
| **Variable `MV_APP_MODE`** | `demo` (default) | `production` |
| **Servicio Cloud Run** | `memoriaviva-rise` | `memoriaviva-clean` |
| **Bucket GCS (`/app/data`)** | `memoriaviva-data-${PROJECT_ID}` | `memoriaviva-clean-data-${PROJECT_ID}` |
| **Bot de Telegram** | `@Memoria_Viva_Demo_bot` | `@Memoria_viva_bot` |
| **`CLOUD_RUN_MIN_INSTANCES`** | `1` (siempre tibio para el pitch) | `0` (ahorra créditos hasta probar/presentar) |
| **Datos iniciales** | Don Manuel + 10 postales + 21 días + Simulador | 100% vacío (`0` días, calibrando D1–D14 real) |
| **Android APK (`appId`)** | `memoriaviva-demo.apk` (`org.memoriaviva.rise.demo`) | `memoriaviva-clean.apk` (`org.memoriaviva.rise`) |

> **Regla de oro:** Dos servicios Cloud Run con `getUpdates` **NUNCA** pueden compartir el mismo `TELEGRAM_BOT_TOKEN` (genera `409 Conflict` y robo de `/start <uuid>`). El script [cloudrun-deploy.sh](file:///home/d13go/MemoriaViva-V1/deploy/cloudrun-deploy.sh) tiene una **guardia anti-colisión** que aborta el despliegue si detecta el bot equivocado para el modo elegido.

---

## 2. Despliegue Paso a Paso en Cloud Shell

Primero actualiza el repositorio en Cloud Shell:

```bash
cd MemoriaViva-V1
git pull origin main
```

### A. Desplegar o Actualizar **Demo** (`memoriaviva-rise`)

```bash
GEMINI_API_KEY="<TU_GEMINI_KEY>" \
TELEGRAM_DEMO_BOT_TOKEN="<TOKEN_DE_Memoria_Viva_Demo_bot>" \
./deploy/cloudrun-deploy.sh
```

### B. Desplegar **Producción Limpia** (`memoriaviva-clean`)

```bash
MV_APP_MODE=production \
GEMINI_API_KEY="<TU_GEMINI_KEY>" \
TELEGRAM_CLEAN_BOT_TOKEN="<TOKEN_DE_Memoria_viva_bot>" \
./deploy/cloudrun-deploy.sh
```

Al terminar, el script imprime la URL HTTPS del servicio (ej. `https://memoriaviva-clean-xxxxx-uc.a.run.app`).

---

## 3. Verificación Rápida (1 Comando)

Consulta `/api/health` en cualquiera de los dos servicios para confirmar modo, bot y estado de Gemini:

```bash
curl -s https://memoriaviva-rise-gz3a6hv2fa-uc.a.run.app/api/health
```

Qué debes revisar en la respuesta JSON:
- `"app_mode"`: `"demo"` en `memoriaviva-rise`, `"production"` en `memoriaviva-clean`.
- `"telegram_bot_username"`: `"Memoria_Viva_Demo_bot"` en demo, `"Memoria_viva_bot"` en clean.
- `"gemini_configured"`: `true`.
- `"gemini"`: después de ejecutar 1 turno, `"last_model"` mostrará el modelo usado (ej. `"gemini-flash-latest"`). Si cayó a `deterministic_fallback`, `"last_error"` mostrará el motivo exacto sanitizado (sin exponer la llave).

---

## 4. Cómo Hacer el Switch / Toggle sin Recompilar

### A. Cambiar `min-instances` en `memoriaviva-clean` (Ahorro de Créditos)
Por defecto `memoriaviva-clean` arranca con `min-instances=0`. Justo antes de una demo o prueba en vivo con usuarios reales, súbelo a `1` en 5 segundos sin reconstruir la imagen:

```bash
gcloud run services update memoriaviva-clean --region us-central1 --min-instances 1
```

Cuando termines las pruebas, regrésalo a `0`:

```bash
gcloud run services update memoriaviva-clean --region us-central1 --min-instances 0
```

### B. Cambiar `MV_APP_MODE` en un Servicio Existente (No recomendado salvo emergencia)
Si necesitaras cambiar el modo de un servicio ya desplegado, recuerda actualizar **también** su bot de Telegram para evitar colisiones:

```bash
gcloud run services update <NOMBRE_SERVICIO> \
  --region us-central1 \
  --update-env-vars "MV_APP_MODE=production,TELEGRAM_BOT_USERNAME=Memoria_viva_bot,TELEGRAM_BOT_TOKEN=<TOKEN_LIMPIO>"
```

> **Recomendación:** Es mucho más seguro mantener `memoriaviva-rise` siempre en `demo` y `memoriaviva-clean` siempre en `production` con sus buckets separados.

---

## 5. Conectar `memoriaviva-clean.apk` a la URL Limpia

1. Copia la URL HTTPS que devolvió `memoriaviva-clean` al desplegar.
2. En GitHub, ve a **Settings → Secrets and variables → Actions → Variables**.
3. Crea o actualiza la variable **`APP_CLEAN_SERVER_URL`** con esa URL (sin `/` al final).
4. Ve a **Actions → Build MemoriaViva RISE Android APK → Run workflow** (o publica un nuevo tag `v*.*.*`) para generar `memoriaviva-clean.apk` apuntando a tu instancia limpia.

---

## 6. Preguntas Frecuentes (Troubleshooting Rápido)

- **¿Por qué Gemini responde `deterministic_fallback`?**
  Ejecuta un turno y revisa `curl -s https://<URL>/api/health`. El campo `gemini.last_error` te dirá si falta cuota, si la llave está restringida por región/IP o si el modelo devolvió error.
- **¿Por qué Telegram dice "Enlace inválido" al escanear el QR?**
  Revisa que `memoriaviva-rise` tenga `TELEGRAM_BOT_USERNAME=Memoria_Viva_Demo_bot` y `memoriaviva-clean` tenga `TELEGRAM_BOT_USERNAME=Memoria_viva_bot`, cada uno con su propio token.
- **¿Cómo reinicio el Demo de Don Manuel antes del pitch?**
  En el Panel Familiar (**Configuración** o **Simulador Demo**), pulsa **"Reiniciar datos Demo"**. No afecta al servicio `memoriaviva-clean`.
