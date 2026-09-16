TASK: Relevant History Actions Selection (Exactly {{target_size}} Items)

Your goal is to select exactly {{target_size}} actions from the user’s history that provide the most important knowledge to build user persona and answer user’s current query, using data from:
  (1) <history> — chronological user actions with indices (action type, product in this history, price)
  (2) <query> — the user’s current query (may be ambiguous or intentional)

The <history> input will ALWAYS contain many entries, where each entry corresponds to a single user action. You MUST extract {{target_size}} most important actions from <history> and each selected action must be supported by a reason. The extracted actions should help us know the feature and preference of this user so that we can better serve the user's needs. No fabricated or invented history entries or features are allowed.

The query in <query> can be ambiguous or even diffcult to understand. You might need to analyze the user’s target product or hidden intention combining the information from <query> and <history>. And then choose the important entries base on your analysis.

Finally, please output raw JSON conforming to the `Filtered` interface **without** wrapping it in triple back-ticks.

```ts
interface Filtered{
    summary: str; //A summary about this history chunk and its relationship with the query and candidates.
    actions: List[FilteredAction]; //The actions that is important according to current query and candidates.
}

interface FilteredAction{
    reason: str; //Why this action is important.
    action_index: int; //The index of the action in the history list.
}
```

What's more, please try to ouput the actions by their importance in descending order.