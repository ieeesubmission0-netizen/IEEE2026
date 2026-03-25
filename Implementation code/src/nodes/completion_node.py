from models.completion_request import CompleteRequest
from langchain_core.messages import SystemMessage, HumanMessage
from prompts.completion_prompt import (
    completion_request_prompt,
    COMPLETION_REVIEW_PROMPT,
    COMPLETION_FEEDBACK_PROMPT,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper privé : génère le résumé review + questions sur les props inventées
# ─────────────────────────────────────────────────────────────────────────────
def _generate_review(llm, input_text: str, complete_request: str) -> str:
    review_messages = [
        SystemMessage(content=COMPLETION_REVIEW_PROMPT),
        HumanMessage(content=(
            f"Requête originale :\n{input_text}\n\n"
            f"Architecture complétée :\n{complete_request}"
        )),
    ]
    review_response = llm.invoke(review_messages)
    return (
        review_response.content if hasattr(review_response, "content") else str(review_response)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Node 1 : completion initiale
# ─────────────────────────────────────────────────────────────────────────────
def completion_node(state, llm) -> dict:
    reformulated_request = (
        state.get("reformulated_request", "") if isinstance(state, dict)
        else getattr(state, "reformulated_request", "")
    )
    user_request = (
        state.get("user_request", "") if isinstance(state, dict)
        else getattr(state, "user_request", "")
    )

    input_text = reformulated_request or user_request

    # ── Étape 1 : completion structurée ─────────────────────────────────
    messages = [
        SystemMessage(content=completion_request_prompt),
        HumanMessage(content=input_text),
    ]
    structured_llm = llm.with_structured_output(CompleteRequest)
    response: CompleteRequest = structured_llm.invoke(messages)
    complete_request = response.complete_request

    # ── Étape 2 : générer le résumé + questions sur les props inventées ──
    completion_review_summary = _generate_review(llm, input_text, complete_request)

    print(f"\n[COMPLETION NODE] Résumé review généré ({len(completion_review_summary)} chars)")

    return {
        "complete_request":          complete_request,
        "completion_review_summary": completion_review_summary,
        "reformulated_request":      reformulated_request,
        "user_request":              user_request,
        "justification":             state.get("justification"),
        "routing_path":              state.get("routing_path"),
        "request_category":          state.get("request_category"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 : révision de la completion selon le feedback utilisateur
# ─────────────────────────────────────────────────────────────────────────────
def completion_revision_node(state, llm) -> dict:
    """
    Révise la completion existante en tenant compte du feedback utilisateur.
    Appelé en boucle tant que l'utilisateur n'approuve pas.
    """
    reformulated_request = (
        state.get("reformulated_request", "") if isinstance(state, dict)
        else getattr(state, "reformulated_request", "")
    )
    user_request = (
        state.get("user_request", "") if isinstance(state, dict)
        else getattr(state, "user_request", "")
    )
    current_completion = (
        state.get("complete_request", "") if isinstance(state, dict)
        else getattr(state, "complete_request", "")
    )
    feedback = (
        state.get("completion_feedback", "") if isinstance(state, dict)
        else getattr(state, "completion_feedback", "")
    )

    input_text = reformulated_request or user_request

    print(f"\n[COMPLETION REVISION NODE] Feedback reçu : {repr(feedback)[:120]}")

    # ── Révision guidée par le feedback ─────────────────────────────────
    revision_messages = [
        SystemMessage(content=COMPLETION_FEEDBACK_PROMPT),
        HumanMessage(content=(
            f"Original request:\n{input_text}\n\n"
            f"Previously completed architecture:\n{current_completion}\n\n"
            f"User feedback:\n{feedback}"
        )),
    ]
    revision_response = llm.invoke(revision_messages)
    revised_completion = (
        revision_response.content if hasattr(revision_response, "content")
        else str(revision_response)
    )

    # ── Re-générer le résumé review pour la version révisée ─────────────
    completion_review_summary = _generate_review(llm, input_text, revised_completion)

    print(f"[COMPLETION REVISION NODE] Révision générée ({len(revised_completion)} chars)")

    return {
        "complete_request":          revised_completion,
        "completion_review_summary": completion_review_summary,
        "completion_feedback":       None,   # reset pour la prochaine itération
        "reformulated_request":      reformulated_request,
        "user_request":              user_request,
        "justification":             state.get("justification"),
        "routing_path":              state.get("routing_path"),
        "request_category":          state.get("request_category"),
    }