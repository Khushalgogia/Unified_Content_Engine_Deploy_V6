"""
V11 Logic Engine - Gemini API Client (with OpenAI Fallback)
Refactored for Unified Content Engine — reads API key from .env
Strategy: Gemini first → 1 retry on server errors → OpenAI GPT-4o-mini fallback
"""

import os
import json
import re
import time
from google import genai
from google.genai import types


# Initialize the Gemini client from environment
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment. Check your .env file.")

client = genai.Client(api_key=API_KEY)


# Model configuration
MODELS = {
    "classification": "gemini-3-flash-preview",
    "extraction": "gemini-3-flash-preview",
    "generation": "gemini-3-flash-preview",
}

# Errors that should trigger retry / fallback
RETRIABLE_ERRORS = (
    "500", "503", "429", "RESOURCE_EXHAUSTED", "UNAVAILABLE",
    "INTERNAL", "deadline", "timeout", "overloaded", "rate limit",
    "capacity", "server error",
)


def _is_retriable(error_str: str) -> bool:
    """Check if an error message indicates a retriable server-side issue."""
    error_lower = error_str.lower()
    return any(code.lower() in error_lower for code in RETRIABLE_ERRORS)


def call_gemini(
    prompt: str,
    system_instruction: str = None,
    model_stage: str = "classification",
    temperature: float = 0.3,
    max_tokens: int = 8192,
    json_output: bool = True,
    _retries: int = 1,
    _retry_delay: float = 3.0,
) -> dict | str:
    """
    Call Gemini API with retry logic.
    On server errors (500/503/429), retries once after a delay.
    Returns result dict or error dict.
    """
    model = MODELS.get(model_stage, MODELS["classification"])

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    if system_instruction:
        config.system_instruction = system_instruction

    if json_output:
        config.response_mime_type = "application/json"

    last_error = None

    for attempt in range(_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            result_text = response.text

            if json_output:
                try:
                    return json.loads(result_text)
                except json.JSONDecodeError as e:
                    # Try to find complete JSON
                    json_match = re.search(r'\{[\s\S]*\}', result_text)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except json.JSONDecodeError:
                            pass

                    # Extract partial result from truncated response
                    engine_match = re.search(r'"engine_selected":\s*"([^"]+)"', result_text)
                    reasoning_match = re.search(r'"reasoning":\s*"([^"]*)"', result_text)
                    joke_match = re.search(r'"draft_joke":\s*"([^"]*)"', result_text)
                    strategy_match = re.search(r'"selected_strategy":\s*"([^"]*)"', result_text)

                    if engine_match:
                        return {
                            "engine_selected": engine_match.group(1),
                            "reasoning": reasoning_match.group(1) if reasoning_match else "Response was truncated",
                            "brainstorming": ["Response was truncated"],
                            "selected_strategy": strategy_match.group(1) if strategy_match else "N/A",
                            "draft_joke": joke_match.group(1) if joke_match else "Unable to extract joke from truncated response"
                        }

                    return {"error": f"Failed to parse JSON: {str(e)}", "raw": result_text[:500]}

            return result_text

        except Exception as e:
            last_error = str(e)
            if attempt < _retries and _is_retriable(last_error):
                print(f"   ⚠️ Gemini attempt {attempt+1} failed ({last_error[:80]}), retrying in {_retry_delay}s...")
                time.sleep(_retry_delay)
            else:
                break

    # If we exhausted retries, return an error with a flag for fallback
    return {"error": last_error, "_gemini_failed": True}


def call_openai_fallback(
    prompt: str,
    system_instruction: str = None,
    temperature: float = 0.5,
    json_output: bool = True,
) -> dict | str:
    """
    OpenAI GPT-4o-mini fallback — used when Gemini is unavailable.
    Same prompt format, same JSON output structure.
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not found — cannot fallback"}

    openai_client = OpenAI(api_key=api_key)

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    try:
        kwargs = {
            "model": "gpt-4o",
            "messages": messages,
            "temperature": temperature,
        }
        if json_output:
            kwargs["response_format"] = {"type": "json_object"}

        response = openai_client.chat.completions.create(**kwargs)
        result_text = response.choices[0].message.content

        if json_output:
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[\s\S]*\}', result_text)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
                return {"error": f"OpenAI returned invalid JSON", "raw": result_text[:500]}

        return result_text

    except Exception as e:
        return {"error": f"OpenAI fallback failed: {str(e)}"}


def classify_joke_type(reference_joke: str, new_topic: str) -> dict:
    """
    V11 Enhanced: Classify joke, brainstorm 3 angles, select best, draft joke.
    """
    system_instruction = """You are a Comedy Architect. You reverse-engineer the logic of a reference joke and transplant it into a new topic.

YOUR PROCESS:
1. Analyze the 'Reference Joke' to find the Engine (A, B, or C).
2. BRAINSTORM 3 distinct mapping angles for the New Topic.
3. Select the funniest angle.
4. Draft the final joke.

---
THE ENGINES:

TYPE A: The "Word Trap" (Semantic/Pun)
- Logic: A trigger word bridges two unrelated contexts.
- Mapping: Find a word in the New Topic that has a double meaning. If none exists, FAIL and switch to Type C.

TYPE B: The "Behavior Trap" (Scenario/Character)
- Logic: Character applies a [Mundane Habit] to a [High-Stakes Situation], trivializing it.
- Mapping: 
  1. Identify the Abstract Behavior (e.g. "Being Cheap", "Being Lazy", "Professional Deformation").
  2. You may SWAP the specific trait if a better one exists for the New Topic. 
     (Example: If Ref is "Snoozing", you can swap to "Haggling" if the New Topic is "Medical Costs").
  3. Apply the Trait to the New Context. DO NOT PUN.

TYPE C: The "Hyperbole Engine" (Roast/Exaggeration)
- Logic: A physical trait is exaggerated until it breaks physics/social norms.
- Mapping: 
  1. Identify the Scale (e.g. Size, Weight, Wealth).
  2. Constraint: Conservation of Failure. If Ref fails due to "Lack of Substance," New Joke must also fail due to "Lack of Substance."
  3. Format: Statement ("He is so X..."), NOT a scene.

---
OUTPUT FORMAT (JSON ONLY):
{
  "engine_selected": "Type A/B/C",
  "reasoning": "Explain why this engine fits.",
  "brainstorming": [
    "Option 1: [Trait/Angle] -> [Scenario]",
    "Option 2: [Trait/Angle] -> [Scenario]",
    "Option 3: [Trait/Angle] -> [Scenario]"
  ],
  "selected_strategy": "The best option from above",
  "draft_joke": "The final joke text. Max 40 words. NO FILLER (e.g. 'The health crisis is dire'). Start directly with the setup. LANGUAGE: Use simple, everyday words a 15-year-old would understand. NO complex vocabulary, NO obscure references. Write like you're telling a joke to friends."
}"""

    prompt = f"""REFERENCE JOKE:
"{reference_joke}"

NEW TOPIC:
"{new_topic}"

Analyze the reference joke, brainstorm 3 mapping angles, select the funniest, and draft the final joke."""

    return call_gemini(
        prompt=prompt,
        system_instruction=system_instruction,
        model_stage="classification",
        temperature=0.5,
        json_output=True
    )
