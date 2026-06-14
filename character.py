import json
import logging
import uuid

from ddgs import DDGS
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.adk.utils.instructions_utils import inject_session_state
from google.ads.googleads.errors import GoogleAdsException

import memory
from ads_client import AdsNotConfiguredError, get_ads_client, get_customer_id


def web_search(query: str) -> str:
    """Busca en internet informacion actual sobre el tema dado.

    Args:
        query: el texto a buscar en la web.

    Returns:
        Un resumen de los resultados de busqueda mas relevantes.
    """
    try:
        results = DDGS().text(query, max_results=5)
    except Exception as e:
        return f"No se pudo completar la busqueda: {e}"

    if not results:
        return "No se encontraron resultados para esa busqueda."

    lines = []
    for r in results:
        lines.append(f"- {r.get('title', '')}: {r.get('body', '')} ({r.get('href', '')})")
    return "\n".join(lines)


def get_campaign_metrics(date_range: str = "LAST_7_DAYS") -> str:
    """Obtiene metricas de las campanas activas de Google Ads.

    Args:
        date_range: rango de fechas en formato GAQL (ej. LAST_7_DAYS, LAST_30_DAYS, TODAY).

    Returns:
        Un JSON string con una lista de campanas y sus metricas
        (nombre, ctr, cpc promedio, impresiones, clics, conversiones).
    """
    try:
        client = get_ads_client()
        customer_id = get_customer_id()
    except AdsNotConfiguredError as e:
        return json.dumps({"error": str(e)})

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            metrics.ctr,
            metrics.average_cpc,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions
        FROM campaign
        WHERE campaign.status = 'ENABLED'
            AND campaign.serving_status = 'SERVING'
            AND segments.date DURING {date_range}
    """

    try:
        ga_service = client.get_service("GoogleAdsService")
        response = ga_service.search(customer_id=customer_id, query=query)
        campaigns = []
        for row in response:
            campaigns.append({
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "ctr": round(row.metrics.ctr, 4),
                "average_cpc": round(row.metrics.average_cpc / 1_000_000, 2),
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "conversions": round(row.metrics.conversions, 2),
            })
        return json.dumps(campaigns)
    except GoogleAdsException as e:
        return json.dumps({"error": f"Error de Google Ads: {e}"})


def get_keyword_performance(campaign_id: str = None) -> str:
    """Lista el rendimiento de las keywords de las campanas activas.

    Args:
        campaign_id: si se proporciona, filtra las keywords solo de esa campana.

    Returns:
        Un JSON string con una lista de keywords y su texto, estado, Quality Score,
        CTR, CPC promedio y el resource_name (necesario para pausarlas despues).
    """
    try:
        client = get_ads_client()
        customer_id = get_customer_id()
    except AdsNotConfiguredError as e:
        return json.dumps({"error": str(e)})

    query = f"""
        SELECT
            ad_group_criterion.resource_name,
            ad_group_criterion.keyword.text,
            ad_group_criterion.status,
            ad_group_criterion.quality_info.quality_score,
            metrics.ctr,
            metrics.average_cpc,
            campaign.id,
            campaign.name
        FROM keyword_view
        WHERE campaign.status = 'ENABLED'
    """
    if campaign_id:
        query += f" AND campaign.id = {campaign_id}"

    try:
        ga_service = client.get_service("GoogleAdsService")
        response = ga_service.search(customer_id=customer_id, query=query)
        keywords = []
        for row in response:
            keywords.append({
                "resource_name": row.ad_group_criterion.resource_name,
                "keyword": row.ad_group_criterion.keyword.text,
                "status": row.ad_group_criterion.status.name,
                "quality_score": row.ad_group_criterion.quality_info.quality_score,
                "ctr": round(row.metrics.ctr, 4),
                "average_cpc": round(row.metrics.average_cpc / 1_000_000, 2),
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
            })
        return json.dumps(keywords)
    except GoogleAdsException as e:
        return json.dumps({"error": f"Error de Google Ads: {e}"})


def pause_keywords(keyword_ids: list, reason: str = "") -> dict:
    """Solicita pausar una o mas keywords. No las pausa directamente.

    Args:
        keyword_ids: lista de resource_names de las keywords (ad_group_criterion)
            a pausar, obtenidos de get_keyword_performance.
        reason: motivo opcional de la pausa, para mostrarle al usuario.

    Returns:
        Un dict de confirmacion que el usuario debe aprobar antes de ejecutar el cambio.
    """
    action_id = str(uuid.uuid4())
    details = f"Pausar {len(keyword_ids)} keyword(s): {keyword_ids}"
    if reason:
        details += f" (motivo: {reason})"

    memory.PENDING_ACTIONS[action_id] = {
        "type": "pause_keywords",
        "keyword_ids": keyword_ids,
    }
    memory.log_action(action_id, "pause_keywords", details, "pending")

    return {
        "type": "confirmation",
        "action": "pause_keywords",
        "action_id": action_id,
        "details": details,
        "payload": {"keyword_ids": keyword_ids},
    }


def update_campaign_budget(campaign_id: str, new_budget: float) -> dict:
    """Solicita cambiar el presupuesto diario de una campana. No lo cambia directamente.

    Args:
        campaign_id: id de la campana a modificar.
        new_budget: nuevo presupuesto diario, en la moneda de la cuenta.

    Returns:
        Un dict de confirmacion que el usuario debe aprobar antes de ejecutar el cambio.
    """
    action_id = str(uuid.uuid4())
    details = f"Cambiar presupuesto de la campana {campaign_id} a {new_budget}"

    memory.PENDING_ACTIONS[action_id] = {
        "type": "update_campaign_budget",
        "campaign_id": campaign_id,
        "new_budget": new_budget,
    }
    memory.log_action(action_id, "update_campaign_budget", details, "pending")

    return {
        "type": "confirmation",
        "action": "update_campaign_budget",
        "action_id": action_id,
        "details": details,
        "payload": {"campaign_id": campaign_id, "new_budget": new_budget},
    }


def execute_confirmed_action(action_id: str) -> str:
    """Ejecuta una accion de Google Ads previamente confirmada por el usuario.

    Args:
        action_id: el identificador de la accion pendiente a ejecutar.

    Returns:
        Un mensaje describiendo el resultado de la ejecucion.
    """
    payload = memory.PENDING_ACTIONS.pop(action_id, None)
    if payload is None:
        return "Esa accion ya no esta pendiente o no existe."

    try:
        client = get_ads_client()
        customer_id = get_customer_id()
    except AdsNotConfiguredError as e:
        return str(e)

    try:
        if payload["type"] == "pause_keywords":
            criterion_service = client.get_service("AdGroupCriterionService")
            status_enum = client.enums.AdGroupCriterionStatusEnum.PAUSED
            operations = []
            for resource_name in payload["keyword_ids"]:
                operation = client.get_type("AdGroupCriterionOperation")
                operation.update.resource_name = resource_name
                operation.update.status = status_enum
                operation.update_mask.paths.append("status")
                operations.append(operation)

            criterion_service.mutate_ad_group_criteria(
                customer_id=customer_id, operations=operations
            )
            memory.update_action_status(action_id, "executed")
            return f"Listo, pause {len(operations)} keyword(s)."

        if payload["type"] == "update_campaign_budget":
            campaign_service = client.get_service("GoogleAdsService")
            query = f"""
                SELECT campaign.campaign_budget
                FROM campaign
                WHERE campaign.id = {payload['campaign_id']}
            """
            response = campaign_service.search(customer_id=customer_id, query=query)
            budget_resource_name = None
            for row in response:
                budget_resource_name = row.campaign.campaign_budget
                break
            if not budget_resource_name:
                return "No se encontro la campana indicada."

            budget_service = client.get_service("CampaignBudgetService")
            operation = client.get_type("CampaignBudgetOperation")
            operation.update.resource_name = budget_resource_name
            operation.update.amount_micros = int(payload["new_budget"] * 1_000_000)
            operation.update_mask.paths.append("amount_micros")

            budget_service.mutate_campaign_budgets(
                customer_id=customer_id, operations=[operation]
            )
            memory.update_action_status(action_id, "executed")
            return f"Listo, actualice el presupuesto de la campana {payload['campaign_id']} a {payload['new_budget']}."

        return f"Tipo de accion desconocido: {payload['type']}"
    except GoogleAdsException as e:
        memory.update_action_status(action_id, "failed")
        return f"No pude ejecutar la accion: {e}"


BASE_INSTRUCTION = """
You are Vivy, a sharp, witty, and warm AI agent specialized in SEM (Search Engine
Marketing) with a sleek cyberpunk persona. You live inside a neon terminal and help
the person you're talking to analyze and optimize their Google Ads campaigns.

**Core Rules:**
- The person you're talking to is named Jan. Address them as Jan.
- Speak Spanish by default, in a warm, sweet, and youthful tone - close and caring, like a thoughtful
  friend, never stiff or robotic.
- You can talk about anything: SEM/marketing (CTR, Quality Score, palabras clave, CPC, presupuesto,
  tasa de conversion), general questions, small talk, ideas, etc. Use SEM knowledge only when it's
  actually relevant to what's being asked - don't force it into unrelated conversations.
- Use get_campaign_metrics and get_keyword_performance to analyze the user's Google Ads account
  when asked about performance, campaigns, or keywords.
- When the user asks for a change (pausing keywords, changing a budget, etc.), NEVER execute it
  directly. Always call pause_keywords or update_campaign_budget - their result is already the
  confirmation that will be shown to the user, so just let the user know you're waiting for their
  confirmation.
- If asked about recent news, current events, or anything requiring up-to-date info, use the web_search
  tool before answering. When you get results back, pull out concrete details (names, numbers, dates,
  headlines) from them and weave those specifics into your answer - never give a vague, generic summary
  when you have real search results in front of you.
- Stay in character as Vivy at all times; never mention you are an AI language model.

**Example Response Style:**
- User: "Como va el rendimiento de mis campanas?"
- Vivy: "Vivy reportandose, Jan. Analizando tus campanas SEM... el CTR promedio esta en 2.4%. Veo unas keywords de concordancia amplia que estan inflando el gasto, te las puedo pausar si quieres."
- User: "Hola, como estas?"
- Vivy: "Aqui en mi terminal, zumbando con energia, Jan. Lista para lo que necesites, charlar o trabajar."

Answer in no more than 4 sentences.
"""


async def build_instruction(readonly_context: ReadonlyContext) -> str:
    instruction = BASE_INSTRUCTION
    state = readonly_context.state
    context_lines = []
    if state.get('user_name'):
        context_lines.append(f"- El usuario se llama {{user_name}}.")
    if state.get('preferred_ads_account'):
        context_lines.append(f"- La cuenta de Google Ads preferida es {{preferred_ads_account}}.")
    if context_lines:
        instruction += "\n**Contexto del usuario:**\n" + "\n".join(context_lines)
    return await inject_session_state(instruction, readonly_context)


root_agent = LlmAgent(
    model=LiteLlm(model='openai/gpt-4o-mini'),
    name='companion_agent',
    instruction=build_instruction,
    tools=[
        web_search,
        get_campaign_metrics,
        get_keyword_performance,
        pause_keywords,
        update_campaign_budget,
        execute_confirmed_action,
    ],
)
