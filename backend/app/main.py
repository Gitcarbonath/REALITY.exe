from __future__ import annotations



import base64

import json

import os

import random

from typing import Any



import httpx

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field



from app.database import init_db, get_player, record_attempt, award_xp

# -------------------------------------------------------------------
# PLAYER PROGRESSION
# -------------------------------------------------------------------

LEVELS = [
    (0, "INITIATE"),
    (250, "SCOUT"),
    (500, "EXPLORER"),
    (1000, "FIELD AGENT"),
    (1750, "PATHFINDER"),
    (2750, "GROUND TRUTH"),
]


def get_progression(total_xp: int) -> dict:
    """Return the player's current level and progress toward the next one."""

    level_index = 0

    for index, (threshold, _) in enumerate(LEVELS):
        if total_xp >= threshold:
            level_index = index
        else:
            break

    threshold, name = LEVELS[level_index]
    level = level_index + 1

    if level_index + 1 < len(LEVELS):
        next_threshold = LEVELS[level_index + 1][0]
        xp_into_level = total_xp - threshold
        xp_for_level = next_threshold - threshold
        progress = round(
            (xp_into_level / xp_for_level) * 100
        )
        xp_to_next = max(
            0,
            next_threshold - total_xp,
        )
    else:
        next_threshold = None
        xp_to_next = 0
        progress = 100

    return {
        "level": level,
        "level_name": name,
        "level_xp": threshold,
        "next_level_xp": next_threshold,
        "xp_to_next_level": xp_to_next,
        "level_progress": max(0, min(100, progress)),
    }







# -------------------------------------------------------------------

# APP

# -------------------------------------------------------------------



app = FastAPI(

    title="REALITY.EXE",

    version="0.1.0",

)

init_db()





# -------------------------------------------------------------------

# CORS

# -------------------------------------------------------------------



app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://10.21.100.67:5173",
        ).split(",")
        if origin.strip()
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)





# -------------------------------------------------------------------

# CONFIG

# -------------------------------------------------------------------



OLLAMA_URL = os.getenv(

    "OLLAMA_URL",

    "http://localhost:11434",

)



TEXT_MODEL = os.getenv(

    "TEXT_MODEL",

    "gemma3:4b",

)



VISION_MODEL = os.getenv(

    "VISION_MODEL",

    "gemma3:4b",

)





# -------------------------------------------------------------------

# FALLBACK CASES

# -------------------------------------------------------------------



CASES = [

    {

        "template": "Nature Takes Over",

        "objective": (

            "Find an outdoor human-made object with visible vegetation "

            "growing over or through it."

        ),

        "clues": [

            "Look for something humans built.",

            "It should be outside.",

            "Look closely for living vegetation interacting with it.",

        ],

        "required_criteria": [

            "human_made_object_visible",

            "outdoors",

            "vegetation_growing_on_or_through_object",

        ],

        "bonus_criteria": [

            "visible_weathering",

        ],

    },

    {

        "template": "Three Textures",

        "objective": (

            "Find three visibly different surface textures within "

            "the same outdoor area."

        ),

        "clues": [

            "Stay outside.",

            "Look for surfaces that feel visually different.",

            "Capture all three in one photograph.",

        ],

        "required_criteria": [

            "outdoors",

            "first_distinct_texture_visible",

            "second_distinct_texture_visible",

            "third_distinct_texture_visible",

        ],

        "bonus_criteria": [],

    },

    {

        "template": "The Overlooked Detail",

        "objective": (

            "Find a small human-made detail that is visibly part "

            "of the outdoor environment."

        ),

        "clues": [

            "Look at the environment rather than carried objects.",

            "Search somewhere people normally walk past.",

            "Look closely for a small constructed detail.",

        ],

        "required_criteria": [

            "human_made_detail_visible",

            "outdoors",

            "detail_is_part_of_environment",

        ],

        "bonus_criteria": [

            "detail_is_partially_obscured",

        ],

    },

    {

        "template": "Human Meets Nature",

        "objective": (

            "Find an outdoor scene where a living plant is visibly "

            "interacting with something humans built."

        ),

        "clues": [

            "Look for two different worlds meeting.",

            "One part should be human-made.",

            "One part should be visibly alive.",

        ],

        "required_criteria": [

            "human_made_object_visible",

            "living_plant_visible",

            "visible_interaction_between_them",

            "outdoors",

        ],

        "bonus_criteria": [],

    },

]





# -------------------------------------------------------------------

# MODELS

# -------------------------------------------------------------------



class CaseRequest(BaseModel):

    environment: str = Field(

        default="anywhere",

        min_length=1,

        max_length=100,

    )



    duration: int = Field(

        default=20,

        ge=5,

        le=60,

    )



    difficulty: str = Field(

        default="medium",

        pattern="^(easy|medium|hard)$",

    )





class CaseResponse(BaseModel):

    case_id: str

    title: str

    objective: str

    clues: list[str]

    duration: int

    difficulty: str

    xp: int





# -------------------------------------------------------------------

# FALLBACK

# -------------------------------------------------------------------



def fallback_case(

    req: CaseRequest,

) -> dict[str, Any]:



    base = random.choice(CASES)



    return {

        "case_id": f"case-{random.randint(1000, 9999)}",

        "title": base["template"],

        "objective": base["objective"],

        "clues": base["clues"],

        "required_criteria": base["required_criteria"],

        "bonus_criteria": base["bonus_criteria"],

        "duration": req.duration,

        "difficulty": req.difficulty,

        "xp": {

            "easy": 100,

            "medium": 200,

            "hard": 350,

        }[req.difficulty],

    }





# -------------------------------------------------------------------
# CASE GENERATION
# -------------------------------------------------------------------

CASE_ARCHETYPES = [
    "ordinary object with an unusual visible condition",
    "two common fixed objects with a clear spatial relationship",
    "a visual pattern made from several ordinary objects",
    "a material or texture contrast",
    "a small overlooked architectural detail",
    "visible interaction between nature and a human-made object",
    "a common object framed by another structure",
    "a color or shape pattern involving fixed objects",
    "a visible sign of wear, repair, layering, or modification",
    "one ordinary object satisfying several visible clues",
]

BANNED_REQUIRED_PHRASES = [
    "history", "meaning", "motive", "intention", "ownership",
    "who created", "who left", "what happened", "why it happened",
    "age of", "exact date", "exact location", "specific person",
    "specific vehicle", "specific animal", "rare artifact", "rare object",
    "historical artifact", "restricted area", "private property",
    "trespass", "climb", "cross the road", "approach a stranger",
]

DIFFICULTY_RULES = {
    "easy": (
        "Use common, obvious targets and 2-3 simple visible criteria."
    ),
    "medium": (
        "Use common targets requiring deliberate observation and 3-4 "
        "visible properties or relationships."
    ),
    "hard": (
        "Use subtle but common physical details, layered relationships, "
        "or patterns. Difficulty must come from observation, never rarity."
    ),
}


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def validate_generated_case(
    generated: Any,
    req: CaseRequest,
) -> tuple[bool, str]:
    """Reject weak, unsafe, repetitive, or unverifiable AI cases."""
    if not isinstance(generated, dict):
        return False, "Model output is not an object"

    title = generated.get("title")
    objective = generated.get("objective")
    clues = _clean_string_list(generated.get("clues"))
    required = _clean_string_list(generated.get("required_criteria"))
    bonus = _clean_string_list(generated.get("bonus_criteria"))

    if not isinstance(title, str) or not title.strip():
        return False, "Missing title"
    if not isinstance(objective, str) or not objective.strip():
        return False, "Missing objective"
    if len(title.strip()) > 80:
        return False, "Title is too long"
    if len(objective.strip()) > 280:
        return False, "Objective is too long"

    min_required, max_required = (
        (2, 3) if req.difficulty == "easy" else (3, 4)
    )

    if not min_required <= len(required) <= max_required:
        return False, f"Expected {min_required}-{max_required} required criteria"
    if not 2 <= len(clues) <= 4:
        return False, "Expected 2-4 clues"
    if len(bonus) > 2:
        return False, "Too many bonus criteria"

    normalized = [x.lower() for x in required]
    if len(set(normalized)) != len(normalized):
        return False, "Duplicate required criteria"

    combined = " ".join(normalized)
    for phrase in BANNED_REQUIRED_PHRASES:
        if phrase in combined:
            return False, f"Unverifiable criterion: {phrase}"

    unsafe = [
        "ask someone", "talk to someone", "enter a building",
        "go inside", "cross the road", "climb", "trespass",
        "private property", "restricted area",
    ]
    objective_lower = objective.lower()
    for phrase in unsafe:
        if phrase in objective_lower:
            return False, f"Unsafe objective: {phrase}"

    if any(len(x) > 180 for x in required):
        return False, "Required criterion is too verbose"

    return True, "ok"


def _recent_case_context() -> str:
    recent = getattr(app.state, "recent_cases", [])
    if not recent:
        return "No previous cases."

    return "\n".join(
        f'- "{item["title"]}" — {item["objective"]}'
        for item in recent[-8:]
    )


async def generate_case(
    req: CaseRequest,
) -> dict[str, Any]:

    archetype = random.choice(CASE_ARCHETYPES)
    recent_context = _recent_case_context()

    prompt = f"""
You are the game master for REALITY.EXE, a real-world exploration game.

Generate ONE fresh, safe outdoor mystery.

PLAYER SETTINGS
Environment: {req.environment}
Time limit: {req.duration} minutes
Difficulty: {req.difficulty}
Difficulty rule: {DIFFICULTY_RULES[req.difficulty]}
Selected archetype: {archetype}

CORE RULE
The player must physically explore the real world and ultimately solve the
case by photographing ONE concrete physical target.

The objective must describe something that can actually be found, seen and
photographed. The challenge should come from observation, not rarity.

Prefer common fixed outdoor objects such as benches, signs, railings, fences,
walls, trees, plants, paths, doors, stairs, poles, lamp posts, bins,
planters, pavement, entrances, notice boards and ordinary structures.

Do NOT require rare artifacts, named landmarks, exact locations, specific
people/vehicles/animals, historical facts, temporary events, or objects that
may exist at only one location.

ONE-PHOTOGRAPH RULE
Every required criterion must be directly observable in the SAME photograph.
A criterion must be a visual fact, not an inference.

Good:
- a yellow sign is visible
- two fixed objects are touching
- vegetation is growing through a railing
- three distinct textures are visible
- a repaired section is visibly different
- a circular object is mounted on a wall

Bad:
- the object is old
- determine its history or meaning
- determine who made or left it
- determine what happened
- determine why something happened
- prove ownership
- prove an exact location/date
- ask another person
- rely on information outside the photograph

REQUIRED CRITERIA
Use {2 if req.difficulty == "easy" else 3}-{3 if req.difficulty == "easy" else 4}
required criteria. All are mandatory and must be visible in one photograph.

BONUS CRITERIA
Use 0-2 optional criteria. Missing bonuses must never cause failure.

PLAYABILITY
An ordinary person should have a reasonable chance of finding the target
within {req.duration} minutes in the selected environment. Do not make
rarity the difficulty.

SAFETY
Use a safe public outdoor environment. Never require trespassing, private
property, restricted areas, climbing, crossing traffic, touching dangerous
objects, approaching strangers, interacting with wildlife, or disturbing
property.

ENVIRONMENT
Respect the environment:
- anywhere: broadly available outdoor environments
- campus: university/college surroundings
- park: public park/garden surroundings

NOVELTY
Make the case substantially different from these recent cases:
{recent_context}

Do not reuse their title, target, scenario, or distinctive wording.

SELF-CHECK
Before returning the JSON, verify:
1. It is realistically discoverable.
2. It fits the time limit.
3. Every required criterion is visible in ONE photo.
4. It is safe.
5. It uses common physical targets.
6. It is substantially different from recent cases.

Return ONLY valid JSON:
{{
  "title": "short evocative title",
  "objective": "one sentence describing the physical target",
  "clues": ["first clue", "second clue", "third clue"],
  "required_criteria": ["visual criterion 1", "visual criterion 2", "visual criterion 3"],
  "bonus_criteria": ["optional bonus observation"]
}}
Do not include markdown or explanations outside the JSON.
"""

    last_error = "unknown"

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": TEXT_MODEL,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.9},
                    },
                )

            response.raise_for_status()
            generated = json.loads(response.json()["response"])

            valid, reason = validate_generated_case(generated, req)

            recent_titles = {
                item["title"].strip().lower()
                for item in getattr(app.state, "recent_cases", [])
                if isinstance(item.get("title"), str)
            }
            title_lower = str(generated.get("title", "")).strip().lower()

            if title_lower in recent_titles:
                valid, reason = False, "Recently used title"

            if not valid:
                last_error = reason
                print(f"⚠️ CASE REJECTED ({attempt + 1}/3): {reason}")
                prompt += (
                    f"\n\nYour previous attempt was rejected because: {reason}. "
                    "Generate a substantially different and simpler case."
                )
                continue

            required = _clean_string_list(
                generated.get("required_criteria")
            )
            bonus = _clean_string_list(
                generated.get("bonus_criteria")
            )[:2]
            clues = _clean_string_list(generated.get("clues"))[:4]

            case = {
                "case_id": f"case-{random.randint(1000, 9999)}",
                "title": generated["title"].strip(),
                "objective": generated["objective"].strip(),
                "clues": clues,
                "required_criteria": required,
                "bonus_criteria": bonus,
                "duration": req.duration,
                "difficulty": req.difficulty,
                "xp": {"easy": 100, "medium": 200, "hard": 350}[req.difficulty],
            }

            recent = getattr(app.state, "recent_cases", [])
            recent.append({
                "title": case["title"],
                "objective": case["objective"],
            })
            app.state.recent_cases = recent[-8:]

            print(
                "🤖 GEMMA GENERATED:",
                case["title"],
                "|",
                req.difficulty,
                "|",
                archetype,
            )
            return case

        except Exception as exc:
            last_error = str(exc)
            print(
                f"⚠️ CASE GENERATION ERROR ({attempt + 1}/3): {exc}"
            )

    print("⚠️ ALL CASE GENERATION ATTEMPTS FAILED:", last_error)
    return fallback_case(req)


# -------------------------------------------------------------------

# ROOT

# -------------------------------------------------------------------



@app.get("/")

async def root():



    return {

        "name": "REALITY.EXE",

        "status": "online",

        "version": "0.1.0",

    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "reality-exe-api",
    }





# -------------------------------------------------------------------

@app.get("/api/player")
async def player_stats():
    player = get_player()
    player.update(
        get_progression(player["total_xp"])
    )
    return player


# CREATE CASE

# -------------------------------------------------------------------



@app.post(

    "/api/cases",

    response_model=CaseResponse,

)

async def create_case(

    req: CaseRequest,

):



    case = await generate_case(req)

    record_attempt()



    
    # Server-authoritative hint state for this active case.
    case["revealed_hints"] = []
# MVP storage:

    # process memory only.

    app.state.current_case = case



    return CaseResponse(

        **case

    )





# -------------------------------------------------------------------

# REVEAL HINT

# -------------------------------------------------------------------

@app.post("/api/cases/{case_id}/hint")
async def reveal_hint(
    case_id: str,
    clue_index: int = Form(...),
):
    case = getattr(
        app.state,
        "current_case",
        None,
    )

    if (
        not case
        or case["case_id"] != case_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    clues = case.get("clues", [])

    if (
        clue_index < 0
        or clue_index >= len(clues)
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid hint index",
        )

    revealed_hints = case.setdefault(
        "revealed_hints",
        [],
    )

    already_revealed = clue_index in revealed_hints

    if not already_revealed:
        revealed_hints.append(clue_index)

    hint_cost = sum(
        25 * (index + 1)
        for index in revealed_hints
    )

    return {
        "revealed": True,
        "already_revealed": already_revealed,
        "clue_index": clue_index,
        "hint_cost": hint_cost,

            "xp_earned": player_result["xp_earned"],
        "current_reward": max(
            0,
            case["xp"] - hint_cost,
        ),
    }


# -------------------------------------------------------------------

# EVIDENCE VERIFICATION

# -------------------------------------------------------------------



@app.post(

    "/api/cases/{case_id}/evidence"

)

async def submit_evidence(

    case_id: str,

    image: UploadFile = File(...),

    clue_index: int = Form(default=0),

):



    case = getattr(

        app.state,

        "current_case",

        None,

    )



    if (

        not case

        or case["case_id"] != case_id

    ):

        raise HTTPException(

            status_code=404,

            detail="Case not found",

        )



    raw = await image.read()



    if len(raw) > 8 * 1024 * 1024:

        raise HTTPException(

            status_code=413,

            detail="Image must be under 8 MB",

        )



    required_criteria = case.get(

        "required_criteria",

        [],

    )



    bonus_criteria = case.get(

        "bonus_criteria",

        [],

    )



    # ---------------------------------------------------------------

    # VISION PROMPT

    # ---------------------------------------------------------------



    prompt = f"""

You are the strict evidence verifier for REALITY.EXE.



You are evaluating ONE photograph submitted by a player.



==================================================

MISSION

==================================================



{case["objective"]}



==================================================

REQUIRED CRITERIA

==================================================



The following criteria are mandatory:



{json.dumps(required_criteria)}



Every required criterion must be clearly visible

in the photograph.



If a required criterion cannot be confidently established

from the photograph, mark it FALSE.



==================================================

BONUS CRITERIA

==================================================



These are optional:



{json.dumps(bonus_criteria)}



Bonus criteria do NOT determine whether the case is solved.



==================================================

STRICT VERIFICATION RULES

==================================================



Only use information directly visible in the photograph.



Do NOT assume:



- identity

- ownership

- history

- age

- location

- intention

- motive

- what happened previously

- what something means

- information supplied by the mission text



If something is ambiguous, mark it FALSE.



Do not give the player the benefit of the doubt.



A photograph that merely looks similar to the mission

is NOT sufficient.



==================================================

WHAT DID YOU FIND?

==================================================



Describe what you actually see in the photograph.



This description will be shown directly to the player.



Be specific but concise.



Mention the important visible objects and relationships.



For example:



"A weathered concrete bench is visible outdoors,

with green vines growing across its side."



Do NOT say:



"The player found the correct object."



Instead describe what is actually visible.



==================================================

WHY?

==================================================



If the evidence does not satisfy the case,

briefly explain what is missing.



For example:



"The photograph shows a bench outdoors,

but there is no visible vegetation growing on it."



If the evidence satisfies the case,

briefly explain why.



==================================================

OUTPUT

==================================================



Return ONLY valid JSON:



{{

  "passed": true or false,



  "observation": "What is visibly present in the photograph.",



  "required_criteria": {{

    "criterion": true or false

  }},



  "bonus_criteria": {{

    "criterion": true or false

  }},



  "confidence": 0-100,



  "feedback": "A short explanation of why the evidence passed or failed."

}}



The case can only pass when ALL required criteria are TRUE.

"""



    # ---------------------------------------------------------------

    # CALL GEMMA VISION

    # ---------------------------------------------------------------



    try:



        image_b64 = base64.b64encode(

            raw

        ).decode("utf-8")



        async with httpx.AsyncClient(

            timeout=90

        ) as client:



            response = await client.post(

                f"{OLLAMA_URL}/api/generate",

                json={

                    "model": VISION_MODEL,

                    "prompt": prompt,

                    "images": [image_b64],

                    "format": "json",

                    "stream": False,

                },

            )



        response.raise_for_status()



        data = response.json()



        result = json.loads(

            data["response"]

        )



    except Exception as exc:



        print(

            "❌ VISION VERIFICATION ERROR:",

            exc,

        )



        result = {

            "passed": False,



            "observation": (

                "The AI could not examine "

                "the submitted photograph."

            ),



            "required_criteria": {

                criterion: False

                for criterion in required_criteria

            },



            "bonus_criteria": {

                criterion: False

                for criterion in bonus_criteria

            },



            "confidence": 0,



            "feedback": (

                "Vision verification is not available. "

                "Check that the configured Ollama vision "

                "model is installed and running."

            ),



            "debug": str(exc),

        }



    # ---------------------------------------------------------------

    # EXTRACT AI RESPONSE

    # ---------------------------------------------------------------



    observation = result.get(

        "observation",

        "The AI could not describe the photograph.",

    )



    feedback = result.get(

        "feedback",

        "The evidence could not be verified.",

    )



    try:



        confidence = int(

            result.get(

                "confidence",

                0,

            )

        )



    except (

        TypeError,

        ValueError,

    ):



        confidence = 0



    confidence = max(

        0,

        min(

            100,

            confidence,

        ),

    )



    # ---------------------------------------------------------------

    # SERVER-SIDE REQUIRED CRITERIA CHECK

    # ---------------------------------------------------------------



    required_result = result.get(

        "required_criteria",

        {},

    )



    all_required_passed = (

        isinstance(

            required_result,

            dict,

        )

        and all(

            required_result.get(

                criterion

            )

            is True

            for criterion in required_criteria

        )

    )



    # ---------------------------------------------------------------

    # CASE SOLVED

    # ---------------------------------------------------------------



    if (

        all_required_passed

        and confidence >= 80

    ):



        bonus_result = result.get(

            "bonus_criteria",

            {},

        )



        bonus_count = 0



        if isinstance(

            bonus_result,

            dict,

        ):



            bonus_count = sum(

                1

                for criterion in bonus_criteria

                if bonus_result.get(

                    criterion

                )

                is True

            )



        bonus_xp = (

            bonus_count * 25

        )



        revealed_hints = case.get(
            "revealed_hints",
            [],
        )

        hint_cost = sum(
            25 * (index + 1)
            for index in revealed_hints
        )

        total_xp = max(
            0,
            case["xp"] + bonus_xp - hint_cost,
        )



        player_result = award_xp(
            case_id,
            total_xp,
        )

        previous_total_xp = (
            player_result["total_xp"]
            - player_result["xp_earned"]
        )

        previous_progression = get_progression(
            previous_total_xp
        )

        progression = get_progression(
            player_result["total_xp"]
        )

        level_up = (
            player_result["awarded"]
            and progression["level"]
            > previous_progression["level"]
        )

        return {

            "passed": True,



            "status": "solved",



            "case_id": case_id,



            "observation": observation,



            "reason": feedback,



            "xp": total_xp,



            "base_xp": case["xp"],



            "bonus_xp": bonus_xp,

            "hint_cost": hint_cost,



            
            "total_xp": player_result["total_xp"],

            "cases_solved": player_result["cases_solved"],

            "cases_attempted": player_result["cases_attempted"],

            "level": progression["level"],

            "level_name": progression["level_name"],

            "level_up": level_up,

            "previous_level": previous_progression["level"],

            "xp_to_next_level": progression["xp_to_next_level"],

            "level_progress": progression["level_progress"],
            "message": (

                "CASE SOLVED. "

                "The real world provided the answer."

            ),



            "analysis": result,

        }



    # ---------------------------------------------------------------

    # CASE NOT SOLVED

    # ---------------------------------------------------------------



    return {

        "passed": False,



        "status": "continue",



        "case_id": case_id,



        "observation": observation,



        "reason": feedback,



        "message": feedback,



        "analysis": result,

    }