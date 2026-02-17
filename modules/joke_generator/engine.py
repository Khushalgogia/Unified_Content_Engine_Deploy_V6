"""
V11 Logic Engine - Core Engine (with Gemini→OpenAI Fallback)
Refactored for Unified Content Engine.

Strategy:
  1. Try Gemini (with 1 auto-retry on server errors)
  2. If Gemini fails entirely → same prompt goes to OpenAI GPT-4o-mini
  3. Result: near-100% joke delivery rate
"""

from typing import Dict
from .gemini_client import classify_joke_type, call_gemini, call_openai_fallback


# ─── The system prompt & user prompt for classify_joke_type ───────────────────
# (duplicated here so we can replay them against OpenAI on fallback)

_CLASSIFY_SYSTEM = """You are a Comedy Architect. You reverse-engineer the logic of a reference joke and transplant it into a new topic.

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


def _build_classify_prompt(reference_joke: str, new_topic: str) -> str:
    return f"""REFERENCE JOKE:
"{reference_joke}"

NEW TOPIC:
"{new_topic}"

Analyze the reference joke, brainstorm 3 mapping angles, select the funniest, and draft the final joke."""


def generate_v11_joke(reference_joke: str, new_topic: str) -> Dict:
    """
    V11 Enhanced Pipeline: Analyze → Brainstorm → Select → Draft
    With automatic Gemini → OpenAI fallback on server errors.
    """
    required_keys = ["engine_selected", "reasoning", "brainstorming", "selected_strategy", "draft_joke"]

    # ── Attempt 1: Gemini (with built-in retry) ──
    try:
        result = classify_joke_type(reference_joke, new_topic)
    except Exception as e:
        result = {"error": str(e), "_gemini_failed": True}

    # ── Check if Gemini failed and we should fallback ──
    gemini_failed = (
        isinstance(result, dict) and
        result.get("_gemini_failed", False)
    )

    if gemini_failed:
        gemini_error = result.get("error", "Unknown")
        print(f"   🔄 Gemini failed ({gemini_error[:60]}), falling back to OpenAI...")

        # ── Attempt 2: OpenAI GPT-4o-mini ──
        prompt = _build_classify_prompt(reference_joke, new_topic)
        result = call_openai_fallback(
            prompt=prompt,
            system_instruction=_CLASSIFY_SYSTEM,
            temperature=0.5,
            json_output=True,
        )

        if isinstance(result, dict) and "error" not in result:
            result["_provider"] = "openai"
            print(f"   ✅ OpenAI fallback succeeded!")
        else:
            openai_error = result.get("error", "Unknown") if isinstance(result, dict) else "Unexpected"
            return {
                "success": False,
                "error": f"Both Gemini and OpenAI failed. Gemini: {gemini_error}. OpenAI: {openai_error}",
            }

    # ── Process result ──
    if isinstance(result, dict):
        if "error" in result and "_gemini_failed" not in result:
            return {
                "success": False,
                "error": result.get("error"),
                "raw": result.get("raw", "")
            }

        missing = [k for k in required_keys if k not in result]
        if missing:
            for key in missing:
                if key == "brainstorming":
                    result[key] = ["N/A"]
                elif key == "selected_strategy":
                    result[key] = "N/A"
                else:
                    return {
                        "success": False,
                        "error": f"Missing keys in response: {missing}",
                        "partial_result": result
                    }

        result["success"] = True
        # Track which provider generated it
        if "_provider" not in result:
            result["_provider"] = "gemini"
        return result
    else:
        return {
            "success": False,
            "error": "Unexpected response type",
            "raw": str(result)
        }


def regenerate_joke(
    reference_joke: str,
    new_topic: str,
    engine_type: str,
    previous_draft: str
) -> Dict:
    """
    Regenerate a joke with the same engine type but different approach.
    Also has Gemini → OpenAI fallback.
    """
    system_instruction = f"""You are a Comedy Writer. You have already classified this joke as {engine_type}.

Now generate a DIFFERENT version. Brainstorm 3 NEW angles (different from before).

PREVIOUS DRAFT (DO NOT REPEAT):
"{previous_draft}"

Generate a fresh take using the same {engine_type} logic engine."""

    prompt = f"""REFERENCE JOKE:
"{reference_joke}"

NEW TOPIC:
"{new_topic}"

FORCED ENGINE TYPE: {engine_type}

Create 3 NEW mapping options and select a different one from before.

OUTPUT JSON:
{{
  "engine_selected": "{engine_type}",
  "brainstorming": [
    "New Option 1: [Trait/Angle] -> [Scenario]",
    "New Option 2: [Trait/Angle] -> [Scenario]",
    "New Option 3: [Trait/Angle] -> [Scenario]"
  ],
  "selected_strategy": "The new selected approach",
  "draft_joke": "The new joke (max 40 words, different from previous)"
}}"""

    try:
        result = call_gemini(
            prompt=prompt,
            system_instruction=system_instruction,
            model_stage="generation",
            temperature=0.7,
            json_output=True
        )

        # Check for Gemini failure → OpenAI fallback
        if isinstance(result, dict) and result.get("_gemini_failed"):
            print(f"   🔄 Regen: Gemini failed, falling back to OpenAI...")
            result = call_openai_fallback(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.7,
                json_output=True,
            )

        if isinstance(result, dict) and "draft_joke" in result:
            result["success"] = True
            return result
        else:
            return {
                "success": False,
                "error": "Failed to regenerate",
                "result": result
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
