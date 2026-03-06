#!/usr/bin/env python3
"""Automate VLESS + Reality + Vision deployment for Linux VPS."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

XRAY_CONFIG_DEFAULT = "/usr/local/etc/xray/config.json"
XRAY_INSTALL_COMMAND = (
    'bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install'
)


class DeploymentError(RuntimeError):
    """Raised when deployment cannot continue safely."""


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


def run_cmd(cmd, check: bool = True, shell: bool = False) -> CommandResult:
    proc = subprocess.run(
        cmd,
        shell=shell,
        text=True,
        capture_output=True,
        executable="/bin/bash" if shell else None,
    )
    if check and proc.returncode != 0:
        raise DeploymentError(
            f"command failed: {cmd}\nexit={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return CommandResult(proc.stdout.strip(), proc.stderr.strip(), proc.returncode)


def parse_os_release_text(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.lower()] = value.strip().strip('"').strip("'")
    return {"id": parsed.get("id", ""), "id_like": parsed.get("id_like", "")}


def distro_tokens(distro_id: str, distro_like: str) -> set[str]:
    tokens = set()
    for raw in (distro_id, distro_like):
        for token in raw.lower().replace(",", " ").split():
            tokens.add(token)
    return tokens


def get_upgrade_commands(distro_id: str, distro_like: str) -> list[list[str]]:
    tokens = distro_tokens(distro_id, distro_like)
    if "arch" in tokens:
        return [["pacman", "-Syu", "--noconfirm"]]
    if {"debian", "ubuntu"} & tokens:
        return [["apt", "update"], ["apt", "upgrade", "-y"]]
    if {"rhel", "fedora", "centos", "rocky", "almalinux"} & tokens:
        return [["dnf", "upgrade", "--refresh", "-y"]]
    raise DeploymentError(f"unsupported distro for package upgrade: id={distro_id}, like={distro_like}")


def get_firewall_open_command(distro_id: str, distro_like: str, port: int) -> list[str] | None:
    tokens = distro_tokens(distro_id, distro_like)
    if {"debian", "ubuntu"} & tokens:
        return ["ufw", "allow", f"{port}/tcp"]
    if {"rhel", "fedora", "centos", "rocky", "almalinux"} & tokens:
        return ["firewall-cmd", "--permanent", f"--add-port={port}/tcp"]
    return None


def get_sysctl_path(distro_id: str, distro_like: str) -> str:
    tokens = distro_tokens(distro_id, distro_like)
    if "arch" in tokens:
        return "/etc/sysctl.d/99-xray-reality.conf"
    return "/etc/sysctl.conf"


def get_sysctl_apply_command(distro_id: str, distro_like: str) -> list[str]:
    tokens = distro_tokens(distro_id, distro_like)
    if "arch" in tokens:
        return ["sysctl", "--system"]
    return ["sysctl", "-p"]


def detect_distro(args) -> tuple[str, str]:
    if args.distro_id:
        return args.distro_id.lower(), (args.distro_like or "").lower()
    if args.dry_run:
        return "ubuntu", "debian"
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        raise DeploymentError("/etc/os-release not found; pass --distro-id and --distro-like manually")
    parsed = parse_os_release_text(os_release.read_text(encoding="utf-8"))
    distro_id = parsed["id"].lower()
    distro_like = parsed["id_like"].lower()
    if not distro_id:
        raise DeploymentError("unable to parse distro id from /etc/os-release")
    return distro_id, distro_like


def parse_x25519_output(text: str) -> dict[str, str]:
    private_key = ""
    public_key = ""

    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = [p.strip() for p in line.split(":", 1)]
        key_norm = key.lower().replace(" ", "")

        if key_norm in {"privatekey", "private"}:
            private_key = value
        elif key_norm in {"publickey", "password", "public"}:
            public_key = value

    if not private_key or not public_key:
        raise DeploymentError(f"unable to parse x25519 output: {text}")

    return {"private_key": private_key, "public_key": public_key}


def validate_short_id(short_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{8,16}", short_id):
        raise DeploymentError("short-id must be 8-16 lowercase hex chars")
    return short_id


def generate_short_id(length: int = 16) -> str:
    if length < 8 or length > 16:
        raise DeploymentError("short-id length must be between 8 and 16")
    return secrets.token_hex(8)[:length]


def build_xray_config(
    *,
    port: int,
    uuid: str,
    server_name: str,
    private_key: str,
    short_id: str,
    dest: str | None = None,
) -> dict:
    target_dest = dest or f"{server_name}:{port}"
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "port": port,
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": uuid, "flow": "xtls-rprx-vision"}],
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": target_dest,
                        "xver": 0,
                        "serverNames": [server_name],
                        "privateKey": private_key,
                        "shortIds": [short_id],
                    },
                },
            }
        ],
        "outbounds": [{"protocol": "freedom"}],
    }


def ensure_root_or_die(dry_run: bool) -> None:
    if dry_run:
        return
    if os.geteuid() != 0:
        raise DeploymentError("please run as root (sudo)")


def ensure_sysctl_line(path: Path, key: str, value: str, dry_run: bool) -> None:
    expected = f"{key}={value}"
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    if any(line.strip() == expected for line in lines):
        return
    if dry_run:
        return
    with path.open("a", encoding="utf-8") as f:
        if lines and lines[-1].strip() != "":
            f.write("\n")
        f.write(expected + "\n")


def maybe_run(cmd, *, dry_run: bool, shell: bool = False, check: bool = True) -> CommandResult:
    if dry_run:
        shown = cmd if shell else " ".join(cmd)
        print(f"[dry-run] {shown}")
        return CommandResult("", "", 0)
    return run_cmd(cmd, check=check, shell=shell)


def detect_server_ip(dry_run: bool) -> str:
    if dry_run:
        return "<SERVER_IP>"
    res = run_cmd(["hostname", "-I"])
    ips = [x for x in res.stdout.split() if x]
    return ips[0] if ips else "<SERVER_IP>"


def ensure_xray_installed(args) -> None:
    xray_exists = run_cmd(["bash", "-lc", "command -v xray"], check=False)
    if xray_exists.returncode == 0:
        return
    if args.dry_run:
        print("[dry-run] xray not found, would install via official script")
        return
    if args.skip_install_xray:
        raise DeploymentError("xray not found and --skip-install-xray is set")
    maybe_run(XRAY_INSTALL_COMMAND, dry_run=args.dry_run, shell=True)


def setup_bbr(args, distro_id: str, distro_like: str) -> None:
    if args.skip_bbr:
        return
    sysctl_conf = Path(get_sysctl_path(distro_id, distro_like))
    ensure_sysctl_line(sysctl_conf, "net.core.default_qdisc", "fq", args.dry_run)
    ensure_sysctl_line(sysctl_conf, "net.ipv4.tcp_congestion_control", "bbr", args.dry_run)
    maybe_run(get_sysctl_apply_command(distro_id, distro_like), dry_run=args.dry_run)


def write_config(path: Path, config: dict, dry_run: bool) -> None:
    rendered = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        print(f"[dry-run] write config -> {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def gather_identity(args) -> tuple[str, str, str, str]:
    if args.uuid:
        uuid = args.uuid
    else:
        uuid = maybe_run(["xray", "uuid"], dry_run=args.dry_run).stdout or "<UUID>"

    if args.private_key and args.public_key:
        private_key = args.private_key
        public_key = args.public_key
    elif args.private_key or args.public_key:
        raise DeploymentError("private-key and public-key must be provided together")
    else:
        key_output = maybe_run(["xray", "x25519"], dry_run=args.dry_run).stdout
        if args.dry_run:
            private_key = "<PRIVATE_KEY>"
            public_key = "<PUBLIC_KEY>"
        else:
            parsed = parse_x25519_output(key_output)
            private_key = parsed["private_key"]
            public_key = parsed["public_key"]

    short_id = validate_short_id(args.short_id or generate_short_id(16))
    return uuid, private_key, public_key, short_id


def deploy(args) -> None:
    ensure_root_or_die(args.dry_run)
    distro_id, distro_like = detect_distro(args)

    if not args.skip_upgrade:
        for cmd in get_upgrade_commands(distro_id, distro_like):
            maybe_run(cmd, dry_run=args.dry_run)

    setup_bbr(args, distro_id, distro_like)
    ensure_xray_installed(args)

    uuid, private_key, public_key, short_id = gather_identity(args)

    config = build_xray_config(
        port=args.port,
        uuid=uuid,
        server_name=args.server_name,
        private_key=private_key,
        short_id=short_id,
        dest=args.dest,
    )
    config_path = Path(args.config_path)
    write_config(config_path, config, args.dry_run)

    if args.print_config:
        print(json.dumps(config, indent=2, ensure_ascii=False))

    if not args.skip_firewall:
        firewall_cmd = get_firewall_open_command(distro_id, distro_like, args.port)
        if firewall_cmd is not None:
            maybe_run(firewall_cmd, dry_run=args.dry_run, check=False)
            if firewall_cmd[0] == "firewall-cmd":
                maybe_run(["firewall-cmd", "--reload"], dry_run=args.dry_run, check=False)

    maybe_run(["xray", "-test", "-config", args.config_path], dry_run=args.dry_run)
    maybe_run(["systemctl", "enable", "xray"], dry_run=args.dry_run)
    maybe_run(["systemctl", "restart", "xray"], dry_run=args.dry_run)

    server_ip = args.server_ip or detect_server_ip(args.dry_run)

    print("\n=== CLIENT PROFILE ===")
    print(f"Protocol: VLESS")
    print(f"Address: {server_ip}")
    print(f"Port: {args.port}")
    print(f"UUID: {uuid}")
    print("Flow: xtls-rprx-vision")
    print("TLS: reality")
    print(f"SNI: {args.server_name}")
    print(f"PublicKey: {public_key}")
    print(f"ShortId: {short_id}")
    print("Fingerprint: chrome")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deploy Xray VLESS + Reality + Vision on Linux VPS"
    )
    parser.add_argument("--port", type=int, default=443, help="inbound port")
    parser.add_argument("--server-name", default="www.microsoft.com", help="Reality SNI")
    parser.add_argument("--dest", default=None, help="Reality dest, default server-name:port")
    parser.add_argument("--uuid", default=None, help="existing VLESS UUID")
    parser.add_argument("--private-key", default=None, help="existing Reality private key")
    parser.add_argument("--public-key", default=None, help="existing Reality public key")
    parser.add_argument("--short-id", default=None, help="8-16 lowercase hex")
    parser.add_argument("--config-path", default=XRAY_CONFIG_DEFAULT, help="xray config path")
    parser.add_argument("--server-ip", default=None, help="override output server ip")
    parser.add_argument("--distro-id", default=None, help="override distro id, e.g. ubuntu/rocky/arch")
    parser.add_argument("--distro-like", default=None, help="override distro id_like, e.g. debian/rhel")

    parser.add_argument("--skip-upgrade", action="store_true", help="skip system package upgrade")
    parser.add_argument("--skip-bbr", action="store_true", help="skip BBR setup")
    parser.add_argument(
        "--skip-firewall",
        action="store_true",
        dest="skip_firewall",
        help="skip firewall open-port step",
    )
    parser.add_argument(
        "--skip-ufw",
        action="store_true",
        dest="skip_firewall",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--skip-install-xray", action="store_true", help="skip xray install when not found"
    )

    parser.add_argument("--dry-run", action="store_true", help="print actions only")
    parser.add_argument("--print-config", action="store_true", help="print generated config")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        deploy(args)
    except DeploymentError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("[error] interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
