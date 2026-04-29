import json
from sklearn.preprocessing import MultiLabelBinarizer

def load_label_names(label_map_path: str) -> list[str]:
    """Load ordered label names from label_map.json."""
    with open(label_map_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [next(iter(entry)) for entry in raw]

def build_mlb(label_names: list[str]) -> MultiLabelBinarizer:
    """Build a MultiLabelBinarizer with fixed label order."""
    mlb = MultiLabelBinarizer(classes=label_names)
    mlb.fit([label_names])
    return mlb
