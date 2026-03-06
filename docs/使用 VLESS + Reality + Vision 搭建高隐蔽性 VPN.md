
# 使用 VLESS + Reality + Vision 搭建高隐蔽性 VPN

> [!IMPORTANT]
> 1. 本文大部分由 AI 生成，但我花了大量时间整理和验证正确性，对于想要自己搭建 Reality 节点的朋友应该很有帮助。如果你介意 AI 产出的内容，现在是你退出的最佳时机。
> 2. 实际上这篇里的内容是我在安装过程中，多次询问 Gemini 和 ChatGPT，从海量垃圾信息中挑出有用的，并最终实际部署成功后整理的。我整理的目的是为了我将来再次部署时不用重新来一遍，顺便分享出来，所以正确性不用怀疑。

## Reality 介绍
Reality 是 Xray-core 的现代传输协议（2021 年后流行），它使用 uTLS 模拟真实 TLS 握手，能更好地绕过主动探测和 DPI（深度包检测）。它无需自定义域名/TLS 配置，就能实现“真实 TLS”伪装，安全性高于传统 TLS，且支持 Dual-Mode（XHTTP + TCP）。在伊朗和中国社区，许多人切换到 Reality，因为它在重度过滤下更稳定，能自动旋转指纹（fingerprint）避免检测。

相比之下，**Trojan 并没有在技术上彻底失效，但在高强度审查面前，它已经从“隐形斗篷”变成了“半透明薄纱”。**

## 🛡️ 协议现状：Trojan vs. Reality (2026)

| 特性 | Trojan (Legacy) | Reality (Modern Meta) |
| --- | --- | --- |
| **伪装原理** | 模仿 HTTPS 流量（依赖真实域名/证书） | 借用他人的 TLS 握手特征 (uTLS) |
| **抗主动探测** | **弱**。审查系统易通过模拟客户端发现响应异常 | **极强**。通过消除特征指纹让流量完全融入背景 |
| **配置复杂度** | 较高（需购买域名、配置证书、防泄露） | **极低**。无需域名和证书，即开即用 |
| **安全性** | 受限于特定实现（如 CVE-2025-5525 漏洞风险） | 动态指纹旋转，安全性随 Xray 内核实时更新 |
| **适用场景** | 跨境办公、中轻度审查地区 | 深度审查地区（伊朗、中国等）的“保命”选 |

## 🚀 为什么 Reality 是 2026 年的“真香”选择？

Reality 的核心逻辑是：**“如果你不能打败他们，就加入他们。”** 它直接借用像微软、谷歌或雅虎这类大厂的 TLS 握手特征。审查系统很难封锁这类流量，因为一旦误杀，可能会导致正常的互联网业务大面积瘫痪。

> **核心优势总结：**
> * **消除指纹：** 解决了 Trojan 最致命的被动检测问题。
> * **成本更低：** 你不需要再去 Namesilo 或 Cloudflare 买域名了。
> * **Dual-Mode 支持：** 配合 XHTTP 可以在极端恶劣的移动网络环境下依然保持连接感。

如果你身处审查严苛的地区，**Trojan 确实已经进入了“遗产模式” (Legacy Mode)**。除非你有特殊的业务需求必须使用标准 HTTPS 代理，否则切换到 Reality 几乎是 2026 年的必经之路。

## 如何安装

> 我是在 Ubuntu 24.04 上安装的，其他 Linux 发行版也类似。

在 2026 年，基于 Ubuntu 24.04 (Noble Numbat) 搭建 Xray-core 的 Reality 协议已经非常成熟且简化。Reality 最大的优势在于**无需购买域名**和**证书**，它直接“借用”现有的知名网站（如 Microsoft、Apple、Amazon）的 TLS 特征。

以下是搭建指南。

---

### 第一步：服务器基础环境优化

首先，确保你的 Ubuntu 24 系统是最新的，并开启 BBR（拥塞控制算法）以提升网络吞吐量。

1. **更新系统：**
```bash
sudo apt update && sudo apt upgrade -y

```


2. **开启 BBR：**
```bash
echo "net.core.default_qdisc=fq" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

```


*检查是否生效：* `sysctl net.ipv4.tcp_congestion_control`（显示 `bbr` 即表示成功）。

---

### 第二步：安装 Xray-core

使用 XTLS 官方维护的安装脚本，这是目前最推荐、最干净的方式。

1. **执行安装命令：**
```bash
# 该脚本会自动下载 2026 年最新的 v26.x.x 版本并配置 systemd
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

```


2. **生成必要的密钥：**
你需要生成一个 **UUID**（用户 ID）和一对 **x25519 密钥**（用于 Reality 握手）。
```bash
# 生成 UUID
xray uuid
# 生成 Reality 密钥对
xray x25519

```


**请记录下生成的 UUID、Private key（私钥）和 Password(Public key)（公钥），稍后要填入配置文件。**

> 补充说明：旧版本的 `xray x25519` 输出 PrivateKey 和 PublicKey，2026 年的最新版本输出的没有 PublicKey 字段，而是一个 Password 字段，实际就是 PublicKey。请根据你安装的版本输出结果来填写配置文件。

---

### 第三步：配置 Reality 服务端

创建并编辑配置文件 `/usr/local/etc/xray/config.json`。我们将使用 **VLESS + REALITY + Vision** 组合，这是目前公认的隐蔽性天花板。

> **提示：** `dest` 建议选择一个在你服务器本地访问延迟低、且支持 TLS 1.3 的大站。

```json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 443, 
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "你的UUID", // 填入刚才生成的 UUID
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.microsoft.com:443", // 目标网站：端口
          "xver": 0,
          "serverNames": [
            "www.microsoft.com" // 目标网站域名
          ],
          "privateKey": "你的私钥", // 填入刚才生成的 Private Key
          "shortIds": [
            "6baad05011122233" // 填入 8 到 16 位的 16 进制字符串（随便写）
          ]
        }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom"
    }
  ]
}

```

---

### 第四步：开放防火墙与启动服务

Ubuntu 24 默认可能启用了 `ufw` 或控制台安全组限制。

1. **开放 443 端口：**
```bash
sudo ufw allow 443/tcp

```


2. **检查配置并启动：**
```bash
# 验证配置是否有误
xray -test -config /usr/local/etc/xray/config.json

# 启动并设置开机自启
sudo systemctl enable xray
sudo systemctl restart xray

```



---

### 第五步：客户端如何连接？

客户端推荐：
- Windows/Linux/macOS: [v2rayN](https://github.com/2dust/v2rayN)
- Android: [v2rayNG](https://github.com/2dust/v2rayNG)
- iOS: [Shadowrocket](https://apps.apple.com/app/id932747118)

在你的客户端中填入以下关键参数：

* **协议：** VLESS
* **地址/IP：** 你的 VPS 公网 IP
* **端口：** 443
* **UUID：** 你生成的 UUID
* **流控 (Flow)：** `xtls-rprx-vision`
* **传输层安全 (TLS)：** REALITY
* **SNI：** `www.microsoft.com` (必须与服务端 dest 一致)
* **PublicKey：** 你生成的 **Public Key** (公钥)
* **ShortId：** 你在配置中写的 shortId
* **指纹 (Fingerprint)：** chrome 或 firefox

---

以 v2rayN 为例，配置界面如图所示：
![v2rayN Reality 配置示例](../../Assets/v2rayN-1.png)

配置好后不要忘了开启代理，默认是没开的：
![v2rayN 开启代理](../../Assets/v2rayN-2.png)

### 🛡️ 进阶提示：如何判断伪装是否成功？

在 2026 年，如果审查系统对你的 IP 进行探测，它们会看到一个完全正常的 Microsoft 官网证书和响应，而由于你开启了 `xtls-rprx-vision`，你的大流量传输特征也会被重塑，从而绕过 DPI。

