import logging
from app.workers.worker import run_worker_daemon

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [WORKER] %(message)s")
    run_worker_daemon(poll_interval=2.0)
