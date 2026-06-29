"""Spoonacular Recipe API client."""

import os
from pathlib import Path

import requests

API_KEY_FILE = Path.home() / ".meal-planner" / "spoonacular_key"
BASE_URL = "https://api.spoonacular.com"

TRADITION_TO_DIET = {
    "hindu-vegetarian": "vegetarian",
    "sattvic": "vegetarian",
    "jain": "vegetarian",
    "buddhist-vegetarian": "vegetarian",
    "none": "",
    "halal": "",
    "kosher": "",
    "hindu-nonveg": "",
}

TRADITION_TO_EXCLUDE = {
    "halal": "pork,bacon,ham,lard",
    "kosher": "pork,bacon,ham,shellfish,shrimp,crab,lobster",
    "hindu-vegetarian": "meat,chicken,fish,eggs,beef,pork",
    "hindu-nonveg": "beef,pork,bacon,ham",
    "sattvic": "meat,chicken,fish,eggs,onion,garlic",
    "jain": "meat,chicken,fish,eggs,onion,garlic,potato,carrot",
    "buddhist-vegetarian": "meat,chicken,fish,beef,pork",
    "none": "",
}

CUISINE_MAP = {
    "indian": "Indian",
    "mexican": "Mexican",
    "mediterranean": "Mediterranean",
    "asian": "Asian",
    "american": "American",
    "italian": "Italian",
    "thai": "Thai",
    "chinese": "Chinese",
    "korean": "Korean",
}


def get_api_key() -> str:
    key = os.environ.get("SPOONACULAR_API_KEY", "")
    if not key and API_KEY_FILE.exists():
        key = API_KEY_FILE.read_text().strip()
    return key


def search_recipes(
    query: str = "",
    cuisine: str = "",
    dietary_tradition: str = "none",
    dietary_restrictions: list = None,
    exclude_ingredients: list = None,
    max_calories: int = 0,
    min_protein: int = 0,
    max_cook_time: int = 30,
    meal_type: str = "",
    number: int = 5,
) -> list[dict]:
    """Search for recipes matching constraints."""
    api_key = get_api_key()
    if not api_key:
        return []

    # Build params
    params = {
        "apiKey": api_key,
        "number": number,
        "addRecipeNutrition": True,
        "instructionsRequired": True,
        "fillIngredients": True,
    }

    if query:
        params["query"] = query
    if max_cook_time:
        params["maxReadyTime"] = max_cook_time
    if meal_type:
        params["type"] = meal_type

    # Diet from tradition
    diet = TRADITION_TO_DIET.get(dietary_tradition, "")
    if dietary_restrictions:
        if "vegetarian" in dietary_restrictions:
            diet = "vegetarian"
        elif "vegan" in dietary_restrictions:
            diet = "vegan"
        elif "keto" in dietary_restrictions:
            diet = "ketogenic"
        elif "paleo" in dietary_restrictions:
            diet = "paleo"
    if diet:
        params["diet"] = diet

    # Cuisine
    if cuisine and cuisine != "mixed":
        mapped = CUISINE_MAP.get(cuisine, cuisine)
        params["cuisine"] = mapped

    # Excluded ingredients
    excluded = []
    tradition_exclude = TRADITION_TO_EXCLUDE.get(dietary_tradition, "")
    if tradition_exclude:
        excluded.extend(tradition_exclude.split(","))
    if exclude_ingredients:
        excluded.extend(exclude_ingredients)
    if excluded:
        params["excludeIngredients"] = ",".join(set(excluded))

    # Nutrition filters
    if max_calories:
        params["maxCalories"] = max_calories
    if min_protein:
        params["minProtein"] = min_protein

    try:
        resp = requests.get(f"{BASE_URL}/recipes/complexSearch", params=params, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [_normalize(r) for r in data.get("results", [])]
    except Exception:
        return []


def get_recipe_details(recipe_id: int) -> dict:
    """Get full recipe with instructions."""
    api_key = get_api_key()
    if not api_key:
        return {}
    try:
        resp = requests.get(
            f"{BASE_URL}/recipes/{recipe_id}/information",
            params={"apiKey": api_key, "includeNutrition": True},
            timeout=15,
        )
        if resp.status_code != 200:
            return {}
        return _normalize(resp.json())
    except Exception:
        return {}


def _normalize(recipe: dict) -> dict:
    """Normalize Spoonacular recipe to our format."""
    # Extract macros from nutrition
    nutrients = {}
    for n in recipe.get("nutrition", {}).get("nutrients", []):
        if n["name"] == "Calories":
            nutrients["calories"] = round(n["amount"])
        elif n["name"] == "Protein":
            nutrients["protein_g"] = round(n["amount"])
        elif n["name"] == "Carbohydrates":
            nutrients["carbs_g"] = round(n["amount"])
        elif n["name"] == "Fat":
            nutrients["fat_g"] = round(n["amount"])

    # Extract ingredients
    ingredients = []
    for ing in recipe.get("extendedIngredients", recipe.get("missedIngredients", [])):
        ingredients.append({
            "name": ing.get("name", ""),
            "amount": ing.get("amount", 0),
            "unit": ing.get("unit", ""),
            "original": ing.get("original", ""),
        })

    # Extract steps
    steps = []
    for instruction_group in recipe.get("analyzedInstructions", []):
        for step in instruction_group.get("steps", []):
            steps.append(step.get("step", ""))

    return {
        "id": recipe.get("id"),
        "title": recipe.get("title", ""),
        "image": recipe.get("image", ""),
        "source_url": recipe.get("sourceUrl", ""),
        "cook_time_minutes": recipe.get("readyInMinutes", 0),
        "servings": recipe.get("servings", 1),
        "nutrients": nutrients,
        "ingredients": ingredients,
        "steps": steps,
        "cuisines": recipe.get("cuisines", []),
        "diets": recipe.get("diets", []),
    }
