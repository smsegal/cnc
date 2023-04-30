#!/usr/bin/env python

import json
import subprocess
import sys
from pathlib import Path
from time import sleep

from rich.console import Console

console = Console()

CONFIG_FILE = Path(__file__).parent / "config.json"


def load_configuration(config_file):
    with open(config_file) as f:
        return json.load(f)


def select_highpower_host(config):
    hosts = config["hosts"]
    console.print("Select the high-power host to wake up:", style="bold")
    for i, host in enumerate(hosts, start=1):
        console.print(f"{i}. {host['name']}")
    while True:
        choice = console.input("Enter your choice (number): ")
        if choice.isdigit() and 1 <= int(choice) <= len(hosts):
            return hosts[int(choice) - 1]
        console.print("Invalid choice. Please try again.", style="bold red")


def is_host_online(host, proxy):
    try:
        subprocess.run(
            ["ssh", proxy["name"], f'nc -z -w 5 {host["name"]} {host["port"]}'],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def send_wake_on_lan(host, proxy):
    wol_cmd = f'wakeonlan {host["mac"]}'
    subprocess.run(["ssh", proxy["name"], wol_cmd], check=True)


def main():
    config_path = Path(CONFIG_FILE)
    if not config_path.is_file():
        console.print(
            f"Configuration file '{CONFIG_FILE}' not found.", style="bold red"
        )
        sys.exit(1)

    config = load_configuration(CONFIG_FILE)
    proxy = config["proxy"]
    selected_host = select_highpower_host(config)

    if not is_host_online(selected_host, proxy):
        console.print(
            f"Waking up [bold]{selected_host['name']}[/bold]...", style="green"
        )
        send_wake_on_lan(selected_host, proxy)
        sleep(5)

    console.print(
        f"Connecting to [bold]{selected_host['name']}[/bold]...", style="green"
    )
    subprocess.run(["ssh", selected_host["name"]], check=True)


if __name__ == "__main__":
    main()
