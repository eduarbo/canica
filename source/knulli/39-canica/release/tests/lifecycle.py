"""Exercise the service with real ARM64 processes and a simulated local status API."""
import http.server
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path


ROOT = Path("/sc")
SERVICE = "/userdata/system/services/canica"


def service(action):
    return subprocess.check_output(
        ["chroot", ROOT, "bash", SERVICE, action], text=True, stderr=subprocess.DEVNULL
    ).strip()


@contextmanager
def running_help(executable):
    # Blocking stdout keeps --help alive while the service checks the original inode.
    read_fd, write_fd = os.pipe()
    os.set_blocking(write_fd, False)
    try:
        while True:
            os.write(write_fd, b"X" * 4096)
    except BlockingIOError:
        os.set_blocking(write_fd, True)

    try:
        process = subprocess.Popen(
            ["chroot", ROOT, executable, "--help"], stdout=write_fd, stderr=subprocess.DEVNULL
        )
    finally:
        os.close(write_fd)
    try:
        proc_exe = Path("/proc", str(process.pid), "exe")
        for _ in range(100):
            if proc_exe.samefile(ROOT / executable.lstrip("/")):
                break
            time.sleep(0.02)
        else:
            raise RuntimeError("No se encontró el proceso esperado")
        yield
    finally:
        os.close(read_fd)
        process.wait(timeout=5)


class LocalAPI(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/quit":
            self.server.quit_requested.set()
        if self.path == "/runningGame":
            self.server.game_checked.set()
        self.send_response(self.server.game_status if self.path == "/runningGame" else 200)
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    if not Path("/.dockerenv").is_file() or not Path("/qa/scarab.squashfs").is_file():
        raise SystemExit("Ejecuta probar-servicio.sh en un contenedor de pruebas")
    (ROOT / "var/run/emulationstation-standalone").touch()
    with http.server.ThreadingHTTPServer(("127.0.0.1", 1234), LocalAPI) as server:
        server.quit_requested = threading.Event()
        server.game_checked = threading.Event()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for busy in (True, False):
                server.game_status = 200 if busy else 201
                server.quit_requested.clear()
                server.game_checked.clear()
                with running_help("/usr/bin/emulationstation"):
                    service("start")
                    assert server.game_checked.wait(5), "No se consultó la sesión"
                    if busy:
                        assert not server.quit_requested.wait(1), "Reinicio mientras se jugaba"
                    else:
                        assert server.quit_requested.wait(3), "Faltó solicitar la salida limpia"
                    service("stop")

            service("start")
            with running_help("/var/run/canica/bin/emulationstation"):
                assert service("status") == "Canica en ejecución"
                service("stop")
                assert "sigue en ejecución" in service("status")
                service("start")
                assert service("status") == "Canica en ejecución"
                service("stop")
            assert service("status") == "Servicio Canica inactivo"
        finally:
            server.shutdown()
    print("Juego activo respetado, salida limpia y estados de reactivación verificados.")


if __name__ == "__main__":
    main()
