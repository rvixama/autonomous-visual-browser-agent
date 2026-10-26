# Autonomous Visual Browser Agent using Gemini & Playwright

An autonomous browser agent that sees the web the way a person does: it opens a real Chromium browser with **Playwright**, screenshots the viewport, and sends the image to **Google's Gemini API** for computer-vision analysis. Gemini replies with the next action — click, type, scroll, or done — plus screen coordinates, and the agent performs it. The loop repeats until the goal is complete.

## Key highlights

- Built automated browser workflows in Python using Playwright.
- Integrated Google GenAI SDK (Gemini API) for computer vision screenshot analysis.
- Developed visual UI automation scripts capable of dynamic page navigation and element detection.

## Features

- **Visual UI understanding** — no selectors or brittle XPaths; the model reads the rendered page.
- **Coordinate targeting** — actions use normalized 0–1000 coordinates mapped to the viewport.
- **Error handling & API fallback** — rate-limit retries with exponential backoff, plus automatic fallback to a second Gemini model if the first keeps failing.
- **Safe by default** — the API key is read from an environment variable only, never hard-coded.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # then put your key in .env, or export it directly
export GEMINI_API_KEY="your-api-key"
```

## Usage

```bash
python agent.py --url https://example.com --goal "Find the pricing page"
python agent.py --url https://example.com --goal "Search for headphones" --max-steps 15
python agent.py --url https://example.com --goal "Open the contact page" --headed
```

## How it works

1. Playwright launches Chromium and loads the starting URL.
2. The agent screenshots the viewport.
3. The screenshot + goal go to Gemini, which returns one JSON action.
4. The agent performs the action (click at coordinates, type text, scroll).
5. Repeat until Gemini reports the goal done or the step limit is reached.

## Project structure

```
agent.py           # The agent: browser loop + Gemini vision calls
requirements.txt   # playwright, google-genai
.env.example       # Environment variable template (no real keys)
.gitignore         # Keeps .env, caches, and screenshots out of git
```

## Notes

This is a demo-grade agent: it performs one action per model call, works best on simple public pages, and needs a valid `GEMINI_API_KEY`. Use it on sites you have permission to automate, and keep your API key out of version control.
