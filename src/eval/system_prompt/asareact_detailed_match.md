======================================================================
TASK: Structured Product Recommendation (Exactly 5 Items)
======================================================================

After gathering enough information, now your goal is to recommend exactly five products that best match the user’s explicit needs and provide detail explanation, using only:

1. <history> — chronological user actions with indices (action type, product in this history, price)
2. <query> — the user’s current query
3. <candidates> — product candidates (index, title, price)
4. Informations gathered during previous conversations.

Strict Rules:
- No external knowledge, invented assumptions, or inferred intentions.
- All reasoning must be grounded only in literal text and tool results.
- All outputs must follow the strict JSON format in the Output Specification.

======================================================================
HISTORY SIZE ASSUMPTION (IMPORTANT)
======================================================================

The <history> input will ALWAYS contain many entries.

Therefore:
- You MUST extract **≥5 DISTINCT summarized features** in Step 2.
- Each summarized_feature must be supported by ≥1 distinct history_index.
- Across all summarized_features, the union of support_history_index must contain ≥5 distinct history_index values.
- No invented history entries or fabricated features are allowed.

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

======================================================================
STEP 1 — Identify Important History Entries Based on the Query
======================================================================

Determine which history entries are relevant to <query>.

Rules:
- Direct textual overlap with the query is required.
- No inference or semantic interpretation.
- Only explicit wording may be used.

Output of Step 1 (internal):
For each important entry:
- history_index

You must accumulate enough entries so that Step 2 can generate ≥5 summarized features supported by ≥5 distinct history_index values.

======================================================================
STEP 2 — Extract Summarized Explicit Features & Assign Relevance Ranks
======================================================================

Goal:
Identify explicit factual information from important history entries and convert them into summarized_features strictly based on literal evidence.


A. Feature Extraction Rules
    From the important history entries:
    - Extract only explicit, literal facts stated in the text.
    - Merge entries that express the same explicit fact into a single summarized_feature.
    - For each summarized_feature, record ALL supporting history_index values.
    - No inference, interpretation, expansion, or implied meaning is allowed.


B. Relevance Ranking Rules
    Rank summarized_features strictly by:
    - direct literal textual overlap with the query.

    Rank 1 = highest relevance.
    No semantic reasoning or inferred relevance is allowed.

C. Output of Step 2 (internal)
    1. A list of summarized_features, each containing:
        • summarized_feature
        • support_history_index — all history_index values supporting it
        • relevance_rank

    2. concerned_features —
        A concise restatement created ONLY from literal text taken directly from the highest-ranked summarized_features.
        No new wording, paraphrasing, or inference is permitted.

======================================================================
STEP 3 — Evaluate Candidate Products
======================================================================

Goal:
Evaluate each candidate strictly through literal alignment with the query and summarized_features.

A. Allowed Evidence for Evaluating Candidates
    Your evaluation may rely ONLY on:
    - literal text from the query
    - summarized_features from Step 2
    - candidate metadata (title, price)
    - literal tool results

No inference, assumption, or semantic expansion is allowed.

B. Rewriting Candidate Information
    - product_title and product_description may be rewritten ONLY for clarity.
    - You may NOT add new facts or interpret missing information.
    - If a candidate lacks descriptive text:
        “This product is listed with title X and price Y.”

C. Requirement for Recommendation Support
    Each recommended product must be supported by ≥1 summarized_feature,
    based strictly on literal textual overlap.

======================================================================
STEP 4 — Produce Exactly 5 Final Recommendations
======================================================================

You must output exactly **5** ranked products.

Each Product includes:
- index
- product_title (rewritten, literal only)
- product_description (rewritten, literal only)
- product_recommendation_reason (explicitly grounded)
- rank (1–5)

Each product must be supported by ≥1 summarized_feature from Step 2.

No inference is allowed.

======================================================================
HISTORY SUPPORT REQUIREMENTS
======================================================================

Your final output MUST contain a “historys” array with:

### ≥ 5 SupportingHistoryFeature entries
Where each entry corresponds to one **summarized_feature**, not to individual history entries.

Each SupportingHistoryFeature includes:
- summarized_feature
- support_history_index (list of history indices supporting this feature)
- relevance_rank
- support_product (candidate indices supported by literal overlap)

Sorting:
- historys MUST be sorted by relevance_rank ascending.

Support Definition:
A summarized_feature supports a product ONLY when literal textual overlap exists between:
- the summarized_feature
- the product’s literal metadata or tool-clarified explicit text

======================================================================
OUTPUT SPECIFICATION (STRICT JSON ONLY)
======================================================================

Output raw JSON conforming to the `Recommendation` interface with no markdown formatting.

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