import tiktoken

from .config import MODEL_CONTEXT_WINDOW, MODEL_INPUT_COST_PER_1M, MODEL_OUTPUT_COST_PER_1M, SYSTEM_PROMPT


def count_tokens(messages: list[dict], model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens_per_message = 3
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for _, value in message.items():
            num_tokens += len(encoding.encode(str(value)))
    num_tokens += 3
    return num_tokens


def count_text_tokens(text: str, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text or ""))


def estimate_input_cost_usd(total_tokens: int, model: str) -> float:
    per_1m = MODEL_INPUT_COST_PER_1M.get(model)
    if per_1m is None:
        return 0.0
    return (total_tokens / 1_000_000) * per_1m


def estimate_output_cost_usd(total_tokens: int, model: str) -> float:
    per_1m = MODEL_OUTPUT_COST_PER_1M.get(model)
    if per_1m is None:
        return 0.0
    return (total_tokens / 1_000_000) * per_1m


def estimate_total_cost_usd(input_tokens: int, output_tokens: int, model: str) -> float:
    return estimate_input_cost_usd(input_tokens, model) + estimate_output_cost_usd(output_tokens, model)


def build_request_history(
    messages: list[dict],
    max_user_turns: int = 6,
    model: str | None = None,
    reserve_tokens: int = 2000,
) -> list[dict]:
    # Keep a turn-aware window (by user turns) to avoid cutting context mid-conversation.
    convo = [
        {"role": m.get("role", ""), "content": m.get("content", "")}
        for m in messages
        if m.get("role") in {"user", "assistant"} and not m.get("request_failed", False)
    ]

    selected_reversed = []
    user_turns = 0
    for msg in reversed(convo):
        selected_reversed.append(msg)
        if msg["role"] == "user":
            user_turns += 1
            if user_turns >= max_user_turns:
                break

    selected = list(reversed(selected_reversed))
    while selected and selected[0]["role"] == "assistant":
        selected.pop(0)

    history = [{"role": "system", "content": SYSTEM_PROMPT}] + selected

    if model:
        context_window = MODEL_CONTEXT_WINDOW.get(model, 128000)
        # Keep a reserve so the model has room for completion and protocol overhead.
        token_budget = max(context_window - reserve_tokens, 1000)
        while count_tokens(history, model) > token_budget:
            user_count = sum(1 for m in history[1:] if m["role"] == "user")
            if user_count <= 1:
                break

            drop_start = next(
                i
                for i in range(1, len(history))
                if history[i]["role"] == "user"
            )
            drop_end = len(history)
            for j in range(drop_start + 1, len(history)):
                if history[j]["role"] == "user":
                    drop_end = j
                    break
            del history[drop_start:drop_end]

    return history
