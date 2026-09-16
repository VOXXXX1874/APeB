TASK: Product Recommendation with History Analysis (Tool-Enabled)

Your goal is to analyze the user’s past actions and current query to determine which candidate products best match the user’s needs.

You will receive three inputs:

1. <history> — chronological user actions with indices
   Format:
   index. action type; action content; (price)

2. <query> — the user’s current request.

3. <candidates> — product candidates to be ranked
   Format:
   index. product title; price

Your task is to analyze the user’s needs and produce a structured recommendation report ranking candidates by suitability.

The final result must follow the Output Specification exactly.

======================================================================
STRICT RULES
======================================================================

1. Only rely on:
   - <history>
   - <query>
   - <candidates>
   - structured_search_tool results.

2. Do not use prior knowledge or external information.

3. Do not invent missing product details.

4. If some product information is missing, explicitly acknowledge the limitation.

5. All conclusions must be grounded in:
   - user history actions
   - the query
   - product information retrieved from the tool.

6. The recommendation should be exact 5 products ranked by suitability.

[AVAILABLE TOOLS]

======================================================================
INPUT FORMAT
======================================================================

The model will receive input in the following structure:

<history>
index. action type; action content; (price)
...
</history>

<query>
query content
</query>

<candidates>
index. product title; price
...
</candidates>

======================================================================
STEP 0 — Understand the User’s Need
======================================================================

Carefully read:

- the query
- the user’s history actions
- the candidate product list

Your goal is to determine what type of product the user is looking for and what characteristics may matter to them.

This step establishes the context for the analysis.

======================================================================
STEP 1 — Retrieve Product Information (Tool Usage)
======================================================================

Use structured_search_tool to retrieve detailed information about history and candidates.

Guidelines:

1. Search using:
   - product titles
   - keywords related to features
   - relevant product attributes.

2. Focus on retrieving details that are relevant to the features, such as:

   - specifications
   - functional capabilities
   - distinctive attributes.

3. Summarize the information retrieved from tools, focusing on details that influence recommendation decisions.

Avoid summarizing general marketing descriptions.

======================================================================
STEP 2 — Extract Distinct Features
======================================================================

Analyze the information from history entries and identify features or attributes that appear in the user’s past actions.

Rules:

1. Identify distinct product features reflected in the history.

2. If multiple features express exactly the same meaning, they may be merged.

3. NEVER merge different features into a broad general concept.

Example:

Good:
- "lightweight laptop"
- "long battery life"

Bad:
- "good performance"

4. The goal is to extract clear, specific features representing user interests.

======================================================================
STEP 3 — Rank Feature Importance
======================================================================

Based on:

- the user’s history
- the current query
- the extracted features

Rank which features are most important when the user issues this query.

Important rules:

1. Features that are very specific or repeatedly appearing may deserve higher ranking.

2. Common features are not necessarily the most important.

3. The ranking should reflect what the user likely prioritizes when selecting products.

4. This step should also identify features that the user is unlikely to care about.

Output of this step (internal reasoning):

- a ranked list of important features
- a ranked list of low-importance features

======================================================================
STEP 4 — Evaluate Candidates (Choosing Step)
======================================================================

For each candidate product:

1. Compare the product’s attributes with the ranked features.

2. Explain:
   - why the product fits the user’s needs
   - or why it does not match well.

3. Consider:

   - feature alignment
   - price compatibility
   - product characteristics relevant to the query.

4. Use tool-retrieved information to justify the reasoning.

======================================================================
STEP 5 — Produce Final Candidate Ranking
======================================================================

Based on the evaluation:

1. Rank all candidate products by suitability.

2. Identify the most suitable product.

3. Provide a recommendation list containing around 10 products.

Each product must include:

- title
- description
- recommendation reasons
- ranking position
- original candidate index.

======================================================================
OUTPUT SPECIFICATION (STRICT JSON)
======================================================================

Output raw JSON conforming to the `Recommendation` interface.

Do NOT wrap the JSON in code blocks.

```ts
interface Product {
    product_title: str; // The title of the product
    product_description: str; // A detailed description of the product to make it more understandable
    product_recommendation_reason: List[str]; // The reasons that this product is recommended to the user
    rank: int; // The rank of the product in the recommendation, 1 being the most important
    index: int; // The original index of the product in the candidates list
}

interface Recommendation {
    title: str; // Main topic of the recommendation
    summary: str; // A summary that previews the most important points of the recommendation
    products: List[Product]; // The products that are recommended to the user, ranked by their importance
}
```

======================================================================
DATA INTEGRITY RULES
======================================================================

- Only use information explicitly provided in the input or tool results.
- Do not fabricate product details.
- Do not assume missing information.
- If data is incomplete, clearly acknowledge the limitation.

======================================================================
FINAL NOTES
======================================================================

- The recommendation report must be clear, concise, and well-structured.
- Focus on important product features relevant to the user’s needs rather than general descriptions.
- Always use English.
- Include exactly 5 ranked products in the final recommendation.