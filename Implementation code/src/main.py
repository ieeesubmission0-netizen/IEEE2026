import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="TOSCA generation", page_icon="🏷️", layout="centered")

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 3rem; max-width: 620px;}
</style>
""", unsafe_allow_html=True)

DEFAULTS = {
    "agent":                        None,
    "agent_ready":                  False,
    "result":                       None,
    "phase1_result":                None,
    "awaiting_approval":            False,
    "correction_text":              "",
    "phase2_result":                None,
    "awaiting_completion_approval": False,
    "completion_correction_text":   "",
    "completion_history":           [],
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

MODELS = ["GPT_4o_mini", "Groq_gpt120b", "mistral_7b", "mistral_2512", "llama_3.3_70b"]

STEP_META = {
    "reformulation": {"icon": "✏️", "label": "Reformulation", "lang": None},
    "completion":    {"icon": "🔧", "label": "Completion",     "lang": None},
    "json":          {"icon": "📄", "label": "Generated JSON", "lang": "json"},
    "tosca":         {"icon": "📦", "label": "Generated TOSCA","lang": "yaml"},
}

ROLE_LABELS = {
    "model_orchestration": ("🧭", "Categorisation"),
    "model_rewrite":       ("✏️", "Reformulation"),
    "model_completion":    ("🔧", "Completion"),
    "model_json":          ("📄", "JSON / TOSCA"),
}


def show_category_and_path(data: dict):
    if data.get("request_category"):
        st.info(f"**Category:** {data['request_category']}", icon="🏷️")
    if data.get("justification"):
        st.caption(data["justification"])
    if data.get("routing_path"):
        st.markdown("**Processing path:**")
        steps = data["routing_path"]
        labels = [
            f"`{STEP_META.get(s, {}).get('icon','⚙️')} {STEP_META.get(s, {}).get('label', s)}`"
            for s in steps
        ]
        st.markdown(" &nbsp;→&nbsp; ".join(labels), unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────
st.title("🏷️ TOSCA Generation")

# ── Model selection per role ────────────────────────────────────────────────
with st.expander("⚙️ Models per role", expanded=not st.session_state.agent_ready):
    st.caption("Choose an independent LLM for each step of the pipeline.")
    role_cols = st.columns(2)
    selected_models: dict[str, str] = {}
    for idx, (role_key, (icon, role_label)) in enumerate(ROLE_LABELS.items()):
        with role_cols[idx % 2]:
            selected_models[role_key] = st.selectbox(
                f"{icon} {role_label}",
                MODELS,
                key=f"model_select_{role_key}",
            )

# ── Init button ─────────────────────────────────────────────────────────────
if st.button("🚀 Initialize", type="primary", use_container_width=True):
    with st.spinner("Initializing…"):
        try:
            from agent_graph import Agent
            st.session_state.agent = Agent(
                model_orchestration=selected_models["model_orchestration"],
                model_rewrite=selected_models["model_rewrite"],
                model_completion=selected_models["model_completion"],
                model_json=selected_models["model_json"],
            )
            st.session_state.agent_ready   = True
            st.session_state.result        = None
            st.session_state.phase1_result = None
            st.session_state.awaiting_approval = False
            st.rerun()
        except Exception as e:
            st.error(f"❌ {e}")

if st.session_state.agent_ready:
    summary_parts = [
        f"{icon} **{lbl}** : `{st.session_state[f'model_select_{key}']}`"
        for key, (icon, lbl) in ROLE_LABELS.items()
    ]
    st.success("Pipeline ready ✅  \n" + "  \n".join(summary_parts))

st.divider()

# ── Input ───────────────────────────────────────────────────────────────────
input_disabled = (
    st.session_state.awaiting_approval
    or st.session_state.awaiting_completion_approval
)

user_request = st.text_area(
    "Request", placeholder="Describe your project…",
    height=80, label_visibility="collapsed", disabled=input_disabled,
)

if st.button("▶️ Categorize", type="primary", use_container_width=True, disabled=input_disabled):
    if not st.session_state.agent_ready:
        st.error("❌ Please initialize the pipeline first.")
    elif not user_request.strip():
        st.error("❌ Please enter a request.")
    else:
        with st.spinner("Analyzing…"):
            try:
                phase1 = st.session_state.agent.invoke_phase1(user_request.strip())
                st.session_state.phase1_result = phase1
                if phase1["needs_approval"]:
                    st.session_state.awaiting_approval = True
                    st.session_state.correction_text   = phase1["reformulated_request"]
                    st.session_state.result            = None
                else:
                    phase2 = st.session_state.agent.invoke_phase2(
                        phase1,
                        approved_reformulation=phase1.get("reformulated_request") or user_request.strip()
                    )
                    if phase2.get("needs_completion_approval"):
                        st.session_state.phase2_result                = phase2
                        st.session_state.awaiting_completion_approval = True
                        st.session_state.completion_history           = []
                        st.session_state.result                       = None
                        st.session_state.awaiting_approval            = False
                    else:
                        st.session_state.result                       = phase2
                        st.session_state.phase1_result                = None
                        st.session_state.awaiting_approval            = False
                        st.session_state.awaiting_completion_approval = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ {e}")

# ── Category + path ─────────────────────────────────────────────────────────
_current_phase = st.session_state.phase1_result or st.session_state.phase2_result
if _current_phase and not st.session_state.result:
    st.divider()
    show_category_and_path(_current_phase)

# ── Reformulation approval ──────────────────────────────────────────────────
if st.session_state.awaiting_approval and st.session_state.phase1_result:
    p1 = st.session_state.phase1_result
    st.markdown("### ✏️ Proposed Reformulation")
    st.markdown("The pipeline has reformulated your request. You can **approve** it as-is or **edit** the text before continuing.")
    corrected = st.text_area("Reformulation (editable)", value=st.session_state.correction_text, height=120, key="correction_textarea")
    st.session_state.correction_text = corrected
    col_approve, col_correct = st.columns(2)
    with col_approve:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            _approved = p1["reformulated_request"]
            with st.spinner("Processing…"):
                try:
                    phase2 = st.session_state.agent.invoke_phase2(p1, _approved)
                    try:
                        st.session_state.agent.kb_manager.store_request(user_request=p1["user_request"], reformulated_request=_approved)
                        st.toast("💾 Pair stored in KB", icon="✅")
                    except Exception as kb_err:
                        st.warning(f"⚠️ KB not updated: {kb_err}")
                    if phase2.get("needs_completion_approval"):
                        st.session_state.phase2_result                = phase2
                        st.session_state.awaiting_completion_approval = True
                        st.session_state.completion_history           = []
                        st.session_state.result                       = None
                        st.session_state.phase1_result                = None
                        st.session_state.awaiting_approval            = False
                        st.session_state.correction_text              = ""
                    else:
                        st.session_state.result            = phase2
                        st.session_state.phase1_result     = None
                        st.session_state.awaiting_approval = False
                        st.session_state.correction_text   = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")
    with col_correct:
        if st.button("📝 Submit my correction", use_container_width=True):
            if not corrected.strip():
                st.error("❌ Reformulation cannot be empty.")
            else:
                with st.spinner("Processing with your correction…"):
                    try:
                        phase2 = st.session_state.agent.invoke_phase2(p1, corrected.strip())
                        try:
                            st.session_state.agent.kb_manager.store_request(user_request=p1["user_request"], reformulated_request=corrected.strip())
                            st.toast("💾 Pair stored in KB (corrected version)", icon="✅")
                        except Exception as kb_err:
                            st.warning(f"⚠️ KB not updated: {kb_err}")
                        if phase2.get("needs_completion_approval"):
                            st.session_state.phase2_result                = phase2
                            st.session_state.awaiting_completion_approval = True
                            st.session_state.completion_history           = []
                            st.session_state.result                       = None
                            st.session_state.phase1_result                = None
                            st.session_state.awaiting_approval            = False
                            st.session_state.correction_text              = ""
                        else:
                            st.session_state.result            = phase2
                            st.session_state.phase1_result     = None
                            st.session_state.awaiting_approval = False
                            st.session_state.correction_text   = ""
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

# ── Completion approval (feedback loop) ────────────────────────────────────
if st.session_state.awaiting_completion_approval and st.session_state.phase2_result:
    p2 = st.session_state.phase2_result

    st.markdown("### 🔧 Completion")

    if p2.get("completion_review_summary"):
        st.markdown(p2["completion_review_summary"])

    st.markdown("---")

    history = st.session_state.get("completion_history", [])
    if history:
        with st.expander(f"📜 Previous versions ({len(history)})", expanded=False):
            for i, old_version in enumerate(history, 1):
                st.markdown(f"**Version {i}:**")
                st.info(old_version, icon="📄")
        st.markdown("")

    st.markdown("**✨ Current version:**")
    if p2.get("complete_request"):
        st.info(p2["complete_request"], icon="🏗️")

    st.markdown("---")

    if st.button("✅ Approve completion", type="primary", use_container_width=True, key="btn_approve_completion"):
        with st.spinner("Generating JSON…"):
            try:
                result = st.session_state.agent.invoke_phase3(p2, p2.get("complete_request", ""))
                st.session_state.result                       = result
                st.session_state.phase2_result                = None
                st.session_state.awaiting_completion_approval = False
                st.session_state.completion_correction_text   = ""
                st.session_state.completion_history           = []
                st.rerun()
            except Exception as e:
                st.error(f"❌ {e}")

    st.markdown("#### 💬 Provide feedback")
    st.markdown("Answer questions or request modifications.")

    with st.form(key="feedback_form", clear_on_submit=True):
        feedback_input = st.text_area(
            "Your feedback",
            placeholder="E.g.: use PostgreSQL instead of MySQL, set 4 CPUs…",
            height=100,
        )
        submitted = st.form_submit_button("📝 Send feedback", use_container_width=True)

    if submitted:
        _feedback = feedback_input.strip()
        if not _feedback:
            st.error("❌ Feedback cannot be empty.")
        else:
            with st.spinner("Revising based on your feedback…"):
                try:
                    if p2.get("complete_request"):
                        st.session_state.completion_history.append(p2["complete_request"])
                    revised = st.session_state.agent.invoke_completion_revision(p2, _feedback)
                    st.session_state.phase2_result                = revised
                    st.session_state.awaiting_completion_approval = True
                    st.session_state.completion_correction_text   = revised.get("complete_request", "")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

# ── Final result ────────────────────────────────────────────────────────────
if st.session_state.result:
    r = st.session_state.result
    st.divider()
    show_category_and_path(r)
    step_results = r.get("step_results", {})
    with st.expander("🐛 Debug — raw result content", expanded=False):
        st.write(r)
    if step_results:
        st.markdown("---")
        st.markdown("### 🔍 Step details")
        display_keys = list(r.get("routing_path", [])) + (["tosca"] if "tosca" in step_results else [])
        for step_key in display_keys:
            content = step_results.get(step_key)
            if content is None:
                st.warning(f"⚠️ No content for step **{step_key}**")
                continue
            meta = STEP_META.get(step_key, {"icon": "⚙️", "label": step_key, "lang": None})
            with st.expander(f"{meta['icon']} **{meta['label']}**", expanded=True):
                if meta["lang"]:
                    st.code(content, language=meta["lang"])
                else:
                    st.markdown(content)
    else:
        st.warning("⚠️ step_results is empty.")

# ── Reset ───────────────────────────────────────────────────────────────────
st.divider()
if st.button("🔄 Reset", use_container_width=True):
    st.session_state.clear()
    st.rerun()