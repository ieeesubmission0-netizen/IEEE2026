from models.json_request import JsonRequest
from langchain_core.messages import SystemMessage, HumanMessage
from root_state import RootState
from prompts.json_prompt import json_request_prompt
import json as json_lib
import re


_MAX_RETRIES = 3


def _parse_json_from_llm(raw_text: str) -> dict:
    """
    Extrait le JSON de la réponse brute du LLM,
    même si elle est entourée de balises ```json ... ``` ou ``` ... ```.
    """
    # 1) Essai direct
    try:
        return json_lib.loads(raw_text.strip())
    except Exception:
        pass

    # 2) Extraction depuis un bloc markdown ```json ... ``` ou ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if match:
        try:
            return json_lib.loads(match.group(1))
        except Exception:
            pass

    # 3) Extraction du premier { ... } trouvé dans le texte
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            return json_lib.loads(match.group(0))
        except Exception:
            pass

    raise ValueError(f"Impossible d'extraire un JSON valide de la réponse LLM : {raw_text[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation : le LLM produit parfois des dicts à la place de listes
# pour `properties` et `capabilities`. On corrige ici avant model_validate.
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_properties(props) -> list:
    """
    Convertit properties en liste de Property-compatibles.
    Accepte :
      - None / [] → []
      - list déjà correcte → inchangée (on normalise quand même les items)
      - dict plat  {"num_cpus": 2, ...} → [{"name": "num_cpus", "value": 2, ...}]
    """
    if not props:
        return []

    if isinstance(props, dict):
        result = []
        for k, v in props.items():
            if isinstance(v, dict):
                # ex: {"num_cpus": {"value": 2, "description": "..."}}
                item = {"name": k, "value": v.get("value"), "description": v.get("description", ""), "type": v.get("type", "string"), "required": v.get("required", False)}
            else:
                item = {"name": k, "value": v, "description": "", "type": "string", "required": False}
            result.append(item)
        return result

    if isinstance(props, list):
        normalized = []
        for item in props:
            if isinstance(item, dict):
                # S'assurer que les champs obligatoires de Property sont présents
                normalized.append({
                    "name":        item.get("name", ""),
                    "description": item.get("description", ""),
                    "type":        item.get("type", "string"),
                    "required":    item.get("required", False),
                    "value":       item.get("value"),
                })
            else:
                normalized.append(item)
        return normalized

    return []


def _normalize_capabilities(caps) -> list:
    """
    Convertit capabilities en liste de Capability-compatibles.
    Accepte :
      - None / [] → []
      - list déjà correcte → on normalise quand même les properties internes
      - dict {"host": {"valid_source_types": [...], "properties": {...}}}
            → [{"name": "host", "valid_source_types": [...], "properties": [...]}]
    """
    if not caps:
        return []

    if isinstance(caps, dict):
        result = []
        for k, v in caps.items():
            if isinstance(v, dict):
                cap = {
                    "name": k,
                    "valid_source_types": v.get("valid_source_types", []),
                    "properties": _normalize_properties(v.get("properties", [])),
                }
            else:
                cap = {"name": k, "valid_source_types": [], "properties": []}
            result.append(cap)
        return result

    if isinstance(caps, list):
        normalized = []
        for cap in caps:
            if isinstance(cap, dict):
                normalized.append({
                    "name":               cap.get("name", ""),
                    "valid_source_types": cap.get("valid_source_types", []),
                    "properties":         _normalize_properties(cap.get("properties", [])),
                })
            else:
                normalized.append(cap)
        return normalized

    return []


def _normalize_requirements(reqs) -> list:
    """
    Convertit requirements en liste de requirement-compatibles.
    Accepte list ou dict.
    """
    if not reqs:
        return []

    if isinstance(reqs, dict):
        return [{"name": k, "node": v if isinstance(v, str) else v.get("node", "")}
                for k, v in reqs.items()]

    if isinstance(reqs, list):
        return reqs

    return []


def _normalize_node(node: dict) -> dict:
    """Normalise un nœud complet."""
    node["properties"]    = _normalize_properties(node.get("properties", []))
    node["capabilities"]  = _normalize_capabilities(node.get("capabilities", []))
    node["requirements"]  = _normalize_requirements(node.get("requirements", []))
    return node


def _normalize_json_data(data: dict) -> dict:
    """Normalise toute la structure JSON avant model_validate."""
    if "nodes" in data and isinstance(data["nodes"], list):
        data["nodes"] = [_normalize_node(n) for n in data["nodes"]]
    return data


# ─────────────────────────────────────────────────────────────────────────────

def json_node(state: RootState, llm) -> dict:
    complete_request     = state.get("complete_request")         if isinstance(state, dict) else getattr(state, "complete_request", None)
    reformulated_request = state.get("reformulated_request", "") if isinstance(state, dict) else getattr(state, "reformulated_request", "")
    user_request         = state.get("user_request", "")         if isinstance(state, dict) else getattr(state, "user_request", "")
    request_category     = state.get("request_category")         if isinstance(state, dict) else getattr(state, "request_category", None)
    categorized_request  = state.get("categorized_request")      if isinstance(state, dict) else getattr(state, "categorized_request", None)
    reformulation_result = state.get("reformulation_result")     if isinstance(state, dict) else getattr(state, "reformulation_result", None)
    completion_result    = state.get("completion_result")        if isinstance(state, dict) else getattr(state, "completion_result", None)

    request_to_convert = complete_request or reformulated_request or user_request

    print(f"\n📋 [JSON] Génération JSON: '{request_to_convert[:60]}...'")

    base_messages = [
        SystemMessage(content=json_request_prompt),
        HumanMessage(content=f"<request>{request_to_convert}</request>")
    ]

    json_output  = None
    json_result  = None
    last_error   = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            if attempt == 1:
                messages = base_messages
            else:
                correction_hint = (
                    f"Your previous response caused this error: {last_error}. "
                    "Return ONLY a raw JSON object (no markdown, no ```json``` fences). "
                    "CRITICAL FORMAT RULES for every node:\n"
                    "- 'properties' must be a LIST of objects: "
                    "[{\"name\": \"num_cpus\", \"description\": \"...\", \"type\": \"integer\", \"required\": false, \"value\": 2}]\n"
                    "- 'capabilities' must be a LIST of objects with 'name' (string), "
                    "'valid_source_types' (list of strings), and 'properties' (list as above)\n"
                    "- 'requirements' must be a LIST of objects: [{\"name\": \"host\", \"node\": \"MyVM\"}]\n"
                    "- NEVER use a dict/object for 'properties', 'capabilities', or 'requirements'\n"
                    "- 'nodes' must contain at least one complete node object."
                )
                messages = base_messages + [HumanMessage(content=correction_hint)]

            print(f"🔄 [JSON] Tentative {attempt}/{_MAX_RETRIES}…")

            # ── Appel brut ────────────────────────────────────────────────────
            raw_response = llm.invoke(messages)
            raw_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
            print(f"🔍 [JSON] Réponse brute (300 chars) : {raw_text[:300]}\n")

            # ── Parse manuel du JSON ──────────────────────────────────────────
            data = _parse_json_from_llm(raw_text)

            # ── Normalisation dict → list (properties / capabilities / requirements)
            data = _normalize_json_data(data)

            # ── Validation : nodes doit exister et ne pas être vide ──────────
            if not data.get("nodes"):
                raise ValueError("Le JSON parsé ne contient pas de nœuds ('nodes' vide ou absent)")

            # ── Conversion en objet Pydantic JsonRequest ──────────────────────
            json_output = JsonRequest.model_validate(data)

            if not json_output.nodes:
                raise ValueError("JsonRequest.nodes est vide après model_validate")

            print(f"✅ [JSON] Tentative {attempt} réussie — {len(json_output.nodes)} nœuds")

            # Resérialise proprement (enums → strings via mode='json')
            json_result = json_lib.dumps(
                json_output.model_dump(mode="json"), ensure_ascii=False, indent=2
            )
            break

        except Exception as e:
            last_error = str(e)
            print(f"⚠️ [JSON] Tentative {attempt} échouée : {last_error[:150]}")
            if attempt == _MAX_RETRIES:
                print(f"❌ [JSON] Echec après {_MAX_RETRIES} tentatives")
                json_output = None
                json_result = json_lib.dumps(
                    {"description": "Erreur de génération JSON", "nodes": []},
                    ensure_ascii=False, indent=2
                )

    return {
        "json_output":          json_output,
        "json_result":          json_result,
        "complete_request":     complete_request,
        "reformulated_request": reformulated_request,
        "user_request":         user_request,
        "request_category":     request_category,
        "categorized_request":  categorized_request,
        "reformulation_result": reformulation_result,
        "completion_result":    completion_result,
        "justification":  state.get("justification")  if isinstance(state, dict) else getattr(state, "justification", None),
        "routing_path":   state.get("routing_path")   if isinstance(state, dict) else getattr(state, "routing_path", None),
    }