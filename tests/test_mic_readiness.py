"""Offline fixtures only: no robot connection, device access or settings change."""

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import reachy_mic_readiness as m
from scripts import read_reachy_mic_readiness as launcher


MEMORY = "MemTotal: 4000000 kB\nMemAvailable: 2500000 kB\nSwapTotal: 2097148 kB\nSwapFree: 2097148 kB\n"
SWAPS = "Filename\tType\tSize\tUsed\tPriority\n/dev/zram0 partition 2097148 0 100\n"
LIMITS = "Max core file size        0        unlimited        bytes\n"


def stat(pid=940, start=12345):
    return f"{pid} (python ) odd name) " + " ".join(["S", "927"] + ["0"] * 17 + [str(start), "0", "0"])


class FakeReader:
    def __init__(self):
        self.files = {"/proc/meminfo": MEMORY, "/proc/swaps": SWAPS,
                      "/proc/self/limits": LIMITS, "/proc/940/limits": LIMITS,
                      "/proc/940/cmdline": "python\0" + "\0".join(m.DAEMON_ARGS) + "\0",
                      "/proc/940/stat": stat(),
                      "/proc/940/status": "Uid:\t1000 1000 1000 1000\nVmRSS:\t125000 kB\n",
                      "/proc/940/task/940/children": "",
                      "/sys/block/zram0/backing_dev": "/dev/loop0\n",
                      "/sys/block/loop0/loop/backing_file": "/var/swap\n",
                      "/proc/sys/kernel/core_pattern": "core\n",
                      "/etc/fstab": "# comment\nUUID=not-swap / ext4 defaults 0 1\n"}
        self.commands = []
        self.routes = []
        self.listings = []

    def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def names(self, path):
        if path == "/proc":
            return ["940", "not-a-pid"]
        if path == "/proc/940/task":
            return ["940"]
        raise FileNotFoundError(path)

    def run(self, args, accepted=(0,)):
        self.commands.append(args)
        if args[0] == "fuser":
            return "940\n"
        if args[0] == "findmnt":
            return '{"filesystems":[{"target":"/","source":"/dev/mmcblk0p2","fstype":"ext4"}]}'
        if args[1] == "list-units":
            return ("rpi-swap.service loaded active exited\ndev-zram0.swap loaded active active\n"
                    "systemd-zram-setup@zram0.service loaded active exited\n"
                    "rpi-setup-loop@var-swap.service loaded active exited\n"
                    "private-app.service loaded active running\n")
        if args[1] == "list-unit-files":
            return ("rpi-swap.service enabled enabled\nsystemd-zram-setup@.service static -\n"
                    "rpi-remove-swap-file@.service static -\n")
        return "Id=" + args[2] + "\nActiveState=active\n"

    def get(self, route):
        self.routes.append(route)
        if route == "/api/apps/current-app-status":
            return None
        return {"state": "stopped", "version": "1.9.0", "error": None,
                "simulation_enabled": False, "mockup_sim_enabled": False,
                "wireless_version": True, "no_media": False, "media_released": False,
                "backend_status": {"ready": True, "motor_control_mode": "disabled", "error": None}}

    def policy_listing(self, command):
        self.listings.append(command)
        return {"candidate_command": command, "candidate_executed": False,
                "future_execution_privilege_verified": False}


class ParsingTests(unittest.TestCase):
    def test_memory_units_and_required_fields(self):
        self.assertEqual(m.parse_memory(MEMORY)["MemAvailable_KiB"], 2500000)
        for invalid in (MEMORY.replace("kB", "MB"), "MemTotal: 123 kB\n"):
            with self.assertRaises(ValueError):
                m.parse_memory(invalid)

    def test_swap_records_not_pass(self):
        self.assertEqual(m.parse_swaps(SWAPS)[0]["priority"], 100)
        self.assertEqual(m.parse_swaps(SWAPS.splitlines()[0]), [])
        with self.assertRaises(ValueError):
            m.parse_swaps("error")

    def test_process_stat_with_spaces_parentheses(self):
        self.assertEqual(m.parse_identity(stat()), {"pid": 940, "ppid": 927, "start_ticks": 12345})

    def test_soft_and_hard_core_limits_distinct(self):
        self.assertEqual(m.parse_core_limits(LIMITS), {"soft_bytes": 0, "hard_bytes": "unlimited"})
        self.assertEqual(m.parse_core_limits(LIMITS.replace("0        unlimited", "100      200"))["hard_bytes"], 200)
        with self.assertRaises(ValueError):
            m.parse_core_limits("Max open files 1024 524288 files")

    def test_config_does_not_export_unrelated_values(self):
        result = m.filtered_config("# ignored\nPRIORITY=100\nTOKEN=private\n[zram0]\nzram-size=ram / 2\n")
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(result["unreported_active_lines"], 1)
        self.assertIn("PRIORITY=100", result["settings"])

    def test_rpi_headings_are_not_mislabelled_as_active_settings(self):
        fixture = "[Main]\n#Mechanism=auto\n[File]\n#Path=/var/swap\n[Zram]\n#WritebackTrigger=auto\n"
        result = m.filtered_config(fixture)
        self.assertEqual(result["settings"], ["[Main]", "[File]", "[Zram]"])
        self.assertEqual(result["unreported_active_lines"], 0)

    def test_rpi_swap_settings_retained_by_section(self):
        fixture = ("[Main]\nMechanism=zram+file\n[File]\nPath=/var/swap\nMaxDiskPercent=50\n"
                   "RamMultiplier=1\nMaxSizeMiB=2048\n[Zram]\nFixedSizeMiB=2048\n"
                   "WritebackTrigger=timer\nWritebackInitialDelay=180min\nWritebackPeriodicInterval=24h\n")
        result = m.filtered_config(fixture)
        self.assertEqual(result["settings"], fixture.splitlines())
        self.assertEqual(result["unreported_active_lines"], 0)


class ReportTests(unittest.TestCase):
    def collect(self, reader):
        with patch.object(m.shutil, "which", side_effect=lambda name: "/usr/bin/" + name), \
             patch.object(m.os, "geteuid", return_value=1000, create=True), \
             patch.object(m.os, "getgroups", return_value=[1000], create=True):
            return m.Report(reader).collect()

    def test_active_swap_does_not_hide_other_results(self):
        reader = FakeReader()
        report = self.collect(reader)
        self.assertFalse(report["execution_authorized"])
        checks = report["checks"]
        self.assertEqual(checks["swap_before"]["value"][0]["path"], "/dev/zram0")
        self.assertEqual(checks["daemon_process_940"]["value"]["core_limits"]["soft_bytes"], 0)
        self.assertEqual(checks["daemon_status"]["value"]["state"], "stopped")
        self.assertEqual(checks["memory_after"]["status"], "observed")
        self.assertEqual(reader.routes, list(m.STATUS_ROUTES))
        self.assertEqual(len(reader.listings), 2)
        self.assertEqual(checks["policy_core_940"]["status"], "not_needed")
        self.assertNotIn("private-app.service", json.dumps(report))
        json.dumps(report, allow_nan=False)

    def test_failure_does_not_stop_remaining_checks_or_leak_error_text(self):
        reader = FakeReader()
        del reader.files["/proc/meminfo"]
        reader.get = lambda route: (_ for _ in ()).throw(RuntimeError("private diagnostic text"))
        report = self.collect(reader)
        self.assertIn("memory_before", report["unavailable_checks"])
        self.assertEqual(report["checks"]["swap_after"]["status"], "observed")
        self.assertNotIn("private diagnostic text", json.dumps(report))

    def test_pid_reuse_rejected(self):
        reader = FakeReader()
        original = reader.read
        count = 0
        def changing(path):
            nonlocal count
            if path == "/proc/940/stat":
                count += 1
                return stat(start=count)
            return original(path)
        reader.read = changing
        with self.assertRaises(RuntimeError):
            m.Report(reader).process(940)

    def test_unrecognized_process_arguments_not_retained(self):
        reader = FakeReader()
        reader.files["/proc/940/cmdline"] = "python\0app.py\0--token\0private-token\0"
        item = m.Report(reader).process(940)
        self.assertFalse(item["reviewed_daemon_argv_match"])
        self.assertNotIn("private-token", json.dumps(item))

    def test_child_failures_not_daemon_failure(self):
        reader = FakeReader()
        reader.files["/proc/940/task/940/children"] = "941"
        report = self.collect(reader)
        self.assertEqual(report["checks"]["daemon_process_940"]["status"], "observed")
        self.assertIn("child_process_941", report["unavailable_checks"])

    def test_no_swap_does_not_authorize_execution(self):
        reader = FakeReader()
        reader.files["/proc/swaps"] = SWAPS.splitlines()[0]
        report = self.collect(reader)
        self.assertFalse(report["execution_authorized"])
        self.assertTrue(report["remaining_review"])
        self.assertNotIn("policy_swapon", report["checks"])

    def test_optional_absence_is_separate_from_unavailable(self):
        report = self.collect(FakeReader())
        name = "config_/etc/default/zramswap"
        self.assertIn(name, report["optional_not_present"])
        self.assertNotIn(name, report["unavailable_checks"])
        reader = FakeReader()
        original = reader.read
        def denied(path):
            if path == "/etc/default/zramswap":
                raise PermissionError("private error text")
            return original(path)
        reader.read = denied
        report = self.collect(reader)
        self.assertIn(name, report["unavailable_checks"])
        self.assertNotIn(name, report["optional_not_present"])

    def test_actual_instances_inspected_templates_not_queried(self):
        reader = FakeReader()
        report = self.collect(reader)
        inventories = [args for args in reader.commands if args[0] == "systemctl" and args[1].startswith("list-")]
        self.assertTrue(all(args[-4:] == ["--", *m.UNIT_PATTERNS] for args in inventories))
        shows = [args for args in reader.commands if args[:2] == ["systemctl", "show"]]
        self.assertFalse(any(args[2].endswith("@.service") for args in shows))
        self.assertIn("unit_systemd-zram-setup@zram0.service", report["checks"])
        self.assertIn("unit_rpi-setup-loop@var-swap.service", report["checks"])
        self.assertEqual(len(report["checks"]["swap_managers"]["value"]["templates_not_runtime_units"]), 2)
        for property_name in ("BindsTo", "BoundBy", "ExecStop", "TimersMonotonic", "NextElapseUSecMonotonic"):
            self.assertIn(property_name, m.UNIT_PROPERTIES)

    def test_dropins_read_but_never_sourced_or_executed(self):
        reader = FakeReader()
        original_names = reader.names
        directory = "/run/systemd/zram-generator.conf.d"
        path = directory + "/20-rpi-swap-zram0-ctrl.conf"
        reader.names = lambda name: ["20-rpi-swap-zram0-ctrl.conf"] if name == directory else original_names(name)
        reader.files[path] = "[zram0]\nfs-type=swap\nzram-size=2048\nwriteback-device=/dev/loop0\nTOKEN=private\n"
        report = self.collect(reader)
        value = report["checks"]["config_" + path]["value"]
        self.assertIn("writeback-device=/dev/loop0", value["settings"])
        self.assertEqual(value["unreported_active_lines"], 1)
        self.assertNotIn("private", json.dumps(value))

    def test_daemon_running_is_not_motor_mode(self):
        reader = FakeReader()
        status = reader.get(m.STATUS_ROUTES[0])
        status.update(state="running", mockup=False)
        status["backend_status"].update(secret="private", error="private traceback")
        reader.get = lambda route: status
        value = m.Report(reader).status()
        self.assertEqual(value["state"], "running")
        self.assertEqual(value["backend_status"]["motor_control_mode"], "disabled")
        self.assertTrue(value["backend_status"]["error_present"])
        self.assertFalse(value["mockup_sim_enabled"])
        self.assertNotIn("mockup", value)
        self.assertNotIn("private", json.dumps(value))
        self.assertEqual(value["unknown_fields"], [])

    def test_missing_or_malformed_status_not_silently_false(self):
        reader = FakeReader()
        reader.get = lambda route: {"state": "running", "mockup": False,
                                   "simulation_enabled": "false", "backend_status": {"motor_control_mode": "unknown"}}
        value = m.Report(reader).status()
        self.assertIsNone(value["mockup_sim_enabled"])
        self.assertIsNone(value["simulation_enabled"])
        self.assertIsNone(value["backend_status"]["motor_control_mode"])
        self.assertIn("mockup_sim_enabled", value["unknown_fields"])
        self.assertIn("backend_status.motor_control_mode", value["unknown_fields"])

    def test_nonzero_core_limit_policy_listing_retained(self):
        reader = FakeReader()
        reader.files["/proc/940/limits"] = LIMITS.replace("0        unlimited", "2048     unlimited")
        report = self.collect(reader)
        self.assertEqual(len(reader.listings), 4)
        self.assertFalse(report["checks"]["policy_core_restore_940"]["value"]["candidate_executed"])


class IOTests(unittest.TestCase):
    def test_mutating_commands_refused_before_subprocess(self):
        reader = m.Reader()
        with patch.object(m.subprocess, "run") as run:
            for command in (["swapoff", "/dev/zram0"], ["swapon", "/dev/zram0"],
                            ["systemctl", "stop", "rpi-swap.service"], ["arecord"],
                            ["fuser", "-k", "/dev/snd/pcmC0D0c"], ["prlimit", "--core=0"],
                            ["systemctl", "list-units", "--all"],
                            ["systemctl", "show", "private-app.service", "--no-pager",
                             "--property=" + ",".join(m.UNIT_PROPERTIES)]):
                with self.assertRaises(ValueError):
                    reader.run(command)
            run.assert_not_called()

    def test_sbin_fallback_is_lookup_only(self):
        with patch.object(m.shutil, "which", side_effect=[None, "/usr/sbin/swapoff"]) as which, \
             patch.object(m.subprocess, "run") as run:
            self.assertEqual(m.find_tool("swapoff"), "/usr/sbin/swapoff")
            self.assertEqual(which.call_args.kwargs, {"path": "/usr/sbin:/sbin:/usr/bin:/bin"})
            run.assert_not_called()

    def test_bounded_inventory_io_and_reason_codes(self):
        command = ["systemctl", "list-units", "--all", "--no-legend", "--plain", "--no-pager", "--", *m.UNIT_PATTERNS]
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"x" * (m.LIMIT + 1))):
            report = m.Report(m.Reader())
            report.probe("inventory", lambda: report.io.run(command))
            self.assertEqual(report.checks["inventory"]["reason"], "metadata_output_over_64KiB")
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=b"")):
            report = m.Report(m.Reader())
            report.probe("inventory", lambda: report.io.run(command))
            self.assertEqual(report.checks["inventory"]["reason"], "metadata_command_nonzero")
            self.assertEqual(report.checks["inventory"]["returncode"], 1)

    def test_policy_probe_lists_never_executes_candidate(self):
        reader = m.Reader()
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            result = reader.policy_listing(["/usr/sbin/swapoff", "/dev/zram0"])
            command = run.call_args.args[0]
            self.assertEqual(command[:6], ["sudo", "-n", "-k", "-l", "--", "/usr/sbin/swapoff"])
            self.assertFalse(result["candidate_executed"])
            self.assertFalse(result["future_execution_privilege_verified"])
            self.assertTrue(result["policy_lists_candidate"])

    def test_policy_listing_denial_is_not_privilege_verification(self):
        with patch.object(m.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
            result = m.Reader().policy_listing(["/usr/sbin/swapon", "--priority", "100", "/dev/zram0"])
            self.assertFalse(result["policy_lists_candidate"])
            self.assertFalse(result["future_execution_privilege_verified"])
            self.assertTrue(result["negative_result_may_mean_denied_or_authentication_required"])

    def test_expired_budget_does_not_start_command(self):
        reader = m.Reader()
        reader.deadline = 0
        with patch.object(m.subprocess, "run") as run:
            with self.assertRaises(TimeoutError):
                reader.run(["fuser", "/dev/snd/pcmC0D0c"])
            run.assert_not_called()

    def test_http_allowlist_and_redirect_refusal(self):
        with patch.object(m.urllib.request, "build_opener") as opener:
            for route in ("/api/audio/volume", "/api/move/goto", "https://example.com"):
                with self.assertRaises(ValueError):
                    m.Reader().get(route)
            opener.assert_not_called()
        with self.assertRaises(ValueError):
            m.NoRedirect().redirect_request(None)

    def test_collector_source_has_no_setting_or_file_writes(self):
        tree = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
        forbidden = {"setrlimit", "prlimit", "kill", "unlink", "mkdir", "write_bytes", "write_text", "exec", "eval"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                self.assertNotIn(name, forbidden)
                if name == "open" and isinstance(node.func, ast.Name):
                    self.assertEqual(node.args[1].value, "rb")


class LauncherTests(unittest.TestCase):
    def test_default_makes_no_connection(self):
        with patch.object(sys, "argv", ["readiness"]), patch.object(launcher.subprocess, "run") as run:
            self.assertEqual(launcher.main(), 0)
            run.assert_not_called()

    def test_transport_stdin_no_remote_file_or_capture(self):
        command = launcher.ssh_command()
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertEqual(command[-1], "/venvs/mini_daemon/bin/python -I -B - --report")
        self.assertNotIn("--execute", " ".join(command))

    def test_decoder_rejects_unexpected_contract(self):
        for data in ({}, {"schema": m.SCHEMA, "execution_authorized": True}, []):
            with self.assertRaises(ValueError):
                launcher.decode_report(json.dumps(data).encode())
        with self.assertRaises(ValueError):
            launcher.decode_report(b"x" * (1024 * 1024 + 1))

    def test_private_output_is_unique_and_source_identified(self):
        with tempfile.TemporaryDirectory() as directory:
            first = launcher.save_report({"schema": m.SCHEMA}, "fixture-hash", Path(directory))
            second = launcher.save_report({"schema": m.SCHEMA}, "fixture-hash", Path(directory))
            self.assertNotEqual(first, second)
            self.assertEqual(json.loads(first.read_text())["collector_source_sha256"], "fixture-hash")

    def test_collection_transports_only_report_and_saves_private_json(self):
        report = {"schema": m.SCHEMA, "execution_authorized": False,
                  "purpose": "read_only_metadata_review", "checks": {}, "unavailable_checks": []}
        result = SimpleNamespace(returncode=0, stdout=json.dumps(report).encode())
        with patch.object(launcher.subprocess, "run", return_value=result) as run, \
             patch.object(launcher, "save_report", return_value=Path("fixture-report.json")) as save:
            self.assertEqual(launcher.collect(), 0)
            self.assertEqual(run.call_args.args[0], launcher.ssh_command())
            self.assertEqual(run.call_args.kwargs["input"], Path(m.__file__).read_bytes())
            self.assertNotIn("stderr", run.call_args.kwargs)
            self.assertEqual(save.call_args.args[2], launcher.ROOT / "data/private/mic_readiness")

    def test_ssh_failure_never_saves_success_report(self):
        with patch.object(launcher.subprocess, "run", return_value=SimpleNamespace(returncode=255)), \
             patch.object(launcher, "save_report") as save:
            self.assertEqual(launcher.collect(), 2)
            save.assert_not_called()

    def test_timeout_does_not_retry_or_save_report(self):
        with patch.object(launcher.subprocess, "run", side_effect=subprocess.TimeoutExpired("ssh", 150)) as run, \
             patch.object(launcher, "save_report") as save:
            with self.assertRaises(subprocess.TimeoutExpired):
                launcher.collect()
            run.assert_called_once()
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
