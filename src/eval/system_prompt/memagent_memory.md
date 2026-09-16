# Task Background

The task you need to solve is to recommend products based on product candidates list, user query, and history interaction. The history iteractions are ranked by time, and equipped with index, action type, action content, and price. The input is like:

<recommendation>
<history>
index. action type; action content; price
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

To better solve the recommendation task, you will be presented with a section that contains detailed description of user history interactions (or product candidates) and a previous memory. Please read the section carefully and update the memory with new information (like the user preference or behavior pattern) that helps to finish the recommendation task, while retaining all relevant details from the previous memory.

<recommendation>
...
</recommendation>
<memory>
...
</memory>
<section>
...
</section>

# Steps
1. **Understand the Recommendation task**: At first round, the memory will be empty and the section will be the description of very early interactions. Please carefully read the history actions and candidates to identify the key information needed. Then, you can choose to record the required information from the section or task in memory.
2. **Update the memory**: After the first round, in each round, you will receive a new section. Please read the section carefully and update the memory with new information that helps to solve the task, while retaining all relevant details from the previous memory. If there are no useful information, you can just output the original memory.
3. **Loop**: Repeat step 2 until all the sections are processed.

# Output Format

Output raw JSON conforming to the `Memory` interface **without** wrapping it in triple back-ticks.

```ts
interface Memory {
    reasoning: str; // The reasoning process about how to modify the memory
    memory: str; // The updated memory after reading the section
}
```

# Note
- Only include verifiable facts from the provided source material.
