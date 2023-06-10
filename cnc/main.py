import subprocess
from pathlib import Path
from time import sleep
from typing import Any, NewType, Optional, TypeVar, TypedDict
from typing_extensions import NotRequired
import click
import yaml
from pydantic import BaseModel, parse_obj_as, validator
from rich.console import Console
from typing_extensions import Self


console = Console()

CONFIG_DIR = Path.home() / ".config/cnc"
CONFIG_FILE = CONFIG_DIR / "config.yml"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)

HostKey = NewType("HostKey", str)


class BaseHost(BaseModel):
    name: HostKey
    ip: Optional[str]
    user: Optional[str]
    port: int = 22


class Host(BaseHost):
    mac: str
    proxy: HostKey


class ProxyHost(BaseHost):
    ...


T = TypeVar("T", Host, ProxyHost)

S = TypeVar("S")


class ConfigDict(TypedDict):
    hosts: list[dict[str, str | int]]
    proxy_hosts: list[dict[str, str | int]]
    default_host: NotRequired[str]


class CNCConfig(BaseModel):
    proxy_hosts: dict[HostKey, ProxyHost]
    hosts: dict[HostKey, Host]
    default_host: Optional[HostKey] = None

    @validator("default_host")
    def default_host_exists(
        cls, default_host: Optional[HostKey], values: dict[str, Any]
    ):
        if default_host and default_host not in values["hosts"]:
            raise ValueError(f"Default host {default_host} not found in hosts list.")
        return default_host

    @validator("hosts")
    def hosts_have_valid_proxies(
        cls, hosts: dict[HostKey, Host], values: dict[str, Any]
    ):
        for hostname, host in hosts.items():
            if host.proxy not in values["proxy_hosts"]:
                raise ValueError(
                    f"Proxy host {host.proxy} for Host {hostname} not found in proxy hosts."
                )
        return hosts

    @classmethod
    def from_dict(cls, config_dict: ConfigDict) -> Self:
        return parse_obj_as(
            cls,
            {
                "hosts": {
                    host["name"]: Host.parse_obj(host) for host in config_dict["hosts"]
                },
                "proxy_hosts": {
                    host["name"]: ProxyHost.parse_obj(host)
                    for host in config_dict["proxy_hosts"]
                },
                "default_host": config_dict.get("default_host"),
            },
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
@click.argument("host", required=False)
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
    hostname = HostKey(hostname or (config.default_host or ""))
    host = config.hosts.get(hostname)
    selected_host = host or select_highpower_host(config.hosts)
    proxy = config.proxy_hosts[config.hosts[selected_host.name].proxy]

    if not is_host_online(selected_host, proxy):
        console.print(f"Waking up [bold]{selected_host.name}[/bold]...", style="green")
        send_wake_on_lan(selected_host, proxy)
        sleep(5)

    console.print(f"Connecting to [bold]{selected_host.name}[/bold]...", style="green")
    subprocess.run(["ssh", selected_host.name], check=True)
