"""
Verso Prompt Evaluation & Benchmarking (DSPy-based)

Runs 5 test documents x 8 preference combos = 40 eval tests.
Scores each output on 6 metrics. Prints scorecard + saves JSON.

Usage:
    cd backend
    python evals.py              # full eval (needs Ollama running)
    python evals.py --dry-run    # test metrics only (no LLM calls)
"""

import json
import re
import sys
import os
from datetime import datetime
from difflib import SequenceMatcher

try:
    import dspy
    HAS_DSPY = True
except ImportError:
    HAS_DSPY = False

from config import OLLAMA_HOST, LLM_MODEL, CLASSIFICATION_MODEL, REEL_MODEL
from llm import (
    generate_reels, detect_doc_type, detect_subject_category,
    extract_topics, gather_topic_content, generate_topic_reel,
)
from eval_fixtures import TEST_DOCS, EVAL_COMBOS, QUICK_EVAL_PAIRS, QUICK_TOPIC_REEL_PAIRS


# ═══════════════════════════════════════════════════════════════════════════
# DSPy Setup (optional — eval metrics work without it)
# ═══════════════════════════════════════════════════════════════════════════

if HAS_DSPY:
    class ReelGenerationSignature(dspy.Signature):
        """Generate learning reels and flashcards from document text."""
        text: str = dspy.InputField(desc="Document text")
        doc_type: str = dspy.InputField(desc="Document classification")
        learning_style: str = dspy.InputField(desc="visual/auditory/reading/mixed")
        content_depth: str = dspy.InputField(desc="brief/balanced/detailed")
        use_case: str = dspy.InputField(desc="exam/work/learning/research")
        flashcard_difficulty: str = dspy.InputField(desc="easy/medium/hard")
        reels_json: str = dspy.OutputField(desc='JSON with "reels" and "flashcards" arrays')


# ═══════════════════════════════════════════════════════════════════════════
# Metrics — each returns (pass: bool, details: dict)
# ═══════════════════════════════════════════════════════════════════════════

def _count_sentences(text: str) -> int:
    """Count sentences by splitting on sentence-ending punctuation."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return len([s for s in sentences if len(s.strip()) > 3])


def metric_json_valid(raw_output: str, **_) -> tuple[bool, dict]:
    """Metric 1: Does the output parse as valid JSON with reels + flashcards?"""
    try:
        data = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
        has_reels = "reels" in data and isinstance(data["reels"], list)
        has_fcs = "flashcards" in data and isinstance(data["flashcards"], list)
        return has_reels and has_fcs, {"parsed": True, "has_reels": has_reels, "has_flashcards": has_fcs}
    except (json.JSONDecodeError, TypeError):
        return False, {"parsed": False}


def metric_schema_complete(parsed: dict, **_) -> tuple[bool, dict]:
    """Metric 2: All required fields present in every reel and flashcard?"""
    reel_fields = {"title", "summary", "category", "keywords"}
    fc_fields = {"question", "answer"}
    missing = []

    for i, reel in enumerate(parsed.get("reels", [])):
        for f in reel_fields:
            if f not in reel or not reel[f]:
                missing.append(f"reel[{i}].{f}")

    for i, fc in enumerate(parsed.get("flashcards", [])):
        for f in fc_fields:
            if f not in fc or not fc[f]:
                missing.append(f"flashcard[{i}].{f}")

    return len(missing) == 0, {"missing_fields": missing}


def metric_depth_match(parsed: dict, prefs: dict, **_) -> tuple[bool, dict]:
    """Metric 3: Summary sentence count matches requested depth?"""
    depth = prefs.get("content_depth", "balanced")
    expected = {"brief": (1, 3), "balanced": (1, 4), "detailed": (2, 7)}
    lo, hi = expected.get(depth, (1, 5))

    reels = parsed.get("reels", [])
    if not reels:
        return False, {"reason": "no reels", "expected": f"{lo}-{hi} sentences"}

    counts = []
    for reel in reels:
        count = _count_sentences(reel.get("summary", ""))
        counts.append(count)

    avg = sum(counts) / len(counts) if counts else 0
    passed = lo <= avg <= hi
    return passed, {"sentence_counts": counts, "avg": round(avg, 1), "expected_range": f"{lo}-{hi}"}


def metric_style_match(parsed: dict, prefs: dict, **_) -> tuple[bool, dict]:
    """Metric 4: Output follows the requested learning style?"""
    style = prefs.get("learning_style", "mixed")
    reels = parsed.get("reels", [])
    if not reels:
        return False, {"reason": "no reels"}

    all_summaries = " ".join(r.get("summary", "") for r in reels)

    if style == "mixed":
        return True, {"reason": "mixed always passes"}

    if style == "visual":
        markers = {
            "bold": bool(re.search(r'\*\*\w+', all_summaries)),
            "bullets": bool(re.search(r'[-•]\s', all_summaries)),
            "numbers": bool(re.search(r'\d+[\.\)]\s', all_summaries)),
            "structured_language": bool(re.search(r'(First|Second|Third|Step \d|Key point|Key idea)', all_summaries, re.IGNORECASE)),
            "short_sentences": _count_sentences(all_summaries) >= len(reels),
        }
        found = sum(markers.values())
        return found >= 1, {"style": "visual", "markers": markers}

    if style == "auditory":
        conversational = ["you", "imagine", "think of", "let's", "we", "picture",
                          "notice", "consider", "here's", "so ", "basically", "right"]
        lower = all_summaries.lower()
        found = [w for w in conversational if w in lower]
        return len(found) >= 1, {"style": "auditory", "markers_found": found}

    if style == "reading":
        has_bullets = bool(re.search(r'[-•]\s', all_summaries))
        words = all_summaries.split()
        avg_sentence_len = len(words) / max(1, _count_sentences(all_summaries))
        return not has_bullets and avg_sentence_len > 10, {
            "style": "reading", "has_bullets": has_bullets, "avg_sentence_words": round(avg_sentence_len, 1)
        }

    return True, {"reason": f"unknown style: {style}"}


def metric_content_quality(parsed: dict, source_text: str, **_) -> tuple[float, dict]:
    """Metric 5: Content quality score (0-1). Checks title, keywords, originality."""
    reels = parsed.get("reels", [])
    if not reels:
        return 0.0, {"reason": "no reels"}

    checks = {}
    total = 0
    passed = 0

    # Check 1: At least 1 reel
    total += 1
    checks["has_reels"] = len(reels) > 0
    passed += int(checks["has_reels"])

    # Check 2: Titles under 60 chars
    total += 1
    title_ok = all(len(r.get("title", "")) <= 60 for r in reels)
    checks["titles_short"] = title_ok
    passed += int(title_ok)

    # Check 3: Summary is not a verbatim copy (< 80% overlap with source)
    total += 1
    all_summaries = " ".join(r.get("summary", "") for r in reels)
    overlap = SequenceMatcher(None, source_text[:500].lower(), all_summaries[:500].lower()).ratio()
    checks["not_verbatim"] = overlap < 0.80
    checks["overlap_ratio"] = round(overlap, 3)
    passed += int(checks["not_verbatim"])

    # Check 4: Keywords contain at least 1 word from source
    total += 1
    source_words = set(re.findall(r'\b\w{4,}\b', source_text.lower()))
    all_kw = " ".join(r.get("keywords", "") for r in reels).lower()
    kw_words = set(re.findall(r'\b\w{4,}\b', all_kw))
    common = source_words & kw_words
    checks["keywords_relevant"] = len(common) > 0
    checks["common_keywords"] = list(common)[:5]
    passed += int(checks["keywords_relevant"])

    return passed / total, checks


def metric_flashcard_quality(parsed: dict, **_) -> tuple[float, dict]:
    """Metric 6: Flashcard quality score (0-1)."""
    fcs = parsed.get("flashcards", [])
    checks = {}
    total = 0
    passed = 0

    # Check 1: At least 1 flashcard
    total += 1
    checks["has_flashcards"] = len(fcs) > 0
    passed += int(checks["has_flashcards"])

    if not fcs:
        return passed / total, checks

    # Check 2: Questions end with ?
    total += 1
    q_marks = all(fc.get("question", "").strip().endswith("?") for fc in fcs)
    checks["questions_have_qmark"] = q_marks
    passed += int(q_marks)

    # Check 3: Answers are substantial (>= 10 chars)
    total += 1
    answers_ok = all(len(fc.get("answer", "").strip()) >= 10 for fc in fcs)
    checks["answers_substantial"] = answers_ok
    passed += int(answers_ok)

    # Check 4: Question and answer are different
    total += 1
    different = all(fc.get("question", "").strip() != fc.get("answer", "").strip() for fc in fcs)
    checks["qa_different"] = different
    passed += int(different)

    return passed / total, checks


# ═══════════════════════════════════════════════════════════════════════════
# Metric 7: Narration quality (prompt-rule-aligned)
# ═══════════════════════════════════════════════════════════════════════════

CONTRACTIONS = ["don't", "isn't", "you're", "it's", "here's", "can't",
                "won't", "doesn't", "couldn't", "wouldn't", "they're", "we're"]

CONVERSATION_STARTERS = ["here's the thing", "think about it", "now ", "now,",
                         "so ", "so,", "imagine", "you know", "let's"]

TEXTBOOK_PHRASES = [
    "is defined as", "refers to the process", "is characterized by",
    "plays a crucial role", "it is important to note", "in conclusion",
    "furthermore", "moreover", "thus,", "hence,", "therefore,",
    "one can observe", "it should be noted",
]


def metric_narration_quality(parsed: dict, **_) -> tuple[float, dict]:
    """Metric 7: Narration follows the spoken-audio rules from REEL_GENERATION_PROMPT."""
    reels = parsed.get("reels", [])
    if not reels:
        return 0.0, {"reason": "no reels"}

    for i, reel in enumerate(reels):
        narration = reel.get("narration", "") or ""
        words = narration.split()
        word_count = len(words)
        sentences = [s.strip() for s in re.split(r'[.!?]', narration) if s.strip()]

        # Check 1: Word count in 40-70 range
        total += 1
        length_ok = 30 <= word_count <= 75  # generous tolerance
        checks[f"reel_{i}_word_count"] = word_count
        checks[f"reel_{i}_word_count_ok"] = length_ok
        passed += int(length_ok)

        # Check 2: Has at least 1 contraction
        total += 1
        contraction_count = sum(1 for c in CONTRACTIONS if c in narration.lower())
        has_contraction = contraction_count >= 1
        checks[f"reel_{i}_contractions"] = contraction_count
        passed += int(has_contraction)

        # Check 3: Has conversational starter
        total += 1
        lower_narr = narration.lower()
        has_starter = any(s in lower_narr for s in CONVERSATION_STARTERS)
        checks[f"reel_{i}_has_starter"] = has_starter
        passed += int(has_starter)

        # Check 4: No passive voice in first sentence
        total += 1
        first_sentence = sentences[0] if sentences else ""
        passive_starts = ["is ", "are ", "was ", "were ", "has been", "it is", "there is", "there are"]
        active_start = not any(first_sentence.lower().startswith(p) for p in passive_starts)
        checks[f"reel_{i}_active_start"] = active_start
        passed += int(active_start)

        # Check 5: Uses pause markers (... or —)
        total += 1
        has_pauses = "..." in narration or "—" in narration or " -- " in narration
        checks[f"reel_{i}_has_pauses"] = has_pauses
        passed += int(has_pauses)

        # Check 6: No textbook phrases
        total += 1
        textbook_count = sum(1 for p in TEXTBOOK_PHRASES if p in lower_narr)
        no_textbook = textbook_count == 0
        checks[f"reel_{i}_textbook_phrases"] = textbook_count
        passed += int(no_textbook)

        # Check 7: Sentence length variety (has short AND long sentences)
        total += 1
        if len(sentences) >= 2:
            lengths = [len(s.split()) for s in sentences]
            has_short = any(l <= 8 for l in lengths)
            has_long = any(l >= 12 for l in lengths)
            has_variety = has_short and has_long
        else:
            has_variety = False
        checks[f"reel_{i}_sentence_variety"] = has_variety
        passed += int(has_variety)

    score = passed / total if total else 0.0
    return score, checks


def score_reel(reel_dict: dict, source_text: str, prefs: dict = None) -> dict:
    """Composite scorer: returns 0-1 score + per-metric breakdown."""
    if prefs is None:
        prefs = {
            "learning_style": "mixed",
            "content_depth": "balanced",
            "use_case": "learning",
            "flashcard_difficulty": "medium",
        }

    raw_str = json.dumps(reel_dict) if isinstance(reel_dict, dict) else str(reel_dict)
    results = {}

    ok, _ = metric_json_valid(raw_str)
    results["json_valid"] = {"score": 1.0 if ok else 0.0, "pass": ok, "weight": 1.0}

    ok, _ = metric_schema_complete(reel_dict)
    results["schema_complete"] = {"score": 1.0 if ok else 0.0, "pass": ok, "weight": 1.0}

    ok, _ = metric_depth_match(reel_dict, prefs)
    results["depth_match"] = {"score": 1.0 if ok else 0.0, "pass": ok, "weight": 1.0}

    ok, _ = metric_style_match(reel_dict, prefs)
    results["style_match"] = {"score": 1.0 if ok else 0.0, "pass": ok, "weight": 1.0}

    score, _ = metric_content_quality(reel_dict, source_text)
    results["content_quality"] = {"score": score, "pass": score >= 0.75, "weight": 1.5}

    score, _ = metric_flashcard_quality(reel_dict)
    results["flashcard_quality"] = {"score": score, "pass": score >= 0.75, "weight": 1.0}

    score, _ = metric_narration_quality(reel_dict)
    results["narration_quality"] = {"score": score, "pass": score >= 0.6, "weight": 1.5}

    total_weight = sum(m["weight"] for m in results.values())
    weighted_sum = sum(m["score"] * m["weight"] for m in results.values())
    composite = weighted_sum / total_weight if total_weight else 0.0

    return {"composite_score": round(composite, 3), "metrics": results}


# ═══════════════════════════════════════════════════════════════════════════
# Topic-based Metrics (new pipeline)
# ═══════════════════════════════════════════════════════════════════════════

def metric_topic_extraction(topics: list, source_text: str, num_requested: int, **_) -> tuple[float, dict]:
    """Topic extraction quality score (0-1). Checks structure, count, distinctness, relevance."""
    checks = {}
    total = 0
    passed = 0

    # Check 1: Got at least 1 topic
    total += 1
    checks["has_topics"] = len(topics) > 0
    passed += int(checks["has_topics"])
    if not topics:
        return passed / total, checks

    # Check 2: Each topic has required fields (topic + keywords)
    total += 1
    fields_ok = all("topic" in t and "keywords" in t and t["topic"] and t["keywords"] for t in topics)
    checks["fields_complete"] = fields_ok
    passed += int(fields_ok)

    # Check 3: Reasonable count (at least half of requested)
    total += 1
    count_ok = len(topics) >= max(1, num_requested // 2)
    checks["count_ok"] = count_ok
    checks["found"] = len(topics)
    checks["requested"] = num_requested
    passed += int(count_ok)

    # Check 4: Topics are distinct (no near-duplicate names)
    total += 1
    names = [t["topic"].lower() for t in topics]
    distinct = True
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if SequenceMatcher(None, names[i], names[j]).ratio() > 0.8:
                distinct = False
                break
    checks["distinct"] = distinct
    passed += int(distinct)

    # Check 5: Topics are relevant to source text (keywords appear in text)
    total += 1
    src = source_text.lower()
    relevant = 0
    for t in topics:
        words = set(re.findall(r'\b\w{4,}\b', (t["topic"] + " " + t.get("keywords", "")).lower()))
        if any(w in src for w in words):
            relevant += 1
    checks["relevant"] = f"{relevant}/{len(topics)}"
    checks["relevant_ok"] = relevant >= max(1, len(topics) // 2)
    passed += int(checks["relevant_ok"])

    return passed / total, checks


def run_topic_extraction_eval(doc: dict, dry_run: bool = False) -> dict:
    """Test extract_topics + gather_topic_content on a single document."""
    text = doc["text"]
    num_topics = 3

    if dry_run:
        topics = [
            {"topic": "Key Concept One", "keywords": "test, concept, example"},
            {"topic": "Key Concept Two", "keywords": "another, topic, here"},
        ]
        gather_len = 200
    else:
        topics = extract_topics(text, num_topics=num_topics)
        if topics:
            content = gather_topic_content(topics[0], text)
            gather_len = len(content)
        else:
            gather_len = 0

    score, details = metric_topic_extraction(topics or [], text, num_topics)

    return {
        "doc": doc["name"],
        "topics": [t.get("topic", "") for t in (topics or [])],
        "gather_len": gather_len,
        "gather_ok": gather_len > 50,
        "score": score,
        "pass": score >= 0.6,
        "details": details,
    }


def run_topic_reel_eval(doc: dict, prefs: dict, topics: list = None, dry_run: bool = False) -> dict:
    """Run eval on topic-based reel generation (new pipeline).
    Pre-extracted topics can be passed to avoid redundant LLM calls."""
    text = doc["text"]
    doc_type = doc["doc_type"]

    if dry_run:
        raw = {
            "reels": [{"title": "Topic Reel", "summary": "Test summary for topic-based reel generation eval.", "narration": "Test narration here.", "category": "general", "keywords": "test, topic"}],
            "flashcards": [{"question": "What is this?", "answer": "This is a dry run test of the topic reel generation pipeline."}],
        }
    else:
        if topics is None:
            topics = extract_topics(text, num_topics=3)
        if not topics:
            return {
                "doc": doc["name"], "doc_type": doc_type, "prefs": prefs["label"],
                "output": None,
                "metrics": {n: {"pass": False, "error": "no topics extracted"} for n in
                            ["json_valid", "schema_complete", "depth_match", "style_match", "content_quality", "flashcard_quality"]},
            }
        topic = topics[0]
        topic_text = gather_topic_content(topic, text)
        raw = generate_topic_reel(topic["topic"], topic_text, doc_type, prefs)

    raw_str = json.dumps(raw) if isinstance(raw, dict) else str(raw)

    # Score with the same 6 metrics as old reel eval
    results = {}

    ok, details = metric_json_valid(raw_str)
    results["json_valid"] = {"pass": ok, **details}

    parsed = raw if isinstance(raw, dict) else {}
    try:
        parsed = json.loads(raw_str) if isinstance(raw_str, str) else raw
    except (json.JSONDecodeError, TypeError):
        parsed = {"reels": [], "flashcards": []}

    ok, details = metric_schema_complete(parsed)
    results["schema_complete"] = {"pass": ok, **details}

    ok, details = metric_depth_match(parsed, prefs)
    results["depth_match"] = {"pass": ok, **details}

    ok, details = metric_style_match(parsed, prefs)
    results["style_match"] = {"pass": ok, **details}

    score, details = metric_content_quality(parsed, text)
    results["content_quality"] = {"score": score, "pass": score >= 0.75, **details}

    score, details = metric_flashcard_quality(parsed)
    results["flashcard_quality"] = {"score": score, "pass": score >= 0.75, **details}

    return {
        "doc": doc["name"],
        "doc_type": doc_type,
        "prefs": prefs["label"],
        "output": raw,
        "metrics": results,
    }


def print_topic_extraction_scorecard(results: list[dict]):
    """Print topic extraction eval results."""
    print()
    print("-" * 60)
    print("TOPIC EXTRACTION EVAL")
    print("-" * 60)

    for r in results:
        symbol = "+" if r["pass"] else "-"
        topics_str = ", ".join(r.get("topics", [])[:3])
        gather_str = f"gather={r.get('gather_len', 0)} chars" if r.get("gather_ok") else "gather=FAIL"
        print(f"  {r['doc']:<25s}  {symbol} {r['score']:.0%}  [{len(r.get('topics', []))} topics: {topics_str}]  {gather_str}")

    te_passed = sum(1 for r in results if r["pass"])
    print(f"\n  Topic extraction: {te_passed}/{len(results)} passed ({te_passed/len(results)*100:.0f}%)")


# ═══════════════════════════════════════════════════════════════════════════
# Eval Runner
# ═══════════════════════════════════════════════════════════════════════════

ALL_METRICS = [
    ("json_valid", None),
    ("schema_complete", None),
    ("depth_match", None),
    ("style_match", None),
    ("content_quality", None),
    ("flashcard_quality", None),
]


def run_single_eval(doc: dict, prefs: dict, dry_run: bool = False) -> dict:
    """Run one eval: generate reels + score on all metrics."""
    text = doc["text"]
    doc_type = doc["doc_type"]

    # Generate output
    if dry_run:
        # Use a dummy output for testing metrics locally
        raw = {
            "reels": [{"title": "Test Reel", "summary": "This is a test summary for dry run.", "category": "general", "keywords": "test, dry run"}],
            "flashcards": [{"question": "What is this?", "answer": "This is a dry run test of the eval system."}],
        }
    else:
        raw = generate_reels(text, doc_type, prefs)

    raw_str = json.dumps(raw) if isinstance(raw, dict) else str(raw)

    # Score all metrics
    results = {}

    # 1. JSON validity
    ok, details = metric_json_valid(raw_str)
    results["json_valid"] = {"pass": ok, **details}

    # Parse for remaining metrics
    parsed = raw if isinstance(raw, dict) else {}
    try:
        parsed = json.loads(raw_str) if isinstance(raw_str, str) else raw
    except (json.JSONDecodeError, TypeError):
        parsed = {"reels": [], "flashcards": []}

    # 2. Schema
    ok, details = metric_schema_complete(parsed)
    results["schema_complete"] = {"pass": ok, **details}

    # 3. Depth
    ok, details = metric_depth_match(parsed, prefs)
    results["depth_match"] = {"pass": ok, **details}

    # 4. Style
    ok, details = metric_style_match(parsed, prefs)
    results["style_match"] = {"pass": ok, **details}

    # 5. Content quality
    score, details = metric_content_quality(parsed, text)
    results["content_quality"] = {"score": score, "pass": score >= 0.75, **details}

    # 6. Flashcard quality
    score, details = metric_flashcard_quality(parsed)
    results["flashcard_quality"] = {"score": score, "pass": score >= 0.75, **details}

    return {
        "doc": doc["name"],
        "doc_type": doc_type,
        "prefs": prefs["label"],
        "output": raw,
        "metrics": results,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Scorecard Printer
# ═══════════════════════════════════════════════════════════════════════════

def print_scorecard(all_results: list[dict], title: str = "VERSO PROMPT EVAL"):
    """Print a formatted scorecard from eval results."""
    total_tests = len(all_results)
    metric_names = ["json_valid", "schema_complete", "depth_match", "style_match", "content_quality", "flashcard_quality"]

    print()
    print("=" * 60)
    print(f" {title}")
    print(f" Reel model: {REEL_MODEL}  |  Classification: {CLASSIFICATION_MODEL}")
    print(f" Chat model: {LLM_MODEL}  |  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f" Tests: {total_tests}")
    print("=" * 60)

    # Per-doc results
    current_doc = None
    for r in all_results:
        if r["doc"] != current_doc:
            current_doc = r["doc"]
            print(f"\nDOC: {r['doc']} ({r['doc_type']})")

        m = r["metrics"]
        checks = []
        for name in metric_names[:4]:
            symbol = "+" if m[name]["pass"] else "-"
            checks.append(f"{name[:6]} {symbol}")

        cq = m["content_quality"].get("score", 0)
        fq = m["flashcard_quality"].get("score", 0)
        checks.append(f"content {cq:.0%}")
        checks.append(f"fc {fq:.0%}")

        print(f"  {r['prefs']:<35s}  {' | '.join(checks)}")

    # Summary by metric
    print()
    print("-" * 60)
    print("RESULTS BY METRIC:")
    for name in metric_names:
        passed = sum(1 for r in all_results if r["metrics"][name]["pass"])
        pct = passed / total_tests * 100 if total_tests else 0

        if name in ("content_quality", "flashcard_quality"):
            avg_score = sum(r["metrics"][name].get("score", 0) for r in all_results) / total_tests
            print(f"  {name:<22s}  {passed}/{total_tests}  ({pct:5.1f}%)  [avg: {avg_score:.2f}]")
        else:
            print(f"  {name:<22s}  {passed}/{total_tests}  ({pct:5.1f}%)")

    # Summary by style
    print()
    print("RESULTS BY STYLE:")
    styles = ["visual", "auditory", "reading", "mixed"]
    style_scores = {}
    for style in styles:
        style_results = [r for r in all_results if style in r["prefs"]]
        if style_results:
            score = sum(
                sum(1 for name in metric_names if r["metrics"][name]["pass"])
                for r in style_results
            ) / (len(style_results) * len(metric_names)) * 100
            style_scores[style] = score
    print("  " + "  |  ".join(f"{s}: {v:.0f}%" for s, v in style_scores.items()))

    # Summary by depth
    print()
    print("RESULTS BY DEPTH:")
    depths = ["brief", "balanced", "detailed"]
    depth_scores = {}
    for depth in depths:
        depth_results = [r for r in all_results if depth in r["prefs"]]
        if depth_results:
            score = sum(
                sum(1 for name in metric_names if r["metrics"][name]["pass"])
                for r in depth_results
            ) / (len(depth_results) * len(metric_names)) * 100
            depth_scores[depth] = score
    print("  " + "  |  ".join(f"{d}: {v:.0f}%" for d, v in depth_scores.items()))

    # Overall
    all_passed = sum(
        sum(1 for name in metric_names if r["metrics"][name]["pass"])
        for r in all_results
    )
    all_total = total_tests * len(metric_names)
    overall = all_passed / all_total * 100 if all_total else 0

    print()
    print(f"OVERALL SCORE: {overall:.1f}%")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# Classification Eval
# ═══════════════════════════════════════════════════════════════════════════

def run_classification_eval(dry_run: bool = False) -> list[dict]:
    """Test detect_doc_type() and detect_subject_category() on all test docs."""
    results = []
    for doc in TEST_DOCS:
        name = doc["name"]
        text = doc["text"]
        expected_doc_type = doc["doc_type"]
        expected_subject = doc.get("subject_category", "general")

        if dry_run:
            predicted_doc_type = expected_doc_type
            predicted_subject = expected_subject
        else:
            print(f"  {name}: doc_type...", end=" ", flush=True)
            predicted_doc_type = detect_doc_type(text)
            print(f"{predicted_doc_type}", end="  subject...", flush=True)
            predicted_subject = detect_subject_category(text)
            print(f"{predicted_subject}")

        results.append({
            "doc": name,
            "doc_type_expected": expected_doc_type,
            "doc_type_predicted": predicted_doc_type,
            "doc_type_pass": predicted_doc_type == expected_doc_type,
            "subject_expected": expected_subject,
            "subject_predicted": predicted_subject,
            "subject_pass": predicted_subject == expected_subject,
        })
    return results


def print_classification_scorecard(results: list[dict]):
    """Print classification accuracy results."""
    print()
    print("-" * 60)
    print(f"CLASSIFICATION EVAL ({CLASSIFICATION_MODEL})")
    print("-" * 60)

    doc_type_correct = 0
    subject_correct = 0

    for r in results:
        dt_symbol = "+" if r["doc_type_pass"] else "-"
        sc_symbol = "+" if r["subject_pass"] else "-"
        dt_detail = f"{r['doc_type_predicted']}" if r["doc_type_pass"] else f"{r['doc_type_predicted']} (expected {r['doc_type_expected']})"
        sc_detail = f"{r['subject_predicted']}" if r["subject_pass"] else f"{r['subject_predicted']} (expected {r['subject_expected']})"
        print(f"  {r['doc']:<25s}  doc_type {dt_symbol} {dt_detail:<20s}  subject {sc_symbol} {sc_detail}")
        doc_type_correct += int(r["doc_type_pass"])
        subject_correct += int(r["subject_pass"])

    total = len(results)
    print()
    print(f"  doc_type accuracy:  {doc_type_correct}/{total}  ({doc_type_correct/total*100:.0f}%)")
    print(f"  subject accuracy:   {subject_correct}/{total}  ({subject_correct/total*100:.0f}%)")
    print(f"  overall:            {doc_type_correct + subject_correct}/{total * 2}  ({(doc_type_correct + subject_correct) / (total * 2) * 100:.0f}%)")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("DRY RUN MODE — testing metrics with dummy outputs (no Ollama needed)")
    else:
        print(f"Connecting to Ollama at {OLLAMA_HOST}...")
        print(f"  Reel model: {REEL_MODEL}  |  Classification: {CLASSIFICATION_MODEL}  |  Chat: {LLM_MODEL}")
        if HAS_DSPY:
            try:
                lm = dspy.LM(
                    model=f"ollama_chat/{LLM_MODEL}",
                    api_base=OLLAMA_HOST,
                    api_key="",
                )
                dspy.configure(lm=lm)
                print("DSPy configured with Ollama")
            except Exception as e:
                print(f"DSPy config warning (non-fatal, using direct calls): {e}")
        else:
            print("DSPy not installed — using direct generate_reels() calls")

    classify_only = "--classify" in sys.argv
    quick = "--quick" in sys.argv

    # Run classification eval first (fast — ~3-7s per doc)
    if not classify_only:
        print(f"\n--- Classification Eval ({len(TEST_DOCS)} docs) ---\n")
    else:
        print(f"\nRunning classification eval only ({len(TEST_DOCS)} docs)...\n")
    classify_results = run_classification_eval(dry_run=dry_run)
    print_classification_scorecard(classify_results)

    if classify_only:
        output_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
        save_data = {
            "reel_model": REEL_MODEL,
            "classification_model": CLASSIFICATION_MODEL,
            "chat_model": LLM_MODEL,
            "date": datetime.now().isoformat(),
            "dry_run": dry_run,
            "classification": classify_results,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nResults saved to: {output_path}")
        return

    # ── Topic Extraction Eval (5 docs — always runs) ──────────────────────
    print(f"\n--- Topic Extraction Eval ({len(TEST_DOCS)} docs) ---\n")
    topic_extract_results = []
    for i, doc in enumerate(TEST_DOCS):
        print(f"  [{i+1}/{len(TEST_DOCS)}] {doc['name']}...", end=" ", flush=True)
        try:
            result = run_topic_extraction_eval(doc, dry_run=dry_run)
            symbol = "+" if result["pass"] else "-"
            topics_preview = ", ".join(result.get("topics", [])[:3])
            print(f"{symbol} {result['score']:.0%} [{len(result.get('topics', []))} topics: {topics_preview}]")
            topic_extract_results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            topic_extract_results.append({"doc": doc["name"], "pass": False, "score": 0, "topics": [], "gather_len": 0, "gather_ok": False, "details": {"error": str(e)}})
    print_topic_extraction_scorecard(topic_extract_results)

    # ── Legacy Reel Eval (generate_reels — old chunk-based pipeline) ──────
    if quick:
        pairs = []
        for doc_name, combo_label in QUICK_EVAL_PAIRS:
            doc = next(d for d in TEST_DOCS if d["name"] == doc_name)
            combo = next(c for c in EVAL_COMBOS if c["label"] == combo_label)
            pairs.append((doc, combo))
    else:
        pairs = [(doc, combo) for doc in TEST_DOCS for combo in EVAL_COMBOS]

    total = len(pairs)
    print(f"\n--- Legacy Reel Eval ({total} tests {'- quick' if quick else f'- {len(TEST_DOCS)} docs x {len(EVAL_COMBOS)} combos'}) ---\n")

    all_results = []
    for doc, combo in pairs:
        label = combo["label"]
        print(f"  [{len(all_results)+1}/{total}] {doc['name']} + {label}...", end=" ", flush=True)
        try:
            result = run_single_eval(doc, combo, dry_run=dry_run)
            passed = sum(1 for m in result["metrics"].values() if m.get("pass", False))
            print(f"{passed}/6 passed")
            all_results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            all_results.append({
                "doc": doc["name"],
                "doc_type": doc["doc_type"],
                "prefs": label,
                "output": None,
                "metrics": {n: {"pass": False, "error": str(e)} for n in
                            ["json_valid", "schema_complete", "depth_match",
                             "style_match", "content_quality", "flashcard_quality"]},
            })

    print_scorecard(all_results, title="LEGACY REEL EVAL (generate_reels)")

    # ── Topic Reel Eval (new pipeline: extract_topics → generate_topic_reel) ──
    if quick:
        topic_pairs = []
        for doc_name, combo_label in QUICK_TOPIC_REEL_PAIRS:
            doc = next(d for d in TEST_DOCS if d["name"] == doc_name)
            combo = next(c for c in EVAL_COMBOS if c["label"] == combo_label)
            topic_pairs.append((doc, combo))
    else:
        topic_pairs = [(doc, combo) for doc in TEST_DOCS for combo in EVAL_COMBOS]

    total_topic = len(topic_pairs)
    print(f"\n--- Topic Reel Eval ({total_topic} tests {'- quick' if quick else f'- {len(TEST_DOCS)} docs x {len(EVAL_COMBOS)} combos'}) ---\n")

    # Pre-extract topics per doc to avoid redundant LLM calls in full mode
    doc_topics_cache = {}
    if not dry_run:
        unique_docs = {doc["name"]: doc for doc, _ in topic_pairs}
        for name, doc in unique_docs.items():
            print(f"  Pre-extracting topics for {name}...", end=" ", flush=True)
            try:
                topics = extract_topics(doc["text"], num_topics=3)
                doc_topics_cache[name] = topics
                print(f"{len(topics)} topics")
            except Exception as e:
                print(f"FAILED: {e}")
                doc_topics_cache[name] = []

    topic_reel_results = []
    for doc, combo in topic_pairs:
        label = combo["label"]
        print(f"  [{len(topic_reel_results)+1}/{total_topic}] {doc['name']} + {label}...", end=" ", flush=True)
        try:
            cached_topics = doc_topics_cache.get(doc["name"])
            result = run_topic_reel_eval(doc, combo, topics=cached_topics, dry_run=dry_run)
            passed = sum(1 for m in result["metrics"].values() if m.get("pass", False))
            print(f"{passed}/6 passed")
            topic_reel_results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            topic_reel_results.append({
                "doc": doc["name"],
                "doc_type": doc["doc_type"],
                "prefs": label,
                "output": None,
                "metrics": {n: {"pass": False, "error": str(e)} for n in
                            ["json_valid", "schema_complete", "depth_match",
                             "style_match", "content_quality", "flashcard_quality"]},
            })

    print_scorecard(topic_reel_results, title="TOPIC REEL EVAL (new pipeline)")

    # ── Combined Summary ──────────────────────────────────────────────────
    total_evals = len(all_results) + len(topic_reel_results) + len(topic_extract_results)
    print()
    print("=" * 60)
    print(f" COMBINED SUMMARY")
    print(f" Total eval tests: {total_evals}")
    print("=" * 60)

    te_pass = sum(1 for r in topic_extract_results if r["pass"])
    legacy_pass = sum(sum(1 for m in r["metrics"].values() if m.get("pass", False)) for r in all_results)
    legacy_total = len(all_results) * 6
    topic_pass = sum(sum(1 for m in r["metrics"].values() if m.get("pass", False)) for r in topic_reel_results)
    topic_total = len(topic_reel_results) * 6

    print(f"  Topic Extraction:  {te_pass}/{len(topic_extract_results)} ({te_pass/max(1,len(topic_extract_results))*100:.0f}%)")
    print(f"  Legacy Reels:      {legacy_pass}/{legacy_total} ({legacy_pass/max(1,legacy_total)*100:.0f}%)")
    print(f"  Topic Reels:       {topic_pass}/{topic_total} ({topic_pass/max(1,topic_total)*100:.0f}%)")
    combined_pass = te_pass + legacy_pass + topic_pass
    combined_total = len(topic_extract_results) + legacy_total + topic_total
    print(f"  OVERALL:           {combined_pass}/{combined_total} ({combined_pass/max(1,combined_total)*100:.0f}%)")
    print("=" * 60)

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    save_data = {
        "reel_model": REEL_MODEL,
        "classification_model": CLASSIFICATION_MODEL,
        "chat_model": LLM_MODEL,
        "date": datetime.now().isoformat(),
        "dry_run": dry_run,
        "classification": classify_results,
        "topic_extraction": topic_extract_results,
        "legacy_reel_tests": len(all_results),
        "topic_reel_tests": len(topic_reel_results),
        "total_tests": total_evals,
        "legacy_results": [],
        "topic_results": [],
    }
    for r in all_results:
        save_data["legacy_results"].append({
            "doc": r["doc"], "doc_type": r["doc_type"], "prefs": r["prefs"], "metrics": r["metrics"],
        })
    for r in topic_reel_results:
        save_data["topic_results"].append({
            "doc": r["doc"], "doc_type": r.get("doc_type", ""), "prefs": r.get("prefs", ""), "metrics": r["metrics"],
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
