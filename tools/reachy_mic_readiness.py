"""One-shot READ-ONLY metadata report; standard library only, no media/device API.

The local launcher sends this source to Python stdin. No robot file is created.
This is not the microphone helper, protection supervisor, or an execution gate.
Only --report collects anything; importing this module has no side effects.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request


SCHEMA = "reachy-mic-readiness-v2"
LIMIT = 65536
DAEMON_ARGS = ["-u", "-m", "reachy_mini.daemon.app.main",
               "--wireless-version", "--no-wake-up-on-start"]
STATUS_ROUTES = ("/api/daemon/status", "/api/apps/current-app-status")
UNIT_PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState",
                   "FragmentPath", "DropInPaths", "What", "Options", "Priority",
                   "Restart", "Triggers", "TriggeredBy", "ExecStart", "ExecStop",
                   "ExecStartPre", "ExecStartPost", "ExecStopPost", "Requires", "RequiredBy",
                   "BindsTo", "BoundBy", "PartOf", "ConsistsOf", "StopWhenUnneeded",
                   "After", "Before", "TimersMonotonic", "TimersCalendar",
                   "NextElapseUSecRealtime", "NextElapseUSecMonotonic", "LastTriggerUSec",
                   "AccuracyUSec", "RandomizedDelayUSec", "Persistent")
UNIT_PATTERNS = ("*swap*", "*zram*", "rpi-setup-loop@*.service")
UNIT_NAME = r"[A-Za-z0-9_.@\\:-]+\.(service|timer|swap|target)"
CONFIGS = (
    "/etc/rpi/swap.conf", "/etc/default/rpi-swap", "/etc/default/zramswap",
    "/etc/dphys-swapfile", "/etc/systemd/zram-generator.conf",
    "/run/rpi/swap.conf", "/usr/local/lib/rpi/swap.conf", "/usr/lib/rpi/swap.conf",
    "/run/systemd/zram-generator.conf", "/usr/local/lib/systemd/zram-generator.conf",
    "/usr/lib/systemd/zram-generator.conf",
)
CONFIG_DIRS = tuple(path + ".d" for path in CONFIGS
                    if path.endswith(("/swap.conf", "/zram-generator.conf")))


class MetadataError(ValueError):
    """Fixed diagnostic codes only; no arbitrary command/API body retention."""
    def __init__(self, reason, returncode=None):
        self.reason = reason
        self.returncode = returncode
        super().__init__(reason)


def find_tool(name):
    # Non-login SSH PATH often omits sbin. Locate, never run, these tools.
    return shutil.which(name) or shutil.which(name, path="/usr/sbin:/sbin:/usr/bin:/bin")


def relevant_unit(name):
    return bool(re.fullmatch(UNIT_NAME, name)) and (
        "swap" in name.lower() or "zram" in name.lower() or name.startswith("rpi-setup-loop@"))


def parse_memory(text):
    wanted = {"MemTotal", "MemAvailable", "MemFree", "SwapTotal", "SwapFree",
              "SwapCached", "CommitLimit", "Committed_AS"}
    values = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if key in wanted:
            number, unit = value.split()
            if unit != "kB":
                raise ValueError("unexpected memory unit")
            values[key + "_KiB"] = int(number)
    if not {"MemTotal_KiB", "MemAvailable_KiB", "SwapTotal_KiB", "SwapFree_KiB"} <= values.keys():
        raise ValueError("missing memory field")
    return values


def parse_swaps(text):
    lines = text.strip().splitlines()
    if not lines or lines[0].split() != ["Filename", "Type", "Size", "Used", "Priority"]:
        raise ValueError("invalid swap table")
    result = []
    for line in lines[1:]:
        path, kind, size, used, priority = line.split()
        result.append(dict(path=path, type=kind, size_KiB=int(size),
                           used_KiB=int(used), priority=int(priority)))
    return result


def parse_identity(stat_text):
    # Field 2 can contain spaces and ')'; fields after its LAST ')' start at 3.
    prefix, tail = stat_text.rsplit(")", 1)
    fields = tail.split()
    return {"pid": int(prefix.split("(", 1)[0]), "ppid": int(fields[1]),
            "start_ticks": int(fields[19])}


def parse_core_limits(text):
    match = re.search(r"(?m)^Max core file size\s+(\d+|unlimited)\s+(\d+|unlimited)\s+bytes\s*$", text)
    if not match:
        raise ValueError("missing core limits")
    return {"soft_bytes": match[1] if match[1] == "unlimited" else int(match[1]),
            "hard_bytes": match[2] if match[2] == "unlimited" else int(match[2])}


def filtered_config(text):
    """Only known swap settings; never source shell configuration or copy secrets."""
    keys = {"CONF_SWAPSIZE", "CONF_SWAPFILE", "CONF_MAXSWAP", "CONF_SWAPFACTOR",
            "ALGO", "PERCENT", "SIZE", "PRIORITY", "ZRAM_SIZE", "SWAP_SIZE",
            "SWAPFILE", "SWAP_ENABLED", "ZRAM_ENABLED", "WRITEBACK_ENABLED",
            "zram-size", "zram-resident-limit", "compression-algorithm",
            "writeback-device", "swap-priority", "options", "host-memory-limit", "fs-type",
            "Mechanism", "Path", "RamMultiplier", "MaxSizeMiB", "MaxDiskPercent",
            "FixedSizeMiB", "WritebackTrigger", "WritebackInitialDelay",
            "WritebackPeriodicInterval"}
    kept, omitted = [], 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        key = line.split("=", 1)[0].strip()
        if key in keys or re.fullmatch(r"\[(Main|File|Zram|zram\d+)\]", line):
            kept.append(line)
        else:
            omitted += 1
    return {"settings": kept, "unreported_active_lines": omitted,
            "sha256": hashlib.sha256(text.encode()).hexdigest()}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("redirect refused")


class Reader:
    """Small bounded IO surface. No setter, SDK construction, shell or sudo exec."""
    def __init__(self):
        self.deadline = time.monotonic() + 60

    def remaining(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("report budget expired")
        return min(2, left)

    def read(self, path):
        self.remaining()
        with open(path, "rb") as source:
            data = source.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise MetadataError("metadata_file_over_64KiB")
        return data.decode("utf-8")

    def names(self, path):
        self.remaining()
        with os.scandir(path) as entries:
            names = []
            for entry in entries:
                if len(names) >= 4096:
                    raise ValueError("directory inventory too large")
                names.append(entry.name)
        return names

    def run(self, args, accepted=(0,)):
        # These are the only command shapes this report can launch.
        inventory = any(args == ["systemctl", operation, "--all", "--no-legend",
                                 "--plain", "--no-pager", "--", *UNIT_PATTERNS]
                        for operation in ("list-units", "list-unit-files"))
        show = (len(args) == 5 and args[:2] == ["systemctl", "show"]
                and relevant_unit(args[2]) and not args[2].endswith("@.service")
                and args[3:] == ["--no-pager", "--property=" + ",".join(UNIT_PROPERTIES)])
        allowed = inventory or show or args in (
            ["fuser", "/dev/snd/pcmC0D0c"], ["fuser", "/dev/snd/pcmC0D0p"],
            ["findmnt", "--json", "--target", "/var/swap", "--output", "TARGET,SOURCE,FSTYPE"],
        )
        if not allowed:
            raise ValueError("command not allowlisted")
        outcome = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                 timeout=self.remaining(), check=False,
                                 env={**os.environ, "LC_ALL": "C", "SYSTEMD_PAGER": "cat"})
        if outcome.returncode not in accepted:
            raise MetadataError("metadata_command_nonzero", outcome.returncode)
        if len(outcome.stdout) > LIMIT:
            raise MetadataError("metadata_output_over_64KiB")
        return outcome.stdout.decode("utf-8")

    def get(self, route):
        if route not in STATUS_ROUTES:
            raise ValueError("HTTP route not allowlisted")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        request = urllib.request.Request("http://127.0.0.1:8000" + route, method="GET")
        with opener.open(request, timeout=min(0.75, self.remaining())) as response:
            data = response.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("status too large")
        return json.loads(data)

    def policy_listing(self, command):
        # -l LISTS policy; it never executes the following command. -n avoids
        # prompting; -k with -l ignores and does not refresh cached credentials.
        # A positive listing is NOT proof of password-free future execution.
        outcome = subprocess.run(["sudo", "-n", "-k", "-l", "--", *command],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, timeout=self.remaining(), check=False)
        return {"candidate_command": command, "listing_returncode": outcome.returncode,
                "policy_lists_candidate": outcome.returncode == 0,
                "negative_result_may_mean_denied_or_authentication_required": True,
                "candidate_executed": False, "future_execution_privilege_verified": False}


class Report:
    def __init__(self, reader):
        self.io = reader
        self.checks = {}

    def probe(self, name, action, optional=False):
        try:
            value = action()
        except Exception as error:
            # Do not retain arbitrary stderr, API error bodies or exception text.
            status = "not_present" if optional and isinstance(error, FileNotFoundError) else "unavailable"
            self.checks[name] = {"status": status, "error_type": type(error).__name__}
            if isinstance(error, MetadataError):
                self.checks[name].update(reason=error.reason, returncode=error.returncode)
            return None
        self.checks[name] = {"status": "observed", "value": value}
        return value

    def text(self, name, path):
        return self.probe(name, lambda: self.io.read(path).strip())

    def process(self, pid):
        root = "/proc/" + str(int(pid))
        before = parse_identity(self.io.read(root + "/stat"))
        args = self.io.read(root + "/cmdline").rstrip("\0").split("\0")
        status = self.io.read(root + "/status")
        fields = {}
        for line in status.splitlines():
            key, _, value = line.partition(":")
            if key in {"Uid", "Gid", "VmRSS", "VmSwap", "Threads", "CapEff"}:
                fields[key] = value.strip()
        limits = parse_core_limits(self.io.read(root + "/limits"))
        after = parse_identity(self.io.read(root + "/stat"))
        if before != after:
            raise RuntimeError("process changed during snapshot")
        match = args[1:] == DAEMON_ARGS and Path(args[0]).name.startswith("python")
        return {**before, "reviewed_daemon_argv_match": match,
                "command": [Path(args[0]).name] + DAEMON_ARGS if match else "unreported_other_process",
                "status_fields": fields, "core_limits": limits}

    def processes(self):
        candidates, denied = [], 0
        for name in self.io.names("/proc"):
            if not name.isdigit():
                continue
            try:
                args = self.io.read("/proc/" + name + "/cmdline").split("\0")
            except (OSError, UnicodeError):
                denied += 1
                continue
            if "reachy_mini.daemon.app.main" in args:
                candidates.append(int(name))
        for pid in candidates[:8]:
            self.probe("daemon_process_" + str(pid), lambda pid=pid: self.process(pid))
            self.probe("daemon_children_" + str(pid), lambda pid=pid: self.children(pid))
        return {"candidate_pids": candidates, "unreadable_cmdlines": denied,
                "detailed_process_limit": 8, "complete_consumer_isolation_proven": False}

    def children(self, pid):
        # All threads, not only /task/PID/children. Direct children only.
        children = set()
        for tid in self.io.names(f"/proc/{pid}/task"):
            if tid.isdigit():
                text = self.io.read(f"/proc/{pid}/task/{tid}/children")
                children.update(int(value) for value in text.split())
        for child in sorted(children)[:16]:
            self.probe("child_process_" + str(child), lambda child=child: self.process(child))
        return {"direct_child_pids": sorted(children), "detail_limit": 16,
                "descendants_and_remote_clients_not_exhaustively_enumerated": True}

    def owners(self, node):
        output = self.io.run(["fuser", node], accepted=(0, 1))
        pids = [int(value) for value in output.split()]
        for pid in pids[:16]:
            self.probe("pcm_owner_process_" + str(pid), lambda pid=pid: self.process(pid))
        return {"visible_pids": pids, "empty_output_does_not_prove_unused": True,
                "shared_memory_and_remote_clients_not_enumerated": True}

    def managers(self):
        units = set()
        for operation in ("list-units", "list-unit-files"):
            def inventory(operation=operation):
                # Filter at the source, not after reading every unrelated unit.
                rows = self.io.run(["systemctl", operation, "--all", "--no-legend", "--plain", "--no-pager",
                                    "--", *UNIT_PATTERNS])
                matched = []
                for line in rows.splitlines():
                    parts = line.split()
                    if parts and relevant_unit(parts[0]):
                        matched.append(parts[0])
                units.update(matched)
                return sorted(set(matched))
            self.probe("swap_manager_" + operation, inventory)
        templates = sorted(unit for unit in units if unit.endswith("@.service"))
        instances = sorted(units.difference(templates))
        for unit in instances[:16]:
            def details(unit=unit):
                args = ["systemctl", "show", unit, "--no-pager", "--property=" + ",".join(UNIT_PROPERTIES)]
                text = self.io.run(args)
                return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
            self.probe("unit_" + unit, details)
        return {"matched_units": sorted(units), "templates_not_runtime_units": templates,
                "detail_limit": 16, "details_truncated": len(instances) > 16,
                "automatic_reactivation_and_exact_activation_flags_require_review": True}

    def config_dropins(self, directory):
        all_names = self.io.names(directory)
        names = sorted(name for name in all_names
                       if re.fullmatch(r"[A-Za-z0-9_.-]+\.conf", name))
        for name in names[:16]:
            path = directory + "/" + name
            self.probe("config_" + path, lambda path=path: filtered_config(self.io.read(path)))
        return {"files": names, "detail_limit": 16, "details_truncated": len(names) > 16,
                "unread_unrecognized_conf_names": sum(name.endswith(".conf") and name not in names for name in all_names),
                "effective_precedence_not_inferred": True}

    def status(self):
        result = self.io.get(STATUS_ROUTES[0])
        if not isinstance(result, dict):
            raise ValueError("invalid daemon status")
        keys = ("state", "version", "simulation_enabled", "mockup_sim_enabled", "wireless_version",
                "no_media", "media_released")
        selected = {key: result.get(key) for key in keys}
        for key in keys[2:]:
            if type(selected[key]) is not bool:
                selected[key] = None
        if selected["state"] not in ("not_initialized", "starting", "running", "stopping", "stopped", "error"):
            selected["state"] = None
        if not isinstance(selected["version"], str) or not re.fullmatch(r"[0-9A-Za-z.+_-]{1,64}", selected["version"]):
            selected["version"] = None
        selected["error_present"] = result["error"] is not None if "error" in result else None
        backend = result.get("backend_status")
        selected["backend_status_present"] = isinstance(backend, dict)
        backend = backend if isinstance(backend, dict) else {}
        mode = backend.get("motor_control_mode")
        selected["backend_status"] = {
            "ready": backend.get("ready") if type(backend.get("ready")) is bool else None,
            "motor_control_mode": mode if mode in ("enabled", "disabled", "gravity_compensation") else None,
            "error_present": backend["error"] is not None if "error" in backend else None,
        }
        selected["unknown_fields"] = [key for key in keys if selected[key] is None]
        if selected["error_present"] is None:
            selected["unknown_fields"].append("error_present")
        selected["unknown_fields"].extend("backend_status." + key for key, value in
                                          selected["backend_status"].items() if value is None)
        selected["no_motor_state_inference_from_daemon_state"] = True
        return selected

    def privileges(self):
        swap = self.checks.get("swap_before", {}).get("value", [])
        if len(swap) == 1 and swap[0]["path"] == "/dev/zram0":
            candidates = (
                ("swapoff", ["/dev/zram0"]),
                ("swapon", ["--priority", str(swap[0]["priority"]), "/dev/zram0"]),
            )
            for program, args in candidates:
                path = find_tool(program)
                if path:
                    self.probe("policy_" + program, lambda path=path, args=args: self.io.policy_listing([path, *args]))
        path = find_tool("prlimit")
        for name, check in list(self.checks.items()):
            item = check.get("value")
            if name.startswith("daemon_process_") and item and item["reviewed_daemon_argv_match"] and path:
                limits = item["core_limits"]
                if limits["soft_bytes"] == 0:
                    self.checks["policy_core_" + str(item["pid"])] = {
                        "status": "not_needed", "reason": "soft_core_limit_already_zero"}
                    continue
                for label, soft in (("protect", 0), ("restore", limits["soft_bytes"])):
                    command = [path, "--pid", str(item["pid"]), "--core=" + str(soft) + ":" + str(limits["hard_bytes"])]
                    self.probe("policy_core_" + label + "_" + str(item["pid"]),
                               lambda command=command: self.io.policy_listing(command))
        return {"policy_listing_only": True, "no_privileged_candidate_executed": True,
                "activation_options_and_supervisor_capabilities_still_require_review": True}

    def collect(self):
        started = datetime.now(timezone.utc).isoformat()
        self.probe("memory_before", lambda: parse_memory(self.io.read("/proc/meminfo")))
        self.probe("swap_before", lambda: parse_swaps(self.io.read("/proc/swaps")))
        self.text("boot_id", "/proc/sys/kernel/random/boot_id")
        self.text("core_pattern", "/proc/sys/kernel/core_pattern")
        self.probe("collector_core_limits", lambda: parse_core_limits(self.io.read("/proc/self/limits")))
        self.text("zram_backing_device", "/sys/block/zram0/backing_dev")
        self.text("loop_backing_file", "/sys/block/loop0/loop/backing_file")
        for attribute in ("writeback_limit_enable", "writeback_limit", "bd_stat", "mm_stat", "disksize"):
            self.text("zram_" + attribute, "/sys/block/zram0/" + attribute)
        self.probe("backing_file_mount", lambda: json.loads(self.io.run(
            ["findmnt", "--json", "--target", "/var/swap", "--output", "TARGET,SOURCE,FSTYPE"])))
        self.probe("swap_fstab_entries", lambda: [line.strip() for line in self.io.read("/etc/fstab").splitlines()
                                                if not line.lstrip().startswith("#") and
                                                len(line.split()) >= 3 and line.split()[2] == "swap"])
        for path in CONFIGS:
            self.probe("config_" + path, lambda path=path: filtered_config(self.io.read(path)), optional=True)
        for directory in CONFIG_DIRS:
            self.probe("config_directory_" + directory,
                       lambda directory=directory: self.config_dropins(directory), optional=True)
        self.probe("swap_managers", self.managers)
        self.probe("daemon_inventory", self.processes)
        self.probe("capture_owners", lambda: self.owners("/dev/snd/pcmC0D0c"))
        self.probe("playback_owners", lambda: self.owners("/dev/snd/pcmC0D0p"))
        self.probe("daemon_status", self.status)
        self.probe("current_app", lambda: {"app_present": self.io.get(STATUS_ROUTES[1]) is not None})
        self.probe("tools", lambda: {name: find_tool(name) for name in
                                    ("swapon", "swapoff", "prlimit", "sudo", "systemctl",
                                     "findmnt", "fuser", "arecord", "timeout", "amixer")})
        self.probe("caller", lambda: {"effective_uid": os.geteuid(), "group_ids": os.getgroups()})
        self.probe("privilege_listings", self.privileges)
        self.probe("memory_after", lambda: parse_memory(self.io.read("/proc/meminfo")))
        self.probe("swap_after", lambda: parse_swaps(self.io.read("/proc/swaps")))
        return {"schema": SCHEMA, "started_utc": started,
                "finished_utc": datetime.now(timezone.utc).isoformat(),
                "purpose": "read_only_metadata_review", "execution_authorized": False,
                "checks": self.checks,
                "unavailable_checks": [name for name, value in self.checks.items() if value["status"] == "unavailable"],
                "optional_not_present": [name for name, value in self.checks.items() if value["status"] == "not_present"],
                "remaining_review": [
                    "No readiness PASS: review current robot state and all unavailable fields.",
                    "Freeze memory budget/reserve with helper requirements; no threshold assumed here.",
                    "Review swap manager units/config for activation options and automatic reactivation.",
                    "Sudo policy listings do not prove future restoration ability or authorize execution.",
                    "Confirm all external/shared media consumers are closed; these observations cannot prove isolation.",
                    "Decide privacy scope and residual OS retention before any acquisition approval.",
                    "Protection supervisor implementation/rehearsal and explicit live approval still required.",
                ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="read metadata only, print JSON, then exit")
    args = parser.parse_args()
    if not args.report:
        parser.print_help()
        return 0
    # Account/platform check does not create files or alter process limits.
    import pwd
    if sys.platform != "linux" or pwd.getpwuid(os.geteuid()).pw_name != "pollen":
        raise RuntimeError("requires the reviewed Linux pollen account")
    print(json.dumps(Report(Reader()).collect(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
