"""
Shared OpenAI Client
Refactored for Unified Content Engine — reads API key from .env
"""

import os
from openai import OpenAI


# Initialize from environment
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment. Check your .env file.")

client = OpenAI(api_key=API_KEY)


def generate_content(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 500, temperature: float = 0.7) -> str:
    """
    Generate content using OpenAI models.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating content: {e}")
        return None
