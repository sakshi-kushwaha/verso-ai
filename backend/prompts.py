DOC_TYPE_PROMPT = """Classify this document into exactly one category: textbook, research_paper, business, fiction, technical, or general.

Return ONLY the category name, nothing else.

Text:
{text}"""


REEL_GENERATION_PROMPT = """You are a learning content creator. Given the following text from a {doc_type} document, generate reels and flashcards.

Each reel is a bite-sized learning card. Each flashcard is a question-answer pair for self-testing.

Return ONLY valid JSON in this exact format, no other text:
{{
  "reels": [
    {{
      "title": "short catchy title",
      "summary": "2-3 sentence summary of the key idea",
      "category": "topic category",
      "keywords": "comma separated keywords"
    }}
  ],
  "flashcards": [
    {{
      "question": "a question about the content",
      "answer": "concise answer"
    }}
  ]
}}

Generate 1-3 reels and 1-3 flashcards based on content density.

Text:
{text}"""
