from __future__ import annotations

import os
import time
from pathlib import Path


def main() -> None:
    receipts = Path(os.getenv("RECEIPTS_DIR", "/data/receipts"))
    queue = Path(os.getenv("RECEIPT_QUEUE_DIR", "/data/receipt-queue"))
    receipts.mkdir(parents=True, exist_ok=True)
    queue.mkdir(parents=True, exist_ok=True)

    print("receipt-worker: v0 queue watcher online")
    print(f"receipt-worker: receipts={receipts}")
    print(f"receipt-worker: queue={queue}")

    while True:
        pending = sorted(queue.glob("*.json"))
        if pending:
            print(f"receipt-worker: {len(pending)} queued receipt request(s); API owns creation in v0")
        time.sleep(30)


if __name__ == "__main__":
    main()

