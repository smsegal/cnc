import subprocess
from pathlib import Path
from time import sleep
from typing import NewType, Optional, Type, TypeVar

import click
import yaml
from pydantic import BaseModel
from rich.console import Console
from typing_extensions import Self

console = Console()

CONFIG_DIR = Path.home() / ".config/cnc"
CONFIG_FILE = CONFIG_DIR / "config.yml"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)


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

S = TypeVar("S")

# recursive dict type
RecDict = dict[str, S | dict[str, "RecDict[S]"]]


class CNCConfig(BaseModel):
    default_host: Optional[HostKey] = None
    hosts: dict[HostKey, Host]
    proxy_hosts: dict[HostKey, ProxyHost]

    @classmethod
    def from_dict(cls, config_dict: dict[str, RecDict[str]]) -> Self:
        def _parse_host(
            host_type: Type[T], host_dict: RecDict[str]
        ) -> dict[HostKey, T]:
            parsed_dict: dict[HostKey, T] = {}
            for k, v in host_dict.items():
                hostkey = HostKey(k)
                if isinstance(v, dict):
                    parsed_dict[hostkey] = host_type.parse_obj({"name": hostkey, **v})
                else:
                    raise ValueError(f"Invalid host configuration: {k}")
            return parsed_dict

        hosts = _parse_host(Host, config_dict["hosts"])
        proxy_hosts = _parse_host(ProxyHost, config_dict["proxy_hosts"])
        default_host = config_dict.get("default_host", "")
        if isinstance(default_host, str):
            default_host = HostKey(default_host)
        else:
            raise ValueError(
                f"Invalid default host configuration, expected name of host, got {default_host}"
            )
        return cls(
            default_host=HostKey(default_host),
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


if __name__ == "__main__":
    cli()