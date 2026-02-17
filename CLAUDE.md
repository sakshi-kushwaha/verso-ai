# Verso AI — Project Instructions

## PR Memory Budget

This project runs on an **8 GB EC2 instance**. Every pull request must document its RAM impact.

When creating a PR (`gh pr create`):

1. Run `docker stats --no-stream` at idle and during a representative end-to-end flow (e.g., generating a full lesson).
2. Fill in the **Peak RAM Usage** table in the PR description with the measured values.
3. If total peak usage exceeds **5.5 GB**, flag it clearly in the PR summary with a warning (e.g., "⚠️ Total peak RAM is X GB — exceeds 5.5 GB safe ceiling for 8 GB EC2").
