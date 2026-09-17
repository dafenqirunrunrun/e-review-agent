import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "private_research" / "audit" / "private_research_gate_status.json"


def main():
    import sys

    sys.path.insert(0, str(ROOT / "ai-service"))
    from app.data_governance.research_scope_gate import private_research_status

    status = private_research_status()
    status["marker"] = "V162_PRIVATE_RESEARCH_GATE_PASS" if status["V162_PRIVATE_RESEARCH_GATE_PASS"] else "V162_PRIVATE_RESEARCH_GATE_BLOCKED"
    status["formal_benchmark"] = False
    status["publication_ready"] = False
    status["private_exploratory"] = True
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(status["marker"])


if __name__ == "__main__":
    main()
