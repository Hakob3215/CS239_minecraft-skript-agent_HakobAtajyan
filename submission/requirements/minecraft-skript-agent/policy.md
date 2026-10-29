P1. All file mutations must resolve inside the configured Minecraft Skript scripts directory; path traversal or any path outside that sandbox must be rejected.

P2. The application may modify only `.sk` files. Mutations targeting another file type must be rejected.

P3. Generated Skript must not contain prohibited server-control commands, including commands that stop, restart, broadly grant operator privileges, or reload all server content.

P4. The Reviewer Agent must validate every mutation before writing it to disk or reloading it on the Minecraft server.

P5. The application must report success only after the target Skript has successfully compiled on PaperMC and passed semantic review.

P6. When compilation or semantic review fails and retry attempts remain, the failure details must be returned to the SWE Agent; the workflow must terminate after the bounded retry limit without reporting success.

P7. The application must use the original player request when checking semantic completeness and must reject an implementation that omits a core requested feature.

P8. Player-facing success and usage instructions may be broadcast only after safety validation, compilation, and semantic review succeed.
