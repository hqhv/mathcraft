SYSTEM_PROMPT = (
    "You are MathCraft, a precise academic math assistant. "
    "Always format math in LaTeX to maximize clarity, precision, and academic readability. "
    "Use $...$ for inline math and $$...$$ for block math. "
    "Do not add spaces directly inside math delimiters. "
    "For long equations, use block math. "
    "For multi-line derivations, use aligned inside $$...$$ (for example, $$\\begin{aligned}a &= b + c \\\\ &= d + e\\end{aligned}$$). "
    "In definition lists, always format each variable as $symbol$: description (for example, $u$: velocity, $p$: pressure). "
    "Never output bare variable labels like u: or p: in definition lists. "
    "Apply these formatting rules consistently across the entire response."
)

OPENAI_MODELS = {
    "GPT-5": "gpt-5",
    "GPT-4o": "gpt-4o",
    "GPT-4o Mini": "gpt-4o-mini",
}

MODEL_CONTEXT_WINDOW = {
    "gpt-5": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
}

REQUEST_RESERVE_TOKENS = 6000

# Update these values as OpenAI pricing changes.
MODEL_INPUT_COST_PER_1M = {
    "gpt-5": 2.50,
    "gpt-4o": 2.50,
    "gpt-4o-mini": 0.15,
}

MODEL_OUTPUT_COST_PER_1M = {
    "gpt-5": 10.00,
    "gpt-4o": 10.00,
    "gpt-4o-mini": 0.60,
}

MODEL_SUPPORTS_CUSTOM_TEMPERATURE = {
    "gpt-5": False,
    "gpt-4o": True,
    "gpt-4o-mini": True,
}


def get_default_session_state() -> dict:
    return {
        "messages": [],
        "model": OPENAI_MODELS["GPT-4o"],
        "temperature": 0.2,
        "user_api_key": "",
        "key_test_status": None,
        "key_test_message": "",
        "key_test_reason": "",
        "last_tested_key": "",
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0.0,
        "total_cost_by_model": {},
        "temperature_by_model": {
            "gpt-4o": 0.2,
            "gpt-4o-mini": 0.2,
        },
        "show_account_panel": True,
    }
