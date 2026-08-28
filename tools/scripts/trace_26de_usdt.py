#!/usr/bin/env python3

import json
import urllib.request
from decimal import Decimal
from datetime import datetime, timezone

RPC = "https://bsc-dataseed.binance.org/"
TOKEN = "0x55d398326f99059ff775485246999027b3197955".lower()
TARGET = "0x26de9d249bc22b014885314410ad2411cebc2fdd".lower()

KNOWN_TX = "0xe439725cec02ba95802fc7fe32888831f89a4b68b6ab3aea576c989cd59aaaf8"

TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa"
    "952ba7f163c4a11628f55a4df523b3ef"
)

TARGET_TOPIC = "0x" + "0" * 24 + TARGET[2:]


def rpc(method, params):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }).encode()

    req = urllib.request.Request(
        RPC,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())

    if "error" in data:
        raise RuntimeError(data["error"])

    return data["result"]


def addr(topic):
    return "0x" + topic[-40:]


def amount(data):
    return Decimal(int(data, 16)) / Decimal(10**18)


def get_time(block):
    b = rpc("eth_getBlockByNumber", [hex(block), False])
    ts = int(b["timestamp"], 16)
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def code_type(address):
    code = rpc("eth_getCode", [address, "latest"])
    return "EOA" if code == "0x" else "CONTRACT"


print("=== TARGET ===")
print(TARGET)

print("\n=== ADDRESS TYPE ===")
print(code_type(TARGET))

print("\n=== CURRENT USDT BALANCE ===")

data = "0x70a08231" + "0" * 24 + TARGET[2:]
raw = rpc(
    "eth_call",
    [{
        "to": TOKEN,
        "data": data,
    }, "latest"]
)

bal = Decimal(int(raw, 16)) / Decimal(10**18)
print(bal, "USDT")

print("\n=== KNOWN WITHDRAWAL ===")

receipt = rpc(
    "eth_getTransactionReceipt",
    [KNOWN_TX]
)

if receipt is None:
    raise SystemExit("Known transaction not found")

start_block = int(receipt["blockNumber"], 16)

print("Known TX block:", start_block)
print("Known TX time :", get_time(start_block))

latest = int(rpc("eth_blockNumber", []), 16)

print("Latest block  :", latest)

print("\n=== SCANNING USDT TRANSFERS ===")

events = []

# 20k blocks per query, automatically reduced on RPC errors
chunk = 20000
block = start_block

while block <= latest:

    end = min(block + chunk - 1, latest)

    try:
        # OUTGOING: topic1 = TARGET
        outgoing = rpc(
            "eth_getLogs",
            [{
                "fromBlock": hex(block),
                "toBlock": hex(end),
                "address": TOKEN,
                "topics": [
                    TRANSFER_TOPIC,
                    TARGET_TOPIC,
                ],
            }]
        )

        # INCOMING: topic2 = TARGET
        incoming = rpc(
            "eth_getLogs",
            [{
                "fromBlock": hex(block),
                "toBlock": hex(end),
                "address": TOKEN,
                "topics": [
                    TRANSFER_TOPIC,
                    None,
                    TARGET_TOPIC,
                ],
            }]
        )

    except Exception:
        if chunk <= 500:
            raise

        chunk //= 2
        continue

    for log in incoming:
        events.append({
            "direction": "IN",
            "block": int(log["blockNumber"], 16),
            "tx": log["transactionHash"],
            "from": addr(log["topics"][1]),
            "to": addr(log["topics"][2]),
            "amount": amount(log["data"]),
        })

    for log in outgoing:
        events.append({
            "direction": "OUT",
            "block": int(log["blockNumber"], 16),
            "tx": log["transactionHash"],
            "from": addr(log["topics"][1]),
            "to": addr(log["topics"][2]),
            "amount": amount(log["data"]),
        })

    block = end + 1


events.sort(key=lambda x: (x["block"], x["direction"]))

seen_blocks = {}

print("\n=== RESULTS ===")

total_in = Decimal(0)
total_out = Decimal(0)

for e in events:

    if e["block"] not in seen_blocks:
        seen_blocks[e["block"]] = get_time(e["block"])

    when = seen_blocks[e["block"]]

    print()
    print("TIME      :", when)
    print("DIRECTION :", e["direction"])
    print("AMOUNT    :", e["amount"], "USDT")
    print("FROM      :", e["from"])
    print("TO        :", e["to"])
    print("TX        :", e["tx"])

    if e["direction"] == "IN":
        total_in += e["amount"]
    else:
        total_out += e["amount"]

        try:
            print("TO TYPE   :", code_type(e["to"]))
        except Exception:
            print("TO TYPE   : unknown")


print("\n=== TOTALS ===")
print("TOTAL IN :", total_in)
print("TOTAL OUT:", total_out)
print("NET      :", total_in - total_out)
print("BALANCE  :", bal)

print("\n=== OUTGOING DESTINATIONS ===")

for e in events:
    if e["direction"] == "OUT":
        print(
            e["amount"],
            "USDT ->",
            e["to"],
            "TX:",
            e["tx"]
        )
