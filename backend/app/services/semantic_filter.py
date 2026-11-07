import re

GLOBAL_REJECT_TERMS = [
    "illustration",
    "illustrated",
    "document",
    "diagram",
    "chart",
    "graph",
    "map",
    "blueprint",
    "drawing",
    "sketch",
    "painting",
    "watercolor",
    "cartoon",
    "logo",
    "icon",
    "infographic",
    "screenshot",
    "manuscript",
    "vector",
]

CATEGORY_OBJECT_RULES = {
    "sofa": {
        "label": "sofa/couch",
        "accept": [
            "sofa",
            "sofas",
            "couch",
            "couches",
            "settee",
            "loveseat",
            "love seat",
            "chesterfield",
            "divan",
            "sectional",
            "daybed",
            "futon",
        ],
    },
    "chair": {
        "label": "chair",
        "accept": [
            "chair",
            "chairs",
            "armchair",
            "lounge chair",
            "recliner",
            "chaise",
            "chaise lounge",
            "stool",
            "rocking chair",
            "dining chair",
            "bar chair",
            "accent chair",
        ],
    },
    "table": {
        "label": "table",
        "accept": [
            "table",
            "tables",
            "coffee table",
            "dining table",
            "side table",
            "console table",
            "desk",
            "nightstand",
            "end table",
            "desk table",
        ],
    },
    "lighting": {
        "label": "lighting",
        "accept": [],
        "subtypes": [
            ("floor", ["floor lamp", "standing lamp", "floorlamp", "floor light", "torchiere", "floor-standing lamp", "lamp floor"]),
            ("pendant", ["pendant", "pendant lamp", "pendant light", "hanging lamp", "hanging light", "drop light"]),
            ("ceiling", ["ceiling lamp", "ceiling light", "chandelier", "flush mount", "semi-flush"]),
            ("wall", ["wall lamp", "wall light", "sconce", "wall sconce"]),
            ("desk", ["desk lamp", "task lamp", "reading lamp"]),
            ("table", ["table lamp", "bedside lamp", "nightstand lamp"]),
        ],
        "default_accept": ["lamp", "lamps", "light", "lighting", "chandelier", "sconce", "lantern", "lamp shade", "lamp"],
    },
    "rug": {
        "label": "rug/carpet",
        "accept": [
            "rug",
            "rugs",
            "carpet",
            "carpets",
            "mat",
            "runner",
            "kilim",
            "area rug",
        ],
    },
    "wall decor": {
        "label": "wall decor",
        "accept": [
            "wall art",
            "wall decor",
            "mirror",
            "poster",
            "print",
            "painting",
            "canvas",
            "art print",
            "wall hanging",
            "tapestry",
        ],
    },
    "storage": {
        "label": "storage",
        "accept": [
            "bookshelf",
            "bookcase",
            "cabinet",
            "wardrobe",
            "shelf",
            "shelving",
            "sideboard",
            "drawer",
            "storage",
            "cupboard",
        ],
    },
    "accessories": {
        "label": "accessories",
        "accept": [
            "cushion",
            "pillow",
            "tray",
            "vase",
            "basket",
            "decor",
            "candle",
            "clock",
            "accessory",
        ],
    },
    "plant decor": {
        "label": "plant decor",
        "accept": [
            "plant",
            "plants",
            "planter",
            "potted plant",
            "potted",
            "floral",
            "flower",
        ],
    },
    "bedding": {
        "label": "bedding",
        "accept": [
            "bedding",
            "linen",
            "duvet",
            "comforter",
            "pillow",
            "sheet",
            "blanket",
            "quilt",
            "bed set",
            "bed linen",
        ],
    },
}


def _has_term(text: str, term: str) -> bool:
    if not term:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def derive_object_rule(product) -> dict:
    category = (product.category.name if product.category else "").strip().lower()
    rule = CATEGORY_OBJECT_RULES.get(category)
    if rule is None:
        return {"label": category or "product", "accept": [], "reject": list(GLOBAL_REJECT_TERMS)}

    accept = list(rule.get("accept") or [])
    label = rule.get("label") or category

    if "subtypes" in rule:
        name = (product.name or "").lower()
        for keyword, terms in rule["subtypes"]:
            if keyword in name:
                accept = list(terms)
                label = keyword
                break
        else:
            accept = list(rule.get("default_accept") or accept)

    return {"label": label, "accept": accept, "reject": list(GLOBAL_REJECT_TERMS)}


def semantic_assess(candidate: dict, rule: dict) -> dict:
    text = " ".join([candidate.get("title") or "", " ".join(candidate.get("tags") or [])]).lower()
    label = rule.get("label") or "product"

    for term in rule.get("reject") or []:
        if _has_term(text, term):
            return {"semantic_decision": "REJECT", "semantic_score": 0, "semantic_reason": f"mismatch term: {term}"}

    accept = rule.get("accept") or []
    matched = next((term for term in accept if _has_term(text, term)), None)
    if matched is None:
        return {"semantic_decision": "REJECT", "semantic_score": 0, "semantic_reason": f"no {label} term"}

    score = 20 if matched == accept[0] else 12
    return {"semantic_decision": "ACCEPT", "semantic_score": score, "semantic_reason": f"matched: {matched}"}
