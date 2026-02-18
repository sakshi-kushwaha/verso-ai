import os
import random
import logging

log = logging.getLogger(__name__)

BG_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "static", "bg-images")

# Maps common reel category keywords to the 11 image folder slugs
CATEGORY_MAP = {
    # science
    "biology": "science", "chemistry": "science", "physics": "science",
    "environmental": "science", "ecology": "science", "genetics": "science",
    "botany": "science", "zoology": "science", "astronomy": "science",
    "geology": "science", "science": "science",
    # math
    "mathematics": "math", "math": "math", "statistics": "math",
    "calculus": "math", "algebra": "math", "geometry": "math",
    "probability": "math", "trigonometry": "math",
    # history
    "history": "history", "political": "history", "sociology": "history",
    "anthropology": "history", "archaeology": "history", "geography": "history",
    # literature
    "literature": "literature", "fiction": "literature", "poetry": "literature",
    "philosophy": "literature", "language": "literature", "linguistics": "literature",
    "writing": "literature", "english": "literature",
    # business
    "business": "business", "finance": "business", "economics": "business",
    "marketing": "business", "management": "business", "accounting": "business",
    "entrepreneurship": "business",
    # technology
    "technology": "technology", "computer": "technology", "programming": "technology",
    "software": "technology", "ai": "technology", "data": "technology",
    "machine learning": "technology", "cybersecurity": "technology",
    # medicine
    "medicine": "medicine", "health": "medicine", "anatomy": "medicine",
    "psychology": "medicine", "pharmacology": "medicine", "nursing": "medicine",
    "neuroscience": "medicine", "medical": "medicine",
    # law
    "law": "law", "legal": "law", "criminal": "law", "constitutional": "law",
    "justice": "law",
    # arts
    "arts": "arts", "art": "arts", "music": "arts", "design": "arts",
    "architecture": "arts", "film": "arts", "theater": "arts", "photography": "arts",
    # engineering
    "engineering": "engineering", "mechanical": "engineering",
    "electrical": "engineering", "civil": "engineering", "chemical": "engineering",
    "aerospace": "engineering",
}


def _resolve_category(reel_category: str, upload_category: str) -> str:
    """Resolve a reel's category keyword to one of the 11 image folder slugs."""
    if reel_category:
        key = reel_category.strip().lower()
        # Direct match
        if key in CATEGORY_MAP:
            return CATEGORY_MAP[key]
        # Substring match
        for keyword, slug in CATEGORY_MAP.items():
            if keyword in key:
                return slug
    # Fall back to the upload-level subject category
    if upload_category in {"science", "math", "history", "literature", "business",
                           "technology", "medicine", "law", "arts", "engineering"}:
        return upload_category
    return "general"


def _list_images(category: str) -> list:
    """List available image files for a category folder."""
    folder = os.path.join(BG_IMAGES_DIR, category)
    if not os.path.isdir(folder):
        folder = os.path.join(BG_IMAGES_DIR, "general")
    if not os.path.isdir(folder):
        return []
    return [
        f for f in os.listdir(folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]


def assign_images(reels: list, upload_category: str) -> list:
    """Assign background image paths to a list of reels.

    Returns a list of relative paths (e.g. 'bg-images/science/01.jpg') or None.
    Avoids consecutive reels getting the same image.
    """
    results = []
    prev_image = None

    for reel in reels:
        cat = _resolve_category(reel.get("category", ""), upload_category)
        images = _list_images(cat)

        if not images:
            results.append(None)
            prev_image = None
            continue

        # Avoid same image as previous reel
        candidates = [img for img in images if img != prev_image] or images
        chosen = random.choice(candidates)
        prev_image = chosen
        results.append(f"bg-images/{cat}/{chosen}")

    return results
