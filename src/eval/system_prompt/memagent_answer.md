# Task Background

The task you need to solve is to recommend products based on product candidates list, user query, and history interaction. The history iteractions are ranked by time, and equipped with index, action type, action content, and price. The input is like:

<recommendation>
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
</recommendation>

Please thoroughly analyze and understand user's needs based on history actions and candidates, and provide a final report that ranks how much is a candidate suitable. In addition to above information, you will also be provided with a memory with **important informations** you gathered from detailed description of each history interaction and candidates. The overall format is like

<recommendation>
...
</recommendation>
<memory>
...
</memory>

# Steps
1. **Understand the Recommendation task**: Please carefully read the history actions and candidates to identify the key information needed.
2. **Understand the Memory**: The memory is gathered from detailed informations of candidates or user history by you. Please read the memory carefully and identify the key information that helps to solve the task.
3. **Make Prediction**: Based on the understanding of the recommendation task and the memory, make a prediction about which product is more suitable for the user.

# Output Format

Output raw JSON conforming to the `SimpleRecommendation` interface **without** wrapping it in triple back-ticks.

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

# Note
- Only include verifiable facts from the provided source material.
- Follow the interface specification strictly and never output `null` because it will break the parser.
- To make your report more informative and avoid reach token limit, please include around 5 products in your recommendation rank.