import streamlit as st
from openai import OpenAI
from datetime import datetime
from pathlib import Path
import hashlib
import json

from .config import (
    MODEL_CONTEXT_WINDOW,
    MODEL_INPUT_COST_PER_1M,
    MODEL_OUTPUT_COST_PER_1M,
    MODEL_SUPPORTS_CUSTOM_TEMPERATURE,
    OPENAI_MODELS,
    REQUEST_RESERVE_TOKENS,
    get_default_session_state,
)
from .errors import (
    auth_error_reason,
    auth_error_user_message,
    is_auth_error,
    is_context_length_error,
    should_exclude_failed_prompt,
)
from .openai_client import ask_openai, validate_openai_key
from .rendering import inject_styles, render_response_as_blocks
from .token_utils import (
    build_request_history,
    count_text_tokens,
    count_tokens,
    estimate_input_cost_usd,
    estimate_total_cost_usd,
)


def get_time_based_version() -> str:
    today = datetime.now().strftime("%y.%m.%d")
    repo_root = Path(__file__).resolve().parents[1]
    state_file = repo_root / ".mathcraft_version_state.json"

    tracked_files = [repo_root / "MathCraft.py"]
    tracked_files.extend(sorted((repo_root / "mathcraft_app").glob("*.py")))

    hasher = hashlib.sha256()
    for file_path in tracked_files:
        if file_path.exists():
            hasher.update(file_path.name.encode("utf-8"))
            hasher.update(file_path.read_bytes())
    current_hash = hasher.hexdigest()

    state = {
        "date": today,
        "count": 1,
        "last_hash": current_hash,
    }
    try:
        if state_file.exists():
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded_date = str(loaded.get("date", ""))
                loaded_count = int(loaded.get("count", 1))
                loaded_hash = str(loaded.get("last_hash", ""))

                if loaded_date == today:
                    state["count"] = loaded_count if loaded_count > 0 else 1
                    if loaded_hash != current_hash:
                        state["count"] += 1
                state["date"] = today
                state["last_hash"] = current_hash
    except Exception:
        # Fall back to a safe default if state parsing fails.
        state = {
            "date": today,
            "count": 1,
            "last_hash": current_hash,
        }

    try:
        state_file.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception:
        pass

    return f"v{today}.{state['count']}"


def initialize_session_state() -> None:
    defaults = get_default_session_state()
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### MathCraft")
        st.caption(get_time_based_version())

        with st.expander("Account", expanded=st.session_state.show_account_panel):
            current_key = st.text_input(
                "OpenAI Key",
                type="password",
                key="user_api_key",
                placeholder="sk-...",
                help="Your key is stored only in this browser session.",
            )
            normalized_key = current_key.strip()

            if normalized_key != st.session_state.last_tested_key and (
                st.session_state.key_test_status is not None or st.session_state.key_test_message
            ):
                st.session_state.key_test_status = None
                st.session_state.key_test_message = ""
                st.session_state.key_test_reason = ""
                st.session_state.show_account_panel = True

            if st.button("Check Key", use_container_width=True):
                with st.spinner("Testing API key..."):
                    entered_key = st.session_state.user_api_key.strip()
                    ok, msg, reason = validate_openai_key(entered_key)
                    st.session_state.key_test_message = msg
                    st.session_state.key_test_reason = reason or ""
                    if ok is True:
                        st.session_state.key_test_status = True
                        st.session_state.last_tested_key = entered_key
                        st.session_state.show_account_panel = False
                    elif ok is False:
                        st.session_state.key_test_status = False
                        st.session_state.last_tested_key = entered_key
                        st.session_state.show_account_panel = True
                    else:
                        st.session_state.key_test_status = None
                        st.session_state.last_tested_key = entered_key
                        st.session_state.show_account_panel = True

            if st.session_state.key_test_status is True:
                st.caption("Key status: Valid")
            elif st.session_state.key_test_status is False:
                if st.session_state.key_test_reason == "invalid_key":
                    st.caption("Key status: Invalid")
                else:
                    st.caption("Key status: Authorization issue")
                st.error(st.session_state.key_test_message)
            elif st.session_state.key_test_message:
                st.warning(st.session_state.key_test_message)

        with st.expander("Model", expanded=True):
            model_names = list(OPENAI_MODELS.keys())
            model_values = list(OPENAI_MODELS.values())
            try:
                default_model_index = model_values.index(st.session_state.model)
            except ValueError:
                default_model_index = 1

            model_display = st.selectbox("Model", model_names, index=default_model_index)
            st.session_state.model = OPENAI_MODELS[model_display]
            if MODEL_SUPPORTS_CUSTOM_TEMPERATURE.get(st.session_state.model, True):
                temp_by_model = dict(st.session_state.temperature_by_model)
                current_temp = float(temp_by_model.get(st.session_state.model, 0.2))
                chosen_temp = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=current_temp,
                    step=0.1,
                    help="Lower values are more consistent. Higher values are more creative.",
                )
                st.session_state.temperature = chosen_temp
                temp_by_model[st.session_state.model] = chosen_temp
                st.session_state.temperature_by_model = temp_by_model
            else:
                st.session_state.temperature = 1.0
                st.caption("This model uses fixed temperature.")
            in_rate = MODEL_INPUT_COST_PER_1M.get(st.session_state.model, 0.0)
            out_rate = MODEL_OUTPUT_COST_PER_1M.get(st.session_state.model, 0.0)
            st.caption(f"Pricing profile: ${in_rate:.2f} in / ${out_rate:.2f} out per 1M tokens")

        with st.expander("Usage", expanded=True):
            st.metric("Total Cost", f"${st.session_state.total_cost_usd:.4f}")
            st.caption(
                f"Session: {st.session_state.total_input_tokens:,} in / {st.session_state.total_output_tokens:,} out"
            )
            if st.session_state.total_cost_by_model:
                label_by_value = {value: label for label, value in OPENAI_MODELS.items()}
                breakdown_items = sorted(
                    st.session_state.total_cost_by_model.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
                breakdown_lines = [
                    f"- {label_by_value.get(model_id, model_id)}: ${cost:.4f}"
                    for model_id, cost in breakdown_items
                ]
                st.caption("By model")
                st.markdown("\n".join(breakdown_lines))

            if st.session_state.messages:
                stats_history = build_request_history(
                    st.session_state.messages,
                    model=st.session_state.model,
                    reserve_tokens=REQUEST_RESERVE_TOKENS,
                )
                eligible_for_context = sum(
                    1
                    for m in st.session_state.messages
                    if m.get("role") in {"user", "assistant"} and not m.get("request_failed", False)
                )
                kept_in_context = max(len(stats_history) - 1, 0)
                trimmed_from_context = max(eligible_for_context - kept_in_context, 0)
                total_tokens = count_tokens(stats_history, st.session_state.model)
                estimated_cost = estimate_input_cost_usd(total_tokens, st.session_state.model)
                context_window = MODEL_CONTEXT_WINDOW.get(st.session_state.model, 128000)
                request_budget = max(context_window - REQUEST_RESERVE_TOKENS, 1000)
                context_usage = min(total_tokens / request_budget, 1.0)

                col1, col2 = st.columns(2)
                col1.metric("Next Req Tokens", f"{total_tokens:,}")
                col2.metric("Next Input Cost", f"${estimated_cost:.4f}")
                try:
                    st.progress(context_usage, text=f"Next Req Context: {context_usage:.1%}")
                except TypeError:
                    st.progress(context_usage)
                    st.caption(f"Next Req Context: {context_usage:.1%}")
                st.metric("Trimmed Messages", f"{trimmed_from_context:,}")
                st.caption("Request estimate includes input tokens only.")
            else:
                st.caption("No request stats yet.")

        with st.expander("Session", expanded=False):
            chat_text = "\n\n".join(
                f"{m['role'].title()}: {m['content']}" for m in st.session_state.messages
            )
            st.download_button(
                label="Export Chat",
                data=chat_text,
                file_name="mathcraft_chat.txt",
                mime="text/plain",
                use_container_width=True,
            )


def render_chat_history() -> None:
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant":
                    render_response_as_blocks(msg["content"])
                else:
                    st.markdown(msg["content"])
                    if msg.get("request_failed", False):
                        st.caption("Previous send failed and is excluded from model context.")
        st.markdown("</div>", unsafe_allow_html=True)


def process_prompt(client: OpenAI) -> None:
    prompt = st.chat_input("Ask a math or physics question...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                history = build_request_history(
                    st.session_state.messages,
                    model=st.session_state.model,
                    reserve_tokens=REQUEST_RESERVE_TOKENS,
                )

                context_window = MODEL_CONTEXT_WINDOW.get(st.session_state.model, 128000)
                reserve_tokens = REQUEST_RESERVE_TOKENS

                try:
                    answer, prompt_tokens, completion_tokens = ask_openai(
                        client=client,
                        model=st.session_state.model,
                        messages=history,
                        temperature=st.session_state.temperature,
                    )
                except Exception as api_exc:
                    if not is_context_length_error(api_exc):
                        raise

                    retry_reserve_tokens = min(reserve_tokens + 6000, context_window - 1000)
                    retry_history = build_request_history(
                        st.session_state.messages,
                        model=st.session_state.model,
                        reserve_tokens=retry_reserve_tokens,
                    )
                    history = retry_history
                    try:
                        answer, prompt_tokens, completion_tokens = ask_openai(
                            client=client,
                            model=st.session_state.model,
                            messages=history,
                            temperature=st.session_state.temperature,
                        )
                    except Exception as retry_exc:
                        if is_context_length_error(retry_exc):
                            raise ValueError(
                                "Message is too long for the selected model context. "
                                "Please shorten or split your prompt."
                            ) from retry_exc
                        raise

                if prompt_tokens == 0:
                    prompt_tokens = count_tokens(history, st.session_state.model)
                if completion_tokens == 0:
                    completion_tokens = count_text_tokens(answer, st.session_state.model)

                st.session_state.total_input_tokens += prompt_tokens
                st.session_state.total_output_tokens += completion_tokens
                request_cost = estimate_total_cost_usd(prompt_tokens, completion_tokens, st.session_state.model)
                st.session_state.total_cost_usd += request_cost

                by_model = dict(st.session_state.total_cost_by_model)
                by_model[st.session_state.model] = by_model.get(st.session_state.model, 0.0) + request_cost
                st.session_state.total_cost_by_model = by_model

                st.session_state.messages.append({"role": "assistant", "content": answer})
                render_response_as_blocks(answer)
            except Exception as exc:
                # Keep the failed prompt visible in chat, but exclude it from
                # future model context to avoid unanswered-turn accumulation.
                if should_exclude_failed_prompt(exc) and st.session_state.messages:
                    last_msg = st.session_state.messages[-1]
                    if last_msg.get("role") == "user" and last_msg.get("content") == prompt:
                        last_msg["request_failed"] = True

                if is_context_length_error(exc):
                    err = (
                        "Error: Message is too long for the selected model context. "
                        "Please shorten or split your prompt."
                    )
                else:
                    err = f"Error: {exc}"
                if is_auth_error(exc):
                    st.session_state.key_test_status = False
                    st.session_state.key_test_message = auth_error_user_message(exc)
                    st.session_state.key_test_reason = auth_error_reason(exc)
                    st.session_state.last_tested_key = st.session_state.user_api_key.strip()
                    st.session_state.show_account_panel = True
                st.error(err)


def run_app() -> None:
    inject_styles()
    initialize_session_state()
    render_sidebar()

    api_key = st.session_state.user_api_key.strip()
    if not api_key:
        st.warning("Enter your OpenAI API key in the sidebar to start chatting.")
        st.stop()

    client = OpenAI(api_key=api_key)
    render_chat_history()
    process_prompt(client)
