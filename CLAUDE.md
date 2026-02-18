# Verso AI — Project Instructions

## PR Memory Budget

This project runs on an **8 GB EC2 instance**. Every pull request must document its RAM impact.

When creating a PR (`gh pr create`):

1. Run `docker stats --no-stream` at idle and during a representative end-to-end flow (e.g., generating a full lesson).
2. Fill in the **Peak RAM Usage** table in the PR description with the measured values.
3. If total peak usage exceeds **5.5 GB**, flag it clearly in the PR summary with a warning (e.g., "⚠️ Total peak RAM is X GB — exceeds 5.5 GB safe ceiling for 8 GB EC2").

---

## Testing Prompt & Reel Quality

### Quick eval (automated)

```bash
cd backend
python evals.py --quick      # 8 tests against Ollama (needs qwen2.5:3b running)
python evals.py              # full 40 tests (5 doc types x 8 preference combos)
python evals.py --dry-run    # test metrics only, no Ollama needed
```

Target: **95%+ overall score** across 6 metrics (json_valid, schema_complete, depth_match, style_match, content_quality, flashcard_quality).

### Manual testing (upload PDFs)

Upload one of each doc type and verify output quality:

| Doc type | Example | What to check |
|----------|---------|---------------|
| Textbook | Biology, physics chapter | Reels teach one concept each, flashcards test definitions |
| Research paper | Any with abstract/methodology | Reels cover findings, not just abstract |
| Business | Quarterly report, memo | Reels highlight metrics and decisions |
| Fiction | Short story, novel excerpt | Reels capture themes, not just plot |
| Technical | API docs, manual | Reels explain specs clearly |

### Reel output checklist

- [ ] Valid JSON returned (no broken responses in console)
- [ ] Titles are short and catchy (under 60 characters)
- [ ] Style matches onboarding preference:
  - **Visual** — structured language ("First", "Second", "Key point")
  - **Auditory** — conversational words ("you", "imagine", "let's", "consider")
  - **Reading** — long prose sentences (12+ words each), no bullet points
- [ ] Depth matches onboarding preference:
  - **Brief** — 1-3 sentences, under 40 words
  - **Balanced** — 2-4 sentences, 40-80 words
  - **Detailed** — 3+ sentences, 80-120 words
- [ ] Narration field exists on each reel (for TTS)
- [ ] Keywords are relevant to the content

### Flashcard output checklist

- [ ] At least 1 flashcard per reel batch (never empty)
- [ ] Every question ends with `?`
- [ ] Every answer is at least 10 words long
- [ ] Difficulty matches setting (easy = recall, medium = comprehension, hard = analysis)

### Red flags

- Empty `flashcards` array
- Single-sentence summaries when depth is "detailed"
- Generic summaries unrelated to actual content
- JSON parse errors in backend logs
