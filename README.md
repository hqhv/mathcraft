# MathCraft

AI-powered workspace for math chat and formula rendering.

MathCraft is a Streamlit app that uses OpenAI models to help with math and physics questions, render readable math output, and track token usage and estimated cost per session.

## Features

- Chat interface focused on math and physics Q&A
- LaTeX-friendly responses for clearer equations
- Model selection (GPT-5, GPT-4o, GPT-4o mini)
- API key check inside the app UI
- Session usage and estimated cost tracking
- Export chat history to a text file

## Tech Stack

- Python 3.10+
- Streamlit
- OpenAI Python SDK
- tiktoken

## Project Structure

- `MathCraft.py` - app entry point
- `mathcraft_app/` - app modules (UI, config, rendering, OpenAI client, token utils)
- `requirements.txt` - Python dependencies
- `install_requirements.bat` - dependency install helper for Windows
- `run_mathcraft.bat` - start script for Windows

## Quick Start (Windows)

1. Create and activate virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
.\install_requirements.bat
```

3. Run the app:

```powershell
.\run_mathcraft.bat
```

## Manual Run (Any OS)

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start Streamlit:

```bash
streamlit run MathCraft.py
```

## OpenAI Key

- Open the app sidebar and paste your key in the Account section.
- Use the Check Key button to validate access.
- The key is stored only in the current browser session.

## Troubleshooting

- If `git` is not recognized: install Git for Windows and reopen terminal.
- If `.venv` is missing: run `py -m venv .venv` first.
- If install fails: upgrade pip and retry `pip install -r requirements.txt`.

## License

No license specified yet.
