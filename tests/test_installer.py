import io
import unittest
from contextlib import redirect_stdout

from reality_installer import (
    CommandResult,
    build_parser,
    command_not_found_hint,
    DeploymentError,
    build_xray_config,
    get_firewall_open_command,
    get_sysctl_apply_command,
    get_sysctl_path,
    get_upgrade_commands,
    parse_os_release_text,
    parse_x25519_output,
    print_client_profile,
    run_cmd,
    warn_optional_failure,
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


class RunCommandBehaviorTests(unittest.TestCase):
    def test_run_cmd_missing_binary_with_check_false_returns_nonzero_result(self):
        result = run_cmd(["definitely-not-a-real-command-123"], check=False)
        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stdout, "")

    def test_run_cmd_missing_binary_with_check_true_raises_deployment_error(self):
        with self.assertRaises(DeploymentError):
            run_cmd(["definitely-not-a-real-command-123"], check=True)

    def test_run_cmd_missing_xray_includes_install_hint(self):
        with self.assertRaisesRegex(DeploymentError, r"install xray first"):
            run_cmd(["xray", "-test", "-config", "/tmp/xray.json"], check=True)

    def test_command_not_found_hint_for_systemctl(self):
        self.assertIn("systemd-based Linux", command_not_found_hint("systemctl"))


class OptionalStepWarningTests(unittest.TestCase):
    def test_warn_optional_failure_for_missing_command(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            warn_optional_failure(
                "open firewall port",
                ["ufw", "allow", "443/tcp"],
                CommandResult("", "missing", 127),
            )
        self.assertIn("optional step skipped", buffer.getvalue())
        self.assertIn("command not found", buffer.getvalue())
        self.assertIn("firewall rules may be unchanged", buffer.getvalue())

    def test_warn_optional_failure_for_nonzero_exit(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            warn_optional_failure(
                "reload firewalld",
                ["firewall-cmd", "--reload"],
                CommandResult("", "firewalld not running", 1),
            )
        self.assertIn("optional step failed", buffer.getvalue())
        self.assertIn("firewalld not running", buffer.getvalue())
        self.assertIn("firewall rules may be unchanged", buffer.getvalue())


class ClientProfileOutputTests(unittest.TestCase):
    def test_print_client_profile_includes_config_path_and_save_reminder(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_client_profile(
                server_ip="1.2.3.4",
                port=443,
                uuid="u-1",
                server_name="www.microsoft.com",
                public_key="pub",
                short_id="6baad05011122233",
                config_path="/usr/local/etc/xray/config.json",
                config_written="yes",
            )
        output = buffer.getvalue()
        self.assertIn("ConfigPath: /usr/local/etc/xray/config.json", output)
        self.assertIn("ConfigWritten: yes", output)
        self.assertIn("请务必将这些信息妥善保存，客户端连接时需要用到。", output)


class ParserTests(unittest.TestCase):
    def test_parser_accepts_verbose_flag(self):
        args = build_parser().parse_args(["--verbose"])
        self.assertTrue(args.verbose)


if __name__ == "__main__":
    unittest.main()
