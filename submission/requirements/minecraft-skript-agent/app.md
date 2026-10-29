# Minecraft Skript Agent

Minecraft Skript Agent is a workflow-oriented multi-agent application that lets Minecraft players request creation, modification, and repair of Skript programs through in-game chat.

Supported requests use `!create`, `!update`, or `!fix`. The application watches the PaperMC log, routes each request through a Secretary Agent, generates or repairs Skript through a Software Engineering Agent, and validates the result with a Reviewer Agent. The Reviewer checks the mutation sandbox, reloads the script through Minecraft RCON, performs a semantic review, broadcasts usage instructions, and records an auditable JSON trace.

The workflow is implemented as a Secretary -> SWE -> Reviewer LangGraph. Compiler errors and semantic failures return to the SWE Agent for up to three repair attempts. The application supports single-file and directory-scoped Skript changes, documentation-grounded code generation, live PaperMC compilation, and explicit failure reporting.
