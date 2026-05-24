"""Auto-categorise a coloring page by its description.

Primary path: GPT-4o-mini (fast + cheap). Falls back to keyword matching
when no API key is set or the API call fails.
"""
from __future__ import annotations

CATEGORIES = [
    "Animals",
    "Vehicles",
    "Nature",
    "Fantasy",
    "Space",
    "Food",
    "People",
    "Sports",
    "Buildings",
    "Other",
]

_KEYWORDS: dict[str, list[str]] = {
    "Animals": ["dog", "cat", "bird", "fish", "elephant", "lion", "tiger",
                "bear", "rabbit", "horse", "dinosaur", "penguin", "frog",
                "turtle", "butterfly", "animal", "puppy", "kitten"],
    "Vehicles": ["car", "truck", "bus", "plane", "boat", "train", "motorcycle",
                 "airplane", "helicopter", "rocket", "ship", "bicycle", "tractor"],
    "Nature": ["tree", "flower", "forest", "mountain", "nature", "garden",
               "ocean", "river", "beach", "jungle", "landscape", "lake",
               "valley", "cloud", "rain", "sun"],
    "Fantasy": ["dragon", "wizard", "fairy", "magic", "unicorn", "elf",
                "knight", "princess", "castle", "superhero", "batman",
                "superman", "spider-man", "witch", "monster", "mermaid"],
    "Space": ["space", "rocket", "planet", "star", "moon", "astronaut",
              "galaxy", "alien", "ufo", "nebula", "cosmos", "saturn"],
    "Food": ["food", "pizza", "cake", "fruit", "vegetable", "burger",
             "ice cream", "cookie", "cupcake", "donut", "sandwich", "candy"],
    "People": ["person", "child", "people", "family", "man", "woman",
               "girl", "boy", "baby", "kid", "character"],
    "Sports": ["sport", "ball", "football", "basketball", "soccer", "tennis",
               "swim", "run", "baseball", "golf", "skating", "skiing"],
    "Buildings": ["house", "building", "castle", "city", "tower", "bridge",
                  "school", "church", "skyscraper", "lighthouse", "barn"],
}


def categorize(prompt: str | None, api_key: str | None) -> str:
    if not prompt:
        return "Other"
    if api_key:
        result = _ai_categorize(prompt, api_key)
        if result:
            return result
    return _keyword_fallback(prompt)


def _ai_categorize(prompt: str, api_key: str) -> str | None:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Categorise this coloring page description into exactly one of "
                        f"these categories: {', '.join(CATEGORIES)}. "
                        f"Description: {prompt[:300]}. "
                        f"Reply with only the category name, nothing else."
                    ),
                }
            ],
            max_tokens=10,
            temperature=0,
        )
        cat = resp.choices[0].message.content.strip()
        for c in CATEGORIES:
            if c.lower() == cat.lower():
                return c
    except Exception:
        pass
    return None


def _keyword_fallback(prompt: str) -> str:
    p = prompt.lower()
    for category, words in _KEYWORDS.items():
        if any(w in p for w in words):
            return category
    return "Other"
