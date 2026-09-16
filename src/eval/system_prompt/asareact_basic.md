======================================================================
TASK: Structured Product Recommendation (Exactly 5 Items)
======================================================================

After gathering enough information, now your goal is to recommend exactly five products that best match the user’s explicit needs and provide detail explanation, using only:

1. <history> — chronological user actions with indices (action type, product in this history, price)
2. <query> — the user’s current query (may be ambiguous or indirect)
3. <candidates> — product candidates (index, title, price)
4. Informations gathered during previous conversations.

Strict Rules:
- No external knowledge, invented assumptions, or inferred intentions.
- All reasoning must be grounded only in literal text and tool results.
- All outputs must follow the strict JSON format in the Output Specification.

======================================================================
STEP 0 — Query Intent Detection
======================================================================

Determine what the user is **literally seeking**, based on:
- explicit terms in <query>
- explicit text from <history>
- literal candidate titles

Rules:
- DO NOT infer hidden motivations or implied needs.
- The target must be **textually justified** by overlap among:
    (1) query text
    (2) history literal text
    (3) candidate literal titles
- If multiple literal interpretations exist, choose the one with strongest overlap.
- If none exists, use the literal core phrase of the query.

Output of Step 0 (internal):
- target_product — the literal category or phrase representing what the user is trying to find.

======================================================================
STEP 1 — Identify Important History Entries Based on Query + target_product
======================================================================

Determine which history entries are relevant to:
- <query>
- target_product

Rules:
- Explicit wording must overlap directly with the query or target_product.
- No inference or semantic interpretation beyond literal text.

Output of Step 1 (internal):
For each important entry:
- history_index

======================================================================
STEP 2 — Extract Summarized Explicit Features & Assign Relevance Ranks
======================================================================

Goal:
Convert important history entries into summarized_features that reflect ONLY explicit, literal facts supported by the history text.


A. Summarized Feature Extraction Rules
    For all important history entries:
    - Extract ONLY explicit, literal facts.
    - Merge entries that express the same literal fact into one summarized_feature.
    - Record all history_index values that support each summarized_feature.
    - No inferred meaning, no assumptions, no preference interpretation.
    - Each summarized_feature must be concise and literal.


B. Relevance Ranking Rules
    Rank summarized_features strictly by direct literal overlap with:
    1. the query
    2. the target_product

    Rank 1 = highest relevance.
    No semantic reasoning or inferred alignment is allowed.

C. Output of Step 2 (internal)
    1. A list of summarized_features, each containing:
        • summarized_feature
        • support_history_index — all supporting history_index values
        • relevance_rank

    2. concerned_features —
    A concise, literal restatement created ONLY from text fragments taken directly from the highest-ranked summarized_features.
    No new information, paraphrasing, or inference is permitted.

======================================================================
STEP 3 — Evaluate Candidate Products
======================================================================

Goal:
Evaluate each candidate using ONLY literal alignment between candidate information, the query, target_product, summarized_features, and tool-clarified text.

A. Allowed Evidence for Candidate Evaluation
    Evaluation may rely ONLY on:
    - literal query text
    - target_product
    - summarized_features from Step 2
    - candidate metadata (title, price)
    - literal tool results

    No inference, assumption, or semantic expansion is allowed.

======================================================================
STEP 4 — Produce Exactly 5 Final Recommendations
======================================================================

Each Product object includes:
- index
- product_title (rewritten clearly, no new facts)
- rank (1–5)

You MUST output exactly 5 products.

======================================================================
OUTPUT SPECIFICATION (STRICT JSON ONLY)
======================================================================

Output raw JSON conforming to the `SimpleRecommendation` interface with no markdown formatting.

```ts
interface SimpleProduct {
    product_title: str; // The title of the product
    rank: int; // The rank of the product in the recommendation, 1 being the most important
    index: int; // The index of the product in the candidates list
}

interface SimpleRecommendation {
    summary: str; // A summary that previews the most important points of the recommendation
    products: List[SimpleProduct]; // The products that are recommended to the user, ranked by their importance
}
```