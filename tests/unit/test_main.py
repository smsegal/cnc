from rich.console import Console

from hypothesis import given, strategies as st

from cnc.main import CNCConfig, ConfigDict, Host

console = Console()
mac_addresses = st.text(alphabet="0123456789abcdef", min_size=12, max_size=12).map(
    lambda s: ":".join(s[i : i + 2] for i in range(0, len(s), 2))
)


@st.composite
def config_dicts(draw: st.DrawFn) -> ConfigDict:
    host_name_strategy = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_1234567890", min_size=1
    )
    host_names = draw(st.lists(host_name_strategy, min_size=1, unique=True))
    proxy_host_names = draw(st.lists(host_name_strategy, min_size=1, unique=True))
    proxy_hosts = [
        draw(
            st.fixed_dictionaries(
                {
                    "name": st.just(pname),
                    "port": st.integers(min_value=1, max_value=65535),
                },
                optional={
                    "ip": st.ip_addresses().map(str),
                    "user": st.text(),
                },
            )
        )
        for pname in proxy_host_names
    ]

    hosts = [
        draw(
            st.fixed_dictionaries(
                {
                    "name": st.just(host_name),
                    "mac": mac_addresses,
                    "port": st.integers(min_value=1, max_value=65535),
                    "proxy": st.sampled_from(proxy_host_names),
                },
                optional={
                    "ip": st.ip_addresses().map(str),
                    "user": st.text(),
                },
            )
        )
        for host_name in host_names
    ]
    if draw(st.booleans()):
        default_host = {"default_host": st.sampled_from(host_names)}
    else:
        default_host = {}
    return draw(
        st.builds(
            ConfigDict,
            hosts=st.just(hosts),
            proxy_hosts=st.just(proxy_hosts),
            **default_host
        )
    )


@given(config_dicts())
def test_config_from_dict(config_dict: ConfigDict):
    cnc_config = CNCConfig.from_dict(config_dict)
    assert cnc_config.hosts
    if cnc_config.default_host:
        assert cnc_config.default_host in cnc_config.hosts

    for host in cnc_config.hosts.values():
        assert isinstance(host, Host)
        assert host.proxy in cnc_config.proxy_hosts
