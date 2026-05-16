"""
SMILE-IoT — InfluxDB data manager with background batching, retry and offline buffer.

Configuration is read from environment variables (or .env):
 - INFLUX_URL (default: http://localhost:8086)
 - INFLUX_TOKEN (default: none)
 - INFLUX_ORG (default: smile_org)
 - INFLUX_BUCKET (default: energy_data)
 - INFLUX_BATCH_SIZE (default: 100)
 - INFLUX_FLUSH_INTERVAL (seconds, default: 5.0)
 - INFLUX_MAX_RETRIES (default: 5)
 - INFLUX_BACKOFF_BASE (seconds, default: 1.0)
 - INFLUX_OFFLINE_PATH (default: ./software/data/offline_influx_queue.jsonl)
"""

import os
import json
import time
import logging
import threading
import queue
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Read configuration from environment with sensible defaults (match docker-compose where appropriate)
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "smile_org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "energy_data")

INFLUX_BATCH_SIZE = int(os.getenv("INFLUX_BATCH_SIZE", "100"))
INFLUX_FLUSH_INTERVAL = float(os.getenv("INFLUX_FLUSH_INTERVAL", "5.0"))
INFLUX_MAX_RETRIES = int(os.getenv("INFLUX_MAX_RETRIES", "5"))
INFLUX_BACKOFF_BASE = float(os.getenv("INFLUX_BACKOFF_BASE", "1.0"))

DEFAULT_OFFLINE_PATH = Path(__file__).resolve().parents[2] / "data" / "offline_influx_queue.jsonl"
INFLUX_OFFLINE_PATH = Path(os.getenv("INFLUX_OFFLINE_PATH", str(DEFAULT_OFFLINE_PATH)))
INFLUX_OFFLINE_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("influx_manager")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(os.getenv("INFLUX_LOG_LEVEL", "INFO"))


class InfluxDBManager:
    """
    Manager that enqueues line-protocol strings, batches them in a background thread,
    retries on transient errors with exponential backoff, and falls back to a local
    offline file when Influx is unavailable.
    """

    def __init__(self):
        self.url = INFLUX_URL
        self.token = INFLUX_TOKEN
        self.org = INFLUX_ORG
        self.bucket = INFLUX_BUCKET

        self.batch_size = INFLUX_BATCH_SIZE
        self.flush_interval = INFLUX_FLUSH_INTERVAL
        self.max_retries = INFLUX_MAX_RETRIES
        self.backoff_base = INFLUX_BACKOFF_BASE
        self.offline_path = INFLUX_OFFLINE_PATH

        # Thread-safe queue storing line-protocol strings
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._background_worker, name="InfluxWriteWorker", daemon=True)

        # lazily create client so creation errors are logged but don't crash import
        try:
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            logger.info("InfluxDB client initialized (%s)", self.url)
        except Exception as e:
            self.client = None
            self.write_api = None
            logger.exception("Failed to initialize InfluxDB client: %s", e)

        self._worker_thread.start()

    def _background_worker(self):
        last_flush = time.time()
        while not self._stop_event.is_set():
            try:
                now = time.time()
                # build a batch if available
                batch: List[str] = []
                while len(batch) < self.batch_size:
                    try:
                        lp = self._queue.get_nowait()
                        batch.append(lp)
                    except queue.Empty:
                        break

                # If we have enough points or the flush interval passed, flush
                if batch and (len(batch) >= self.batch_size or (now - last_flush) >= self.flush_interval):
                    logger.debug("Flushing %d points to Influx", len(batch))
                    success = self._attempt_write(batch)
                    if not success:
                        self._append_to_offline(batch)
                    last_flush = time.time()

                # If queue empty, try to flush offline file if client healthy
                if self._queue.empty() and self.offline_path.exists() and self.write_api:
                    try:
                        self._flush_offline_file()
                    except Exception:
                        logger.exception("Error flushing offline file")

                time.sleep(0.5)

            except Exception:
                # Ensure worker never dies
                logger.exception("Unhandled exception in Influx background worker")

        # On stop: flush remaining queue synchronously
        remaining: List[str] = []
        while not self._queue.empty():
            remaining.append(self._queue.get())
        if remaining:
            logger.info("Worker stopping — flushing %d remaining points", len(remaining))
            ok = self._attempt_write(remaining)
            if not ok:
                self._append_to_offline(remaining)

    def _attempt_write(self, line_protocols: List[str]) -> bool:
        """Try writing to Influx with retries. Returns True on success."""
        if not self.write_api:
            logger.warning("No write_api available; will buffer to offline file")
            return False

        attempt = 0
        while attempt <= self.max_retries:
            try:
                # write accepts line protocol strings
                self.write_api.write(bucket=self.bucket, record=line_protocols)
                logger.debug("Successfully wrote %d points to Influx", len(line_protocols))
                return True
            except Exception as e:
                attempt += 1
                wait = self.backoff_base * (2 ** (attempt - 1))
                logger.warning("Influx write failed (attempt %d/%d): %s — retrying in %.1fs", attempt, self.max_retries, e, wait)
                time.sleep(wait)
                # if max retries exceeded, give up
                if attempt > self.max_retries:
                    logger.error("Max retries exceeded for Influx write")
                    return False
        return False

    def _append_to_offline(self, line_protocols: List[str]):
        try:
            with self.offline_path.open("a", encoding="utf-8") as f:
                for lp in line_protocols:
                    f.write(lp.replace("\n", "") + "\n")
            logger.info("Appended %d points to offline queue %s", len(line_protocols), self.offline_path)
        except Exception:
            logger.exception("Failed to append points to offline file")

    def _flush_offline_file(self):
        """Try to read offline file and write its contents. Truncate on success."""
        if not self.write_api:
            return
        lines = []
        try:
            with self.offline_path.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if ln:
                        lines.append(ln)
        except FileNotFoundError:
            return

        if not lines:
            try:
                self.offline_path.unlink()
            except Exception:
                pass
            return

        logger.info("Attempting to flush %d offline points", len(lines))
        if self._attempt_write(lines):
            try:
                self.offline_path.unlink()
                logger.info("Offline queue flushed and file removed")
            except Exception:
                logger.exception("Failed to remove offline queue file after flush")
        else:
            logger.warning("Could not flush offline queue; will retry later")

    def save_energy_reading(self, current_a: float, power_w: float, voltage_v: float, outlet_state: str):
        """Create a Point and enqueue its line-protocol string for background writing."""
        try:
            point = Point("energy_reading") \
                .tag("device", "SCT-013_ESP32") \
                .tag("outlet_state", str(outlet_state)) \
                .field("current_A", float(current_a)) \
                .field("power_W", float(power_w)) \
                .field("voltage_V", float(voltage_v))

            # Convert to line-protocol string for reliable local buffering
            try:
                lp = point.to_line_protocol()
            except Exception:
                # fallback to a minimal line-protocol builder
                tags = ",".join(f"{k}={v}" for k, v in point.to_dict().get("tags", {}).items())
                fields = ",".join(f"{k}={json.dumps(v)}" for k, v in point.to_dict().get("fields", {}).items())
                lp = f"energy_reading,{tags} {fields}"

            self._queue.put(lp)
            logger.debug("Enqueued point for background write")
        except Exception:
            logger.exception("Failed to enqueue energy reading")

    def close(self, timeout: float = 5.0):
        """Stop background worker and close client gracefully."""
        logger.info("Closing InfluxDBManager...")
        self._stop_event.set()
        self._worker_thread.join(timeout=timeout)
        try:
            if self.client:
                self.client.close()
        except Exception:
            logger.exception("Error closing InfluxDB client")


# Module-level instance for other modules to use
influx_db = InfluxDBManager()