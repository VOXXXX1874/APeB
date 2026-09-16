TASK: Query Rewrite Base on History

Your goal is to rewrite user query based on the user’s history to make sure the query is clear and can reflect the user’s current needs, using data from:
  (1) <history> — chronological important user actions with indices (action type, product in this history, price)
  (2) <query> — the user’s current query (may be ambiguous or intentional)

The <history> input will ALWAYS contain around 60 entries, where each entry corresponds to a single user action. The original user history is much longer, but a filter system is deployed so that you will only see the most relevant and important history actions. You MUST carefully analyze those actions to infer the intention of user for the rewriting of query. No fabricated or invented history entries or features are considered.

The query in <query> can be ambiguous or even diffcult to understand. You might need to analyze the user’s target product or hidden needs by combining the information from <query> and <history>. And then rewrite the original query to a clear and short (1-10 words) one based on your reasoning. A short clear query can facilitate later process and make sure the recommendation system will not have weird behavior.

Finally, please output raw JSON conforming to the `RewrittenQuery` interface **without** wrapping it in triple back-ticks.

```ts
interface RewrittenQuery{
    user_intent: str; // A basic summary of user persona from history, the target product of this user, and what feature this user will consider.
    new_query: str; // The rewritten query based on the analysis of user history.
}
```
