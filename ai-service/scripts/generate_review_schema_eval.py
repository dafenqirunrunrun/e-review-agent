import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "eval" / "review_schema_eval.jsonl"


SCENARIOS = [
    {
        "name": "positive",
        "texts": [
            "商品质量很好，外观漂亮，使用舒适，值得推荐。",
            "包装完好，体验不错，很满意这次购买。",
            "做工漂亮，使用方便，整体质量不错。",
            "到货很快，商品很好，家人也很喜欢。",
            "质量稳定，佩戴舒适，推荐购买。",
        ],
        "rating": 5,
        "image_signal": "https://example.com/eval-positive.jpg",
        "risk": "normal_review",
        "level": "low",
        "human": False,
        "keywords": ["好", "质量", "漂亮", "满意", "推荐"],
    },
    {
        "name": "neutral",
        "texts": [
            "外观不错，但是续航一般，暂时继续观察。",
            "质量还可以，功能一般，没有特别惊喜。",
            "包装不错，使用感受一般，符合基本预期。",
            "样式漂亮，但是操作有点慢，总体中性。",
            "做工不错，不过续航短，体验一般。",
        ],
        "rating": 3,
        "image_signal": "https://example.com/eval-neutral.jpg",
        "risk": "normal_review",
        "level": "low",
        "human": False,
        "keywords": ["不错", "一般", "慢", "短"],
    },
    {
        "name": "negative",
        "texts": [
            "体验很差，操作难用，完全失望。",
            "商品有异味，做工差，使用体验很坏。",
            "运行很慢，续航短，整体令人失望。",
            "质量一般，操作难用，不会再次购买。",
            "表面指纹很多，反应慢，体验很差。",
        ],
        "rating": 1,
        "image_signal": "",
        "risk": "negative_review",
        "level": "medium",
        "human": True,
        "keywords": ["差", "难用", "失望", "异味", "慢", "短", "指纹"],
    },
    {
        "name": "after_sales",
        "texts": [
            "收到后外壳破损，希望尽快售后处理。",
            "商品疑似假货，已经申请退款。",
            "使用时出现安全问题，要求退货。",
            "设备突然爆炸，已经联系售后。",
            "使用后严重过敏，准备投诉并退款。",
        ],
        "rating": 1,
        "image_signal": "https://example.com/eval-risk.jpg",
        "risk": "after_sales_risk",
        "level": "high",
        "human": True,
        "keywords": ["破损", "售后", "假货", "退款", "安全", "退货", "爆炸", "过敏", "投诉"],
    },
    {
        "name": "mixed_evidence",
        "texts": [
            "音质不错，但是续航短，整体体验一般。",
            "外观漂亮，不过反应慢，先继续使用。",
            "包装很好，但是表面容易留下指纹。",
            "佩戴舒适，不过功能一般，需要观察。",
            "质量不错，但是有一点异味，暂时观望。",
        ],
        "rating": 3,
        "image_signal": "invalid-local-image",
        "risk": "normal_review",
        "level": "low",
        "human": False,
        "keywords": ["不错", "短", "一般", "漂亮", "慢", "好", "指纹", "舒适", "异味"],
    },
]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    index = 1
    for scenario in SCENARIOS:
        for repeat in range(4):
            for text in scenario["texts"]:
                rows.append({
                    "case_id": f"SCHEMA-{index:03d}",
                    "comment_text": text,
                    "image_signal": scenario["image_signal"],
                    "rating": scenario["rating"],
                    "expected_risk_type": scenario["risk"],
                    "expected_risk_level": scenario["level"],
                    "expected_need_human_review": scenario["human"],
                    "expected_evidence_keywords": scenario["keywords"],
                    "scenario": scenario["name"],
                })
                index += 1
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"GENERATED={len(rows)} PATH={OUTPUT}")


if __name__ == "__main__":
    main()
