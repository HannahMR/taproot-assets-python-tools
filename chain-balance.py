#!/usr/bin/env python3

import subprocess
import sys
import json


def run_command(command):
    """
    Runs a command using subprocess and returns the JSON-decoded output.
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}")
        sys.exit(1)


def get_onchain_balance(identifier, id_type, network):
    """
    Retrieves and returns the total on-chain balance for the given identifier.
    """
    asset_list_command = [
        "tapcli",
        "--tlscertpath",
        "~/.lit/tls.cert",
        f"--rpcserver=localhost:8443",
        f"--network={network}",
        "assets",
        "list",
    ]

    data = run_command(asset_list_command)

    # Initialize a variable to hold the total balance
    total_balance = 0

    # Extract and sum the balances
    for asset in data.get("assets", []):
        asset_id = asset.get("asset_genesis", {}).get("asset_id")
        asset_group = asset.get("asset_group", {})
        raw_group_key = asset_group.get("raw_group_key")
        tweaked_group_key = asset_group.get("tweaked_group_key")
        script_key_is_local = asset.get("script_key_is_local", False)

        # Check if the asset matches the identifier (either by asset_id, raw_group_key, or tweaked_group_key)
        if script_key_is_local and (
            asset_id == identifier
            or raw_group_key == identifier
            or tweaked_group_key == identifier
        ):
            amount = int(asset.get("amount", 0))
            total_balance += amount

    if total_balance > 0:
        print(f"Found on-chain balance")
    else:
        print(
            f"No on-chain balance information found for {id_type} {identifier} on {network}."
        )

    return total_balance


def get_off_chain_balances(identifier, id_type, network, asset_ids=None):
    """
    Retrieves and returns the total off-chain capacity, local balance, and remote balance
    for the given identifier. If the identifier is a group key, it uses the list of asset IDs.
    """
    channel_balance_command = ["lncli", f"--network={network}", "listchannels"]

    data = run_command(channel_balance_command)

    total_capacity = 0
    total_local_balance = 0
    total_remote_balance = 0

    # Determine if we're working with a single asset ID or a list of asset IDs
    identifiers_to_check = [identifier] if id_type == "asset_id" else asset_ids

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
            if asset_id in identifiers_to_check:
                # If asset ID matches any of the identifiers, extract the balances
                capacity = int(asset.get("capacity", 0))
                local_balance = int(asset.get("local_balance", 0))
                remote_balance = int(asset.get("remote_balance", 0))

                # Accumulate the totals
                total_capacity += capacity
                total_local_balance += local_balance
                total_remote_balance += remote_balance

    # print(f"Off-chain total capacity: {total_capacity}")
    # print(f"Off-chain total local balance: {total_local_balance}")
    # print(f"Off-chain total remote balance: {total_remote_balance}")

    return total_capacity, total_local_balance, total_remote_balance


def list_assets(group_key, network):
    """
    Runs a CLI command to list all assets associated with a group key and returns a list of asset IDs.
    """
    list_assets_command = [
        "tapcli",
        "--tlscertpath",
        "~/.lit/tls.cert",
        f"--rpcserver=localhost:8443",
        f"--network={network}",
        "assets",
        "list",
    ]

    data = run_command(list_assets_command)

    # Initialize an empty list to collect asset IDs
    asset_ids = []

    # Iterate over the assets in the returned data
    for asset in data.get("assets", []):
        asset_group = asset.get("asset_group")

        # Check if asset_group is not None and then proceed
        if asset_group:
            raw_group_key = asset_group.get("raw_group_key")
            tweaked_group_key = asset_group.get("tweaked_group_key")

            # Check if either the raw or tweaked group key matches the provided group key
            if raw_group_key == group_key or tweaked_group_key == group_key:
                asset_id = asset.get("asset_genesis", {}).get("asset_id")
                if asset_id:
                    asset_ids.append(asset_id)

    # Return the list of matched asset IDs
    return asset_ids


# Main program starts here

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
    asset_ids = [identifier]  # Single asset ID in a list
elif len(identifier) == 66:
    id_type = "group_key"
    # Retrieve all asset IDs linked to the group key
    asset_ids = list_assets(identifier, network)
    print(f"Found {len(asset_ids)} assets linked to group key {identifier}.")
else:
    print(
        "Error: Invalid identifier length. Asset ID should be 64 characters and group key should be 66 characters."
    )
    sys.exit(1)

print(f"Calculating total balance for {id_type} {identifier} on {network}...")

# Initialize total balances
total_off_chain_capacity = 0
total_off_chain_local_balance = 0
total_off_chain_remote_balance = 0

# Iterate over each asset ID and accumulate balances
simple_balance = 0
for asset_id in asset_ids:
    # Process simple balance
    simple_balance += get_onchain_balance(asset_id, id_type, network)

# Process off-chain balances for either a single asset ID or multiple asset IDs
total_capacity, total_local_balance, total_remote_balance = get_off_chain_balances(
    identifier,
    id_type,
    network,
    asset_ids=asset_ids if id_type == "group_key" else None,
)

# Update total balances
total_off_chain_capacity += total_capacity
total_off_chain_local_balance += total_local_balance
total_off_chain_remote_balance += total_remote_balance

# Calculate final balances
total_on_chain_balance = simple_balance
total_offchain_funds = total_off_chain_capacity
total_balance = total_on_chain_balance + total_off_chain_local_balance

# Output the total balances
print(f"----Totals----")
print(f"On-chain balance: {total_on_chain_balance}")
print(f"Off-chain capacity: {total_offchain_funds}")
print(f"Off-chain local balance: {total_off_chain_local_balance}")
print(f"Total balance: {total_balance}")
