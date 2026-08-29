#!/usr/bin/env bash
set -euo pipefail

RPC="https://bsc-dataseed.binance.org/"
TOKEN="0x55d398326f99059fF775485246999027B3197955"
TARGET="0x26de9d249bc22b014885314410ad2411cebc2fdd"
SOURCE_TX="0xe439725cec02ba95802fc7fe32888831f89a4b68b6ab3aea576c989cd59aaaf8"

TRANSFER_TOPIC="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
FROM_TOPIC="0x000000000000000000000000${TARGET#0x}"

rpc() {
  curl -sS -X POST "$RPC" \
    -H 'Content-Type: application/json' \
    --data "$1"
}

echo "=== Contract code ==="
rpc "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getCode\",\"params\":[\"$TARGET\",\"latest\"],\"id\":1}" | jq .

echo
echo "=== Current USDT balance ==="

BAL=$(rpc "{\"jsonrpc\":\"2.0\",\"method\":\"eth_call\",\"params\":[{\"to\":\"$TOKEN\",\"data\":\"0x70a08231000000000000000000000000${TARGET#0x}\"},\"latest\"],\"id\":1}" | jq -r .result)

python3 - "$BAL" <<'PY'
import sys
raw=int(sys.argv[1],16)
print("Raw:", raw)
print("USDT:", raw / 10**18)
PY

echo
echo "=== Original withdrawal receipt ==="

RECEIPT=$(rpc "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getTransactionReceipt\",\"params\":[\"$SOURCE_TX\"],\"id\":1}")

echo "$RECEIPT" | jq .

START_HEX=$(echo "$RECEIPT" | jq -r '.result.blockNumber')

if [[ "$START_HEX" == "null" || -z "$START_HEX" ]]; then
    echo "Could not obtain source transaction block."
    exit 1
fi

START=$((16#${START_HEX#0x}))

LATEST_HEX=$(rpc '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' | jq -r .result)
LATEST=$((16#${LATEST_HEX#0x}))

echo
echo "Source block : $START"
echo "Latest block : $LATEST"

echo
echo "=== Searching outgoing USDT transfers ==="

CHUNK=2000

for ((FROM=START; FROM<=LATEST; FROM+=CHUNK)); do

    TO=$((FROM + CHUNK - 1))
    (( TO > LATEST )) && TO=$LATEST

    FROM_HEX=$(printf '0x%x' "$FROM")
    TO_HEX=$(printf '0x%x' "$TO")

    RESULT=$(rpc "{
      \"jsonrpc\":\"2.0\",
      \"method\":\"eth_getLogs\",
      \"params\":[{
        \"fromBlock\":\"$FROM_HEX\",
        \"toBlock\":\"$TO_HEX\",
        \"address\":\"$TOKEN\",
        \"topics\":[
          \"$TRANSFER_TOPIC\",
          \"$FROM_TOPIC\"
        ]
      }],
      \"id\":1
    }")

    echo "$RESULT" | jq -c '.result[]?' | while read -r LOG; do

        TX=$(echo "$LOG" | jq -r '.transactionHash')
        TOPIC_TO=$(echo "$LOG" | jq -r '.topics[2]')
        DATA=$(echo "$LOG" | jq -r '.data')

        RECIPIENT="0x${TOPIC_TO:26}"

        AMOUNT=$(python3 - "$DATA" <<'PY'
import sys
print(int(sys.argv[1],16) / 10**18)
PY
)

        echo
        echo "OUTGOING USDT FOUND"
        echo "TX       : $TX"
        echo "FROM     : $TARGET"
        echo "TO       : $RECIPIENT"
        echo "AMOUNT   : $AMOUNT USDT"
    done
done

echo
echo "=== Finished ==="
