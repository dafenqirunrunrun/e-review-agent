import json
from pathlib import Path

from scripts.build_realworld_split import load_jsonl, main as split_main
from scripts.ingest_public_review_dataset import rows_from_source


def test_banglishrev_streaming_ingest_redacts_and_hashes(tmp_path):
    source = tmp_path / "reviews v1.json"
    source.write_text(json.dumps([
        {
            "Product ID": "P-1",
            "Product Name": "Perfume",
            "Category": "beauty",
            "Reviews": [
                {
                    "Buyer ID": "1797097",
                    "Current Rating": 1,
                    "Review Content": "broken bottle phone 13800138000 order 123456789",
                    "Images": ["Review Images 1/a.jpg"],
                }
            ],
        }
    ], ensure_ascii=False), encoding="utf-8")
    rows = rows_from_source(source, 10, "test_source")
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "test_source"
    assert row["original_record_id_hash"]
    assert "1797097" not in json.dumps(row, ensure_ascii=False)
    assert "[PHONE]" in row["review_text"]
    assert row["image_available"] is True
    assert row["privacy_status"] == "text_redacted_image_not_downloaded"


def test_realworld_split_blocks_when_not_enough_rows(tmp_path, monkeypatch, capsys):
    source = tmp_path / "small.jsonl"
    source.write_text(json.dumps({"sample_id": "1", "review_text": "ok"}) + "\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["build_realworld_split.py", "--input", str(source), "--dev-size", "2", "--test-size", "1"])
    assert split_main() == 0
    captured = capsys.readouterr().out
    assert "REALWORLD_SPLIT_BLOCKED" in captured
    assert load_jsonl(source)[0]["sample_id"] == "1"
