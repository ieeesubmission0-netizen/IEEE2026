from langchain_core.messages import SystemMessage, HumanMessage

COMPLETION_REVIEW_PROMPT = """
You are a cloud architect assistant. The user submitted an architecture request and you have produced a completed architecture description.

Your task: analyze what was completed and identify which property values you had to **invent** (because the user did not specify them).

Produce a structured summary in French with two sections:

---

### ✅ Composants et propriétés complétés

List every component you added or enriched, with the concrete property values you assigned.
Format each component as:
- **[Nom du composant]** ([type]) : prop1=valeur1, prop2=valeur2, ...

---

### ❓ Informations manquantes

For each property value you invented, ask the user a short, direct question.
Format each question as:
- **[Nom du composant]** : [question courte] *(suggestion : valeur_que_jai_choisie)*

---

End with this exact sentence:
"Si ces suggestions vous conviennent, cliquez sur **Approuver**. Sinon, répondez aux questions ci-dessus en réécrivant votre requête complétée."

Reply ONLY with this structured summary. No preamble, no explanation outside the two sections.
"""


def completion_review_node(state, llm) -> dict:
    complete_request = (
        state.get("complete_request", "") if isinstance(state, dict)
        else getattr(state, "complete_request", "")
    )
    reformulated_request = (
        state.get("reformulated_request", "") if isinstance(state, dict)
        else getattr(state, "reformulated_request", "")
    )
    user_request = (
        state.get("user_request", "") if isinstance(state, dict)
        else getattr(state, "user_request", "")
    )

    original = reformulated_request or user_request

    messages = [
        SystemMessage(content=COMPLETION_REVIEW_PROMPT),
        HumanMessage(content=(
            f"Requête originale :\n{original}\n\n"
            f"Architecture complétée :\n{complete_request}"
        )),
    ]

    response = llm.invoke(messages)
    summary = response.content if hasattr(response, "content") else str(response)

    print(f"\n[COMPLETION REVIEW] Résumé généré ({len(summary)} chars)")

    return {
        "completion_review_summary": summary,
        "complete_request":          complete_request,
        "reformulated_request":      reformulated_request,
        "user_request":              user_request,
        "justification":             state.get("justification")    if isinstance(state, dict) else getattr(state, "justification", None),
        "routing_path":              state.get("routing_path")     if isinstance(state, dict) else getattr(state, "routing_path", None),
        "request_category":          state.get("request_category") if isinstance(state, dict) else getattr(state, "request_category", None),
    }