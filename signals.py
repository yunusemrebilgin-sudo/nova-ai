def normalize_decision_label(label: str) -> str:
    if label in {"AL", "TAKİP ET", "BEKLE", "SAT"}:
        return label
    return "BEKLE"
