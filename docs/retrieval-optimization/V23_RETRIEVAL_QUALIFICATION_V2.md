# V2.3 Retrieval Qualification Benchmark V2

```json
{
  "answerableLabelAuditComplete": true,
  "artifactPolicy": "full queries are generated in code but not written to audit artifacts",
  "caseFamilyLeakageCount": 0,
  "datasetLightHash": "ebae944ddd1709128843a142d63e75e51f174d2461e1956ee8ed6f95c905ae18",
  "datasetVersion": "v23-retrieval-qualification-v2",
  "difficultyMaxSpread": 0.0,
  "documentFamilyLeakageCount": 0,
  "intentMaxSpread": 0.006667,
  "manifest": {
    "caseCount": 375,
    "caseFamilySplitMapHash": "46716a5348a3e68ef7ecf507fdfd8ec327b3aa4543f5a79ff9e372f8af9f7288",
    "caseIdsHash": "4b87ec386854010cd308b2a6db46f0dcd83d3aedb95be88acd3ae9328ad464f4",
    "datasetHash": "d638d44c69e1e678c2f990fd193af23d2ac18962b6e2be5eaf1ffd19e4575e47",
    "datasetVersion": "v23-retrieval-qualification-v2",
    "documentFamilySplitMapHash": "6c8227bfcd88414bd32a4358a26d6052a06a3474588bebfa420bdc964851b7c6",
    "queryHashesHash": "ae0386fb84a9dc0e0d42057000c6b60e0443325f78078f4bf021dd6351194e2a",
    "splitDifficultyDistribution": {
      "calibration": {
        "easy": 0.08,
        "hard": 0.413333,
        "medium": 0.506667
      },
      "challenge": {
        "easy": 0.08,
        "hard": 0.413333,
        "medium": 0.506667
      },
      "evaluation": {
        "easy": 0.08,
        "hard": 0.413333,
        "medium": 0.506667
      }
    },
    "splitIntentDistribution": {
      "calibration": {
        "ABBREVIATION": 0.04,
        "COLLOQUIAL_QUERY": 0.04,
        "CONDITIONAL_RULE": 0.04,
        "CONFLICTING_WITHOUT_RESOLUTION": 0.02,
        "ENTITY_MISMATCH": 0.02,
        "ENTITY_RELATION": 0.04,
        "INSUFFICIENT_SPECIFICITY": 0.02,
        "LEXICAL_DECOY": 0.02,
        "LEXICAL_EXACT_MATCH": 0.04,
        "LEXICAL_PARTIAL_MATCH": 0.04,
        "LONG_QUERY": 0.04,
        "LOW_FREQUENCY_TERM": 0.04,
        "MULTIPLE_DISTRACTORS": 0.04,
        "MULTI_CONDITION_QUERY": 0.04,
        "NEAR_DUPLICATE_DISTRACTORS": 0.04,
        "NEGATION": 0.04,
        "OUT_OF_DOMAIN": 0.02,
        "PARENT_CONTEXT_REQUIRED": 0.04,
        "RELATION_MISMATCH": 0.02,
        "SCOPE_CONDITION": 0.04,
        "SCOPE_MISMATCH": 0.02,
        "SECTION_DEPENDENT": 0.04,
        "SEMANTIC_NEAR_MISS": 0.02,
        "SEMANTIC_PARAPHRASE": 0.04,
        "SHORT_QUERY": 0.04,
        "TEMPORAL_CONDITION": 0.04,
        "TEMPORAL_MISMATCH": 0.02,
        "TITLE_DEPENDENT": 0.04,
        "TYPO_OR_VARIANT": 0.04,
        "UNSUPPORTED_COMPOSITE_QUERY": 0.02
      },
      "challenge": {
        "ABBREVIATION": 0.04,
        "COLLOQUIAL_QUERY": 0.04,
        "CONDITIONAL_RULE": 0.04,
        "CONFLICTING_WITHOUT_RESOLUTION": 0.013333,
        "ENTITY_MISMATCH": 0.026667,
        "ENTITY_RELATION": 0.04,
        "INSUFFICIENT_SPECIFICITY": 0.013333,
        "LEXICAL_DECOY": 0.013333,
        "LEXICAL_EXACT_MATCH": 0.04,
        "LEXICAL_PARTIAL_MATCH": 0.04,
        "LONG_QUERY": 0.04,
        "LOW_FREQUENCY_TERM": 0.04,
        "MULTIPLE_DISTRACTORS": 0.04,
        "MULTI_CONDITION_QUERY": 0.04,
        "NEAR_DUPLICATE_DISTRACTORS": 0.04,
        "NEGATION": 0.04,
        "OUT_OF_DOMAIN": 0.026667,
        "PARENT_CONTEXT_REQUIRED": 0.04,
        "RELATION_MISMATCH": 0.026667,
        "SCOPE_CONDITION": 0.04,
        "SCOPE_MISMATCH": 0.013333,
        "SECTION_DEPENDENT": 0.04,
        "SEMANTIC_NEAR_MISS": 0.026667,
        "SEMANTIC_PARAPHRASE": 0.04,
        "SHORT_QUERY": 0.04,
        "TEMPORAL_CONDITION": 0.04,
        "TEMPORAL_MISMATCH": 0.026667,
        "TITLE_DEPENDENT": 0.04,
        "TYPO_OR_VARIANT": 0.04,
        "UNSUPPORTED_COMPOSITE_QUERY": 0.013333
      },
      "evaluation": {
        "ABBREVIATION": 0.04,
        "COLLOQUIAL_QUERY": 0.04,
        "CONDITIONAL_RULE": 0.04,
        "CONFLICTING_WITHOUT_RESOLUTION": 0.02,
        "ENTITY_MISMATCH": 0.02,
        "ENTITY_RELATION": 0.04,
        "INSUFFICIENT_SPECIFICITY": 0.02,
        "LEXICAL_DECOY": 0.02,
        "LEXICAL_EXACT_MATCH": 0.04,
        "LEXICAL_PARTIAL_MATCH": 0.04,
        "LONG_QUERY": 0.04,
        "LOW_FREQUENCY_TERM": 0.04,
        "MULTIPLE_DISTRACTORS": 0.04,
        "MULTI_CONDITION_QUERY": 0.04,
        "NEAR_DUPLICATE_DISTRACTORS": 0.04,
        "NEGATION": 0.04,
        "OUT_OF_DOMAIN": 0.02,
        "PARENT_CONTEXT_REQUIRED": 0.04,
        "RELATION_MISMATCH": 0.02,
        "SCOPE_CONDITION": 0.04,
        "SCOPE_MISMATCH": 0.02,
        "SECTION_DEPENDENT": 0.04,
        "SEMANTIC_NEAR_MISS": 0.02,
        "SEMANTIC_PARAPHRASE": 0.04,
        "SHORT_QUERY": 0.04,
        "TEMPORAL_CONDITION": 0.04,
        "TEMPORAL_MISMATCH": 0.02,
        "TITLE_DEPENDENT": 0.04,
        "TYPO_OR_VARIANT": 0.04,
        "UNSUPPORTED_COMPOSITE_QUERY": 0.02
      }
    },
    "splitLabelCounts": {
      "calibration": {
        "answerable": 120,
        "no_answer": 30
      },
      "challenge": {
        "answerable": 60,
        "no_answer": 15
      },
      "evaluation": {
        "answerable": 120,
        "no_answer": 30
      }
    }
  },
  "noAnswerCorpusAuditComplete": true,
  "oldCaseCount": 300,
  "oldCaseIdIntersectionCount": 0,
  "oldQueryHashIntersectionCount": 0,
  "schemaVersion": "agent-rag-v23-retrieval-dataset-v2-audit-v1"
}
```
