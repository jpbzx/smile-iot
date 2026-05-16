"""
Simple runnable test/snippet for InfluxDBManager.

This script demonstrates behavior when Influx is unreachable: writes are buffered
to an offline file. Run it as a script:

    python -m software.db.tests.test_influx_manager

It intentionally points to an invalid Influx URL to force offline buffering.
"""
import os
import time
from pathlib import Path

# Set environment for the test run (force an unreachable Influx)
os.environ.setdefault("INFLUX_URL", "http://localhost:59999")  # assuming nothing listening here
os.environ.setdefault("INFLUX_BATCH_SIZE", "1")
os.environ.setdefault("INFLUX_FLUSH_INTERVAL", "1")
TEST_OFFLINE = Path(__file__).resolve().parents[2] / "data" / "offline_influx_queue_test.jsonl"
os.environ.setdefault("INFLUX_OFFLINE_PATH", str(TEST_OFFLINE))

from software.db.influx_manager import influx_db

def run_demo():
    # ensure previous test file removed
    try:
        TEST_OFFLINE.unlink()
    except Exception:
        pass

    print("Writing a test energy reading (should be buffered to offline file)...")
    influx_db.save_energy_reading(current_a=0.5, power_w=2.0, voltage_v=220.0, outlet_state="on")

    # Wait enough for background worker to attempt flush and fallback to offline
    time.sleep(3)

    if TEST_OFFLINE.exists():
        print("Offline file created:", TEST_OFFLINE)
        print(TEST_OFFLINE.read_text()[:1000])
    else:
        print("No offline file created — write may have succeeded (Influx reachable?)")

    # clean up and close manager
    influx_db.close()

if __name__ == "__main__":
    run_demo()
