#!/usr/bin/env python3
"""AI Meal Planner — generates weekly meal plans based on your profile.

Usage:
    python3 planner.py generate              # Generate this week's plan
    python3 planner.py generate --day monday # Generate just one day
    python3 planner.py swap lunch wednesday  # Regenerate one meal
    python3 planner.py grocery              # Print grocery list from current plan
    python3 planner.py stats                # Show your nutrition targets
    python3 planner.py history              # Show past plans
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
PLANS_DIR = DATA_DIR / "plans"

# Dietary tradition rules
TRADITION_RULES = {
    "halal": {"exclude": ["pork", "bacon", "ham", "lard", "gelatin"], "notes": "All meat must be halal. No alcohol in cooking."},
    "kosher": {"exclude": ["pork", "bacon", "ham", "shellfish", "shrimp", "crab", "lobster"], "notes": "No mixing meat and dairy in same meal."},
    "hindu-vegetarian": {"exclude": ["meat", "chicken", "fish", "shrimp", "eggs", "beef", "pork", "goat", "lamb"], "notes": "Lacto-vegetarian. Dairy is fine."},
    "hindu-nonveg": {"exclude": ["beef", "pork", "bacon", "ham"], "notes": "Chicken, goat, shrimp, fish, eggs are all fine."},
    "sattvic": {"exclude": ["meat", "chicken", "fish", "eggs", "onion", "garlic", "mushrooms"], "notes": "Pure vegetarian. No stimulating foods."},
    "jain": {"exclude": ["meat", "chicken", "fish", "eggs", "onion", "garlic", "potato", "carrot", "beet", "radish"], "notes": "No root vegetables."},
    "buddhist-vegetarian": {"exclude": ["meat", "chicken", "fish", "shrimp", "goat", "lamb", "beef", "pork"], "notes": "Plant-based with eggs and dairy."},
    "none": {"exclude": [], "notes": ""},
}


def load_profile(path: str = "profile.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def calculate_nutrition(profile: dict) -> dict:
    """Calculate TDEE, daily calories, and macro targets."""
    units = profile.get("units", "metric")

    # Convert to metric for calculation
    if units == "imperial":
        height_cm = (profile.get("height_ft", 5) * 12 + profile.get("height_in", 9)) * 2.54
        weight_kg = profile.get("weight_lbs", 165) / 2.205
        target_kg = profile.get("target_weight_lbs", 0) / 2.205 if profile.get("target_weight_lbs") else 0
    else:
        height_cm = profile.get("height_cm", 175)
        weight_kg = profile.get("weight_kg", 75)
        target_kg = profile.get("target_weight_kg", 0)

    age = profile.get("age", 28)
    gender = profile.get("gender", "male")

    # BMR (Mifflin-St Jeor)
    if gender == "female":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5

    # Activity multiplier
    multipliers = {
        "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
        "active": 1.725, "very-active": 1.9,
    }
    tdee = bmr * multipliers.get(profile.get("activity_level", "moderate"), 1.55)

    # Goal adjustment
    goal = profile.get("goal", "maintenance")
    pace = profile.get("weight_loss_pace", "moderate")
    deficit_map = {"slow": 250, "moderate": 500, "aggressive": 750}

    if goal == "weight-loss":
        daily_cal = tdee - deficit_map.get(pace, 500)
    elif goal == "muscle-gain":
        daily_cal = tdee + 300
    else:
        daily_cal = tdee

    # Override if manually set
    if profile.get("daily_calories", 0) > 0:
        daily_cal = profile["daily_calories"]

    # Macros
    protein = profile.get("protein_target_grams", 0)
    if protein == 0:
        if goal == "muscle-gain":
            protein = round(weight_kg * 2.0)
        elif goal == "weight-loss":
            protein = round(weight_kg * 1.8)
        else:
            protein = round(weight_kg * 1.6)

    fat_cal = daily_cal * 0.25
    protein_cal = protein * 4
    carb_cal = daily_cal - fat_cal - protein_cal

    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "daily_calories": round(daily_cal),
        "protein_g": protein,
        "fat_g": round(fat_cal / 9),
        "carbs_g": round(carb_cal / 4),
        "weight_kg": round(weight_kg, 1),
        "height_cm": round(height_cm, 1),
    }


def build_prompt(profile: dict, nutrition: dict, day: str = None) -> str:
    """Build the AI prompt for meal plan generation."""
    tradition = profile.get("dietary_tradition", "none")
    rules = TRADITION_RULES.get(tradition, TRADITION_RULES["none"])

    excluded = rules["exclude"] + profile.get("disliked_foods", []) + profile.get("allergies", [])
    restrictions = profile.get("dietary_restrictions", [])

    days = [day] if day else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    busy_days = profile.get("busy_days", [])
    prep_day = profile.get("prep_day", "sunday")

    # Meal prep mode: same meals repeated all week
    repeat_meals = profile.get("repeat_meals", False)
    if repeat_meals:
        prompt = f"""Generate a MEAL PREP plan (same meals every day for 7 days).

NUTRITION TARGETS (per day):
- Calories: {nutrition['daily_calories']} kcal
- Protein: {nutrition['protein_g']}g
- Carbs: {nutrition['carbs_g']}g
- Fat: {nutrition['fat_g']}g

RULES:
- Meals per day: {profile.get('meals_per_day', 3)}
- NEVER include: {', '.join(excluded) if excluded else 'no restrictions'}
- Dietary restrictions: {', '.join(restrictions) if restrictions else 'none'}
- Tradition notes: {rules['notes']}
- Favorite foods (include often): {', '.join(profile.get('favorite_foods', [])) or 'none specified'}
- Cuisines: {', '.join(profile.get('cuisines', ['mixed']))}
- Skill level: {profile.get('skill_level', 'intermediate')}
- Budget: {profile.get('budget', 'medium')}
- Servings per meal: 7 (one batch for the whole week)

Generate exactly ONE breakfast, ONE lunch, and ONE dinner that:
1. Hit the daily macro targets when combined
2. Store well in the fridge for 5 days (or freeze)
3. Reheat easily (microwave-friendly)
4. Are satisfying enough to eat every day

FORMAT:

## Breakfast (eaten daily, made in one batch)
- **[Meal name]**: [description]
- Per serving: [X] cal | Protein: [X]g | Carbs: [X]g | Fat: [X]g
- Makes: 7 servings
- Storage: [how long it lasts, how to store]
- Reheat: [instructions]
- Full recipe (7 servings):
  - Ingredients: [list with exact quantities for 7 servings]
  - Steps: [numbered cooking steps]

## Lunch (eaten daily, made in one batch)
[same format]

## Dinner (eaten daily, made in one batch)
[same format]

## Daily Totals
- Calories: [X] | Protein: [X]g | Carbs: [X]g | Fat: [X]g

## Grocery List
Group by section (Produce, Protein, Dairy, Pantry) with exact quantities for 7 days.

## Prep Day Instructions
Step-by-step for cooking all 3 meals in one session. Include estimated total prep time.
"""
        return prompt

    prompt = f"""Generate a meal plan with these requirements:

NUTRITION TARGETS (per day):
- Calories: {nutrition['daily_calories']} kcal
- Protein: {nutrition['protein_g']}g
- Carbs: {nutrition['carbs_g']}g
- Fat: {nutrition['fat_g']}g

RULES:
- Meals per day: {profile.get('meals_per_day', 3)}
- NEVER include: {', '.join(excluded) if excluded else 'no restrictions'}
- Dietary restrictions: {', '.join(restrictions) if restrictions else 'none'}
- Tradition notes: {rules['notes']}
- Favorite foods (include often): {', '.join(profile.get('favorite_foods', [])) or 'none specified'}
- Cuisines: {', '.join(profile.get('cuisines', ['mixed']))}
- Max cook time: {profile.get('max_cook_time_minutes', 30)} minutes per meal
- Skill level: {profile.get('skill_level', 'intermediate')}
- Budget: {profile.get('budget', 'medium')}
- Prep style: {profile.get('prep_style', 'hybrid')}
- Batch prep day: {prep_day}
- Busy days (quick/leftover meals): {', '.join(busy_days) if busy_days else 'none'}
- Breakfast style: {profile.get('breakfast_style', 'quick')}
- Lunch style: {profile.get('lunch_style', 'packed')}
- Dinner style: {profile.get('dinner_style', 'cooked')}
- Variety: {profile.get('variety', 'moderate')}
- Servings: {profile.get('servings', 1)}

Generate plan for: {', '.join(days)}

FORMAT (respond in this exact format):
For each day:

## [Day]

**Breakfast** (~{nutrition['daily_calories'] // profile.get('meals_per_day', 3)} cal)
- [Meal name]: [brief description]
- Prep time: [X] min
- Protein: [X]g | Carbs: [X]g | Fat: [X]g

**Lunch** (~{nutrition['daily_calories'] // profile.get('meals_per_day', 3)} cal)
- [Meal name]: [brief description]
- Prep time: [X] min
- Protein: [X]g | Carbs: [X]g | Fat: [X]g

**Dinner** (~{nutrition['daily_calories'] // profile.get('meals_per_day', 3)} cal)
- [Meal name]: [brief description]
- Prep time: [X] min
- Protein: [X]g | Carbs: [X]g | Fat: [X]g

After all days, add:

## Grocery List
Group by section (Produce, Protein, Dairy, Pantry, Frozen) with quantities.

## Prep Day ({prep_day.title()}) Instructions
Step-by-step batch cooking instructions for meals that can be prepped ahead.
"""
    return prompt


def generate_plan(profile: dict, day: str = None) -> str:
    """Generate meal plan — uses Spoonacular recipes if API key available, else AI-only."""
    nutrition = calculate_nutrition(profile)

    # Try recipe-based generation first
    from recipe_api import get_api_key, search_recipes
    if get_api_key():
        return _generate_with_recipes(profile, nutrition, day)

    # Fallback: pure AI generation
    prompt = build_prompt(profile, nutrition, day)
    try:
        result = subprocess.run(
            ["kiro-cli", "chat", prompt, "--legacy-ui", "--trust-tools=", "--agent", "gpu-minimal"],
            capture_output=True, text=True, timeout=180,
        )
        raw = result.stdout
        raw = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw).replace('\r', '\n')
        lines = [l for l in raw.split('\n') if l.strip() and not any(
            k in l for k in ['Thinking', 'WARNING', 'hooks', 'Credits:', 'exit', 'changelog', 'Model:']
        )]
        return '\n'.join(lines).strip()
    except subprocess.TimeoutExpired:
        return "Error: AI timed out. Try again."
    except FileNotFoundError:
        return "Error: kiro-cli not found. Install it or use a different AI backend."


def _generate_with_recipes(profile: dict, nutrition: dict, day: str = None) -> str:
    """Generate plan using real Spoonacular recipes."""
    from recipe_api import search_recipes

    tradition = profile.get("dietary_tradition", "none")
    restrictions = profile.get("dietary_restrictions", [])
    excluded = profile.get("disliked_foods", []) + profile.get("allergies", [])
    cuisines = profile.get("cuisines", ["mixed"])
    max_time = profile.get("max_cook_time_minutes", 30)
    meals_per_day = profile.get("meals_per_day", 3)
    cal_per_meal = nutrition["daily_calories"] // meals_per_day
    protein_per_meal = nutrition["protein_g"] // meals_per_day

    days = [day.title()] if day else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    busy_days = [d.lower() for d in profile.get("busy_days", [])]

    output = []
    grocery = {}  # ingredient -> amount

    for d in days:
        output.append(f"\n## {d}\n")
        is_busy = d.lower() in busy_days

        for meal_type in ["breakfast", "lunch", "dinner"][:meals_per_day]:
            cuisine = cuisines[hash(d + meal_type) % len(cuisines)] if cuisines[0] != "mixed" else ""
            cook_time = 15 if is_busy else max_time

            # Adjust search for meal type
            query = ""
            if meal_type == "breakfast":
                query = profile.get("breakfast_style", "quick") + " breakfast"
                if profile.get("breakfast_style") == "skip":
                    continue
            elif meal_type == "lunch":
                query = "lunch meal prep" if profile.get("lunch_style") == "packed" else "lunch"

            recipes = search_recipes(
                query=query,
                cuisine=cuisine,
                dietary_tradition=tradition,
                dietary_restrictions=restrictions,
                exclude_ingredients=excluded,
                max_calories=cal_per_meal + 100,
                min_protein=protein_per_meal - 10,
                max_cook_time=cook_time,
                meal_type=meal_type if meal_type != "lunch" else "main course",
                number=3,
            )

            if recipes:
                # Pick best match by protein
                recipe = max(recipes, key=lambda r: r["nutrients"].get("protein_g", 0))
                n = recipe["nutrients"]
                output.append(f"**{meal_type.title()}** ({n.get('calories', '?')} cal)")
                output.append(f"- **{recipe['title']}**")
                output.append(f"- ⏱️ {recipe['cook_time_minutes']} min | Protein: {n.get('protein_g', '?')}g | Carbs: {n.get('carbs_g', '?')}g | Fat: {n.get('fat_g', '?')}g")
                if recipe["source_url"]:
                    output.append(f"- 📖 [Full Recipe]({recipe['source_url']})")
                output.append("")

                # Collect grocery items
                for ing in recipe["ingredients"]:
                    name = ing["name"]
                    grocery[name] = grocery.get(name, 0) + 1
            else:
                output.append(f"**{meal_type.title()}**")
                output.append(f"- No matching recipe found (try broadening preferences)")
                output.append("")

    # Grocery list
    output.append("\n## 🛒 Grocery List\n")
    for item, count in sorted(grocery.items()):
        output.append(f"- {item}" + (f" (×{count})" if count > 1 else ""))

    return "\n".join(output)


def cmd_generate(args):
    profile = load_profile(args.profile)
    nutrition = calculate_nutrition(profile)

    print(f"🍽️  Generating {'daily' if args.day else 'weekly'} meal plan...")
    print(f"   Targets: {nutrition['daily_calories']} cal | {nutrition['protein_g']}g protein | {nutrition['carbs_g']}g carbs | {nutrition['fat_g']}g fat\n")

    plan = generate_plan(profile, args.day)

    # Save plan
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    plan_file = PLANS_DIR / f"plan_{date_str}.md"
    plan_file.write_text(plan)
    print(plan)
    print(f"\n📄 Saved to: {plan_file}")

    # Send to Slack if configured
    webhook = profile.get("slack_webhook", "")
    if webhook:
        import requests
        requests.post(webhook, json={"text": f"*🍽️ Meal Plan — {date_str}*\n\n{plan[:3000]}"}, timeout=10)
        print("📨 Sent to Slack!")


def cmd_stats(args):
    profile = load_profile(args.profile)
    nutrition = calculate_nutrition(profile)
    tradition = profile.get("dietary_tradition", "none")

    print(f"\n📊 Your Nutrition Profile")
    print(f"   Height: {nutrition['height_cm']}cm | Weight: {nutrition['weight_kg']}kg")
    print(f"   BMR: {nutrition['bmr']} cal | TDEE: {nutrition['tdee']} cal")
    print(f"   Goal: {profile.get('goal', 'maintenance')}")
    print(f"\n🎯 Daily Targets:")
    print(f"   Calories: {nutrition['daily_calories']} kcal")
    print(f"   Protein:  {nutrition['protein_g']}g")
    print(f"   Carbs:    {nutrition['carbs_g']}g")
    print(f"   Fat:      {nutrition['fat_g']}g")
    print(f"\n🍽️  Dietary tradition: {tradition}")
    if tradition != "none":
        rules = TRADITION_RULES[tradition]
        print(f"   Excluded: {', '.join(rules['exclude'])}")
        print(f"   Notes: {rules['notes']}")


def cmd_grocery(args):
    plans = sorted(PLANS_DIR.glob("plan_*.md"), reverse=True)
    if not plans:
        print("No plans generated yet. Run: python3 planner.py generate")
        return
    plan = plans[0].read_text()
    # Extract grocery section
    match = re.search(r'## Grocery List(.*?)(?=## |$)', plan, re.DOTALL)
    if match:
        print(f"🛒 Grocery List (from {plans[0].name}):\n")
        print(match.group(1).strip())
    else:
        print("No grocery list found in the latest plan.")


def cmd_swap(args):
    profile = load_profile(args.profile)
    print(f"🔄 Regenerating {args.meal} for {args.day}...")
    plan = generate_plan(profile, args.day)
    print(plan)


def main():
    parser = argparse.ArgumentParser(description="AI Meal Planner")
    parser.add_argument("--profile", "-p", default="profile.yaml")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate meal plan")
    gen.add_argument("--day", help="Single day (monday, tuesday, etc.)")

    sub.add_parser("stats", help="Show nutrition targets")
    sub.add_parser("grocery", help="Print grocery list")

    swap = sub.add_parser("swap", help="Regenerate one meal")
    swap.add_argument("meal", help="breakfast, lunch, or dinner")
    swap.add_argument("day", help="Day of week")

    sub.add_parser("history", help="Show past plans")

    args = parser.parse_args()

    if args.command == "generate": cmd_generate(args)
    elif args.command == "stats": cmd_stats(args)
    elif args.command == "grocery": cmd_grocery(args)
    elif args.command == "swap": cmd_swap(args)
    elif args.command == "history":
        plans = sorted(PLANS_DIR.glob("plan_*.md"))
        for p in plans:
            print(f"  {p.name} ({p.stat().st_size} bytes)")
    else: parser.print_help()


if __name__ == "__main__":
    main()
