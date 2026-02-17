"""
V12 Bridge Embedding Manager
Refactored for Unified Content Engine — uses relative imports.
"""

from . import openai_client


def create_joke_bridge(joke_text: str) -> str:
    """
    Creates a 'Bridge String' that describes the joke's logic abstractly.
    This is what we will embed and search against.
    """
    prompt = f"""
    Analyze this joke: "{joke_text}"

    Write a 1-sentence "Search Description" for this joke.
    
    RULES:
    1. Do NOT mention specific nouns (e.g., don't say 'Coma', say 'Long Delay').
    2. Focus on the EMOTION and the MECHANISM.
    3. Use keywords that describe what kind of topics this joke fits.
    
    Example Output: "A joke about extreme procrastination where a high-stakes timeline is ignored for comfort."
    
    OUTPUT: Just the description, nothing else.
    """

    response_text = openai_client.generate_content(
        prompt=prompt,
        model="gpt-4o-mini",
        max_tokens=200,
        temperature=0.3
    )

    if response_text is None:
        return "A joke with an unclear mechanism"

    bridge_string = response_text.strip()
    bridge_string = bridge_string.strip('"').strip("'")

    return bridge_string


def expand_headline_to_themes(headline: str) -> str:
    """
    Expands a headline into abstract themes for semantic search.
    """
    prompt = f"""
    Topic: "{headline}"
    
    List 5 themes for finding JOKE STRUCTURES that could work for this topic.
    Mix abstract emotions AND concrete relatable situations people joke about.
    
    GOOD example: If topic is "Zomato raises delivery fee to ₹50",
    themes are "Price shock, Being Cheap, Hidden Costs, Paying More for Less, Corporate Greed"
    
    BAD example: "Frustration, Sadness, Anger, Disappointment, Stress"
    (These are too generic and won't find relevant joke structures)
    
    OUTPUT: Just the comma-separated themes, nothing else.
    """

    response_text = openai_client.generate_content(
        prompt=prompt,
        model="gpt-4o-mini",
        max_tokens=100,
        temperature=0.3
    )

    if response_text is None:
        return headline

    return response_text.strip()
