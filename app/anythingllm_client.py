"""
Purpose: Optional AnythingLLM workspace chat client for conversational fallback.
Sample input: A natural-language question not covered by deterministic SQL routing.
Output: AnythingLLM text response, or a clear integration error.
Dependencies: httpx, config.py.
Architecture: query_router returns None -> AnythingLLM -> response_formatter.
Security: API key is read from .env and never logged.
"""

import httpx
from .config import Settings

async def ask_anythingllm(question: str, settings: Settings, session_id: str) -> str:
    """
    Send a question to the configured AnythingLLM workspace.
    Input: question, settings and stable Telegram session ID.
    Output: textResponse from AnythingLLM.
    """
    if not settings.anythingllm_enabled:
        return ("This question requires the AnythingLLM conversational layer, which is not enabled yet. "
                "Please configure the AnythingLLM API key and workspace in .env.")
    url = (
        f"{settings.anythingllm_base_url}/api/v1/workspace/"
        f"{settings.anythingllm_workspace_slug}/chat"
    )
    headers = {"Authorization": f"Bearer {settings.anythingllm_api_key}",
               "Content-Type": "application/json"}
    payload = {"message": question, "mode": "query", "sessionId": session_id}
    async with httpx.AsyncClient(timeout=settings.anythingllm_timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    answer = data.get("textResponse")
    if not answer:
        raise RuntimeError(f"Unexpected AnythingLLM response shape: {list(data.keys())}")
    return answer
