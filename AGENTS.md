# CRITICAL RULES

1. Preserve all existing functionality unless explicitly instructed otherwise.
2. Make the smallest possible change to accomplish the task.
3. Never remove models, workflows, UI components, settings, integrations, or business logic without approval.
4. Before editing, identify all potentially impacted features.
5. After editing, perform a regression review and verify nothing was removed.
6. If there is any risk of breaking existing functionality, stop and ask for guidance.
7. Prefer additive changes over replacement changes.
8. Show a summary of changed files and preserved functionality after every task.
9. When providing shell commands for this repo, use PowerShell-safe syntax only. Do not chain commands with `&&`; use separate commands or PowerShell separators that work on this machine.
