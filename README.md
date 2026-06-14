# vivy-agente-sem

Agente SEM con IA que analiza campañas, sugiere optimizaciones y ejecuta cambios directos en Google Ads mediante lenguaje natural.

## Cómo funciona

Jan (chat)
     │
     ▼
Vivy — Agente LLM (GPT-4o-mini + Google ADK)
     │
     ├─► Google Ads API ──► leer métricas (CTR, CPC, impresiones, conversiones)
     │                  ──► pausar keywords / ajustar presupuesto (con confirmación)
     │
     ├─► Web Search (DuckDuckGo) ──► contexto de mercado y noticias
     │
     ├─► Visión multimodal ──► análisis de capturas de pantalla de Google Ads
     │
     └─► Flask backend ──► historial de conversaciones + memoria de preferencias
                       ──► reporte HTML descargable por rango de fechas

## Stack

| Capa | Tecnología |
|---|---|
| Agente | Google ADK + LiteLLM (GPT-4o-mini) |
| Backend | Python / Flask |
| Ads | Google Ads API v19 |
| Search | DuckDuckGo Search |
| Frontend | Vanilla JS / CSS — modos Cyber y Elegante |
| Deploy | Railway |

## Setup

1. Clona el repo
2. Copia `.env.example` a `.env` y llena las variables
3. `pip install -r requirements.txt`
4. `python app.py`

## Variables de entorno

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | API key de OpenAI |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Token de desarrollador de Google Ads |
| `GOOGLE_ADS_CLIENT_ID` | OAuth client ID |
| `GOOGLE_ADS_CLIENT_SECRET` | OAuth client secret |
| `GOOGLE_ADS_REFRESH_TOKEN` | Refresh token OAuth |
| `GOOGLE_ADS_CUSTOMER_ID` | ID de cuenta de Google Ads |
