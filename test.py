#!/usr/bin/env python3
"""Derive ETH or BTC addresses from a recovery phrase.

    /home/tony/Documents/.venv/bin/python /home/tony/Documents/test.py
    /home/tony/Documents/.venv/bin/python /home/tony/Documents/test.py --coin btc

Type the mnemonic when asked. It is not saved.
"""

import argparse
import getpass
import json
import time
import urllib.error
import urllib.request
from time import sleep
from mnemonic import Mnemonic

from bip_utils import (
    Bip39SeedGenerator,
    Bip44,
    Bip44Changes,
    Bip44Coins,
    Bip49,
    Bip49Coins,
    Bip84,
    Bip84Coins,
)
from eth_account import Account

Account.enable_unaudited_hdwallet_features()

# Ethereum (MetaMask):     m/44'/60'/0'/0/{index}
# Bitcoin native SegWit:   m/84'/0'/0'/0/{index}   bc1q...
# Bitcoin nested SegWit:   m/49'/0'/0'/0/{index}   3...
# Bitcoin legacy:          m/44'/0'/0'/0/{index}   1...
ETH_PATH = "m/44'/60'/0'/0/{index}"
BTC_PATHS = {
    "native": "m/84'/0'/0'/0/{index}",
    "nested": "m/49'/0'/0'/0/{index}",
    "legacy": "m/44'/0'/0'/0/{index}",
}
# Public RPCs often block Python's default User-Agent with HTTP 403.
ETH_RPCS = (
    "https://ethereum.publicnode.com",
    "https://1rpc.io/eth",
    "https://rpc.ankr.com/eth",
    "https://cloudflare-eth.com",
)
HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}
BTC_API = "https://blockstream.info/api/address/{address}"


def eth_balance(address):
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getBalance",
            "params": [address, "latest"],
        }
    ).encode()
    errors = []
    for rpc in ETH_RPCS:
        request = urllib.request.Request(rpc, data=payload, headers=HTTP_HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            errors.append(f"{rpc}: HTTP {exc.code}")
            continue
        except urllib.error.URLError as exc:
            errors.append(f"{rpc}: {exc.reason}")
            continue
        if "result" not in body:
            errors.append(f"{rpc}: {body.get('error', body)}")
            continue
        return int(body["result"], 16) / 10**18
    raise RuntimeError("Could not fetch ETH balance. " + "; ".join(errors))


def btc_balance(address):
    with urllib.request.urlopen(BTC_API.format(address=address), timeout=20) as response:
        data = json.loads(response.read())
    funded = data["chain_stats"]["funded_txo_sum"]
    spent = data["chain_stats"]["spent_txo_sum"]
    return (funded - spent) / 10**8


def derive_btc(mnemonic, index, kind):
    seed = Bip39SeedGenerator(mnemonic).Generate()
    change = Bip44Changes.CHAIN_EXT
    if kind == "legacy":
        ctx = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
        path = BTC_PATHS["legacy"].format(index=index)
    elif kind == "nested":
        ctx = Bip49.FromSeed(seed, Bip49Coins.BITCOIN)
        path = BTC_PATHS["nested"].format(index=index)
    else:
        ctx = Bip84.FromSeed(seed, Bip84Coins.BITCOIN)
        path = BTC_PATHS["native"].format(index=index)
    key = ctx.Purpose().Coin().Account(0).Change(change).AddressIndex(index)
    return path, key.PublicKey().ToAddress(), key.PrivateKey().Raw().ToHex()


def main():
    parser = argparse.ArgumentParser(description="Open an ETH or BTC wallet from a mnemonic.")
    parser.add_argument("--coin", choices=("eth", "btc"), default="eth")
    parser.add_argument(
        "--btc-type",
        choices=("native", "nested", "legacy"),
        default="native",
        help="Bitcoin address type. native = bc1q (most modern wallets)",
    )
    parser.add_argument("--key", action="store_true", help="also print the private key")
    parser.add_argument("--balance", action="store_true", help="look up on-chain balance")
    parser.add_argument("--index", type=int, default=0, help="address index (0 is the first)")
    args = parser.parse_args()
    mnemo = Mnemonic("english")
    mnemonic_phrase = mnemo.generate(strength=128)

    print("Mnemonic phrase:", mnemonic_phrase)

    # Validate the mnemonic phrase
    if mnemo.check(mnemonic_phrase):
        print("Mnemonic phrase is valid.")
    else:
        print("Mnemonic phrase is invalid.")
    if not mnemonic_phrase:
        raise SystemExit("No mnemonic entered.")

    eth_amount = 0.0
    btc_amount = 0.0

    if args.coin == "eth":
        path = ETH_PATH.format(index=args.index)
        account = Account.from_mnemonic(mnemonic_phrase, account_path=path)
        try:
            eth_amount = eth_balance(account.address)
        except Exception as e:
            eth_amount = None
        print("Coin:           Ethereum")
        print("Derivation path:", path)
        print("Wallet address:", account.address)
        print("Wallet balance: ", eth_amount)

    path, address, private_key = derive_btc(mnemonic_phrase, args.index, args.btc_type)
    try:
        btc_amount = btc_balance(address)
    except Exception as e:
        btc_amount = None
    print("Coin:           Bitcoin")
    print("Address type:  ", args.btc_type)
    print("Derivation path:", path)
    print("Wallet address:", address)
    print("BTC balance:   ", btc_amount)
    return eth_amount, btc_amount


if __name__ == "__main__":
    while True:
        eth_amount, btc_amount = main()
        if ((eth_amount is not None and eth_amount > 0.0001) or (btc_amount is not None and btc_amount > 0.0000001)):
            print("Success")
            break
        elif eth_amount is None or btc_amount is None:
            sleep(10000)
            continue
        else:
            print("Error: ", e)
            continue
