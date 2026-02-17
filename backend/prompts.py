SUBJECT_CATEGORY_PROMPT = """Classify this document's subject into exactly one category.

Categories: science, math, history, literature, business, technology, medicine, law, arts, engineering, general

Rules:
- science: Biology, Chemistry, Physics, Environmental Science
- math: Mathematics, Statistics, Calculus, Algebra
- history: History, Political Science, Sociology, Anthropology
- literature: Fiction, Poetry, Philosophy, Language Arts, Linguistics
- business: Finance, Economics, Marketing, Management, Accounting
- technology: Computer Science, Programming, AI/ML, Software, Data Science
- medicine: Health, Anatomy, Psychology, Pharmacology, Nursing
- law: Legal Studies, Criminal Justice, Constitutional Law
- arts: Music, Visual Arts, Design, Architecture, Film
- engineering: Mechanical, Electrical, Civil, Chemical Engineering
- general: Anything that doesn't fit above

Respond with ONLY the single category word, nothing else.

Text:
{text}

Category:"""

DOC_TYPE_PROMPT = """Classify this document into exactly one category.

Categories: textbook, research_paper, business, fiction, technical, general

Rules:
- textbook: chapters, exercises, learning objectives
- research_paper: abstract, methodology, citations, findings
- business: reports, proposals, memos, financial data
- fiction: narrative, characters, dialogue, plot
- technical: API docs, manuals, specifications, code
- general: anything that doesn't fit above

Text:
{text}

Category:"""

# ---------------------------------------------------------------------------
# Personalization dicts (mirrors chat.py pattern)
# ---------------------------------------------------------------------------

REEL_STYLE_INSTRUCTIONS = {
    "visual": "Use bold **key terms**, numbered steps, and bullet-point structure. Summaries should be scannable with clear visual hierarchy.",
    "auditory": "Write summaries in a warm, conversational tone as if explaining to a friend. Use natural speech patterns.",
    "reading": "Write summaries as clear, well-structured prose paragraphs. Include full context and nuance.",
    "mixed": "Balance structure with readability. Use short paragraphs with occasional bold terms.",
}

REEL_DEPTH_INSTRUCTIONS = {
    "brief": "Each reel summary should be 1-2 sentences. Focus only on the single most important idea.",
    "balanced": "Each reel summary should be 2-3 sentences. Cover the main idea with enough context.",
    "detailed": "Each reel summary should be 3-4 sentences. Include examples and connections to related concepts.",
}

REEL_USE_CASE_INSTRUCTIONS = {
    "exam": "Focus on definitions, formulas, and testable facts. Flashcard questions should target exam-style recall.",
    "work": "Focus on practical takeaways and actionable insights. Flashcard questions should test application.",
    "learning": "Focus on understanding and why things work. Flashcard questions should test comprehension.",
    "research": "Focus on methodology, evidence, and findings. Flashcard questions should test analytical thinking.",
}

DOC_TYPE_INSTRUCTIONS = {
    "textbook": "Extract key concepts, definitions, and learning objectives. Each reel should teach one concept.",
    "research_paper": "Extract findings, methodology insights, and conclusions. Each reel should cover one finding.",
    "business": "Extract key metrics, decisions, and recommendations. Each reel should highlight one business insight.",
    "fiction": "Extract themes, character developments, and plot turning points. Each reel should capture one narrative moment.",
    "technical": "Extract specifications, procedures, and important parameters. Each reel should explain one technical concept.",
    "general": "Extract the most important ideas and facts. Each reel should present one key point.",
}

FLASHCARD_DIFFICULTY_INSTRUCTIONS = {
    "easy": "Flashcard questions should be straightforward recall — who, what, when, where. Answers should be short and direct.",
    "medium": "Flashcard questions should require understanding — explain, compare, describe. Answers should show comprehension.",
    "hard": "Flashcard questions should require analysis — why, how, what if, evaluate. Answers should demonstrate deep understanding.",
}

# ---------------------------------------------------------------------------
# Few-shot example (one example to show format without bloating prompt)
# ---------------------------------------------------------------------------

REEL_FEW_SHOT = """Example:
Input: "Photosynthesis is the process by which plants convert light energy into chemical energy. Chlorophyll in the leaves absorbs sunlight. The plant uses CO2 from air and water from soil to produce glucose and oxygen."
Output: {"reels":[{"title":"How Plants Make Food","summary":"Photosynthesis converts light energy into chemical energy using chlorophyll. Plants absorb CO2 and water to produce glucose and oxygen, powering life on Earth.","category":"Biology","keywords":"photosynthesis, chlorophyll, glucose, oxygen"}],"flashcards":[{"question":"What are the inputs and outputs of photosynthesis?","answer":"Inputs: light energy, CO2, and water. Outputs: glucose and oxygen."}]}"""

# ---------------------------------------------------------------------------
# Main reel generation prompt
# ---------------------------------------------------------------------------

REEL_GENERATION_PROMPT = """You are a learning content creator for Verso. Generate reels and flashcards from the text below.

DOCUMENT TYPE: {doc_type}
{doc_type_instruction}

STYLE: {style_instruction}
LENGTH: {depth_instruction}
FOCUS: {use_case_instruction}
DIFFICULTY: {difficulty_instruction}

{few_shot}

STRICT RULES:
1. Return ONLY valid JSON — no markdown, no explanation, no text before or after.
2. Every reel MUST have all 5 fields: "title", "summary", "narration", "category", "keywords".
3. Every flashcard MUST have both "question" and "answer".
4. "keywords" must be a comma-separated string, not a list.
5. Generate 1-3 reels and 1-3 flashcards based on content density.
6. If the text is too short or unclear, still produce at least 1 reel and 1 flashcard.
7. "narration" is a spoken-audio version of the summary. Write it as if explaining to a friend in a warm, conversational tone. Use natural phrasing, no bullet points, no special symbols, no abbreviations. It should sound great when read aloud by a text-to-speech engine.

REQUIRED JSON SCHEMA:
{{"reels":[{{"title":"string","summary":"string","narration":"string","category":"string","keywords":"string"}}],"flashcards":[{{"question":"string","answer":"string"}}]}}

Text:
{text}

JSON:"""
