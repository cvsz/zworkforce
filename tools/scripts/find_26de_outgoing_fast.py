#!/usr/bin/env python3
import json
import urllib.request
from decimal import Decimal

RPC = "https://bsc-dataseed.binance.org/"
TOKEN = "0x55d398326f99059ff775485246999027b3197955"
TARGET = "0x26de9d249bc22b014885314410ad2411cebc2fdd"

START = 102118077

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
FROM_TOPIC = "0x" + "0"*24 + TARGET[2:]

def rpc(method, params):
    req = urllib.request.Request(
        RPC,
        data=json.dumps({
            "jsonrpc":"2.0",
            "method":method,
            "params":params,
            "id":1
        }).encode(),
        headers={"Content-Type":"application/json"}
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        x = json.loads(r.read())

    if "error" in x:
        raise RuntimeError(x["error"])

    return x["result"]

def address(topic):
    return "0x" + topic[-40:]

def value(data):
    return Decimal(int(data,16)) / Decimal(10**18)

# First search about 1,000,000 blocks after the original withdrawal.
# Expand later if necessary.
END = START + 1_000_000

chunk = 5000

print("Searching:", START, "->", END)

for begin in range(START, END + 1, chunk):
    finish = min(begin + chunk - 1, END)

    try:
        logs = rpc("eth_getLogs", [{
            "fromBlock": hex(begin),
            "toBlock": hex(finish),
            "address": TOKEN,
            "topics": [
                TRANSFER,
                FROM_TOPIC
            ]
        }])
    except Exception as e:
        print("RPC error", begin, finish, e)
        continue

    if logs:
        for log in logs:
            to = address(log["topics"][2])
            amount = value(log["data"])

            print()
            print("FOUND OUTGOING")
            print("BLOCK :", int(log["blockNumber"],16))
            print("AMOUNT:", amount, "USDT")
            print("FROM  :", TARGET)
            print("TO    :", to)
            print("TX    :", log["transactionHash"])

    if begin % 100000 == START % 100000:
        print("scanned through", finish)

print("DONE")
