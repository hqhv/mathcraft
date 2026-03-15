import html
import json
import re

import requests
import streamlit as st
import streamlit.components.v1 as components

API_KEY = "ef33bc1b5db07fa62e72840b7c518abf815226446fec854831a927696534b250"
URL = "https://api.1min.ai/api/chat-with-ai"
HEADERS = {
    "Content-Type": "application/json",
    "API-KEY": API_KEY
}

MODELS = {
    "OpenAI - GPT-5": {"id": "gpt-5", "desc": "Most advanced GPT model"},
    "OpenAI - GPT-4o": {"id": "gpt-4o", "desc": "Balanced performance & cost"},
    "OpenAI - GPT-4o Mini": {"id": "gpt-4o-mini", "desc": "Fast & affordable"},
    "OpenAI - GPT-3.5 Turbo": {"id": "gpt-3.5-turbo", "desc": "Legacy reliable model"},
    "Anthropic - Claude Sonnet 4.5": {"id": "claude-sonnet-4-5-20250929", "desc": "Excellent reasoning"},
    "Anthropic - Claude Opus 4.5": {"id": "claude-opus-4-5-20251101", "desc": "Most capable Claude"},
    "GoogleAI - Gemini 3.1 Pro": {"id": "gemini-3.1-pro-preview", "desc": "Google's latest"},
    "GoogleAI - Gemini 2.5 Pro": {"id": "gemini-2.5-pro", "desc": "Stable Gemini"},
    "xAI - Grok 4 Fast Reasoning": {"id": "grok-4-fast-reasoning", "desc": "xAI's fast thinker"},
    "DeepSeek - DeepSeek Reasoner": {"id": "deepseek-reasoner", "desc": "Strong reasoning"},
    "Mistral - Mistral Large": {"id": "mistral-large-latest", "desc": "European AI"}
}

SYSTEM_PROMPT = (
    "Act as a LaTeX expert. All math must be in LaTeX. "
    "Use $ for inline math and $$ for block math. "
    "Crucial: Ensure there is NO space between the $ delimiter and the first or last character of the formula. "
    "Treat inline math as a word boundary: include one space before an opening $ and one space after a closing $, unless punctuation follows. "
    "Example: the value is $x=5$ now. "
    "For chemical elements or units, use \\text{} (or \\mathrm{}). "
    "If an equation is longer than 50 characters, always use $$ (block format) to prevent layout breaking. "
    "When defining variables in a list, always wrap the symbol in single dollar signs (e.g., $v$) and put the definition immediately after. "
    "For multi-line equations, always use the aligned environment inside $$: "
    "$$\\begin{aligned} x &= y + z \\\\ &= a + b \\end{aligned}$$."
)

def ultra_clean_latex(text):
    """Normalize LaTeX delimiters and spacing for Streamlit markdown."""
    if not text:
        return ""

    # 1) Normalize bracket/paren delimiters to Streamlit-friendly forms.
    text = re.sub(r'\\\[\s*(.*?)\s*\\\]', r'$$\1$$', text, flags=re.DOTALL)
    text = re.sub(r'\\\(\s*(.*?)\s*\\\)', r'$\1$', text, flags=re.DOTALL)

    # 2) Tighten spaces inside delimiters, keeping block and inline separate.
    text = re.sub(r'\$\$\s*(.*?)\s*\$\$', r'$$\1$$', text, flags=re.DOTALL)
    text = re.sub(r'(?<!\$)\$\s*([^$\n]+?)\s*\$(?!\$)', r'$\1$', text)

    # 3) Add visual word-boundary spacing around inline math tokens only.
    text = re.sub(r'(?<=[A-Za-z0-9\)\]])(\$[^$\n]+?\$)', r' \1', text)
    text = re.sub(r'(\$[^$\n]+?\$)(?=[A-Za-z0-9\(])', r'\1 ', text)

    # 4) Remove duplicated equation lines (common model artifact).
    lines = text.splitlines()
    out = []
    seen_eq = set()
    for ln in lines:
        key = re.sub(r'\s+', '', ln)
        is_equation = ('=' in ln) and ('$' in ln or '\\' in ln)
        if is_equation and key in seen_eq:
            continue
        if is_equation:
            seen_eq.add(key)
        out.append(ln)

    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()


def auto_highlight_variables(text):
    """Wrap short inline math variables with a styled span for emphasis."""
    if not text:
        return ""

    # Match only true single-variable inline tokens like $v$, $t$, or $\rho$.
    # This intentionally excludes short expressions such as $x+1$ or $ab$.
    variable_pattern = r'\$(\\[A-Za-z]+|[A-Za-z])\$'

    def replace_with_style(match):
        var = match.group(1)
        return f'<span class="math-variable">${var}$</span>'

    return re.sub(variable_pattern, replace_with_style, text)


def sanitize_model_markdown(text):
    """Escape raw HTML from model output before using unsafe_allow_html."""
    if not text:
        return ""
    return html.escape(text, quote=False)


def render_response_as_blocks(text):
    """Render assistant output with enhanced LaTeX visibility."""
    cleaned_text = ultra_clean_latex(text)
    equation_counter = 0

    def _equation_columns():
        """Create equation/number columns with centered alignment when supported."""
        try:
            return st.columns([20, 1], vertical_alignment="center")
        except TypeError:
            return st.columns([20, 1])

    def _render_mathjax_fallback(equation, number=None):
        """Render complex equations with MathJax in an isolated HTML block."""
        label = f"({number})" if number is not None else ""
        html = f"""
        <div style="margin:0.8em 0;padding:12px 20px;background:rgba(31, 119, 180, 0.05);border-radius:4px;border-left:3px solid #1f77b4;box-shadow:0 2px 4px rgba(0,0,0,0.02);overflow-x:auto;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
                <div id="mj-eq">\\[{equation}\\]</div>
                <div style="color:#666;font-style:italic;white-space:nowrap;">{label}</div>
            </div>
        </div>
        <script>
            window.MathJax = {{
                tex: {{
                    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                    processEscapes: true
                }},
                options: {{ enableMenu: true }}
            }};
        </script>
        <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
        """
        components.html(html, height=120, scrolling=True)

    def _needs_mathjax_fallback(equation):
        complex_tokens = [
            "\\begin{aligned}", "\\begin{matrix}", "\\begin{pmatrix}",
            "\\begin{bmatrix}", "\\begin{cases}", "\\tag{"
        ]
        return any(token in equation for token in complex_tokens)

    parts = re.split(r'(\$\$.*?\$\$)', cleaned_text, flags=re.DOTALL)
    for part in parts:
        if not part.strip():
            continue
        if part.startswith('$$') and part.endswith('$$'):
            equation = part[2:-2].strip()
            if equation:
                equation_counter += 1
                if _needs_mathjax_fallback(equation):
                    _render_mathjax_fallback(equation, equation_counter)
                else:
                    col_eq, col_no = _equation_columns()
                    with col_eq:
                        st.latex(equation)
                    with col_no:
                        st.markdown(
                            f"<div style='text-align:right; color:#666; font-style:italic; line-height:1.4;'>({equation_counter})</div>",
                            unsafe_allow_html=True,
                        )
        else:
            safe_part = sanitize_model_markdown(part)
            processed_part = auto_highlight_variables(safe_part)
            st.markdown(processed_part, unsafe_allow_html=True)


def call_ai_api(prompt, model):
    """Call the 1min.ai API with the given prompt and model."""
    data = {
        "type": "UNIFY_CHAT_WITH_AI",
        "model": model,
        "promptObject": {
            "prompt": prompt,
            "systemPrompt": SYSTEM_PROMPT,
            "settings": {
                "historySettings": {
                    "isMixed": False,
                    "historyMessageLimit": 10
                }
            }
        }
    }
    
    try:
        response = requests.post(URL, headers=HEADERS, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Extract credit info
        team_user = result["aiRecord"]["teamUser"]
        credit_limit = team_user["creditLimit"]
        used_credit = team_user["usedCredit"]
        available_credit = credit_limit - used_credit
        
        return {
            "response": result["aiRecord"]["aiRecordDetail"]["resultObject"][0],
            "credit_limit": credit_limit,
            "used_credit": used_credit,
            "available_credit": available_credit
        }
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")
    except (KeyError, json.JSONDecodeError) as e:
        raise Exception(f"Invalid API response: {str(e)}")

st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 2.5em;
        margin-bottom: 1em;
    }
    .chat-container {
        max-width: 800px;
        margin: 0 auto;
    }
    .sidebar-content {
        padding: 1em;
    }
    .model-desc {
        font-size: 0.9em;
        color: #666;
        margin-top: 0.5em;
    }
    .stChatMessage {
        border-radius: 15px;
        margin: 0.5em 0;
        padding: 1em;
    }
    .stChatMessage[data-testid="user"] {
        background-color: #e3f2fd;
        border: 1px solid #bbdefb;
    }
    .stChatMessage[data-testid="assistant"] {
        background-color: #f5f5f5;
        border: 1px solid #e0e0e0;
    }

    /* The Master Container for Math Blocks */
    .katex-display {
        background-color: rgba(31, 119, 180, 0.05) !important;
        padding: 12px 20px !important;
        margin: 0.8em 0 !important;
        border-left: 3px solid #1f77b4 !important;
        border-radius: 4px !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02) !important;
        overflow-x: auto !important;
    }

    /* Enhanced inline math styling */
    .katex {
        font-size: 1.1em !important;
    }

    /* Color coding for math elements */
    .katex .mord {
        color: #1f77b4 !important;
    }
    .katex .mbin {
        color: #ff7f0e !important;
    }
    .katex .mrel {
        color: #2ca02c !important;
    }

    /* Optional variable-highlight utility for prose around formulas */
    .math-variable {
        background-color: rgba(31, 119, 180, 0.15);
        padding: 0px 6px;
        border-radius: 4px;
        display: inline-block;
        line-height: 1.2;
    }
    .math-variable .katex {
        font-size: 0.95em !important;
    }

</style>
""", unsafe_allow_html=True)

defaults = {
    "messages": [],
    "selected_model": "gpt-4o",
    "credit_info": {"limit": None, "used": None, "available": None},
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)

st.markdown("<h1 class=\"main-header\">🤖 1minAI Chat</h1>", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class=\"chat-container\">", unsafe_allow_html=True)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                render_response_as_blocks(message["content"])
            else:
                st.markdown(message["content"])

    st.markdown('</div>', unsafe_allow_html=True)

user_prompt = st.chat_input("Type your message here...", key="chat_input")

if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.spinner("🤔 AI is thinking..."):
        try:
            api_result = call_ai_api(user_prompt, st.session_state.selected_model)
            ai_response = api_result["response"]

            st.session_state.credit_info = {
                "limit": api_result["credit_limit"],
                "used": api_result["used_credit"],
                "available": api_result["available_credit"]
            }

            st.session_state.messages.append({"role": "assistant", "content": ai_response})

            with st.chat_message("assistant"):
                render_response_as_blocks(ai_response)

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            with st.chat_message("assistant"):
                st.error(error_msg)

with st.sidebar:
    st.markdown("<div class=\"sidebar-content\">", unsafe_allow_html=True)
    st.header("⚙️ Settings")

    selected_display = st.selectbox(
        "🤖 Select AI Model",
        options=list(MODELS.keys()),
        index=list(MODELS.keys()).index("OpenAI - GPT-4o"),
        help="Choose the AI model for responses"
    )
    st.session_state.selected_model = MODELS[selected_display]["id"]

    st.markdown(f"<p class=\"model-desc\">{MODELS[selected_display]['desc']}</p>", unsafe_allow_html=True)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    with col2:
        if st.button("💾 Export Chat", use_container_width=True):
            chat_text = "\n\n".join([f"{msg['role'].title()}: {msg['content']}" for msg in st.session_state.messages])
            st.download_button(
                label="Download",
                data=chat_text,
                file_name="chat_history.txt",
                mime="text/plain"
            )
    
    st.markdown("---")
    st.markdown(f"**Current Model:** {selected_display}")
    st.markdown("**Messages:** " + str(len(st.session_state.messages)))

    if st.session_state.credit_info["limit"] is not None:
        st.markdown("### 💰 Team Credits")
        st.markdown(f"**Available:** {st.session_state.credit_info['available']:,.0f}")
        st.markdown(f"**Used:** {st.session_state.credit_info['used']:,.0f}")
        st.markdown(f"**Limit:** {st.session_state.credit_info['limit']:,.0f}")

        usage_percent = (st.session_state.credit_info["used"] / st.session_state.credit_info["limit"]) * 100
        st.progress(min(usage_percent / 100, 1.0))
        st.caption(f"Usage: {usage_percent:.1f}%")

        st.caption("*Note: These are team credits, not your personal account balance.*")

    st.markdown("</div>", unsafe_allow_html=True)