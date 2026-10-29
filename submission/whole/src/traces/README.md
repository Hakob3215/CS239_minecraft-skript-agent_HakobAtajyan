# Execution Traces

This directory contains verified execution traces captured from live runs against the PaperMC server. Each JSON file records the player request, agent decisions, mutations, compiler feedback, retry count, and final reviewer outcome.

## Trace Summary

| Trace File | Request Type | Scenario | Triggered Policies | Outcome |
| :--- | :--- | :--- | :--- | :--- |
| `20261028_175529_items_tp_elytra.json` | `!create` | Teleport Elytra creation; initial dynamic location syntax failed PaperMC compilation and was repaired on retry 1. | **P1, P2, P4, P5, P6, P8** | `APPROVED` (`retry_count: 1`, `success: true`) |
| `20261028_185955_mobs_vengeful_creeper.json` | `!fix` | Vengeful Creeper repair; block breaking and damage recursion loops were fixed on the first pass. | **P1, P2, P4, P5, P6, P8** | `APPROVED` (`retry_count: 0`, `success: true`) |
| `20261028_183635_mobs_vengeful_creeper.json` | `!create` | Vengeful Creeper creation; invalid explosion and target expressions persisted through three compiler retries. | **P1, P2, P4, P5** | `REJECTED` (`retry_count: 3`, `success: false`) |

## Policy and Scenario Details

### Teleport Elytra creation

The player requested a firework-activated teleport mechanic. The Secretary Agent selected `items/tp_elytra.sk`; the SWE Agent generated the file; and the Reviewer Agent safely wrote and reloaded it. PaperMC rejected the initial dynamic location syntax. The compiler output was returned to the SWE Agent, which generated a corrected mutation. The second reload and semantic review succeeded. This demonstrates sandbox and file-type validation (P1 and P2), reviewer gating (P4), compilation-before-success (P5), compiler-feedback recovery (P6), and post-approval player guidance (P8).

### Vengeful Creeper repair

The player requested two fixes to an existing script: prevent block destruction and prevent creeper damage from recursively spawning another creeper. The Secretary Agent loaded `mobs/vengeful_creeper.sk`; the SWE Agent added safe explosion handling and excluded creeper attackers; and the Reviewer Agent approved the first generated repair after successful compilation and semantic review. This demonstrates P1, P2, P4, P5, P6, and P8.

### Vengeful Creeper retry exhaustion

The player requested creation of a non-destructive retaliatory creeper. The generated script failed on unsupported explosion syntax, then failed on an invalid explosion-radius expression, and finally failed on an invalid death-event entity expression. After three compiler retries, the graph terminated without approval or success broadcast. This demonstrates that P1, P2, and P4 remain active for every attempt, P5 prevents false success, and P6 bounds the recovery loop.

## Reading a Trace

The `success` field indicates whether the workflow completed with a successful compilation and reviewer approval. `retry_count` records the number of retry attempts. The `traces` array contains the Secretary, SWE, and Reviewer events, including compiler diagnostics and applied file operations.
