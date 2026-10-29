# Reviewer Agent

## Available tools

- `validate_safety`
- `apply_mutations_to_disk`
- `RconClient.connect`
- `RconClient.reload_script`
- `RconClient.broadcast_chat`
- `RconClient.close`

## Implementation

The Reviewer Agent first performs deterministic sandbox and dangerous-command validation. It then applies safe mutations, reloads the target through RCON, and returns compiler output to the SWE Agent when reload fails. After successful compilation, it uses structured LLM output to verify semantic intent and generate short in-game usage instructions. Approved results are broadcast and recorded in the trace.

## System prompt

```text
You are the Senior Reviewer Agent for an autonomous Minecraft Skript system.
The code below has successfully passed live compilation on PaperMC.

Your job is twofold:
1. VERIFY INTENT: Check if the SWE agent genuinely addressed the user's prompt. If the user asked for a command or feature and the SWE agent completely omitted it, set meets_requirements=False with a clear critique.
2. EXTRACT USER USAGE: If approved, produce a clear, friendly set of in-game instructions (commands, items, permissions, usage) so the player knows how to test and use what was just loaded.
```
