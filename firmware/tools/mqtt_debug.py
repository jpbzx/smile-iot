#!/usr/bin/env python3
"""
SMILE-IoT firmware MQTT debug tool.

Connects to a broker/topics and lets you publish fake telemetry or ON/OFF/RESET
commands interactively -- useful for exercising the backend (ingest worker +
API) end-to-end without a phone or a physical board.

Defaults to the LOCAL Mosquitto from `software/docker-compose.yml`
(localhost:1883, anonymous -- no credentials needed), matching how
backend/config.py and the ingest worker connect.

Boards flashed before 2026-07 still point at the public broker.emqx.io with
the credentials hardcoded in firmware/include/config.h -- bridge to one of
those instead with --host/--username/--password if you need to talk to a
real board that hasn't been reflashed yet:

Usage:
    .venv/bin/python mqtt_debug.py                     # local Mosquitto (default)
    .venv/bin/python mqtt_debug.py --host broker.emqx.io --username 1211189 --password isep

Once connected, type at the prompt:
    on      -> publish "ON"  to the command topic
    off     -> publish "OFF" to the command topic
    reset   -> publish "RESET" to the command topic (clears an overcurrent trip)
    quit    -> disconnect and exit
"""

import argparse
import json
import sys
import threading
from datetime import datetime

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 1883
DEFAULT_TOPIC_POWER = "smile-iot/power"
DEFAULT_TOPIC_COMMAND = "smile-iot/command"
# Empty on purpose: the default target is the local Mosquitto from
# software/docker-compose.yml, which allows anonymous connections. Filling these
# in would send credentials the local broker neither needs nor checks.
# The public broker.emqx.io account used by boards not yet reflashed is
# username "1211189" / password "isep" -- pass it explicitly when you need it:
#     mqtt_debug.py --host broker.emqx.io --username 1211189 --password isep
DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""

COMMANDS = {"on": "ON", "off": "OFF", "reset": "RESET"}


def parse_args():
    parser = argparse.ArgumentParser(description="SMILE-IoT MQTT debug tool")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--topic-power", default=DEFAULT_TOPIC_POWER)
    parser.add_argument("--topic-command", default=DEFAULT_TOPIC_COMMAND)
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="omit for local Mosquitto (anonymous)")
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    return parser.parse_args()


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code == 0:
        print(f"[{timestamp()}] Connected. Subscribing to '{userdata['topic_power']}'")
        client.subscribe(userdata["topic_power"])
    else:
        print(f"[{timestamp()}] Connection failed: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print(f"[{timestamp()}] Disconnected ({reason_code}).")


def on_message(client, userdata, msg):
    raw = msg.payload.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
        pretty = " | ".join(f"{k}={v}" for k, v in data.items())
        print(f"[{timestamp()}] {msg.topic}: {pretty}")
    except json.JSONDecodeError:
        print(f"[{timestamp()}] {msg.topic}: (unparsable) {raw}")


def input_loop(client, command_topic):
    print("\nCommands: on | off | reset | quit\n")
    while True:
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd in ("quit", "exit", "q"):
            break
        if cmd in COMMANDS:
            payload = COMMANDS[cmd]
            client.publish(command_topic, payload, qos=1)
            print(f"[{timestamp()}] Published '{payload}' -> {command_topic}")
        elif cmd:
            print(f"Unknown command: '{cmd}'. Use: on | off | reset | quit")


def main():
    args = parse_args()

    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        userdata={"topic_power": args.topic_power},
    )
    if args.username:
        client.username_pw_set(args.username, args.password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    who = f"as '{args.username}'" if args.username else "(anonymous)"
    print(f"Connecting to {args.host}:{args.port} {who}...")
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    try:
        input_loop(client, args.topic_command)
    finally:
        client.loop_stop()
        client.disconnect()
        print("Bye.")


if __name__ == "__main__":
    sys.exit(main())
