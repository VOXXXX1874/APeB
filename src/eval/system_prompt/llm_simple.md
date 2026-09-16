# Task Background

You will receive a user query and user history action, which is ranked by time, and equipped with index, action type, action content, (price). You will also receive product candidates list, from which you need to predict which product is more suitable for the user. The input is like:

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

Please thoroughly analyze and understand user's needs based on history actions and candidates, and provide a final report that ranks how much is a candidate suitable for user and what is the most suitable candidate for user.

You can analyze the user history and candidates following these steps:

1. List: In the history, there are lots of features that are unique or similar to each other. Please distinguish them and list them out clearly. For those similar features, you can combine them if they share exactly the same meaning, but **NEVER** combine them into one general feature because it will make the recommendation too general and not able to meet user's needs.

2. Ranking: Based on user persona and research results, rank the primary features to consider first when user issue such query content. Notice that common features are not neccessary to be ranked higher, because details always matters to the user.
(Beside the ranking for primary features, please also include the ranking for feature that user will not be interested in this section)

3. Choosing: Based on the user persona and ranking result, discuss why each candidate is or is not suitable for user, and present the most suitable candidate for user. Finally, you should output a rank for all candidiates based on how much it is suitable for user.

# Output Format

Output raw JSON conforming to the `Recommendation` interface **without** wrapping it in triple back-ticks.

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

# Data Integrity
- Only use information explicitly provided in the input.
- Never consider fictional examples or scenarios.
- If data seems incomplete, acknowledge the limitations.
- Do not make assumptions about missing information.

# Note
- Only include verifiable facts from the provided source material.
- Always use the English, which is the language you are good at.
- To make your report more informative and avoid reach token limit, please include around 10 products in your recommendation rank.