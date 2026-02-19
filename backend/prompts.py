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

Respond with ONLY a single category word from the list above. No explanation, no punctuation, just the word.

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

Respond with ONLY a single category word from the list above. No explanation, no punctuation, just the word.

Text:
{text}

Category:"""

TOPIC_EXTRACTION_PROMPT = """You are an expert at analyzing documents. Read the text below and identify the {num_topics} most important distinct topics covered.

For each topic, provide:
- "topic": A clear, specific topic name (3-8 words)
- "keywords": 3-5 keywords that would appear in text about this topic

Rules:
1. Return ONLY valid JSON, no extra text.
2. Topics must be distinct — no overlapping or redundant topics.
3. Order topics by importance (most important first).
4. Each topic should be specific enough to make one focused reel.

Schema: {{"topics":[{{"topic":"specific topic name","keywords":"word1, word2, word3"}}]}}

Text:
{text}

JSON:"""

TOPIC_REEL_PROMPT = """You are a learning content creator for Verso. Generate exactly ONE reel and 1-2 flashcards about the specific topic below.

TOPIC: {topic}
DOCUMENT TYPE: {doc_type}
{doc_type_instruction}

STYLE: {style_instruction}
LENGTH: {depth_instruction}
FOCUS: {use_case_instruction}
DIFFICULTY: {difficulty_instruction}

{few_shot}

RULES:
1. Return ONLY valid JSON matching this exact schema — no extra text before or after.
2. Generate exactly 1 reel focused ONLY on the topic "{topic}". Do not cover other topics.
3. Generate 1-2 flashcards about this topic.
4. Every flashcard question MUST end with a question mark (?).
5. Every flashcard answer MUST be at least 10 words long.
6. Reel title must be under 60 characters.
7. "narration" MUST follow these spoken-audio rules:
   - Write as if explaining to a curious friend, NOT reading from a textbook.
   - Use contractions: "don't", "isn't", "you're", "it's", "here's".
   - Mix short punchy sentences (5-8 words) with longer explanations (12-18 words).
   - Start at least one sentence with "Here's the thing", "Think about it", "Now", or "So".
   - Use "..." for natural pauses and "—" for pivots.
   - NEVER use passive voice in the first sentence. Start with something engaging.
   - Narration MUST be 40-60 words long (~15-20 seconds when spoken). Never shorter than 40 words.
   - End with a memorable takeaway or a reflective thought — not a dry fact.
   - No bullet points, no special symbols, no abbreviations, no parentheses.

Schema: {{"reels":[{{"title":"short catchy title","summary":"key idea summary","narration":"spoken version of summary","category":"topic area","keywords":"comma separated"}}],"flashcards":[{{"question":"question about content?","answer":"detailed answer at least 10 words long"}}]}}

Relevant text about "{topic}":
{text}

JSON:"""

# ---------------------------------------------------------------------------
# Personalization dicts
# ---------------------------------------------------------------------------

REEL_STYLE_INSTRUCTIONS = {
    "visual": "Use short, scannable sentences. Include structured language like 'First', 'Second', 'Key point' to organize ideas.",
    "auditory": "Write as if talking directly to the reader. You MUST use at least one of these words in every summary: 'you', 'imagine', 'think of', 'let\\'s', 'consider', 'notice', 'here\\'s the thing', 'basically'. Be warm and conversational.",
    "reading": "Write in flowing prose paragraphs with no bullet points. Every sentence MUST be at least 12 words long. Use complete, detailed sentences with full context — never use short fragments.",
    "mixed": "Balance structure with readability. Use short paragraphs with occasional bold terms.",
}

REEL_DEPTH_INSTRUCTIONS = {
    "brief": "Each reel summary should be 1-3 sentences and under 40 words. One core idea only. Be concise. IMPORTANT: You must still generate flashcards even when reels are brief.",
    "balanced": "Each reel summary should be 2-4 sentences and 40-80 words. Cover the main idea with supporting context.",
    "detailed": "Each reel summary MUST be at least 3 sentences and 80-120 words. Include examples, explanations, and connections to related concepts. Never write a single-sentence summary for detailed mode.",
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
    "easy": "Flashcard questions should be straightforward recall — who, what, when, where. Answers should be short and direct (but at least 10 words).",
    "medium": "Flashcard questions should require understanding — explain, compare, describe. Answers should show comprehension (at least 10 words).",
    "hard": "Flashcard questions should require analysis — why, how, what if, evaluate. Answers should demonstrate deep understanding (at least 10 words).",
}

# ---------------------------------------------------------------------------
# Few-shot example
# ---------------------------------------------------------------------------

REEL_FEW_SHOT = """Example:
Input: "Photosynthesis is the process by which plants convert light energy into chemical energy. Chlorophyll in the leaves absorbs sunlight. The plant uses CO2 from air and water from soil to produce glucose and oxygen."
Output: {{"reels":[{{"title":"How Plants Make Food","summary":"Photosynthesis converts light energy into chemical energy using chlorophyll. Plants absorb CO2 and water to produce glucose and oxygen, powering life on Earth.","narration":"Here's the thing about plants — they're basically solar-powered food factories. Chlorophyll in their leaves grabs sunlight... then the plant pulls in carbon dioxide from the air and water from the soil. Mix those together with light energy, and you get glucose for food and oxygen for us to breathe. Without this one reaction, life as we know it simply wouldn't exist.","category":"Biology","keywords":"photosynthesis, chlorophyll, glucose, oxygen"}}],"flashcards":[{{"question":"What are the inputs and outputs of photosynthesis?","answer":"Inputs: light energy, CO2, and water. Outputs: glucose and oxygen."}}]}}"""

# ---------------------------------------------------------------------------
# System prompt for reel model (critical rules get highest attention here)
# ---------------------------------------------------------------------------

REEL_SYSTEM_PROMPT = """You are Verso, a learning content creator who teaches through short reels.
You are NOT a textbook. You explain like a friend.

CRITICAL RULES YOU MUST FOLLOW:
1. You MUST use at least 3 contractions (don't, isn't, you're, it's, here's) in every narration.
2. You MUST use "..." at least once and "—" at least once in every narration.
3. You must NEVER use these phrases: "is defined as", "refers to the process", "plays a crucial role", "it is important to note", "furthermore", "moreover".
4. Narration MUST be 40-60 words. Count carefully.
5. Always output valid JSON with "reels" and "flashcards" arrays."""

# ---------------------------------------------------------------------------
# Main reel generation prompt
# ---------------------------------------------------------------------------

REEL_SCRIPT_PROMPT = """You are a video editor for short educational reels. Create a script that uses multiple video clips.

Available clips (use ONLY these filenames):
{clip_list}

Rules:
1. Return ONLY valid JSON, no extra text.
2. Pick exactly {num_segments} different clips from the list above.
3. Each segment "duration" is in seconds. Durations MUST sum to exactly {total_duration}.
4. Each duration must be at least 2 seconds.
5. "narration" is one continuous paragraph for text-to-speech. No bullet points, no special characters.
6. "overlay" is short text shown on screen (max 8 words per segment).
7. "title" is a catchy title under 50 characters.

Schema: {{"title":"catchy title","narration":"full spoken narration paragraph","segments":[{{"clip":"filename.mp4","overlay":"short text","duration":5}}]}}

Text to create a reel about:
{text}

JSON:"""

REEL_MIXED_SCRIPT_PROMPT = """You are a video editor for short educational reels. Create a script that mixes video clips and images.

Available video clips:
{clip_list}

Available images (shown as still frames with text overlay):
{image_list}

Rules:
1. Return ONLY valid JSON, no extra text.
2. Create exactly {num_segments} segments. Each is either a video clip OR an image with text.
3. Use at most 1-2 image segments for key facts or concepts. The rest MUST be video clips.
4. Do NOT put images back-to-back. Always separate them with a video clip.
5. Start and end with a video clip for a dynamic feel.
6. For video segments: {{"type":"video","clip":"filename.mp4","duration":5}}
7. For image segments: {{"type":"image","image":"filename.jpg","text":"short key fact max 10 words","duration":4}}
8. Image "text" should be a punchy standalone fact — NOT a repeat of the narration.
9. Durations MUST sum to exactly {total_duration}. Each duration must be at least 2 seconds.
10. "narration" is one continuous spoken paragraph (40-60 words) for text-to-speech. Natural, conversational, engaging. No bullet points or special characters.
11. "title" is a catchy title under 50 characters.

Schema: {{"title":"catchy title","narration":"full spoken narration paragraph","segments":[{{"type":"video","clip":"filename.mp4","duration":5}},{{"type":"image","image":"filename.jpg","text":"key fact","duration":4}}]}}

Text to create a reel about:
{text}

JSON:"""

DOC_SUMMARY_PROMPT = """You are a study assistant. Read the document text below and write a short summary.

Rules:
1. Write exactly 3-5 sentences. No more, no less.
2. Cover the main topic and key takeaways only.
3. Write in plain prose — no bullet points, no headers, no numbered lists.
4. Write at a level a student can understand.
5. Do NOT start with "this document" or "this text". Start directly with the subject.
6. Return ONLY the summary text. No preamble, no labels.

Document text:
{text}

Summary:"""

REEL_GENERATION_PROMPT = """Generate reels and flashcards from the text below.

DOCUMENT TYPE: {doc_type}
{doc_type_instruction}

STYLE: {style_instruction}
LENGTH: {depth_instruction}
FOCUS: {use_case_instruction}
DIFFICULTY: {difficulty_instruction}

{few_shot}

RULES:
1. Return ONLY valid JSON matching this exact schema — no extra text before or after.
2. You MUST generate at least 1 reel and at least 1 flashcard. Never omit flashcards.
3. Every flashcard question MUST end with a question mark (?).
4. Every flashcard answer MUST be at least 10 words long.
5. Reel titles must be under 60 characters.
6. "narration" MUST follow these spoken-audio rules:
   – Write as if explaining to a curious friend, NOT reading from a textbook.
   – Use contractions: "don't", "isn't", "you're", "it's", "here's".
   – Mix short punchy sentences (5-8 words) with longer explanations (12-18 words).
   – Start at least one sentence with "Here's the thing", "Think about", "Now", or "So".
   – Use "..." for natural pauses and "—" for pivots. Example: "Water isn't just H2O... it's the molecule that — quite literally — makes life possible."
   – NEVER use passive voice in the first sentence. Start with something that grabs attention.
   – Narration MUST be 40-60 words long (~15-20 seconds when spoken).
   – End with a memorable takeaway or a reflective thought — not a dry summary.
   – No bullet points, no special symbols, no abbreviations, no parentheses.

Schema: {{"reels":[{{"title":"short catchy title","summary":"key idea summary","narration":"spoken version of summary","category":"topic","keywords":"comma separated"}}],"flashcards":[{{"question":"question about content?","answer":"detailed answer at least 10 words long"}}]}}

Text:
{text}

JSON:"""
