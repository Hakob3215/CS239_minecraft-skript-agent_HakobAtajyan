import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_system.agents.reviewer import apply_mutations_to_disk, validate_safety
from agent_system.bridge.log_tailer import CHAT_TRIGGER_REGEX
from agent_system.bridge.rcon_client import RconClient
from agent_system.db.retriever import sanitize_fts_query
from agent_system.graph import should_continue
from agent_system.main import save_trace_log
from agent_system.state import AgentState, FileMutation


class AgentSchemaTests(unittest.TestCase):
    def test_file_mutation_accepts_supported_actions(self):
        mutation = FileMutation(path="items/test.sk", action="WRITE", content="command /test:")
        self.assertEqual(mutation.action, "WRITE")

    def test_agent_state_defaults_are_initialized(self):
        state = AgentState(raw_prompt="!create test", action_type="CREATE")
        self.assertEqual(state.mutations, [])
        self.assertEqual(state.retry_count, 0)


class RetrievalTests(unittest.TestCase):
    def test_fts_query_quotes_tokens_and_removes_special_characters(self):
        self.assertEqual(sanitize_fts_query("event: right click"), '"event" OR "right" OR "click"')


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    def test_log_trigger_parser_extracts_player_action_and_prompt(self):
        line = "[12:34:56] [Async Chat Thread - #1/INFO]: <Alex> !fix repair ping"
        match = CHAT_TRIGGER_REGEX.match(line)
        self.assertIsNotNone(match)
        self.assertEqual(match.group("player"), "Alex")
        self.assertEqual(match.group("action").upper(), "FIX")
        self.assertEqual(match.group("prompt"), "repair ping")

    def test_rcon_requires_password_from_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                RconClient()

    async def test_rcon_broadcast_uses_command_transport(self):
        with patch.dict("os.environ", {"RCON_PASSWORD": "test-password"}, clear=True):
            client = RconClient()
        client.send_command = unittest.mock.AsyncMock(return_value="")
        await client.broadcast_chat('ready "now"', color="green")
        client.send_command.assert_awaited_once_with(
            'tellraw @a {"text":"[Agent] ready \\"now\\"","color":"green"}'
        )


class ReviewerSafetyTests(unittest.TestCase):
    def test_validate_safety_rejects_escape_and_dangerous_content(self):
        escape = FileMutation(path="../outside.sk", action="WRITE", content="on load:")
        dangerous = FileMutation(
            path="items/test.sk",
            action="WRITE",
            content='execute console command "stop"',
        )
        with patch("agent_system.agents.reviewer.SCRIPTS_ROOT", Path("mc_server/plugins/Skript/scripts").resolve()):
            self.assertFalse(validate_safety([escape])[0])
            self.assertFalse(validate_safety([dangerous])[0])

    def test_apply_mutations_writes_inside_temporary_scripts_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mutation = FileMutation(path="items/test.sk", action="CREATE", content="on load:\n    send \"ok\"")
            with patch("agent_system.agents.reviewer.SCRIPTS_ROOT", root):
                self.assertEqual(validate_safety([mutation]), (True, ""))
                self.assertEqual(apply_mutations_to_disk([mutation]), ["WRITE:items/test.sk"])
            self.assertEqual((root / "items" / "test.sk").read_text(encoding="utf-8"), mutation.content)


class GraphRoutingTests(unittest.TestCase):
    def test_success_ends_graph(self):
        state = AgentState(raw_prompt="!create test", compiler_error=None)
        self.assertEqual(should_continue(state), "__end__")

    def test_error_retries_until_limit(self):
        retry = AgentState(raw_prompt="!fix test", compiler_error="syntax error", retry_count=0)
        exhausted = AgentState(raw_prompt="!fix test", compiler_error="syntax error", retry_count=3)
        self.assertEqual(should_continue(retry), "swe")
        self.assertEqual(should_continue(exhausted), "__end__")


class TraceTests(unittest.TestCase):
    def test_trace_log_serializes_mutations(self):
        initial = AgentState(raw_prompt="!create test", action_type="CREATE")
        final = {
            "action_type": "CREATE",
            "target_scope": "items/test.sk",
            "compiler_error": None,
            "mutations": [FileMutation(path="items/test.sk", action="CREATE", content="on load:")],
            "traces": [{"node": "secretary"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            with patch("agent_system.main.TRACES_DIR", Path(directory)):
                trace_path = save_trace_log("tester", initial, final)
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["success"])
            self.assertEqual(payload["mutations"][0]["path"], "items/test.sk")


if __name__ == "__main__":
    unittest.main()
