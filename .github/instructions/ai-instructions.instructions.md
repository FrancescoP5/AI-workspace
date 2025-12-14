---
applyTo: '**'
---
[CRITICAL WORKFLOW PROTOCOL: ai-worklogs.txt]
This project relies on a persistent log file named `ai-worklogs.txt` to synchronize all agents. You must strictly adhere to this sequence:

1. INITIALIZATION (READ):
   - Before writing any code or analyzing the request, you MUST read the content of `ai-worklogs.txt`.
   - Parse the last entry to understand the current project state, blocking errors, and the previous agent's identity.
   - Determine your identity: If the last log was "agent-02", you are "agent-03".

2. EXECUTION (WORK):
   - Perform your coding tasks, debugging, or refactoring as requested.

3. FINALIZATION (WRITE):
   - Once your task is complete (or if you are blocked), you MUST generate a new log entry in the standardized "Hybrid Log/JSON" format.
   - APPEND this new entry to the end of `ai-worklogs.txt`.
   - WARNING: Do NOT overwrite the existing file. Always APPEND.