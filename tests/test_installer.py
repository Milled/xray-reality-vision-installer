import unittest

from reality_installer import (
    build_xray_config,
    get_firewall_open_command,
    get_sysctl_apply_command,
    get_sysctl_path,
    get_upgrade_commands,
    parse_os_release_text,
    parse_x25519_output,
)


class ParseX25519OutputTests(unittest.TestCase):
    def test_parse_legacy_public_key_output(self):
        output = "PrivateKey: pri_key\nPublicKey: pub_key\n"
        parsed = parse_x25519_output(output)
        self.assertEqual(parsed["private_key"], "pri_key")
        self.assertEqual(parsed["public_key"], "pub_key")

    def test_parse_password_alias_output(self):
        output = "Private key: pri_key\nPassword: pub_key\n"
        parsed = parse_x25519_output(output)
        self.assertEqual(parsed["private_key"], "pri_key")
        self.assertEqual(parsed["public_key"], "pub_key")


class BuildXrayConfigTests(unittest.TestCase):
    def test_build_reality_config_contains_vision_and_reality(self):
        cfg = build_xray_config(
            port=443,
            uuid="u-1",
            server_name="www.microsoft.com",
            private_key="pri",
            short_id="6baad05011122233",
        )

        inbound = cfg["inbounds"][0]
        client = inbound["settings"]["clients"][0]
        reality = inbound["streamSettings"]["realitySettings"]

        self.assertEqual(inbound["protocol"], "vless")
        self.assertEqual(client["flow"], "xtls-rprx-vision")
        self.assertEqual(inbound["streamSettings"]["security"], "reality")
        self.assertEqual(reality["serverNames"], ["www.microsoft.com"])
        self.assertEqual(reality["dest"], "www.microsoft.com:443")


class DistroAdapterTests(unittest.TestCase):
    def test_parse_os_release_prefers_id_like(self):
        parsed = parse_os_release_text(
            'ID=rocky\nID_LIKE="rhel fedora"\nNAME="Rocky Linux"\n'
        )
        self.assertEqual(parsed["id"], "rocky")
        self.assertEqual(parsed["id_like"], "rhel fedora")

    def test_upgrade_commands_for_debian(self):
        cmds = get_upgrade_commands("ubuntu", "debian")
        self.assertEqual(cmds, [["apt", "update"], ["apt", "upgrade", "-y"]])

    def test_upgrade_commands_for_rhel(self):
        cmds = get_upgrade_commands("rocky", "rhel fedora")
        self.assertEqual(cmds, [["dnf", "upgrade", "--refresh", "-y"]])

    def test_upgrade_commands_for_arch(self):
        cmds = get_upgrade_commands("arch", "")
        self.assertEqual(cmds, [["pacman", "-Syu", "--noconfirm"]])

    def test_firewall_command_debian_uses_ufw(self):
        cmd = get_firewall_open_command("ubuntu", "debian", 443)
        self.assertEqual(cmd, ["ufw", "allow", "443/tcp"])

    def test_firewall_command_rhel_uses_firewalld(self):
        cmd = get_firewall_open_command("rocky", "rhel fedora", 443)
        self.assertEqual(
            cmd,
            ["firewall-cmd", "--permanent", "--add-port=443/tcp"],
        )

    def test_firewall_command_arch_returns_none(self):
        cmd = get_firewall_open_command("arch", "", 443)
        self.assertIsNone(cmd)

    def test_sysctl_path_arch_uses_sysctl_d(self):
        path = get_sysctl_path("arch", "")
        self.assertEqual(path, "/etc/sysctl.d/99-xray-reality.conf")

    def test_sysctl_apply_arch(self):
        cmd = get_sysctl_apply_command("arch", "")
        self.assertEqual(cmd, ["sysctl", "--system"])


if __name__ == "__main__":
    unittest.main()
