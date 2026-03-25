from functools import partial
from langchain_core.messages import SystemMessage, HumanMessage
from prompts.refomulation_prompt import reformulation_request_prompt


def reformulation_node(state, llm, kb_manager) -> dict:
    user_request = (
        state.get("user_request", "")
        if isinstance(state, dict)
        else getattr(state, "user_request", "")
    )

    # ✅ Récupérer les 4 exemples les plus similaires depuis la KB
    examples = kb_manager.get_formatted_examples(user_request, n_examples=4)

    # 🔍 Log des exemples utilisés
    print(f"\n[REFORMULATION NODE] {len(examples)} few-shot example(s) retrieved:")
    for i, ex in enumerate(examples, 1):
        print(f"  [{i}] Request     : {ex['request']}")
        print(f"       Reformulated: {ex['reformulated_request']}")
    print()

    # ✅ Construire le bloc few-shot dynamiquement
    few_shot_block = ""
    if examples:
        few_shot_block = "\n\nHere are similar reformulation examples to guide you:\n"
        for i, ex in enumerate(examples, 1):
            few_shot_block += (
                f"\nExample {i}:"
                f"\n  User request: {ex['request']}"
                f"\n  Reformulated: {ex['reformulated_request']}"
            )
        few_shot_block += "\n"

    # ✅ Injecter les exemples dans le prompt système
    enriched_prompt = reformulation_request_prompt + few_shot_block

    messages = [
        SystemMessage(content=enriched_prompt),
        HumanMessage(content=user_request)
    ]

    response = llm.invoke(messages)
    reformulated_request = (
        response.content if hasattr(response, "content") else str(response)
    )

    return {
        "reformulated_request": reformulated_request,
        "reformulation_result": reformulated_request,
        "user_request": user_request,
        "justification": (
            state.get("justification")
            if isinstance(state, dict)
            else getattr(state, "justification", None)
        ),
        "routing_path": (
            state.get("routing_path")
            if isinstance(state, dict)
            else getattr(state, "routing_path", None)
        ),
        "request_category": (
            state.get("request_category")
            if isinstance(state, dict)
            else getattr(state, "request_category", None)
        ),
    }


def build_reformulation_node(llm, kb_manager):
    return partial(reformulation_node, llm=llm, kb_manager=kb_manager)