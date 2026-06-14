# Agente SEM

Agente conversacional con IA, y avatar animado, que analiza campañas de Google Ads, sugiere optimizaciones y ejecuta cambios (con confirmación) mediante lenguaje natural.

## Cómo funciona

```
Usuario (chat / voz)
     │
     ▼
Vivy — Agente LLM (GPT-4o-mini + Google ADK)
     │
     ├─► Google Ads API ──► leer métricas (CTR, CPC, impresiones, conversiones)
     │                  ──► pausar keywords / ajustar presupuesto (con confirmación)
     │
     ├─► Web Search (DuckDuckGo) ──► contexto de mercado 
     │
     ├─► Visión multimodal ──► análisis de capturas de pantalla de Google Ads
     │
     └─► Flask backend ──► conversaciones y mensajes persistidos en PostgreSQL
                       ──► memoria de preferencias (SQLite)
                       ──► reporte HTML descargable por rango de fechas
```

El avatar anima la boca en sincronía con la respuesta hablada (Web Speech API), y la interfaz tiene dos modos visuales.

---

## Demo

[▶️ Ver video de demo](https://github.com/gopar-ai/vivy-agente-sem/releases/download/demo-v1/Vivy.-.Google.Chrome.2026-06-14.00-36-07.mp4)

---

## Setup

```bash
cp .env.example .env   # completa tus credenciales
pip install -r requirements.txt
python app.py
```

El servidor queda disponible en `http://localhost:5000`.

## Variables de entorno

| Variable | Descripción |
|---|---|
| `PORT` | Puerto del servidor (default: `5000`) |
| `FLASK_DEBUG` | `1` para modo debug, `0` en producción |
| `OPENAI_API_KEY` | API key de OpenAI (modelo GPT-4o-mini vía LiteLLM) |
| `GEMINI_API_KEY` | API key de Gemini (opcional, según el modelo configurado) |
| `DATABASE_URL` | URL de conexión a PostgreSQL para persistir conversaciones y mensajes. Si no está disponible, la app hace fallback automático a SQLite local |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Token de desarrollador de Google Ads |
| `GOOGLE_ADS_CLIENT_ID` | OAuth2 client ID |
| `GOOGLE_ADS_CLIENT_SECRET` | OAuth2 client secret |
| `GOOGLE_ADS_REFRESH_TOKEN` | OAuth2 refresh token |
| `GOOGLE_ADS_CUSTOMER_ID` | ID de cuenta de Google Ads |

---

## Tech stack

- **Google ADK + LiteLLM (GPT-4o-mini)** — agente conversacional
- **Python / Flask** — backend
- **PostgreSQL** — persistencia de conversaciones y mensajes (con fallback a SQLite)
- **Google Ads API v19** — métricas y acciones sobre campañas
- **DuckDuckGo Search** — contexto de mercado y noticias
- **Vanilla JS / CSS** — frontend, modos Cyber y Elegante, animación de avatar y Web Speech API
- **Railway** — deploy
