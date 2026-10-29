get_active_scripts: Accepts no arguments; scans the scripts root and returns a sorted list of non-disabled relative .sk file paths.
load_workspace_context: Accepts a target_scope file or directory path string; returns a dictionary mapping relevant script paths to their text contents.
_get_event_samples: Accepts no arguments; reads the event manifest and returns representative Skript event identifiers as a comma-separated string.
DocRetriever.search: Accepts a query string, optional category, and result limit; queries SQLite FTS5 and returns BM25-ranked documentation entries.
DocRetriever.format_for_prompt: Accepts a query string, optional category, and result limit; returns retrieved Skript documentation formatted for an LLM prompt.
validate_safety: Accepts a list of FileMutation objects; returns a boolean and a rejection reason string.
apply_mutations_to_disk: Accepts validated FileMutation objects; applies create, write, or delete operations inside the scripts root and returns operation tags.
LogTailer.watch: Accepts no arguments; watches latest.log and asynchronously yields ChatTrigger objects containing player, action, and prompt.
RconClient.connect: Accepts no arguments; opens and authenticates an asynchronous TCP connection to the configured Minecraft RCON server.
RconClient.send_command: Accepts a raw Minecraft console command string; sends it over RCON and returns the console response.
RconClient.reload_script: Accepts a script-relative path; sends a Skript reload command and returns a success boolean plus cleaned console output.
RconClient.broadcast_chat: Accepts a message and optional color; broadcasts the message to players through Minecraft tellraw.
RconClient.close: Accepts no arguments; closes the active RCON connection.
save_trace_log: Accepts a player name, initial AgentState, and final state dictionary; serializes the run to a timestamped JSON file and returns its Path.
