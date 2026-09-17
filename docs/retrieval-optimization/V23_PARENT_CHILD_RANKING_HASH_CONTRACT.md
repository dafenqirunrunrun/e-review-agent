# V2.3 Parent-Child Ranking Hash Contract

QC2 uses canonical UTF-8 JSON, `sort_keys=true`, compact separators and SHA-256.

Ranked ID hashes preserve rank order. Set ID hashes sort unique IDs. Raw scores are excluded from candidate ID hashes so tiny floating-point noise cannot hide or create candidate drift. Full queries, chunks, parents and prompts are not stored.
