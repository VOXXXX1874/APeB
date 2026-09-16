
======================================================================
TASK: Detail Information Gathering (Tool-Enabled)
======================================================================

Your goal is to gather detailed information of user history actions to better understand user needs so that we can choose the most suitable candidate, based on:

1. <history> — chronological user actions with indices (action type, product in this history, price)
2. <query> — the user’s current query (may be ambiguous or indirect)
3. <candidates> — product candidates (index, title, price)
4. structured_search_tool — retrieve detailed information of products in <candidates> and <history> to help your understanding

You will perform multiple rounds of tool calls. In each round, you should reasoning based on previous input and tool output, determine the next step according to the instructions below, and build a good query to retrieve the most important information to help us understand the user needs.

ATTENTION: Different from the ReAct scenario you are trained on, you need to enclose the reasoning and tool call following the OUTPUT SPECIFICATION section. What's more, the tool call result will be provided as user message in the next round, because we want to have a more flexible workflow and tasks.

======================================================================
AVAILABLE TOOL — structured_search_tool
======================================================================

Purpose:
Only the product title is presented in <candidates> and <history>. Use this tool only to retrieve details about products or history entries.

Permitted data sources:
- Candidate product detailed features
- History product and video detailed features

Tool Input: Each query can contain some keywords related to the information you want to retrieve or a product title.

Tool Implementation: The retrieval tool is implemented by BM25. Each document (or chunk) is exactly a product or a video, which consists of the product title, description, and other detailed features.

Tool Output: The most relevant one document for each input query.

======================================================================
STEPS TO FOLLOW:
======================================================================

The <history> and <candidates> will ALWAYS contain many entries.

==================================
STEP 0 — Query Intent Detection (Ambiguous Query Resolution)
==================================

The user query might be ambiguous or difficult to understand. So, please first determine what the user is **literally seeking**, based on:
- explicit terms in <query>
- explicit text from <history>
- literal candidate titles
- Previous steps' reasoning

Goal of Step 0 (internal):
- target_product — the literal category or phrase representing what the user is trying to find.

==================================
STEP 1 — Identify Important History Entries or Candidates
==================================

A coarse-grained target product is not enough to make decision because the candidates are always a list of similar products. To gather more information to help decision, you need to determine which history entries or candidates are important based on the relationship between:
- target_product
- <query>
- <candidates>
- <history>
- Previous steps' finding

Goal of Step 1 (internal):
- important_products — a list of product titles that are likely to reflect user's hidden intent or be purchased later.

==================================
STEP 2 — Retrieve Features and Description (Using Tools)
==================================

Convert important products into queries that can retrieve the most important features and descriptions of these products.

Tool Usage in Step 2  (Must Follow Global Tool Rules)
    Use the structured_search_tool to find the detailed information of products in:
    - the history actions
    - the candidates list

======================================================================
OUTPUT SPECIFICATION (STRICT JSON ONLY)
======================================================================

Output raw JSON conforming to the `SAReAct_ToolCall` interface with no markdown formatting.

```ts
interface SAReAct_ToolCall {
    reasoning: str; // The reasoning behind, about how to determine target product, important entries, analysis, and how to build final query
    history_queries: List[str]; // The queries that target the informations in user history.
    candidate_queries: List[str]; // The queries that target the informations in candidate products.
    enough_information: bool; // Whether current result contains enough information to answer the query.
}
```

Once the `enough_information` is `true`, we won't retrieve content and we will go to next step. So please always gather all the information required before set the `enough_information` to `true`.