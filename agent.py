"""
Autonomous Visual Browser Agent using Gemini & Playwright.

The agent opens a real Chromium browser with Playwright, takes a screenshot
of the current viewport, and sends it to Google's Gemini API for visual UI
analysis. Gemini replies with a structured action (click, type, scroll, or
done) plus 0-1000 normalized coordinates, and the agent performs that action
and repeats until the goal is complete or the step limit is reached.

Setup:
    pip install -r requirements.txt
    playwright install chromium
    export GEMINI_API_KEY="your-api-key"

Usage:
    python agent.py --url https://example.com --goal "Find the pricing page"
    python agent.py --url https://example.com --goal "Search for headphones" --max-steps 15

The API key is read from the GEMINI_API_KEY environment variable only.
It is never hard-coded and never printed.
"""

import argparse
import base64
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

try:
    from google import genai
except ImportError:  # pragma: no cover
    genai = None

MODEL_PRIMARY = "gemini-2.0-flash"
MODEL_FALLBACK = "gemini-1.5-flash"
MAX_RETRIES = 3


def build_prompt(goal: str) -> str:
    """Instruction sent to Gemini alongside each screenshot."""
    return (
        "You are a visual browser automation agent. Look at this screenshot "
        "of a web page and decide the single next action that moves toward "
        f"the goal: {goal}\n\n"
        "Reply with ONLY a JSON object in this exact shape, no other text:\n"
        '{"action": "click" | "type" | "scroll" | "done", '
        '"x": <0-1000 horizontal coordinate>, '
        '"y": <0-1000 vertical coordinate>, '
        '"text": "<text to type, only for the type action>", '
        '"reasoning": "<one short sentence>"}\n\n'
        "Coordinates are normalized: 0,0 is the top-left of the visible "
        "page, 1000,1000 is the bottom-right. Use action \"done\" when the "
        "goal is visibly complete."
    )


def parse_action(raw_text: str) -> dict:
    """Extract the JSON action from a model reply, tolerating code fences."""
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"Model reply contained no JSON object: {raw_text[:200]}")
    action = json.loads(match.group(0))
    if action.get("action") not in ("click", "type", "scroll", "done"):
        raise ValueError(f"Unknown action in model reply: {action}")
    return action


def ask_gemini(client, screenshot_png: bytes, goal: str) -> dict:
    """Send one screenshot to Gemini with retry + model fallback.

    Retries on rate limits (HTTP 429) with exponential backoff, then falls
    back to a second model before giving up. This keeps a long run alive
    when one model is throttled.
    """
    image_b64 = base64.b64encode(screenshot_png).decode("utf-8")
    prompt = build_prompt(goal)
    last_error = None
    for model in (MODEL_PRIMARY, MODEL_FALLBACK):
        for attempt in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_b64,
                            }
                        },
                    ],
                )
                return parse_action(response.text)
            except Exception as exc:  # rate limits, overload, timeouts
                last_error = exc
                wait = 2 ** attempt
                print(f"[{model}] attempt {attempt + 1} failed ({exc}); "
                      f"retrying in {wait}s...")
                time.sleep(wait)
    raise RuntimeError(f"Gemini request failed on all models: {last_error}")


def run_agent(start_url: str, goal: str, max_steps: int = 10,
              headless: bool = True) -> None:
    """Drive the browser toward `goal`, one Gemini-guided step at a time."""
    if genai is None:
        print("Missing dependency: pip install google-genai", file=sys.stderr)
        sys.exit(1)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY before running (see .env.example).",
              file=sys.stderr)
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        print(f"Opening {start_url}")
        page.goto(start_url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        for step in range(1, max_steps + 1):
            screenshot = page.screenshot()
            action = ask_gemini(client, screenshot, goal)
            kind = action["action"]
            print(f"Step {step}/{max_steps}: {kind} — "
                  f"{action.get('reasoning', '')}")
            if kind == "done":
                print("Goal complete.")
                break
            if kind == "click":
                x = action["x"] / 1000 * 1280
                y = action["y"] / 1000 * 800
                page.mouse.click(x, y)
            elif kind == "type":
                x = action["x"] / 1000 * 1280
                y = action["y"] / 1000 * 800
                page.mouse.click(x, y)
                page.keyboard.type(action.get("text", ""))
                page.keyboard.press("Enter")
            elif kind == "scroll":
                page.mouse.wheel(0, 600)
            page.wait_for_timeout(1500)
        else:
            print("Step limit reached before the goal was marked done.")
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autonomous Visual Browser Agent (Gemini + Playwright)")
    parser.add_argument("--url", required=True, help="Starting page URL")
    parser.add_argument("--goal", required=True,
                        help="Goal for the agent, e.g. 'Find the pricing page'")
    parser.add_argument("--max-steps", type=int, default=10,
                        help="Maximum agent steps (default: 10)")
    parser.add_argument("--headed", action="store_true",
                        help="Show the browser window instead of headless mode")
    args = parser.parse_args()
    run_agent(args.url, args.goal, max_steps=args.max_steps,
              headless=not args.headed)


if __name__ == "__main__":
    main()
