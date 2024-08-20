#!/usr/bin/env python3

import subprocess
import re
import sys
import json

# Check if the correct number of arguments was provided
if len(sys.argv) != 3:
    print("Error: Both identifier (asset ID or group key) and network are required.")
    print("Usage: python3 chain-balance.py <identifier> <network>")
    sys.exit(1)

# Identifier (can be either asset ID or group key) and network (e.g., testnet, mainnet, regtest)
identifier = sys.argv[1]
network = sys.argv[2]

# Determine if the identifier is an asset ID or a group key
if len(identifier) == 64:
    id_type = "asset_id"
elif len(identifier) == 66:
    id_type = "group_key"
else:
    print(
        "Error: Invalid identifier length. Asset ID should be 64 characters and group key should be 66 characters."
    )
    sys.exit(1)

print(f"Calculating total balance for identifier: {identifier} on {network}")

# Construct the asset balance CLI command
asset_balance_command = [
    "tapcli",
    "--tlscertpath",
    "~/.lit/tls.cert",
    f"--rpcserver=localhost:8443",
    f"--network={network}",
    "assets",
    "balance",
    f"--{id_type}",
    identifier,
]

# Run the CLI command and capture the output
try:
    result = subprocess.run(
        asset_balance_command, capture_output=True, text=True, check=True
    )
    output = result.stdout

    # Parse the JSON output
    data = json.loads(output)

    # Initialize a variable to hold the total balance
    total_balance = 0

    # Extract and sum the balances
    if "asset_balances" in data:
        for asset_id, balance_info in data["asset_balances"].items():
            if asset_id == identifier:
                balance = int(balance_info.get("balance", 0))
                total_balance += balance

        if total_balance > 0:
            print(
                f"Total balance for {id_type} {identifier} on {network}: {total_balance}"
            )
        else:
            print(
                f"No balance information found for {id_type} {identifier} on {network}."
            )
    else:
        print(f"No asset balances found in the output for {network}.")

except subprocess.CalledProcessError as e:
    print(f"Error running command: {e}")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"Error parsing JSON output: {e}")
    sys.exit(1)


# Construct the channel balance command
channel_balance_command = ["lncli", f"--network={network}", "listchannels"]

# Run the channel balance command and capture the output
try:
    result = subprocess.run(
        channel_balance_command, capture_output=True, text=True, check=True
    )
    output = result.stdout

    # Parse the JSON output
    data = json.loads(output)
    total_capacity = 0
    total_local_balance = 0
    total_remote_balance = 0

    # Process each channel in the list
    for channel in data.get("channels", []):
        # Check for custom_channel_data
        custom_data = channel.get("custom_channel_data", {})
        if not custom_data:
            continue  # Skip this channel if no custom_channel_data is found

        # Iterate over the assets in custom_channel_data
        for asset in custom_data.get("assets", []):
            asset_id = (
                asset.get("asset_utxo", {}).get("asset_genesis", {}).get("asset_id")
            )
            if asset_id == identifier:
                # If asset ID matches the identifier, extract the balances
                capacity = int(asset.get("capacity", 0))
                local_balance = int(asset.get("local_balance", 0))
                remote_balance = int(asset.get("remote_balance", 0))

                # Accumulate the totals
                total_capacity += capacity
                total_local_balance += local_balance
                total_remote_balance += remote_balance

    print(
        f"Off-chain total capacity for {id_type} {identifier} on {network}: {total_capacity}"
    )
    print(
        f"Off-chain total local balance for {id_type} {identifier} on {network}: {total_local_balance}"
    )
    print(
        f"Off-chain total remote balance for {id_type} {identifier} on {network}: {total_remote_balance}"
    )

except subprocess.CalledProcessError as e:
    print(f"Error running channel balance command: {e}")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"Error parsing JSON output: {e}")
    sys.exit(1)

# Optionally, you can sum the on-chain and off-chain balances
total_balance = on_chain_balance + total_local_balance + total_remote_balance
print(f"Total balance for {id_type} {identifier} on {network}: {total_balance}")
