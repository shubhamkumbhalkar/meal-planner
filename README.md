# AI Meal Planner

A config-driven meal planning tool that generates weekly plans tailored to your body, goals, dietary traditions, and preferences. Uses AI to create varied, nutritionally balanced meals with grocery lists and prep instructions.

## Features

- **Auto-calculated nutrition** — Enter your height, weight, age, activity level → gets your daily calories and macros
- **Dietary traditions** — Halal, Kosher, Hindu-vegetarian, Hindu-nonveg, Sattvic, Jain, Buddhist-vegetarian
- **Flexible goals** — Weight loss, muscle gain, or maintenance with configurable pace
- **Cuisine variety** — Indian, Mexican, Mediterranean, Asian, American, Italian, Thai, Korean, or mixed
- **Meal prep support** — Batch cooking instructions for your prep day
- **Smart scheduling** — Quick meals on busy days, leftovers planning
- **Grocery list** — Grouped by store section with quantities
- **Swap meals** — Don't like something? Regenerate just that meal
- **Metric + Imperial** — Works with kg/cm or lbs/ft

## Quick Start

```bash
pip install -r requirements.txt
cp profile.example.yaml profile.yaml
# Edit profile.yaml with your details

python3 planner.py stats      # Check your calculated targets
python3 planner.py generate   # Generate this week's plan
python3 planner.py grocery    # Print grocery list
```

## Commands

```bash
python3 planner.py generate              # Full weekly plan
python3 planner.py generate --day monday # Just one day
python3 planner.py swap lunch wednesday  # Regenerate one meal
python3 planner.py grocery              # Grocery list from latest plan
python3 planner.py stats                # Your nutrition targets
python3 planner.py history              # Past plans
```

## Configuration

Copy `profile.example.yaml` to `profile.yaml` and customize. Key sections:

### Body Stats
```yaml
age: 28
gender: "male"
units: "imperial"    # or "metric"
height_ft: 5
height_in: 9
weight_lbs: 165
activity_level: "moderate"
```

### Dietary Tradition
```yaml
dietary_tradition: "hindu-nonveg"
# Options:
#   halal              → no pork, no alcohol, halal meat only
#   kosher             → no pork, no shellfish, no meat+dairy together
#   hindu-vegetarian   → no meat, no eggs, no fish
#   hindu-nonveg       → no beef, no pork; chicken, goat, shrimp, fish, eggs ok
#   sattvic            → no meat, no eggs, no onion, no garlic
#   jain               → no meat, no eggs, no root vegetables
#   buddhist-vegetarian → no meat, no fish
#   none               → no restrictions
```

### Goals
```yaml
goal: "weight-loss"           # weight-loss, muscle-gain, maintenance
weight_loss_pace: "moderate"  # slow, moderate, aggressive
# Calories and macros are auto-calculated, or override:
# daily_calories: 2000
# protein_target_grams: 150
```

## How It Works

1. Calculates your TDEE using the Mifflin-St Jeor equation
2. Adjusts for your goal (deficit for weight loss, surplus for muscle gain)
3. AI generates a meal plan respecting all your rules and preferences
4. Outputs a markdown plan with macros per meal + grocery list

## AI Backend

Uses `kiro-cli` by default (free, local). Can be adapted to use any LLM API.

## Roadmap

Upcoming features:

- [ ] **WhatsApp notifications** — Get your weekly plan + grocery list sent directly to WhatsApp
- [ ] **Shopping list export** — Send grocery list to Apple Reminders, Todoist, or AnyList
- [ ] **Web UI** — Simple form-based interface for non-technical users
- [ ] **Spoonacular integration** — Real recipes from 500K+ database with verified nutrition
- [ ] **Weight tracking** — Log weekly weight, auto-adjust calories when you plateau
- [ ] **Calorie cycling** — Higher carbs on workout days, lower on rest days
- [ ] **Seasonal produce** — Suggest meals based on what's cheap/in-season
- [ ] **Multi-person support** — Different dietary needs in the same household
- [ ] **Cost estimator** — Estimated weekly grocery spend based on your store
- [ ] **Leftover optimizer** — Reuse extra servings in next day's meals

## License

MIT
