from typing import TypedDict, Optional, Annotated


def keep_if_none(current, new):
    """Garde la valeur existante si la nouvelle est None."""
    return new if new is not None else current


def always_replace(current, new):
    """Remplace toujours, même par None — permet de réinitialiser entre phases."""
    return new


class RootState(TypedDict, total=False):
    user_request:               str
    request_category:           Annotated[Optional[str],  keep_if_none]
    justification:              Annotated[Optional[str],  keep_if_none]
    routing_path:               Annotated[Optional[list], keep_if_none]
    categorized_request:        Optional[dict]
    reformulated_request:       Annotated[Optional[str],  keep_if_none]
    # ── Ces champs doivent pouvoir être réinitialisés entre phases ───────────
    complete_request:           Annotated[Optional[str],  always_replace]
    json_output:                Annotated[Optional[dict], always_replace]
    json_result:                Annotated[Optional[str],  always_replace]
    completion_review_summary:  Annotated[Optional[str],  always_replace]
    approved_complete_request:  Annotated[Optional[str],  always_replace]
    # ── Feedback utilisateur sur la completion (boucle de révision) ──────────
    completion_feedback:        Annotated[Optional[str],  always_replace]