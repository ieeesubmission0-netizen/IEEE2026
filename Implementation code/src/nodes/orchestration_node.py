from models.nature_request import RequestCategory
from langchain_core.messages import SystemMessage, HumanMessage
from prompts.orchestration_prompt import orchestration_prompt

ROUTING_PATHS = {
    "business":           ["reformulation", "completion", "json"],
    "service_incomplete": ["completion", "json"],
    "service_complete":   ["json"],
}

def _get_state_value(state, key, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def orchestration_node(state, llm) -> dict:
    user_request = _get_state_value(state, "user_request", "")
    prompt_content = orchestration_prompt.replace("{{USER_REQUEST}}", user_request)

    messages = [
        SystemMessage(content="You are a helpful business analyst. Always respond with exactly two lines: first line starts with CATEGORY: and second line starts with JUSTIFICATION:"),
        HumanMessage(content=prompt_content)
    ]

    response = llm.invoke(messages)
    llm_response = response.content if hasattr(response, 'content') else str(response)
    print(f"🔍 Réponse brute LLM:\n{llm_response}\n")

    category_str, justification = _parse_response(llm_response)
    routing_path = ROUTING_PATHS.get(category_str, ["reformulation", "completion", "json"])

    print(f"✅ Catégorie: {category_str}")
    print(f"📝 Justification: {justification}")
    print(f"🔀 Chemin: {' → '.join(routing_path)}")

    return {
        "request_category": category_str,   # ← string pure ex: "business"
        "justification":    justification,
        "routing_path":     routing_path,
        "user_request":     user_request,
    }


def _parse_response(response: str) -> tuple:
    """Retourne (category_str, justification)"""
    category_str = "business"
    justification = ""

    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("CATEGORY:"):
            raw = line.split(":", 1)[1].strip().lower()
            for cat in RequestCategory:
                if cat.value in raw:
                    category_str = cat.value  # ← .value = "business" etc.
                    break
        elif line.upper().startswith("JUSTIFICATION:"):
            justification = line.split(":", 1)[1].strip()

    if not justification:
        print(f"⚠️ Pas de justification. Réponse brute: {response[:200]}")

    return category_str, justification


def router(state) -> str:
    category = _get_state_value(state, "request_category")
    routing_map = {
        "business":           "reformulation_node",
        "service_incomplete": "completion_node",
        "service_complete":   "json_node",
    }
    destination = routing_map.get(category, "reformulation_node")
    print(f"\n🔀 ROUTER: '{category}' → {destination}\n")
    return destination