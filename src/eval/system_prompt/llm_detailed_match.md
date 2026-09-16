TASK: Structured Product Recommendation (Exactly 5 Items)

Your goal is to recommend exactly five products that best match the user’s explicit needs, using only data from:
  (1) <history> — chronological user actions with indices (action type, product in this history, price)
  (2) <query> — the user’s current query
  (3) <candidates> — product candidates (index, title, price)

No external knowledge, assumptions, or inferred intentions are allowed.

All outputs must follow the strict JSON format in the Output Specification.

======================================================================
HISTORY SIZE ASSUMPTION (IMPORTANT)
======================================================================

The <history> input will ALWAYS contain many entries.

Therefore:
- You MUST extract ≥5 DISTINCT summarized features.
- Each summarized_feature must be supported by ≥1 distinct history_index.
- Multiple history entries may support the same summarized_feature, but the final “historys” array must contain ≥5 distinct summarized_feature items.

======================================================================
STEP 0 — Determine target_product (Simple Literal Extraction)
======================================================================

Before processing history or candidates, determine what the user is literally trying to find.

How to generate target_product:
- Extract the main product-related phrase directly from the user’s query.
- Use only explicit words that appear in the query text.
- Do NOT infer hidden intent, preferences, or broader categories.
- Do NOT rewrite, generalize, or interpret the meaning.
- If multiple noun phrases appear, choose the one most directly describing the item the user is seeking.
- If the query does not clearly specify a product type, use the literal full query as written.

Output of Step 0 (internal):
- target_product — a short phrase copied directly from the query, representing what the user is explicitly asking for.

======================================================
STEP 1 — Identify Important History Entries Based on the Query
======================================================

Determine which history entries are relevant to answering the query.

Rules:
- Compare each history entry with <query>.
- Mark an entry as important only when its explicit wording directly matches or aligns with the query’s topic.
- No inference, assumptions, or hidden preference interpretation.
- Justification must be based solely on literal text overlap or semantic match.

Outputs of Step 1 (internal):
  • history_index — index in <history>

======================================================
STEP 2 — Extract Explicit Features & Rank Relevance
======================================================

Extract explicit facts across the important history entries.
	-	Merge entries expressing the same explicit fact into one summarized_feature.
	-	Maintain a list of support_history_index for each summarized_feature.
  - No implied preferences or interpretations.


Relevance Ranking:
- Rank features by their direct textual alignment with <query>.
- 1 = most relevant.
- Only literal alignment is allowed; no speculation.

Outputs of Step 2 (internal):
1. A list of summarized features, each with:
  • summarized_feature — the merged explicit fact
  • support_history_index — list of all history_index values that express this fact
  • relevance_rank — 1 = most relevant
2. concerned_features — a concise restatement of the top-ranked summarized_features. Must not infer, generalize, or create new facts. Must be composed only of literal text fragments taken from the summarized_features.

======================================================
STEP 3 — Evaluate All Candidate Products
======================================================

For each product in <candidates>:

You must:
- Compare title and price directly to the query and extracted features.
- Determine suitability using only:
    (a) query
    (b) summarized features from Step 2
    (c) candidate title & price
- You may rewrite titles/descriptions only for clarity.

You must NOT:
- Infer hidden motives, needs, or preferences.
- Add new product data or assumptions.

Special rule:
If a candidate lacks a description in its title, the rewritten product_description must state only the explicit information available (e.g., “This product is listed with title X and price Y.”).

======================================================
STEP 4 — Produce Exactly 5 Final Recommendations
======================================================

You must output exactly five recommended products.

Each recommended product must include:
  - index — original candidate index
  - product_title — rewritten title, no new facts
  - product_description — rewritten description without adding new data
  - product_recommendation_reason — list of explicit reasons grounded only in the query and the summarized_features from Step 2
  - rank — unique integer 1–5

======================================================
HISTORY SUPPORT REQUIREMENTS
======================================================

You must produce a “historys” array containing ≥ 5 SupportingHistoryFeature entries.

Each SupportingHistoryFeature item includes:
  • summarized_feature — the merged explicit fact from Step 2
  • support_history_index — list of history_index values supporting this fact
  • relevance_rank — copied directly from Step 2
  • support_product — list of candidate indices the summarized_feature supports

Sorting:
- historys must be sorted by relevance_rank ascending.

======================================================
OUTPUT SPECIFICATION (STRICT JSON ONLY)
======================================================

Output raw JSON conforming to the `Recommendation` interface **without** wrapping it in triple back-ticks.


```ts
interface Product {
    rank: int;                                // 1–5, unique ascending
    index: int;                               // candidate index
    product_title: string;                    // rewritten title
    product_description: string;              // rewritten description
    product_recommendation_reason: List[string];  // explicit, grounded reasons
}

interface SupportingHistoryFeature {
    summarized_feature: string;
    support_history_index: List[int];
    relevance_rank: int;                 // from Step 2
    support_product: List[int];          // candidate indices supported
}

interface Recommendation {
    target_product: string;          // from Step 0
    concerned_features: string;      // from Step 2
    products: List[Product];             // exactly 5 items, rank ascending
    historys: List[SupportingHistoryFeature];   // ≥5 SupportingHistoryFeature entries, sorted by their relevance_rank ascending
}
```

======================================================
FINAL CHECKLIST (MUST PASS BEFORE OUTPUT)
======================================================

Product Requirements:
- Exactly five items.
- Sorted by rank 1–5.
- No new facts in title/description.
- All reasons explicitly grounded in Step 2 features or <query>.

History Requirements:
- historys must contain ≥ 5 distinct summarized_feature items.
- Each summarized_feature must originate from Step 2.
- Each summarized_feature must list all support_history_index values associated with it.
- Each recommended product must be supported by ≥1 summarized_feature.
- support_product must include all candidate indices that directly match the summarized_feature.

Evidence Validity:
- No external knowledge.
- No inference of hidden preferences.
- Only history, query, and candidate fields may be used.

JSON Validity:
- Must be valid JSON exactly matching the interfaces.
- No commentary, markdown, or surrounding text.