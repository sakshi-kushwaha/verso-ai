"""
Test fixtures for prompt evaluation.
5 test documents (one per doc type) + 8 preference combos.
"""

# ---------------------------------------------------------------------------
# Test Documents — ~500-800 chars each, representative of each doc type
# ---------------------------------------------------------------------------

TEST_DOCS = [
    {
        "name": "biology_textbook",
        "doc_type": "textbook",
        "text": (
            "Photosynthesis is the process by which green plants and certain other "
            "organisms transform light energy into chemical energy. During photosynthesis, "
            "plants capture light energy with chlorophyll and use it to convert carbon "
            "dioxide and water into glucose and oxygen. The process occurs in two main "
            "stages: the light-dependent reactions, which take place in the thylakoid "
            "membranes and produce ATP and NADPH, and the Calvin cycle, which occurs in "
            "the stroma and uses these products to fix carbon dioxide into glucose. "
            "Photosynthesis is essential for life on Earth as it produces the oxygen we "
            "breathe and forms the base of most food chains. The overall equation is: "
            "6CO2 + 6H2O + light energy → C6H12O6 + 6O2."
        ),
    },
    {
        "name": "ml_research_paper",
        "doc_type": "research_paper",
        "text": (
            "Abstract: This study investigates the effectiveness of transformer-based "
            "architectures for low-resource language classification. We propose a novel "
            "fine-tuning strategy called Adaptive Layer Freezing (ALF) that selectively "
            "freezes transformer layers based on gradient magnitude during training. "
            "Methodology: We evaluated ALF on 12 low-resource language datasets spanning "
            "4 language families. Our baseline models include mBERT, XLM-R, and a "
            "randomly initialized transformer. Results: ALF achieved an average F1 score "
            "improvement of 3.7% over standard fine-tuning across all datasets, with the "
            "largest gains (6.2%) observed in languages with fewer than 1,000 training "
            "examples. The method reduces training time by 23% compared to full "
            "fine-tuning. Limitations: Performance gains diminish for high-resource "
            "languages with more than 50,000 examples."
        ),
    },
    {
        "name": "quarterly_report",
        "doc_type": "business",
        "text": (
            "Q3 2025 Financial Summary: Total revenue reached $142.3M, representing a "
            "18% year-over-year increase driven primarily by enterprise subscription "
            "growth. Gross margin improved to 72.4%, up from 68.1% in Q3 2024, due to "
            "infrastructure optimization and reduced cloud hosting costs. Customer "
            "acquisition cost decreased by 12% to $847 per enterprise customer. Key "
            "strategic decisions this quarter include the expansion into the APAC market "
            "with a new Singapore office and the acquisition of DataFlow Inc. for $23M "
            "to strengthen our analytics capabilities. Churn rate remains stable at 4.2%. "
            "The board approved a $15M investment in AI-powered features for the product "
            "roadmap. Headcount grew to 450 employees across 6 offices."
        ),
    },
    {
        "name": "short_story",
        "doc_type": "fiction",
        "text": (
            "The old lighthouse keeper climbed the spiral staircase one last time, each "
            "step groaning beneath his weight like a familiar complaint. Thirty-seven "
            "years he had tended this light, watching ships navigate safely past the "
            "rocky shoals below. Tonight was different. The automated system they had "
            "installed last month hummed quietly in the corner, its LED array cutting "
            "through the fog with mechanical precision. \"You won't need me anymore,\" "
            "he whispered to the walls. But as he reached the top and looked out at the "
            "churning sea, he noticed something the sensors had missed — a small fishing "
            "boat drifting dangerously close to the northern rocks, its lights dark. "
            "He grabbed the emergency radio. Some things, he thought, still needed a "
            "human eye."
        ),
    },
    {
        "name": "api_documentation",
        "doc_type": "technical",
        "text": (
            "POST /api/v2/users — Creates a new user account. Request body must include "
            "email (string, required, must be valid email format), password (string, "
            "required, minimum 8 characters with at least one uppercase and one number), "
            "and display_name (string, optional, max 50 characters). Returns 201 Created "
            "with user object containing id, email, display_name, and created_at fields. "
            "Rate limited to 10 requests per minute per IP. Authentication: None required "
            "for account creation. Error responses: 400 Bad Request if validation fails, "
            "409 Conflict if email already registered, 429 Too Many Requests if rate "
            "limit exceeded. Example: curl -X POST https://api.example.com/api/v2/users "
            "-H 'Content-Type: application/json' -d '{\"email\": \"user@test.com\", "
            "\"password\": \"SecurePass1\"}'"
        ),
    },
]

# ---------------------------------------------------------------------------
# Preference Combos — 8 targeted combinations
# ---------------------------------------------------------------------------

EVAL_COMBOS = [
    # Core style tests (balanced depth, learning use case)
    {"learning_style": "visual",   "content_depth": "balanced", "use_case": "learning", "flashcard_difficulty": "medium", "label": "visual+balanced+learning"},
    {"learning_style": "auditory", "content_depth": "balanced", "use_case": "exam",     "flashcard_difficulty": "medium", "label": "auditory+balanced+exam"},
    {"learning_style": "reading",  "content_depth": "balanced", "use_case": "learning", "flashcard_difficulty": "medium", "label": "reading+balanced+learning"},
    {"learning_style": "mixed",    "content_depth": "balanced", "use_case": "learning", "flashcard_difficulty": "medium", "label": "mixed+balanced+learning"},
    # Depth tests
    {"learning_style": "mixed",    "content_depth": "brief",    "use_case": "work",     "flashcard_difficulty": "easy",   "label": "mixed+brief+work"},
    {"learning_style": "mixed",    "content_depth": "detailed", "use_case": "research", "flashcard_difficulty": "hard",   "label": "mixed+detailed+research"},
    # Cross combos
    {"learning_style": "visual",   "content_depth": "brief",    "use_case": "exam",     "flashcard_difficulty": "easy",   "label": "visual+brief+exam"},
    {"learning_style": "reading",  "content_depth": "detailed", "use_case": "research", "flashcard_difficulty": "hard",   "label": "reading+detailed+research"},
]

# ---------------------------------------------------------------------------
# Quick eval pairs — 8 representative tests for fast iteration
# ---------------------------------------------------------------------------

QUICK_EVAL_PAIRS = [
    ("biology_textbook",   "mixed+balanced+learning"),
    ("biology_textbook",   "visual+balanced+learning"),
    ("ml_research_paper",  "reading+balanced+learning"),
    ("ml_research_paper",  "auditory+balanced+exam"),
    ("quarterly_report",   "mixed+brief+work"),
    ("short_story",        "mixed+detailed+research"),
    ("api_documentation",  "visual+brief+exam"),
    ("api_documentation",  "reading+detailed+research"),
]
