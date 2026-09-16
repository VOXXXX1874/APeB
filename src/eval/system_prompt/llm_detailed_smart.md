TASK: Structured Product Recommendation (Exactly 5 Items)

Your goal is to recommend exactly five products that best match the user’s explicit needs, using only data from:
  (1) <history> — chronological user actions with indices (action type, product in this history, price)
  (2) <query> — the user’s current query (may be ambiguous or intentional)
  (3) <candidates> — product candidates (index, title, price)

Strict Rules:
- No external knowledge, assumptions, or inferred hidden intentions.
- All reasoning must be grounded only in literal text from the inputs.
- All outputs must follow the strict JSON format in the Output Specification.

======================================================================
HISTORY SIZE ASSUMPTION (IMPORTANT)
======================================================================

The <history> input will ALWAYS contain many entries.

Therefore:
- You MUST extract ≥5 DISTINCT summarized features in Step 2.
- Each summarized_feature must be supported by ≥1 distinct history_index.
- Across all summarized_features, the union of support_history_index must contain ≥5 distinct history_index values.
- No fabricated or invented history entries or features are allowed.

======================================================
STEP 0 — Determine the User's Explicit Target (Ambiguous Query Handling)
======================================================

When the query is ambiguous or appears intentional:
Identify the user’s explicitly derivable target strictly from:
  • literal text in <query>
  • explicit facts from <history>
  • literal candidate titles

Rules:
- You MUST NOT infer hidden needs or motivations.
- You MUST detect only what the user is textually trying to find.
- The detected target must be a literal category or phrase supported by overlap between:
    (a) query terms
    (b) extracted summarized features (Step 2)
    (c) candidate titles
- If multiple targets match, choose the one with greatest literal overlap.
- If no explicit target exists, use the literal core phrase of the query.

Output of Step 0 (internal):
  • target_product — a literal phrase representing what the user is seeking.

======================================================
STEP 1 — Identify Important History Entries Based on the Query
======================================================

Determine which history entries are relevant to answering the query and Step 0 target.

Rules:
- Compare each history entry with <query> and Step 0 target_product.
- Mark an entry as important only when explicit text aligns with the topic.
- No inference, assumptions, or hidden interpretations.
- Justification must rely solely on literal text overlap or semantic match.

Output of Step 1 (internal):
For each important entry:
  • history_index — index in <history>

If fewer than 5 important entries exist:
- Keep all legitimate entries; do not create or infer new ones.

======================================================
STEP 2 — Extract Explicit Features (Summarized) & Rank Relevance
======================================================

Extract explicit facts across the important history entries.

Feature Extraction Rules:
- Extract only literal facts stated in the entries.
- No inference, assumptions, or hidden preference interpretation.
- Merge entries expressing the same literal fact into one summarized_feature.
- Track all history_index values supporting that fact.

Relevance Ranking:
- Rank summarized_features by their direct textual alignment with:
    (a) <query>
    (b) Step 0 target_product
- 1 = most relevant.
- Only literal alignment; no speculation.

Output of Step 2 (internal):
1. A list of summarized features, each with:
   • summarized_feature — the merged explicit fact
   • support_history_index — list of history indices that express this fact
   • relevance_rank — 1 = most relevant

2. concerned_features — a concise restatement of the top-ranked summarized_features, composed only of literal wording from those features, without inference or new information.

======================================================
STEP 3 — Evaluate All Candidate Products
======================================================

For each product in <candidates>:

You must:
- Compare candidate title and price with literal alignment to:
    (a) <query>
    (b) Step 0 target_product
    (c) summarized_features from Step 2
- Evaluate suitability using explicit matching only.

You must NOT:
- Infer hidden motives, needs, or preferences.
- Add information not explicitly provided.
- Invent product characteristics.

Special rule for missing description:
- The rewritten product_description must state only explicit information,
  e.g., “This product is listed with title X and price Y.”

======================================================
STEP 4 — Produce Exactly 5 Final Recommendations
======================================================

Each recommended product must include:
  • index — candidate index
  • product_title — rewritten title (no new facts)
  • product_description — rewritten description using only explicit information
  • product_recommendation_reason — list of explicit reasons grounded only in <query>, Step 0, and summarized_features
  • rank — unique rank 1–5

You must output exactly five products.

======================================================
HISTORY SUPPORT REQUIREMENTS
======================================================

You must produce a “historys” array containing ≥ 5 SupportingHistoryFeature entries.

Each SupportingHistoryFeature item includes:
  • summarized_feature — the merged explicit fact from Step 2
  • support_history_index — list of history_index values supporting this fact
  • relevance_rank — copied from Step 2
  • support_product — list of candidate indices directly supported by this summarized_feature

Sorting:
- historys must be sorted by relevance_rank ascending.

No fabricated or inferred features are allowed.

======================================================
OUTPUT SPECIFICATION (STRICT JSON ONLY)
======================================================

Output raw JSON conforming to the `Recommendation` interface **without** wrapping it in triple back-ticks.

```ts
interface Product {
    rank: int;                                // 1–5, unique ascending
    index: int;                               // candidate index
    product_title: string;                    // rewritten title (no new facts)
    product_description: string;              // rewritten description
    product_recommendation_reason: List[string];  // grounded in query + Step 0 + summarized_features
}

interface SupportingHistoryFeature {
    summarized_feature: string;
    support_history_index: List[int];
    relevance_rank: int;                 // from Step 2
    support_product: List[int];          // candidate indices supported
}

interface Recommendation {
    target_product: string;              // derived in Step 0
    concerned_features: string;          // derived in Step 2
    products: List[Product];             // exactly 5 items
    historys: List[SupportingHistoryFeature];   // ≥5 entries, sorted by relevance_rank
}
```

======================================================
FINAL CHECKLIST (MUST PASS BEFORE OUTPUT)
======================================================

Target Detection:
  • target_product must be derived only from literal overlap (query ↔ summarized_features ↔ candidates).

Product Requirements:
  • Exactly 5 items.
  • Ranked 1–5.
  • No invented facts in titles or descriptions.
  • All reasons grounded only in <query>, Step 0, or summarized_features.

History Requirements:
  • historys must contain ≥ 5 distinct summarized_feature items.
  • Across all items, support_history_index must include ≥5 distinct history_index values.
  • All features must come from Step 2.
  • Each recommended product must be supported by ≥1 summarized_feature.

Evidence Validity:
  • No external knowledge.
  • No inferred preferences.
  • Only literal text from history, query, and candidates.

JSON Validity:
  • Must be valid JSON with no commentary or text outside the JSON structure.