import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import AsyncGenerator, Optional
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

# Matches Paper 1.21.5 chat logs with optional security prefix and player brackets
CHAT_TRIGGER_REGEX = re.compile(
    r"^\[\d{2}:\d{2}:\d{2}\]\s+\[Async Chat Thread - #\d+/INFO\]:\s+"
    r"(?:\[Not Secure\]\s*)?"
    r"<(?P<player>[A-Za-z0-9_]{3,16})>\s+"
    r"!(?P<action>create|update|fix)\s+"
    r"(?P<prompt>.+)$",
    re.IGNORECASE,
)


@dataclass
class ChatTrigger:
    player: str
    action: str  # "CREATE", "UPDATE", or "FIX"
    prompt: str


class _LogFileHandler(FileSystemEventHandler):
    """Internal Watchdog handler dispatching file modification notifications."""

    def __init__(self, target_path: Path, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.target_path = target_path.resolve()
        self.queue = queue
        self.loop = loop

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).resolve() == self.target_path:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, True)


class LogTailer:
    """
    Asynchronous log watcher that seeks to the end of latest.log
    and yields parsed ChatTrigger events with zero Windows NTFS latency.
    """

    def __init__(self, log_path: Path = Path("server/logs/latest.log")):
        self.log_path = log_path
        self._observer: Optional[Observer] = None
        self._file = None
        self._queue: asyncio.Queue[bool] = asyncio.Queue()
        self._running = False

    def start(self, loop: asyncio.AbstractEventLoop):
        if not self.log_path.exists():
            raise FileNotFoundError(f"Target log file does not exist: {self.log_path}")

        self._file = open(self.log_path, "r", encoding="utf-8", errors="replace")
        self._file.seek(0, os.SEEK_END)
        self._running = True

        handler = _LogFileHandler(self.log_path, self._queue, loop)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.log_path.parent.resolve()), recursive=False)
        self._observer.start()

    async def watch(self) -> AsyncGenerator[ChatTrigger, None]:
        """Async generator yielding parsed chat events with a 250ms fallback."""
        while self._running:
            try:
                # Wait for watchdog event or fallback every 0.25s if Windows delays NTFS sync
                await asyncio.wait_for(self._queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                pass

            if not self._file:
                break

            # Read all newly written bytes
            while True:
                line = self._file.readline()
                if not line:
                    break

                line_clean = line.strip()
                match = CHAT_TRIGGER_REGEX.match(line_clean)
                if match:
                    player = match.group("player")
                    action = match.group("action").upper()
                    prompt = match.group("prompt").strip()

                    yield ChatTrigger(player=player, action=action, prompt=prompt)

    def stop(self):
        """Cleans up system file handles and stops background worker threads."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        if self._file:
            self._file.close()
            self._file = None