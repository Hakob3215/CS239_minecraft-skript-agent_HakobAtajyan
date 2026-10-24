import asyncio
import re
import struct
from typing import Tuple

# handle minecraft color text / strip
MINECRAFT_COLOR_REGEX = re.compile(r"§[0-9a-fk-or]", re.IGNORECASE)
def strip_formatting(text: str) -> str:
    """Removes all Minecraft § color and formatting codes from a string."""
    return MINECRAFT_COLOR_REGEX.sub("", text).strip()

SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0

class RconClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 25575, password: str = "agentic_secret_pass"):
        self.host = host
        self.port = port
        self.password = password
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self._request_id = 0

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _encode_packet(self, request_id: int, packet_type: int, payload: str) -> bytes:
        """Pack ASCII into binary RCON wire format"""
        encoded_payload = payload.encode("utf-8")
        # packet length = 4 (id) + 4 (type) + len(payload) + 2 (null terminators)
        length = 4 + 4 + len(encoded_payload) + 2
        header = struct.pack("<iii", length, request_id, packet_type)
        return header + encoded_payload + b"\x00\x00"

    async def _read_packet(self) -> Tuple[int, int, str]:
        "Read ONE packet from TCP Stream"
        raw_length = await self.reader.readexactly(4)
        length = struct.unpack("<i", raw_length)[0]

        data = await self.reader.readexactly(length)
        request_id, packet_type = struct.unpack("<ii", data[:8]) # take first 8 bytes

        payload = data[8:-2].decode("utf-8", errors="replace") # last two bytes are null terminators

        return request_id, packet_type, payload

    async def connect(self):
        """Establish TCP Connection and authentication"""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

        # send auth packet
        auth_id = self._next_request_id()
        self.writer.write(self._encode_packet(auth_id, SERVERDATA_AUTH, self.password))
        await self.writer.drain()

        # wait for response:
        while True:
            resp_id, resp_type, _ = await self._read_packet()
            if resp_type == SERVERDATA_AUTH_RESPONSE:
                if resp_id == -1:
                    raise PermissionError("RCON auth failed: invalid password")
                break

    async def send_command(self, command: str) -> str:
        """Send console command and return raw output string"""
        cmd_id = self._next_request_id()
        self.writer.write(self._encode_packet(cmd_id, SERVERDATA_EXECCOMMAND, command))
        await self.writer.drain()

        _, _, output = await self._read_packet()
        return output.strip()

    async def broadcast_chat(self, message: str, color: str = "gray"):
        """
        Sends an formatted system message to all players on the server.
        Uses /tellraw for clean, un-prefixed chat delivery.
        """
        safe_message = message.replace('"', '\\"')
        cmd = f'tellraw @a {{"text":"[Agent] {safe_message}","color":"{color}"}}'
        await self.send_command(cmd)

    async def reload_script(self, target_rel_path: str) -> Tuple[bool, str]:
        """
        Reloads a script or folder relative to plugins/Skript/scripts/.
        Returns (success_flag, clean_console_output).
        """
        clean_target = target_rel_path.replace("\\", "/").strip("/")
        if clean_target.startswith("scripts/"):
            clean_target = clean_target[len("scripts/"):].strip("/")

        raw_output = await self.send_command(f"skript reload {clean_target}")
        clean_output = strip_formatting(raw_output)

        lower = clean_output.lower()
        success = ("successfully reloaded" in lower or "loaded 1 script" in lower) and "error" not in lower
        return success, clean_output

    async def close(self):
        """Close TCP connection"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
