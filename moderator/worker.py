import queue
import threading
from dataclasses import dataclass
from typing import Callable

from .models import ChatMessage, ModClientRef, ModClientRef


@dataclass
class HeuristicTask:
    command: str
    nickname: str
    messages: list[ChatMessage]
    photo_path: str | None = None
    client: ModClientRef | None = None
    flood_kind: str | None = None


@dataclass
class MlBatchTask:
    batch: list[ChatMessage]
    photo_path: str
    client: ModClientRef | None = None


class ModerationWorker:
    def __init__(
        self,
        process_heuristic: Callable[[HeuristicTask], None],
        process_ml_batch: Callable[[MlBatchTask], None],
        on_queue_change: Callable[[int], None] | None = None,
        worker_count: int = 3,
    ):
        self._process_heuristic = process_heuristic
        self._process_ml_batch = process_ml_batch
        self._on_queue_change = on_queue_change
        self._worker_count = max(1, worker_count)
        self._queue: queue.Queue[HeuristicTask | MlBatchTask | None] = queue.Queue()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for index in range(self._worker_count):
            thread = threading.Thread(
                target=self._run,
                daemon=True,
                name=f"mod-worker-{index + 1}",
            )
            thread.start()
            self._threads.append(thread)

    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def thread_count(self) -> int:
        return self._worker_count

    def submit_heuristic(
        self,
        command: str,
        nickname: str,
        messages: list[ChatMessage],
        photo_path: str | None = None,
        client: ModClientRef | None = None,
        flood_kind: str | None = None,
    ) -> None:
        self._queue.put(
            HeuristicTask(command, nickname, list(messages), photo_path, client, flood_kind)
        )
        self._notify()

    def submit_ml_batch(
        self,
        batch: list[ChatMessage],
        photo_path: str,
        client: ModClientRef | None = None,
    ) -> None:
        self._queue.put(MlBatchTask(list(batch), photo_path, client))
        self._notify()

    def _notify(self) -> None:
        if self._on_queue_change:
            self._on_queue_change(self.pending())

    def drain_pending(self) -> int:
        dropped = 0
        while True:
            try:
                task = self._queue.get_nowait()
            except queue.Empty:
                break
            if task is not None:
                dropped += 1
            self._queue.task_done()
        if dropped:
            self._notify()
        return dropped

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            try:
                if task is None:
                    return
                if isinstance(task, HeuristicTask):
                    self._process_heuristic(task)
                elif isinstance(task, MlBatchTask):
                    self._process_ml_batch(task)
            finally:
                self._queue.task_done()
                self._notify()
