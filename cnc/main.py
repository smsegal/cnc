import subprocess
from pathlib import Path
from time import sleep
from typing import NewType, Optional, Type, TypeVar

import click
import yaml
from pydantic import BaseModel
from rich.console import Console
from typing_extensions import Self
from xdg_base_dirs import xdg_config_home

console = Console()

CONFIG_DIR = xdg_config_home() / "cnc"
CONFIG_FILE = CONFIG_DIR / "config.yml"


HostKey = NewType("HostKey", str)


class Host(BaseModel):
    name: HostKey
    ip: Optional[str]
    mac: str
    user: Optional[str]
    port: int = 22
    proxy: HostKey


class ProxyHost(BaseModel):
    name: HostKey
    ip: Optional[str]
    user: Optional[str]
    port: int = 22


T = TypeVar("T", Host, ProxyHost)


class CNCConfig(BaseModel):
    default_host: HostKey
    hosts: dict[HostKey, Host]
    proxy_hosts: dict[HostKey, ProxyHost]

    @classmethod
    def from_dict(cls, config_dict: dict) -> Self:
        def _parse_host(host_type: Type[T], host_dict: dict) -> dict[HostKey, T]:
            return {k: host_type(name=k, **v) for k, v in host_dict.items()}

        hosts = _parse_host(Host, config_dict["hosts"])
        proxy_hosts = _parse_host(ProxyHost, config_dict["proxy_hosts"])
        return cls(
            default_host=config_dict["default_host"],
            hosts=hosts,
            proxy_hosts=proxy_hosts,
        )


def write_schema():
    print(CNCConfig.schema_json(indent=2))


def load_configuration(config_file: Path) -> CNCConfig:
    yaml_config = Path(config_file).read_text()
    config_dict = yaml.safe_load(yaml_config)
    return CNCConfig.from_dict(config_dict)


def select_highpower_host(hosts: dict[HostKey, Host]) -> Host:
    console.print("Select the high-power host to wake up:", style="bold")
    for i, hostname in enumerate(hosts, start=1):
        console.print(f"{i}. {hostname}")
    while True:
        choice = console.input("Enter your choice (number): ")
        if choice.isdigit() and 1 <= int(choice) <= len(hosts):
            return list(hosts.values())[int(choice) - 1]
        console.print("Invalid choice. Please try again.", style="bold red")


def is_host_online(host: Host, proxy: ProxyHost) -> bool:
    try:
        subprocess.run(
            ["ssh", proxy.name, f"nc -z -w 5 {host.name} {host.port}"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def send_wake_on_lan(host: Host, proxy: ProxyHost):
    wol_cmd = f"wakeonlan {host.mac}"
    subprocess.run(["ssh", proxy.name, wol_cmd], check=True)


@click.command()
@click.option("-l", "--list", is_flag=True, help="List all hosts")
@click.option("--schema", is_flag=True, help="Print the configuration schema")
@click.option(
    "-c",
    "--config",
    "config_file",
    default=CONFIG_FILE,
    help="Path to configuration file",
)
@click.option("--print-config", is_flag=True, help="Print the configuration")
@click.option("-h", "--host", help="Host to connect to")
def cli(list: bool, schema: bool, config_file: str, host: str, print_config: bool):
    config = load_configuration(Path(config_file))
    if schema:
        write_schema()
    elif list:
        hosts = config.hosts
        console.print("Available hosts:", style="bold")
        for hostname in hosts:
            console.print(hostname)
    elif print_config:
        console.print(config)
    else:
        main(config, host)


def main(config: CNCConfig, hostname: Optional[str] = None):
    proxy = config.proxy_hosts[config.hosts[config.default_host].proxy]
    hostname = HostKey(hostname) if hostname else config.default_host
    host = config.hosts.get(hostname)
    selected_host = host or select_highpower_host(config.hosts)

    if not is_host_online(selected_host, proxy):
        console.print(
            f"Waking up [bold]{selected_host.name}[/bold]...", style="green"
        )
        send_wake_on_lan(selected_host, proxy)
        sleep(5)

    console.print(
        f"Connecting to [bold]{selected_host.name}[/bold]...", style="green"
    )
    subprocess.run(["ssh", selected_host.name], check=True)


if __name__ == "__main__":
    cli()
