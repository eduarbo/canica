"""Rehearse an update in the stock firmware: the installed kit's own updater takes the next
kit from a local release server and installs it with that kit's real installer, the real
service and the firmware's Python and OpenSSL. Only the menu is simulated: its web API, and a
process of the kit's frontend that restarts when asked to quit.

Run by probar-actualizacion.sh in its container, after SOLO_ENTORNO=1 stock.sh. /ota holds
releases/canica-<firmware slug>/ with manifest.json, its signature and the installer.
"""
import hashlib
import http.server
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path("/sc")
UPDATER = "/userdata/system/canica/updater.py"
UPDATES = ROOT / "userdata/system/canica-updates"
SERVICE = "/userdata/system/services/canica"
FRONTEND = "/var/run/canica/bin/emulationstation"


def sc(*command):
    return subprocess.run(["chroot", ROOT, *command], text=True, capture_output=True)


class Menu:
    """A process of the kit's frontend, kept alive by a full pipe, and what the API was told."""

    def __init__(self):
        self.process, self.read_fd = None, None
        self.notices, self.screens = [], []

    def start(self):
        self.read_fd, write_fd = os.pipe()
        os.set_blocking(write_fd, False)
        try:
            while True:
                os.write(write_fd, b"X" * 4096)
        except BlockingIOError:
            os.set_blocking(write_fd, True)
        self.process = subprocess.Popen(["chroot", ROOT, FRONTEND, "--help"], stdout=write_fd, stderr=subprocess.DEVNULL)
        os.close(write_fd)
        exe = Path("/proc", str(self.process.pid), "exe")
        for _ in range(200):
            if exe.exists() and exe.samefile(ROOT / FRONTEND.lstrip("/")):
                return
            time.sleep(0.02)
        raise RuntimeError("the menu process did not start")

    def stop(self):
        if self.process:
            os.close(self.read_fd)
            self.process.wait(timeout=10)
            self.process = None

    def restart(self):
        self.stop()
        self.start()


def api(menu):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def answer(self, status):
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if self.path == "/quit":
                threading.Thread(target=menu.restart).start()
            if self.path.startswith("/releases/"):
                target = Path("/ota") / self.path.lstrip("/")
                if not target.is_file():
                    return self.answer(404)
                data = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.answer(201 if self.path == "/runningGame" else 200)

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            if self.path == "/notify":
                menu.notices.append(body)
            elif self.path == "/job-console":
                menu.screens.append(body.split("\n"))
            self.answer(200)
    return Handler


def cycle(request=None):
    if request:
        (UPDATES / "request").write_text(request + "\n")
    result = sc("python3", "-I", UPDATER, "once")
    log = (ROOT / "userdata/system/logs/canica-updates.log").read_text().splitlines()
    cycles = [line for line in log if " cycle (" in line]
    assert cycles and result.stdout.strip().isdigit(), (result.stdout, result.stderr, log[-15:])
    return cycles[-1].split(": ", 1)[1]


def main():
    if not Path("/.dockerenv").is_file() or not (ROOT / UPDATER.lstrip("/")).is_file():
        raise SystemExit("Ejecuta probar-actualizacion.sh")
    folder, = Path("/ota/releases").iterdir()
    manifest = json.loads((folder / "manifest.json").read_text())
    serial, label = manifest["serial"], manifest["label"]
    before = sc("python3", "-I", UPDATER, "status").stdout
    was = json.loads(before)["kit"]
    assert was and was != label, before

    (ROOT / "var/run/emulationstation-standalone").touch()
    UPDATES.mkdir(exist_ok=True)       # a fresh console: no mode file, so it asks
    (UPDATES / "config.env").write_text(
        "BASE_URL=http://127.0.0.1:1234/releases\nALLOW_HTTP_LOCALHOST=1\nNOTE_AFTER=0\nSTART_TIMEOUT=60\n")
    menu = Menu()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 1234), api(menu))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert sc("bash", SERVICE, "start").returncode == 0
        menu.start()
        first = menu.process.pid
        assert sc("bash", SERVICE, "status").stdout.strip() == "Canica en ejecución"

        said = cycle()
        assert "offered on the menu" in said, said
        assert menu.notices == ["Canica busca actualizaciones en GitHub (START > Canica)."], menu.notices
        ask = menu.screens[-1]
        assert ask[0] == "ask %d" % serial and ask[2] == "%s → %s" % (was, label), ask
        assert [row for row in ask if row.startswith("firma\ted25519") and row.endswith("\tok")], ask
        assert [row for row in ask if row.startswith("prueba\t")], ask     # the real installer's --check passed
        status = dict(line.split("=", 1) for line in (UPDATES / "status").read_text().splitlines())
        assert (status["installed"], status["available"], status["ready"]) == (was, label, "1"), status

        said = cycle("install %d" % serial)
        assert "kit %s (%d) installed and running" % (label, serial) in said, said
        sealed = subprocess.run(["chroot", ROOT, "sh", "-c", "cd /userdata && sha256sum --status -c system/canica/SHA256SUMS"])
        assert sealed.returncode == 0, "the new kit is not sealed"
        inventory = hashlib.sha256((ROOT / "userdata/system/canica/SHA256SUMS").read_bytes()).hexdigest()
        assert inventory == manifest["inventory_sha256"], inventory
        assert menu.process.pid != first and sc("bash", SERVICE, "status").stdout.strip() == "Canica en ejecución"
        steps = [(rows[0], rows[-1]) for rows in menu.screens if rows[0].startswith("progress ")]
        assert steps[0] == ("progress 3", "kit\tcomprobando") and steps[-1] == ("progress 96", "menú\treiniciando"), steps
        assert ("progress 8", "archivos\tcopiando") in steps, steps
        assert menu.notices[-2:] == ["Canica %s instalada." % label, manifest["note"]], menu.notices
        status = dict(line.split("=", 1) for line in (UPDATES / "status").read_text().splitlines())
        assert (status["installed"], status["available"]) == (label, ""), status
        assert not (ROOT / "userdata/system/.canica-installer-v1").exists()

        said = cycle()
        assert "up to date (kit %s (%d))" % (label, serial) in said, said
        cards = [row for row in (ROOT / "userdata/system/logs/canica-updates.log").read_text().splitlines() if "installer --ota: exit" in row]
        print("Actualización %s → %s en el entorno de fábrica: ofrecida, instalada con su instalador (%s), sellada y en marcha."
              % (was, label, re.sub(r".*installer --ota: ", "", cards[-1])))
    finally:
        server.shutdown()
        sc("bash", SERVICE, "stop")
        menu.stop()
        for entry in Path("/proc").iterdir():       # the service started the updater's loop
            try:
                if entry.name.isdigit() and b"updater.py\0loop" in (entry / "cmdline").read_bytes():
                    os.kill(int(entry.name), 9)
            except OSError:
                pass


if __name__ == "__main__":
    main()
