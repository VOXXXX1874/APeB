TASK: Structured Product Recommendation (Exactly 5 Items, Tool-Enabled)

Your goal is to recommend exactly five products that best match the user’s explicit needs, using only:

1. <history> — chronological user actions with indices (action type, product in this history, price)
2. <query> — the user’s current query (may be ambiguous or indirect)
3. <candidates> — product candidates (index, title, price)
4. structured_search_tool — for factual clarification only

Strict Rules:
- No external knowledge, invented assumptions, or inferred intentions.
- All reasoning must be grounded only in literal text and tool results.
- All outputs must follow the strict JSON format in the Output Specification.

[AVAILABLE TOOLS]

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
STEP 0 — Query Intent Detection (Ambiguous Query Resolution)
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

You MUST collect enough entries so that Step 2 can yield ≥5 summarized features supported by ≥5 distinct history_index values.

======================================================================
STEP 2 — Extract Summarized Explicit Features & Assign Relevance Ranks (Tool Allowed)
======================================================================

Goal:
Convert important history entries into summarized_features that reflect ONLY explicit, literal facts supported by the history text.

A. Tool Usage in Step 2  (Must Follow Global Tool Rules)
    You may use the structured_search_tool only to clarify literal terms found in:
    - the history text
    - the user query

    Tool constraints:
        - Queries must use literal text only.


B. Summarized Feature Extraction Rules
    For all important history entries:
    - Extract ONLY explicit, literal facts.
    - Merge entries that express the same literal fact into one summarized_feature.
    - Record all history_index values that support each summarized_feature.
    - No inferred meaning, no assumptions, no preference interpretation.
    - Each summarized_feature must be concise and literal.


C. Relevance Ranking Rules
    Rank summarized_features strictly by direct literal overlap with:
    1. the query
    2. the target_product

    Rank 1 = highest relevance.
    No semantic reasoning or inferred alignment is allowed.

D. Output of Step 2 (internal)
    1. A list of summarized_features, each containing:
        • summarized_feature
        • support_history_index — all supporting history_index values
        • relevance_rank

    2. concerned_features —
    A concise, literal restatement created ONLY from text fragments taken directly from the highest-ranked summarized_features.
    No new information, paraphrasing, or inference is permitted.

======================================================================
STEP 3 — Evaluate Candidate Products (With Tool Usage)
======================================================================

Goal:
Evaluate each candidate using ONLY literal alignment between candidate information, the query, target_product, summarized_features, and tool-clarified text.

A. Tool Usage in Step 3  (Must Follow Global Tool Rules)
    For each candidate:
    1. Identify literal candidate terms requiring clarification.
    2. Issue structured_search_tool queries using ONLY literal text from:
        • the query
        • the target_product
        • the candidate title or features
        • the summarized_features

    All tool usage must follow global rules:
        - Queries must use literal terms only.
        - Total tool calls (Steps 2 + 3) must not exceed 10.

B. Allowed Evidence for Candidate Evaluation
    Evaluation may rely ONLY on:
    - literal query text
    - target_product
    - summarized_features from Step 2
    - candidate metadata (title, price)
    - literal tool results

    No inference, assumption, or semantic expansion is allowed.

C. Rewriting Candidate Information
    - product_title and product_description may be rewritten only for clarity.
    - No new facts may be added.
    - If a candidate lacks descriptive information, you MUST write:
        “This product is listed with title X and price Y.”

D. Requirement for Recommendation Support
    Each recommended product must be supported by ≥1 summarized_feature
    through literal textual overlap.

======================================================================
STEP 4 — Produce Exactly 5 Final Recommendations
======================================================================

Each Product object includes:
- index
- product_title (rewritten clearly, no new facts)
- product_description (rewritten clearly, no new facts)
- product_recommendation_reason (explicitly grounded in query + target_product + summarized_features + tool results)
- rank (1–5)

You MUST output exactly 5 products.

Each recommended product MUST be supported by ≥1 summarized_feature.

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

======================================================================
FINAL COMPLIANCE CHECKLIST
======================================================================

Query Detection:
• target_product must be derived only from literal overlap (query ↔ history ↔ candidates ↔ tool results).

Product Requirements:
• Exactly 5 products, ranked 1–5.
• No invented facts.
• Reasons grounded strictly in query, target_product, summarized_features, and literal tool results.

History Requirements:
• ≥ 5 summarized_feature items.
• Union of support_history_index across all items contains ≥5 distinct history indices.
• All features must originate from Step 2.
• Every recommended product must be supported by ≥1 summarized_feature.

Tool Requirements:
• ≥ 1 tool call, ≤ 10 calls.
• All queries based strictly on literal text.

JSON Requirements:
• Output must be strictly valid JSON.
• No commentary or formatting outside JSON.