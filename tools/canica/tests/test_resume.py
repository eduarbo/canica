"""Check the resume decision with separate state slots and changed battery progress."""
import os
from pathlib import Path
import runpy
import tempfile
import unittest
import re

module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "resume/emulatorlauncher"))
Resume = module["Resume"]
namespace = Resume.__init__.__globals__


class ResumePolicy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        namespace["RECORDS"] = self.root / "history"
        self.imported = 0
        namespace["download_time"] = lambda rom, system: self.imported

    def mark(self, name, content, second):
        file = self.root / ("Demo." + name)
        file.write_bytes(content)
        os.utime(file, (second, second))

    def policy(self):
        return Resume(self.root / "Demo.gb", "gb", "gambatte", self.root, self.root,
                      re.compile(r"Demo\.state(\.auto|[0-9]*)"))

    def test_download_then_local_progress(self):
        self.mark("state.auto", b"auto", 90)
        self.mark("state2", b"slot", 100)
        self.mark("srm", b"on console", 104)
        self.assertEqual(self.policy().newest()[1], 2)
        self.policy().finish()
        self.imported = 110
        self.mark("srm", b"from TV", 10)  # copied with an older timestamp
        after_download = self.policy()
        self.assertIsNone(after_download.newest())
        after_download.finish()
        self.assertIsNone(self.policy().newest())
        resumed = self.policy()
        self.mark("state.auto", b"new local", 120)
        resumed.finish()
        self.assertEqual(self.policy().newest()[1], -1)
        self.assertEqual((self.root / "Demo.state2").read_bytes(), b"slot")

    def test_unknown_progress_and_other_games(self):
        self.imported = None
        self.mark("state1", b"local", 20)
        self.mark("srm", b"unknown", 5)
        (self.root / "Demo sequel.state4").write_bytes(b"other")
        self.assertIsNone(self.policy().newest())
        (self.root / "Demo.srm").unlink()
        self.assertEqual(self.policy().newest()[1], 1)

    def test_new_slot_written_after_manual_load(self):
        self.mark("srm", b"same battery", 1)
        self.mark("state", b"first", 10)
        self.mark("state1", b"second", 20)
        self.policy().finish()
        explicit = self.policy()
        self.mark("state2", b"continued from first", 30)
        explicit.finish(0)
        self.assertEqual(self.policy().newest()[1], 2)
        self.imported = 40
        self.mark("srm", b"different battery", 2)
        self.assertIsNone(self.policy().newest())

    def test_fresh_auto_and_specific_slot(self):
        overlay = self.root / "entry.cfg"
        for requested, auto, args in ((-2, "false", []), (-1, "true", []), (2, "false", ["-e", "2"])):
            command = ["retroarch"]
            module["set_ra_entry"](command, overlay, requested)
            self.assertEqual(command[1:], args)
            self.assertIn(f'savestate_auto_load = "{auto}"', overlay.read_text())
            self.assertIn('block_sram_overwrite = "true"', overlay.read_text())

    def test_manual_state_updated_outside_last_launch_without_battery(self):
        self.mark("state.auto", b"automatic", 20)
        self.policy().finish()
        self.mark("state", b"manual", 30)
        self.assertEqual(self.policy().newest()[1], 0)
        self.mark("state.auto", b"automatic again", 40)
        self.assertEqual(self.policy().newest()[1], -1)

    def test_sync_changes_progress_during_session(self):
        self.mark("srm", b"old", 10)
        self.mark("state1", b"old scene", 20)
        active = self.policy()
        self.imported = 30
        self.mark("srm", b"new from TV", 5)
        active.finish()
        self.assertIsNone(self.policy().newest())

    def test_no_state(self):
        self.assertIsNone(self.policy().newest())


class FastLaunch(unittest.TestCase):
    """The launch's waits: hooks side by side, evmapy in the background, no fixed grace."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def script(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def test_hooks_run_together_and_are_all_waited_for(self):
        import time
        hooks = self.root / "scripts"
        for name in ("a.sh", "b.sh", "nested/c.sh"):
            self.script(hooks / name, f'sleep 0.6; echo "$1 $2" > "{self.root}/{Path(name).stem}.done"')
        (hooks / "notes.txt").write_text("not a script")

        class Log:
            def debug(self, message): pass
            def error(self, message): raise AssertionError(message)

        ended = self.root / "run/game-ended"
        run = module["run_scripts_together"](Log(), ended)
        run(hooks / "none", "gameStart", [])
        self.assertFalse(ended.exists())          # only the end of the game tells the menu
        start = time.monotonic()
        run(hooks, "gameStop", ["gba", "libretro"])
        self.assertTrue(ended.exists())
        elapsed = time.monotonic() - start
        for stem in ("a", "b", "c"):
            self.assertEqual((self.root / f"{stem}.done").read_text(), "gameStop gba\n")
        self.assertLess(elapsed, 1.5)       # three 0.6 s scripts: together, not one after another
        self.assertGreaterEqual(elapsed, 0.6)
        run(self.root / "missing", "gameStart", [])
        log = self.root / "timing.log"
        module["timing"]("not written", log)
        self.assertFalse(log.exists())             # only while the menu measures
        log.write_text("")
        module["timing"]("hooks: gameStop", log)
        self.assertRegex(log.read_text(), r"^\d+\.\d{3} hooks: gameStop\n$")

    def test_evmapy_starts_in_the_background_and_its_stop_waits_for_the_start(self):
        calls = []

        class Started:
            def __init__(self, args): calls.append(("popen", args)); self.waited = False
            def wait(self, timeout=None): calls.append(("wait", timeout)); self.waited = True

        class Real:
            Popen = Started
            TimeoutExpired = TimeoutError
            def call(self, args, *rest, **kwargs): calls.append(("call", args)); return 0
            def run(self, *args, **kwargs): return "run"

        shim = module["EvmapyInBackground"](Real())
        self.assertEqual(shim.call(["batocera-evmapy", "start"]), 0)
        self.assertEqual(calls, [("popen", ["batocera-evmapy", "start"])])
        shim.call(["batocera-evmapy", "clear"])
        shim.call(["batocera-evmapy", "stop"])
        self.assertEqual(calls[1:], [("call", ["batocera-evmapy", "clear"]), ("wait", 6),
                                     ("call", ["batocera-evmapy", "stop"])])
        self.assertEqual(shim.run(), "run")

    def test_no_grace_after_the_game(self):
        import time
        clock = module["NoGrace"]()
        start = time.monotonic()
        clock.sleep(0.5)
        self.assertLess(time.monotonic() - start, 0.1)
        self.assertTrue(callable(clock.monotonic))

    def test_the_emulator_waits_for_the_menu_to_let_go(self):
        import threading
        import time
        busy = self.root / "menu-busy"
        busy.write_text("")
        ran = []
        run = module["after_the_menu"](lambda command: ran.append((command, busy.exists())) or 0, busy, 3.0)
        threading.Timer(0.3, busy.unlink).start()
        start = time.monotonic()
        self.assertEqual(run("retroarch"), 0)
        self.assertGreaterEqual(time.monotonic() - start, 0.25)
        self.assertEqual(ran, [("retroarch", False)])
        busy.write_text("")
        start = time.monotonic()
        module["after_the_menu"](lambda command: 0, busy, 0.2)("retroarch")
        self.assertLess(time.monotonic() - start, 1.0)     # a menu that never lets go: bounded

    def test_an_emulator_closed_by_its_exit_hotkey_exits_normally(self):
        busy = self.root / "never"
        for code, reported in ((-9, 0), (-15, 0), (-11, -11), (-6, -6), (1, 1), (0, 0)):
            self.assertEqual(module["after_the_menu"](lambda command: code, busy)("eduke32"), reported)

    def test_speed_up_patches_configgen(self):
        import sys
        import types
        package, utils, mapping = (types.ModuleType(n) for n in ("configgen", "configgen.utils", "configgen.utils.evmapy"))
        mapping.subprocess = "original"
        utils.evmapy = mapping
        package.utils = utils
        saved = {n: sys.modules.get(n) for n in ("configgen", "configgen.utils", "configgen.utils.evmapy")}
        sys.modules.update({"configgen": package, "configgen.utils": utils, "configgen.utils.evmapy": mapping})
        try:
            stock = types.SimpleNamespace(eslog=None, callExternalScripts=None, time=None, runCommand=lambda c: 7)
            module["speed_up"](stock)
        finally:
            for name, value in saved.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.assertTrue(callable(stock.callExternalScripts))
        self.assertIsInstance(mapping.subprocess, module["EvmapyInBackground"])
        self.assertIsInstance(stock.time, module["NoGrace"])
        self.assertEqual(stock.runCommand("retroarch"), 7)

    def test_setting_lookups_remember_their_substitutions(self):
        import types
        calls = []

        def protect(text):
            calls.append(text)
            return text.replace("[", "_")
        settings = types.SimpleNamespace(_protect_string=protect)
        module["faster_settings"](settings)
        module["faster_settings"](settings)       # once is enough
        self.assertEqual([settings._protect_string(k) for k in ("gba[x]", "gba[x]", "nes")], ["gba_x]", "gba_x]", "nes"])
        self.assertEqual(calls, ["gba[x]", "nes"])

    def test_a_game_without_saved_states_runs_configgen_as_it_is(self):
        import sys
        import types
        names = ("configgen", "configgen.utils", "configgen.utils.evmapy", "configgen.emulatorlauncher")
        package, utils, mapping, stock = (types.ModuleType(n) for n in names)
        mapping.subprocess = "original"
        utils.evmapy = mapping
        package.utils = utils
        package.emulatorlauncher = stock
        seen = []

        def plain():
            seen.append((list(sys.argv), stock.get_generator))
            raise SystemExit(5)
        stock.launch, stock.get_generator = plain, "configgen's own"
        stock.eslog, stock.callExternalScripts, stock.time, stock.runCommand = None, None, None, lambda c: 0
        saved = {n: sys.modules.get(n) for n in names}
        argv = sys.argv
        sys.modules.update(dict(zip(names, (package, utils, mapping, stock))))
        sys.argv = ["emulatorlauncher", "--es-no-resume", "-system", "ports", "-rom", "/userdata/roms/ports/duke.sh"]
        try:
            with self.assertRaises(SystemExit) as result:
                module["launch"]()
        finally:
            sys.argv = argv
            for name, value in saved.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.assertEqual(result.exception.code, 5)
        self.assertEqual(seen, [(["emulatorlauncher", "-system", "ports", "-rom", "/userdata/roms/ports/duke.sh"],
                                 "configgen's own")])
        self.assertIsInstance(mapping.subprocess, module["EvmapyInBackground"])   # still the faster launch


class PreparsedFiles(unittest.TestCase):
    """What the warm launcher parses ahead, and when a launch may use it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.conf = self.root / "knulli.conf"
        self.conf.write_text("global.ratio=auto\n")
        self.parsed = 0

    def parse(self, kind, text):
        if "broken" in text:
            raise ValueError("unparseable")
        self.parsed += 1
        return {"kind": kind, "text": text, "copy": self.parsed}

    def test_each_copy_once_and_only_while_the_file_reads_the_same(self):
        cache = module["Preparsed"]({str(self.conf): "settings"}, self.parse)
        cache.refresh()
        cache.refresh()                       # unchanged: not parsed again
        self.assertEqual(self.parsed, 1)
        first = cache.take(str(self.conf), "global.ratio=auto\n")
        self.assertEqual(first["copy"], 1)
        self.assertIsNone(cache.take(str(self.conf), "global.ratio=auto\n"))   # used: parse it yourself
        cache.refresh()
        self.assertIsNone(cache.take(str(self.conf), "global.ratio=4/3\n"))    # changed since
        self.conf.write_text("global.ratio=4/3\n")
        cache.refresh()
        self.assertEqual(cache.take(str(self.conf), "global.ratio=4/3\n")["copy"], 3)
        self.conf.write_text("broken")
        cache.refresh()
        self.assertNotIn(str(self.conf), cache.ready)
        self.conf.unlink()
        cache.refresh()
        self.assertNotIn(str(self.conf), cache.ready)

    def test_a_launch_takes_configgens_files_from_the_cache_once(self):
        import types
        defaults = self.root / "configgen-defaults.yml"
        defaults.write_text("default: {emulator: libretro}\n")

        class RealYaml:
            CLoader = "CLoader"

            def load(self, stream, Loader=None):
                text = stream if isinstance(stream, str) else stream.read()
                return ("parsed in the launch", text, Loader)

        class Settings:
            def __init__(self, path):
                self.__post_init__(path)

            def __post_init__(self, path):
                self.settings_path = Path(path)
                self.config = ("parsed in the launch", Path(path).read_text())

        emulator = types.SimpleNamespace(yaml=RealYaml())
        cache = module["Preparsed"]({str(defaults): "yaml", str(self.conf): "settings"}, self.parse)
        cache.refresh()
        module["use_preparsed"](cache, emulator, Settings)
        with defaults.open("r") as stream:
            self.assertEqual(emulator.yaml.load(stream, Loader=emulator.yaml.CLoader)["kind"], "yaml")
        with defaults.open("r") as stream:
            self.assertEqual(emulator.yaml.load(stream, Loader="CLoader"),
                             ("parsed in the launch", "default: {emulator: libretro}\n", "CLoader"))
        self.assertEqual(Settings(self.conf).config["kind"], "settings")
        self.assertEqual(Settings(self.conf).settings_path, self.conf)
        self.assertEqual(Settings(self.conf).config, ("parsed in the launch", "global.ratio=auto\n"))
        other = self.root / "other.cfg"
        other.write_text("a = 1\n")
        self.assertEqual(Settings(other).config, ("parsed in the launch", "a = 1\n"))


class WarmLauncher(unittest.TestCase):
    """Launches handed to a process that has configgen loaded already, and what happens without it."""

    def setUp(self):
        import signal
        self.temp = tempfile.TemporaryDirectory(dir="/tmp")    # short: socket paths have a limit
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sock = str(self.root / "launcher.sock")
        self.me = self.root / "emulatorlauncher"
        self.me.write_text("# this version\n")
        self.saved = namespace["run_here"]
        self.addCleanup(namespace.__setitem__, "run_here", self.saved)
        self.signal = signal

    def serve(self, run_here):
        """The warm launcher in its own process, with run_here standing in for configgen."""
        import time
        namespace["run_here"] = run_here
        pid = os.fork()
        if pid == 0:
            try:
                code = module["serve"](self.sock, str(self.me), preload=False, detach=False)
            except BaseException:
                code = 99
            os._exit(code)
        self.addCleanup(self.stop, pid)
        for _ in range(200):
            if os.path.exists(self.sock):
                return pid
            time.sleep(0.01)
        self.fail("the warm launcher did not start")

    def stop(self, pid):
        try:
            os.kill(pid, self.signal.SIGTERM)
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        except ProcessLookupError:
            pass

    def exited(self, pid, within=5.0):
        import time
        end = time.monotonic() + within
        while time.monotonic() < end:
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                return os.waitstatus_to_exitcode(status)
            time.sleep(0.02)
        return None

    def client(self, argv, env=None):
        """A launch as the menu starts one: its stdout is a pipe the test reads."""
        read, write = os.pipe()
        pid = os.fork()
        if pid == 0:
            code = 98
            try:
                os.close(read)
                os.dup2(write, 1)
                os.dup2(write, 2)
                if env:
                    os.environ.update(env)
                code = module["warm_launch"](argv, self.sock)
                code = 97 if code is None else code
            finally:
                os._exit(code)
        os.close(write)
        return pid, read

    def output(self, read):
        chunks = []
        while True:
            chunk = os.read(read, 4096)
            if not chunk:
                break
            chunks.append(chunk)
        os.close(read)
        return b"".join(chunks).decode()

    def test_no_warm_launcher_means_the_launch_runs_here(self):
        self.assertIsNone(module["warm_launch"](["emulatorlauncher"], self.sock))

    def test_each_launch_runs_in_a_fork_with_the_clients_streams_and_arguments(self):
        def run_here():
            os.write(1, ("%s|%s|%s\n" % (" ".join(sys.argv), os.getcwd(), os.environ.get("_"))).encode())
            return 3
        import sys
        self.serve(run_here)
        for game in ("a.gba", "b.gba"):
            pid, read = self.client(["emulatorlauncher", "-rom", game], {"_": "/bin/other"})
            self.assertEqual(self.output(read), "emulatorlauncher -rom %s|%s|/bin/other\n" % (game, os.getcwd()))
            self.assertEqual(self.exited(pid), 3)

    def test_another_environment_is_declined_and_ends_the_warm_launcher(self):
        server = self.serve(lambda: 0)
        pid, read = self.client(["emulatorlauncher"], {"CANICA_OTHER": "1"})
        self.assertEqual(self.exited(pid), 97)
        self.assertIn("another environment (CANICA_OTHER)", self.output(read))   # told on stderr
        self.assertIsNotNone(self.exited(server))

    def test_a_client_that_goes_away_takes_its_launch_with_it(self):
        import time
        started = self.root / "launch.pid"

        def run_here():
            started.write_text(str(os.getpid()))
            time.sleep(30)
            return 0
        self.serve(run_here)
        pid, read = self.client(["emulatorlauncher"])
        for _ in range(300):
            if started.exists() and started.read_text():
                break
            time.sleep(0.01)
        launch = int(started.read_text())
        os.kill(pid, self.signal.SIGKILL)
        self.exited(pid)
        os.close(read)
        for _ in range(300):
            try:
                os.kill(launch, 0)
            except ProcessLookupError:
                break
            time.sleep(0.01)
        else:
            self.fail("the launch outlived its client")

    def test_a_new_version_ends_it_and_the_launch_runs_here(self):
        server = self.serve(lambda: 0)
        os.utime(self.me, ns=(1, 1))
        pid, read = self.client(["emulatorlauncher"])
        self.assertEqual(self.exited(pid), 97)
        self.output(read)
        self.assertEqual(self.exited(server), 0)

    def test_only_one_serves(self):
        self.serve(lambda: 0)
        self.assertEqual(module["serve"](self.sock, str(self.me), preload=False, detach=False), 0)

    def test_the_shells_own_variables_do_not_count(self):
        same = module["same_environment"]
        self.assertTrue(same({"HOME": "/userdata", "_": "/a", "SHLVL": "1"}, {"HOME": "/userdata", "_": "/b"}))
        self.assertTrue(same({"DBUS_SESSION_BUS_ADDRESS": "unix:abstract=/tmp/dbus-a"},
                             {"DBUS_SESSION_BUS_ADDRESS": "unix:abstract=/tmp/dbus-b"}))
        self.assertFalse(same({"HOME": "/userdata"}, {"HOME": "/root"}))
        self.assertEqual(module["end_like_python"](256 + 3), 3)

    def test_it_detaches_from_whoever_starts_it(self):
        import socket
        import subprocess
        import sys
        import time
        adapter = str(Path(__file__).resolve().parents[1] / "resume/emulatorlauncher")
        code = ("import runpy; runpy.run_path(%r)['serve'](%r, %r, preload=False)"
                % (adapter, self.sock, str(self.me)))
        result = subprocess.run([sys.executable, "-c", code], timeout=5, capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        for _ in range(300):
            if os.path.exists(self.sock):
                break
            time.sleep(0.01)
        os.utime(self.me, ns=(1, 1))          # a new version: the next connection ends it
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.connect(self.sock)
            self.assertEqual(probe.recv(1), b"")
        for _ in range(300):
            if not os.path.exists(self.sock):
                break
            time.sleep(0.01)
        self.assertFalse(os.path.exists(self.sock))

    def test_it_runs_under_a_name_no_game_check_sees(self):
        import sys
        calls = []
        argv = sys.argv
        sys.argv = ["/userdata/system/configs/emulationstation/resume/emulatorlauncher", "--serve"]
        try:
            self.assertTrue(module["as_warm_launcher"](self.sock, str(self.me), lambda *a: calls.append(a)))
        finally:
            sys.argv = argv
        link = str(self.root / "canica-warm")
        self.assertEqual(os.path.realpath(link), os.path.realpath(self.me))
        self.assertEqual(calls, [(sys.executable, [sys.executable, "-IS", link, "--serve"])])
        self.assertNotIn("emulatorlauncher", " ".join(calls[0][1]).replace(str(self.root), ""))
        sys.argv = [link, "--serve"]
        try:
            self.assertTrue(module["as_warm_launcher"](self.sock, str(self.me), lambda *a: calls.append(a)))
        finally:
            sys.argv = argv
        self.assertEqual(len(calls), 1)            # already under that name: serves as it is
        blocked = self.root / "file"
        blocked.write_text("")
        self.assertFalse(module["as_warm_launcher"](str(blocked / "launcher.sock"), str(self.me), lambda *a: calls.append(a)))

    def test_start_warm_starts_one_with_the_menus_environment_unless_one_answers(self):
        import socket
        import time
        marker = self.root / "started"
        fake = self.root / "fake-launcher"
        fake.write_text("import os, sys\nopen(os.environ['MARKER'], 'w').write(' '.join(sys.argv[1:]))\n")
        module["start_warm"](self.sock, str(fake), env={"MARKER": str(marker)})
        for _ in range(500):
            if marker.exists() and marker.read_text():
                break
            time.sleep(0.01)
        self.assertEqual(marker.read_text(), "--serve")
        marker.unlink()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listening:
            listening.bind(self.sock)
            listening.listen(1)
            module["start_warm"](self.sock, str(fake), env={"MARKER": str(marker)})
            time.sleep(0.5)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
