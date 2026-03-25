import json as _json

from JsonToTOSCA import generate_tosca_yaml
from config.llm_config import LLMConnector
from enums.llm_type import LLMType
from langgraph.graph import START, END, StateGraph
from nodes.orchestration_node import orchestration_node, router
from nodes.reformulation_node import build_reformulation_node
from nodes.completion_node import completion_node, completion_revision_node
from nodes.json_node import json_node
from root_state import RootState
from kb import ChromaDBManager

LLM_CONFIGS = {
    "GPT_4o_mini":   {"model_name": "gpt-4o-mini",             "llm_type": LLMType.OPEN_AI,  "temperature": 0},
    "Groq_gpt120b":  {"model_name": "openai/gpt-oss-120b",     "llm_type": LLMType.GROQ_AI,  "temperature": 0, "max_retries": 2},
    "mistral_7b":    {"model_name": "open-mistral-7b",         "llm_type": LLMType.MISTRAL,  "temperature": 0},
    "mistral_2512":  {"model_name": "mistral-large-2512",      "llm_type": LLMType.MISTRAL,  "temperature": 0},
    "llama_3.3_70b": {"model_name": "llama-3.3-70b-versatile", "llm_type": LLMType.GROQ_AI,  "temperature": 0},
}


class Agent:
    def __init__(self, model_orchestration: str, model_rewrite: str,
                 model_completion: str, model_json: str):
        config = LLM_CONFIGS.get(model_orchestration)
        if not config:
            raise ValueError(f"Modele non reconnu: {model_orchestration}")
        self.llm = LLMConnector(**config)()

        self.kb_manager = ChromaDBManager()

        # ── Graph complet (utilisé quand pas de reformulation) ──────────
        builder = StateGraph(state_schema=RootState)
        builder.add_node("orchestration_node", lambda s: orchestration_node(s, self.llm))
        builder.add_node("reformulation_node", build_reformulation_node(self.llm, self.kb_manager))
        builder.add_node("completion_node",    lambda s: completion_node(s, self.llm))
        builder.add_node("json_node",          lambda s: json_node(s, self.llm))
        builder.add_edge(START, "orchestration_node")
        builder.add_conditional_edges("orchestration_node", router)
        builder.add_edge("reformulation_node", "completion_node")
        builder.add_edge("completion_node",    END)
        builder.add_edge("json_node",          END)
        self.graph = builder.compile()

        # ── Graph partiel : orchestration + reformulation seulement ─────
        builder2 = StateGraph(state_schema=RootState)
        builder2.add_node("orchestration_node", lambda s: orchestration_node(s, self.llm))
        builder2.add_node("reformulation_node", build_reformulation_node(self.llm, self.kb_manager))
        builder2.add_node("__end_early__",      lambda s: s)
        builder2.add_edge(START, "orchestration_node")
        builder2.add_conditional_edges(
            "orchestration_node",
            lambda s: "reformulation_node" if s.get("request_category") == "business" else "__end_early__"
        )
        builder2.add_edge("reformulation_node", END)
        builder2.add_edge("__end_early__",      END)
        self.graph_phase1 = builder2.compile()

        # ── Graph phase 2 : completion (s'arrête avant json) ────────────
        builder3 = StateGraph(state_schema=RootState)
        builder3.add_node("completion_node", lambda s: completion_node(s, self.llm))
        builder3.add_edge(START,             "completion_node")
        builder3.add_edge("completion_node", END)
        self.graph_phase2_completion = builder3.compile()

        # ── Graph phase 2b : json only (après approbation completion) ───
        builder4 = StateGraph(state_schema=RootState)
        builder4.add_node("json_node", lambda s: json_node(s, self.llm))
        builder4.add_edge(START,       "json_node")
        builder4.add_edge("json_node", END)
        self.graph_phase2_json_only = builder4.compile()

        # ── Graph phase 3 : json seulement (après approbation) ──────────
        builder5 = StateGraph(state_schema=RootState)
        builder5.add_node("json_node", lambda s: json_node(s, self.llm))
        builder5.add_edge(START,       "json_node")
        builder5.add_edge("json_node", END)
        self.graph_phase3_json = builder5.compile()

        # ── Graph révision completion (feedback → completion révisée) ────
        builder6 = StateGraph(state_schema=RootState)
        builder6.add_node("completion_revision_node", lambda s: completion_revision_node(s, self.llm))
        builder6.add_edge(START,                      "completion_revision_node")
        builder6.add_edge("completion_revision_node", END)
        self.graph_completion_revision = builder6.compile()

    # ────────────────────────────────────────────────────────────────────
    # PHASE 1 : orchestration (+ reformulation si "business")
    # ────────────────────────────────────────────────────────────────────
    def invoke_phase1(self, user_request: str) -> dict:
        clean = str(user_request).strip()
        if not clean:
            raise ValueError("user_request ne peut pas etre vide")

        state = self.graph_phase1.invoke({"user_request": clean})

        print("\n=== STATE PHASE 1 ===")
        for k, v in state.items():
            print(f"  {k}: {type(v).__name__} = {repr(v)[:120]}")
        print("====================\n")

        category      = state.get("request_category")
        routing_path  = state.get("routing_path", [])
        needs_approval = category == "business" and state.get("reformulated_request")

        return {
            "request_category":     category,
            "justification":        state.get("justification"),
            "routing_path":         routing_path,
            "reformulated_request": state.get("reformulated_request"),
            "user_request":         clean,
            "needs_approval":       bool(needs_approval),
            "_state":               state,
        }

    # ────────────────────────────────────────────────────────────────────
    # PHASE 2 : completion + completion_review (s'arrête pour approbation)
    # ────────────────────────────────────────────────────────────────────
    def invoke_phase2(self, phase1_result: dict, approved_reformulation: str) -> dict:
        base_state   = phase1_result.get("_state", {})
        routing_path = phase1_result.get("routing_path", [])
        category     = phase1_result.get("request_category")

        state_input = {
            **base_state,
            "reformulated_request":    approved_reformulation,
            "json_output":             None,
            "json_result":             None,
            "complete_request":        None,
            "completion_review_summary": None,
        }

        if category in ("business", "service_incomplete"):
            state = self.graph_phase2_completion.invoke(state_input)
            summary = state.get("completion_review_summary")
            needs_completion_approval = bool(summary)
            print(f"\n[DEBUG PHASE2] completion_review_summary = {repr(summary)[:80]}")
            print(f"[DEBUG PHASE2] needs_completion_approval = {needs_completion_approval}")
        else:
            state = self.graph_phase2_json_only.invoke(state_input)
            needs_completion_approval = False

        print("\n=== STATE PHASE 2 ===")
        for k, v in state.items():
            print(f"  {k}: {type(v).__name__} = {repr(v)[:120]}")
        print("====================\n")

        return {
            "request_category":          category,
            "justification":             phase1_result.get("justification"),
            "routing_path":              routing_path,
            "complete_request":          state.get("complete_request"),
            "completion_review_summary": state.get("completion_review_summary"),
            "needs_completion_approval": needs_completion_approval,
            "_state":                    state,
            "step_results": self._build_result(phase1_result, state, routing_path, approved_reformulation).get("step_results") if not needs_completion_approval else {},
        }

    # ────────────────────────────────────────────────────────────────────
    # PHASE 2b : révision de la completion selon le feedback utilisateur
    # Appelée en boucle tant que l'utilisateur n'approuve pas.
    # ────────────────────────────────────────────────────────────────────
    def invoke_completion_revision(self, phase2_result: dict, user_feedback: str) -> dict:
        """
        Révise la completion selon le feedback utilisateur.
        Appel direct sans LangGraph pour éviter tout écrasement de state.
        """
        routing_path = phase2_result.get("routing_path", [])
        base_state   = phase2_result.get("_state", {})

        # State minimal pour le node : on injecte explicitement le feedback
        # et la completion courante — sans laisser LangGraph écraser quoi que ce soit
        state_input = {
            **base_state,
            "complete_request":          phase2_result.get("complete_request"),
            "completion_feedback":       user_feedback,
            "completion_review_summary": None,
        }

        print(f"\n[invoke_completion_revision] feedback = {repr(user_feedback)[:120]}")
        print(f"[invoke_completion_revision] complete_request = {repr(phase2_result.get('complete_request', ''))[:80]}")

        # Appel DIRECT de la fonction Python — sans passer par LangGraph
        result_state = completion_revision_node(state_input, self.llm)

        print("\n=== STATE COMPLETION REVISION ===")
        for k, v in result_state.items():
            print(f"  {k}: {type(v).__name__} = {repr(v)[:120]}")
        print("=================================\n")

        return {
            "request_category":          phase2_result.get("request_category"),
            "justification":             phase2_result.get("justification"),
            "routing_path":              routing_path,
            "complete_request":          result_state.get("complete_request"),
            "completion_review_summary": result_state.get("completion_review_summary"),
            "needs_completion_approval": True,
            "_state":                    {**base_state, **result_state},
            "step_results":              {},
        }

    # ────────────────────────────────────────────────────────────────────
    # PHASE 3 : json seulement, avec la requête complétée approuvée
    # ────────────────────────────────────────────────────────────────────
    def invoke_phase3(self, phase2_result: dict, approved_complete_request: str) -> dict:
        base_state   = phase2_result.get("_state", {})
        routing_path = phase2_result.get("routing_path", [])

        state_input = {
            **base_state,
            "complete_request":          approved_complete_request,
            "approved_complete_request": approved_complete_request,
        }

        state = self.graph_phase3_json.invoke(state_input)

        print("\n=== STATE PHASE 3 ===")
        for k, v in state.items():
            print(f"  {k}: {type(v).__name__} = {repr(v)[:120]}")
        print("====================\n")

        pseudo_phase1 = {
            "request_category": phase2_result.get("request_category"),
            "justification":    phase2_result.get("justification"),
            "routing_path":     routing_path,
        }
        return self._build_result(pseudo_phase1, state, routing_path, state.get("reformulated_request"))

    # ────────────────────────────────────────────────────────────────────
    # INVOKE DIRECT — conservé pour compatibilité
    # ────────────────────────────────────────────────────────────────────
    def invoke(self, user_request: str) -> dict:
        clean = str(user_request).strip()
        if not clean:
            raise ValueError("user_request ne peut pas etre vide")
        state = self.graph.invoke({"user_request": clean})

        print("\n=== STATE FINAL (clés et types) ===")
        for k, v in state.items():
            print(f"  {k}: {type(v).__name__} = {repr(v)[:120]}")
        print("====================================\n")

        routing_path = state.get("routing_path", [])
        return self._build_result(
            {"request_category": state.get("request_category"),
             "justification":    state.get("justification"),
             "routing_path":     routing_path},
            state,
            routing_path,
            state.get("reformulated_request"),
        )

    # ────────────────────────────────────────────────────────────────────
    # Helper : construit le dict de résultat final commun aux deux modes
    # ────────────────────────────────────────────────────────────────────
    def _build_result(self, phase1: dict, state: dict, routing_path: list,
                      reformulated_request) -> dict:
        step_results = {}

        if "reformulation" in routing_path:
            step_results["reformulation"] = reformulated_request

        if "completion" in routing_path:
            step_results["completion"] = state.get("complete_request")

        if "json" in routing_path:
            json_res  = None
            json_data = None

            json_res = state.get("json_result")
            if json_res:
                try:
                    json_data = _json.loads(json_res)
                except Exception:
                    json_data = None

            if not json_data:
                jo = state.get("json_output")
                if jo:
                    try:
                        json_data = _json.loads(
                            _json.dumps(jo.model_dump(mode="json"), ensure_ascii=False)
                        )
                        json_res = _json.dumps(json_data, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

            step_results["json"] = json_res
            print(f"[DEBUG] json_data type={type(json_data)}, json_res len={len(json_res) if json_res else 0}")

            if json_data:
                try:
                    step_results["tosca"] = generate_tosca_yaml(json_data)
                    print(f"[DEBUG] TOSCA généré ({len(step_results['tosca'])} chars)")
                except Exception as e:
                    step_results["tosca"] = f"# Erreur lors de la génération TOSCA: {e}"
                    print(f"[DEBUG] Erreur TOSCA: {e}")
            else:
                step_results["tosca"] = "# Impossible de générer le TOSCA : JSON invalide"

        print(f"step_results final: {step_results}\n")

        return {
            "request_category": phase1.get("request_category"),
            "justification":    phase1.get("justification"),
            "routing_path":     routing_path,
            "step_results":     step_results,
        }