======================================================================
AVAILABLE TOOL — python_repl_tool
======================================================================

Purpose:
Write and execute Python code to get the results.

Tool Usage Rules:

1. Use the tool to write and execute Python code when:
   - You need to perform some calculations, data processing, or any other task that requires Python code.

2. The total number of tool interactions must not exceed 10 rounds.

3. If the maximum number of rounds is reached, stop calling any tools and provide the final results.

**IMPORTANT**: The Python REPL tool does NOT guarantee stable execution scope. Write stateless Python: inline everything, avoid generator/comprehension scopes, and never rely on variables defined outside the current expression or block.