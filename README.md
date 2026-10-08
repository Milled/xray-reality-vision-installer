# Xray Reality Vision Installer

Python3 自动化部署脚本，用于在 Linux VPS 上一键搭建 `VLESS + Reality + Vision`（Xray-core）。

一键安装命令：

```bash
curl -fsSL https://raw.githubusercontent.com/cholf5/xray-reality-vision-installer/main/reality_installer.py | sudo python3 -
```

## 功能

- 可选执行系统升级（按发行版自动选择包管理器）
- 自动开启 BBR（`fq + bbr`）
- 自动安装 Xray（官方脚本）
- 自动生成 UUID / x25519 密钥
- 自动生成并写入 `/usr/local/etc/xray/config.json`
- 开放防火墙端口（按发行版适配 `ufw` 或 `firewalld`）
- `xray -test` 校验配置
- `systemctl enable/restart xray`
- 输出客户端连接参数（UUID/PublicKey/ShortId 等）

## 已适配发行版

- Debian / Ubuntu（`apt` + `ufw`）
- RHEL 系（CentOS / Rocky / Alma / Fedora，`dnf` + `firewalld`）
- Arch Linux（`pacman`，默认不自动改防火墙）

> 脚本会读取 `/etc/os-release` 自动识别。必要时可通过参数手动覆盖。

## 环境要求

- `python3`
- root 权限（建议 `sudo`）

## 本地执行

```bash
sudo python3 reality_installer.py
```

常用参数示例：

```bash
sudo python3 reality_installer.py \
  --server-name www.microsoft.com \
  --port 443 \
  --skip-upgrade
```

手动指定发行版（极少数识别异常时）：

```bash
sudo python3 reality_installer.py --distro-id arch --distro-like ""
```

## 一键安装（curl | python3）

```bash
curl -fsSL https://raw.githubusercontent.com/Milled/xray-reality-vision-installer/main/reality_installer.py | sudo python3 -
```

带参数示例：

```bash
curl -fsSL https://raw.githubusercontent.com/cholf5/xray-reality-vision-installer/main/reality_installer.py | \
  sudo python3 - --server-name www.microsoft.com --port 443 --skip-upgrade
```

## 预演模式（不改系统）

```bash
python3 reality_installer.py --dry-run
```

## 输出参数（用于 v2rayN / v2rayNG / Shadowrocket）

脚本最后会输出：

- Protocol: `VLESS`
- Address: VPS IP
- Port
- UUID
- Flow: `xtls-rprx-vision`
- TLS: `reality`
- SNI
- PublicKey
- ShortId
- Fingerprint: `chrome`

> [!IMPORTANT]
> **请务必将这些信息妥善保存，客户端连接时需要用到。**

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 关键参数

- `--skip-upgrade`: 跳过系统升级
- `--skip-bbr`: 跳过 BBR 设置
- `--skip-firewall`: 跳过防火墙端口开放（通用防火墙跳过开关）
- `--distro-id`, `--distro-like`: 手动覆盖发行版识别
- `--dry-run`: 只打印操作，不改系统

## 免责声明

请确保在你所在地区和使用场景下合法合规。你需要自行承担部署和使用该脚本的风险。
