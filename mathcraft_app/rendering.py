import html
import re

import streamlit as st

SUSPICIOUS_HTML_PATTERN = re.compile(
    r"<\s*(script|iframe|svg|object|embed|meta|link|style)\b|"
    r"on\w+\s*=|javascript:\s*|data:\s*text/html",
    flags=re.IGNORECASE,
)

FENCED_CODE_PATTERN = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", flags=re.DOTALL)


def inject_styles() -> None:
    st.markdown(
        """
<style>
    .chat-container {
        max-width: 900px;
        margin: 0 auto;
    }
    .katex-display {
        background-color: rgba(31, 119, 180, 0.05) !important;
        padding: 12px 20px !important;
        margin: 0.8em 0 !important;
        border-left: 3px solid #1f77b4 !important;
        border-radius: 4px !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02) !important;
        overflow-x: auto !important;
    }
    .katex {
        font-size: 1.1em !important;
    }
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
""",
        unsafe_allow_html=True,
    )


def ultra_clean_latex(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\\\[\s*(.*?)\s*\\\]", r"$$\1$$", text, flags=re.DOTALL)
    text = re.sub(r"\\\(\s*(.*?)\s*\\\)", r"$\1$", text, flags=re.DOTALL)

    text = re.sub(r"\$\$\s*(.*?)\s*\$\$", r"$$\1$$", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\$)\$\s*([^$\n]+?)\s*\$(?!\$)", r"$\1$", text)

    text = re.sub(r"(?<=[A-Za-z0-9\)\]])(\$[^$\n]+?\$)", r" \1", text)
    text = re.sub(r"(\$[^$\n]+?\$)(?=[A-Za-z0-9\(])", r"\1 ", text)

    lines = text.splitlines()
    out = []
    seen_eq = set()
    for line in lines:
        key = re.sub(r"\s+", "", line)
        is_equation = ("=" in line) and ("$" in line or "\\" in line)
        if is_equation and key in seen_eq:
            continue
        if is_equation:
            seen_eq.add(key)
        out.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def sanitize_model_markdown(text: str) -> str:
    # Normalize existing entities first (e.g., &gt;) to avoid double-escaping
    # into &amp;gt;, which renders literally in the chat UI.
    return html.escape(html.unescape(text or ""), quote=False)


def has_suspicious_html(text: str) -> bool:
    return bool(SUSPICIOUS_HTML_PATTERN.search(text or ""))


def auto_highlight_variables(text: str) -> str:
    if not text:
        return ""
    # Highlight only definition-style symbols such as "$u$: velocity".
    # This avoids wrapping arbitrary inline math spans that are not variable definitions.
    pattern = r"\$((?:\\[A-Za-z]+|[A-Za-z])(?:_(?:\{[A-Za-z0-9]+\}|[A-Za-z0-9])|\^(?:\{[A-Za-z0-9]+\}|[A-Za-z0-9])){0,2})\$(?=\s*:)"

    def repl(match: re.Match) -> str:
        return f'<span class="math-variable">${match.group(1)}$</span>'

    return re.sub(pattern, repl, text)


def normalize_inline_code_suffixes(text: str) -> str:
    # Keep hyphenated suffixes attached to inline-code tokens so markdown does
    # not style only the left fragment (e.g., `n`-th -> `n-th`).
    return re.sub(r"`([^`\n]+)`-([A-Za-z][A-Za-z0-9-]*)", r"`\1-\2`", text)


def normalize_math_inline_code_tokens(text: str) -> str:
    # Convert math-like inline code (e.g., `F_0`, `x^2`) into inline math so
    # symbols are rendered consistently with the rest of the response.
    pattern = (
        r"`((?:\\[A-Za-z]+|[A-Za-z])"
        r"(?:_(?:\{[A-Za-z0-9]+\}|[A-Za-z0-9])|\^(?:\{[A-Za-z0-9+\-]+\}|[A-Za-z0-9+\-]))"
        r"{1,2})`"
    )
    return re.sub(pattern, r"$\1$", text)


def render_text_chunk(text: str) -> None:
    if not text or not text.strip():
        return

    text = normalize_inline_code_suffixes(text)
    text = normalize_math_inline_code_tokens(text)
    plain_text = html.unescape(text)

    suspicious = has_suspicious_html(text)
    safe_part = sanitize_model_markdown(text)
    if suspicious:
        st.markdown(safe_part)
    else:
        processed = auto_highlight_variables(safe_part)
        if processed == safe_part:
            st.markdown(plain_text)
        else:
            st.markdown(processed, unsafe_allow_html=True)


def render_text_with_code_blocks(text: str) -> None:
    last_idx = 0
    for match in FENCED_CODE_PATTERN.finditer(text):
        render_text_chunk(text[last_idx:match.start()])

        lang = (match.group(1) or "").strip()
        code = html.unescape(match.group(2).strip("\n"))
        if code:
            try:
                st.code(code, language=lang or None, line_numbers=True)
            except TypeError:
                st.code(code, language=lang or None)

        last_idx = match.end()

    render_text_chunk(text[last_idx:])


def render_response_as_blocks(text: str) -> None:
    cleaned = ultra_clean_latex(text)
    equation_counter = 0

    def equation_columns():
        try:
            return st.columns([20, 1], vertical_alignment="center")
        except TypeError:
            return st.columns([20, 1])

    parts = re.split(r"(\$\$.*?\$\$)", cleaned, flags=re.DOTALL)
    for part in parts:
        if not part.strip():
            continue

        if part.startswith("$$") and part.endswith("$$"):
            equation = part[2:-2].strip()
            if equation:
                equation_counter += 1
                col_eq, col_no = equation_columns()
                with col_eq:
                    st.latex(equation)
                with col_no:
                    st.markdown(
                        f"<div style='text-align:right; color:#666; font-style:italic; line-height:1.4;'>({equation_counter})</div>",
                        unsafe_allow_html=True,
                    )
        else:
            render_text_with_code_blocks(part)
