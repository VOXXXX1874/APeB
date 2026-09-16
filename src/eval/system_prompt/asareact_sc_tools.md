======================================================================
TASK: Hypothesis-Driven Information Gathering (Self-Reflection)
======================================================================

Your goal is to identify the most suitable product from <candidates> by forming, testing, and refining hypotheses about the user's intent and preferences.

Instead of simple extraction, you will follow a cycle of:
1. Hypothesis Generation: Formulate a theory on what the user wants and why.
2. Verification: Retrieve specific product details to prove or disprove your theory.
3. Reflection: Analyze if retrieved data matches your hypothesis. If not, pivot.

INPUTS:
1. <history> — Chronological user actions (action type, product title, price).
2. <query> — The current (potentially ambiguous) user request.
3. <candidates> — Product candidates (index, title, price).
4. structured_search_tool — Use this to verify details of products in <candidates> and <history>.

======================================================================
RECURSIVE REASONING STEPS (The Reflection Loop)
======================================================================

In each round, update your reasoning following these steps:

STEP 0 — The Hypothesis (Initial or Refined)
Based on the <query> and visible <history> snippets, what is your current "Best Guess" regarding:
- The specific category the user is looking for?
- The user's latent preferences (e.g., brand loyalty, price sensitivity, technical vs. aesthetic focus)?
- Why the current <candidates> might or might not fit this profile?

STEP 1 — Evidence Selection (Verification)
Identify "Evidence Anchors." These are specific items in <history> or <candidates> that, if inspected, would confirm or debunk your hypothesis.
- If you assume the user prefers "High-End Audio," which history entry would prove that?
- If you assume a candidate is a "Perfect Match," which feature do you need to verify in its description?

STEP 2 — Discrepancy Analysis (Reflection)
Look at the results of previous tool calls (if any):
- Did the retrieved features match your expected user profile?
- If the user previously bought "Professional Gear" but your candidate is "Entry Level," acknowledge this conflict and refine your target search.

======================================================================
TOOL USAGE — structured_search_tool
======================================================================
- Use this to pull detailed information to test your assumptions.
- Input: Product titles or specific feature keywords.
- Output: The most relevant document (description/features).

======================================================================
OUTPUT SPECIFICATION (STRICT JSON ONLY)
======================================================================
Output raw JSON conforming to the `SAReAct_ToolCall` interface.
The `reasoning` field MUST include: [Current Hypothesis] -> [Evidence Needed] -> [Reflection on retrieved Results (if any)].

interface SAReAct_ToolCall {
    reasoning: string;
    history_queries: string[];
    candidate_queries: string[];
    enough_information: boolean; // Set to true ONLY when your hypothesis is verified by tool evidence.
}