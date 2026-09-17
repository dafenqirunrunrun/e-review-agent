from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai-service" / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from qualification.run_v23_sparse_empty_vector_rca import canonicalize, convert_tokens, filter_special, parse_raw_sparse, raw_stage, tokenizer_stage, vector_hash  # noqa: E402


class FakeTokenizer:
    pad_token_id = 1
    cls_token_id = 0
    sep_token_id = 2
    bos_token_id = 0
    eos_token_id = 2
    mask_token_id = 3


def test_raw_flagembedding_dict_schema_and_string_token_parsing():
    parsed = parse_raw_sparse({"refund": 0.25, "12": "0.5"})
    assert parsed["stage"]["errorCode"] == "OUTPUT_SCHEMA_PARSE_PASS"
    converted = convert_tokens(parsed["weights"])
    assert converted["stage"]["afterConversionCount"] == 2


def test_integer_token_id_parsing_and_special_token_filtering():
    converted = convert_tokens({0: 1.0, 42: 0.5})
    filtered = filter_special(converted["weights"], FakeTokenizer())
    assert filtered["stage"]["specialTokenRemovedCount"] == 1
    assert filtered["stage"]["afterSpecialFilterCount"] == 1


def test_zero_threshold_and_canonical_vector_hash_are_stable():
    vector = canonicalize({2: 0.1, 1: 0.2})
    assert list(vector) == [1, 2]
    assert vector_hash(vector) == vector_hash(dict(reversed(list(vector.items()))))


def test_empty_and_short_tokenizer_classification():
    empty = tokenizer_stage({"input_ids": [], "attention_mask": []}, FakeTokenizer())
    assert empty["errorCode"] == "TOKENIZER_OUTPUT_EMPTY"
    special = tokenizer_stage({"input_ids": [0, 2], "attention_mask": [1, 1]}, FakeTokenizer())
    assert special["errorCode"] == "TOKENIZER_SPECIAL_ONLY"
    valid = tokenizer_stage({"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1]}, FakeTokenizer())
    assert valid["errorCode"] == "TOKENIZER_VALID"


def test_raw_empty_model_output_is_distinguished_from_parse_loss():
    stage = raw_stage({})
    assert stage["errorCode"] == "MODEL_RAW_SPARSE_EMPTY"
    unsupported = parse_raw_sparse([["token", 1.0]])
    assert unsupported["stage"]["errorCode"] == "OUTPUT_SCHEMA_UNSUPPORTED"
