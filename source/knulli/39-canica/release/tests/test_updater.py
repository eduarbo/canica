#!/usr/bin/env python3
"""Off-device tests of the kit's updater (release/updater.py).

Each case builds a small console under a temporary folder (CANICA_ROOT): firmware files, an
installed kit with its keys and service, a menu process, and around it a release server and
a menu web API on localhost. The kit installer is a stand-in that honours the unattended
interface of the real one (--check, --ota, --recover, a JSON last line).

Run on the build computer:  python3 -B release/tests/test_updater.py   (needs OpenSSL 3+)
"""
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

UPDATER = Path(__file__).resolve().parents[1] / 'updater.py'
FW = 'scarab 2026/05/11 00:09'
SLUG = 'scarab-2026-05-11-00-09'
MODEL = 'Anbernic RG35XX-H'

INSTALLER = '''import hashlib, json, os, shutil, sys
ROOT, BEHAVIOUR = {root!r}, {behaviour!r}
data = ROOT + '/userdata'
open(ROOT + '/calls.log', 'a').write('installer ' + sys.argv[1] + '\\n')
journal = data + '/system/.canica-installer-v1'
def put(rel, text):
    os.makedirs(os.path.dirname(data + '/' + rel), exist_ok=True)
    open(data + '/' + rel, 'w').write(text)
def seal(files):
    for rel, text in files.items(): put(rel, text)
    put('system/canica/SHA256SUMS', ''.join('%s  %s\\n' % (hashlib.sha256(t.encode()).hexdigest(), r) for r, t in sorted(files.items())))
OLD = {old!r}
NEW = {new!r}
if sys.argv[1] == '--recover':
    seal(OLD); shutil.rmtree(journal, ignore_errors=True)
    print(json.dumps(dict(ok=True, recovered=True))); sys.exit(0)
if sys.argv[1] == '--check':
    if BEHAVIOUR == 'no-check': print('uso: Instalar Canica.sh [--ota | --recover]'); sys.exit(2)
    if BEHAVIOUR == 'refuse':
        print(json.dumps(dict(ok=False, reason='Se conserva tu archivo modificado: themes/es-theme-canica/theme.xml'))); sys.exit(1)
    print(json.dumps(dict(ok=True, check=True, files=len(NEW)))); sys.exit(0)
if BEHAVIOUR in ('refuse', 'refuse-late'):
    print(json.dumps(dict(ok=False, reason='Se conserva tu archivo modificado: themes/es-theme-canica/theme.xml'))); sys.exit(1)
if BEHAVIOUR == 'die-midway':
    put('themes/es-theme-canica/theme.xml', NEW['themes/es-theme-canica/theme.xml']); os.makedirs(journal, exist_ok=True); os._exit(9)
print('@canica step files', flush=True)
shutil.rmtree(journal, ignore_errors=True)
seal(NEW)
print('@canica step cards', flush=True)
for i in range(2): print('@canica cards %d 2' % i, flush=True)
print('Tarjetas de juegos con captura: 3')
print(json.dumps(dict(ok=True, written=len(NEW), adapter_kept=False, cards_failed=False)))
'''

SERVICE = '''#!/bin/bash
R={root}
echo "service $1" >> "$R/calls.log"
case "$1" in
  start)
    [ -e "$R/service-refuses" ] && exit 1
    (cd "$R/userdata" && sha256sum --status -c system/canica/SHA256SUMS) || exit 1
    mkdir -p "$R/var/run/canica/bin"
    cmp -s "$R/userdata/system/canica/bin/emulationstation" "$R/var/run/canica/bin/emulationstation" ||
      {{ cp "$R/userdata/system/canica/bin/emulationstation" "$R/var/run/canica/bin/emulationstation.new" &&
         mv -f "$R/var/run/canica/bin/emulationstation.new" "$R/var/run/canica/bin/emulationstation"; }}
    ;;
  stop) ;;
esac
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(ago):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - ago))


class Console:
    """A console under a temporary root, its release server and its menu."""

    def __init__(self, case, mode=None, language='es_MX'):
        self.root = Path(tempfile.mkdtemp()).resolve()
        case.addCleanup(shutil.rmtree, self.root, True)
        self.rel = self.root / 'releases' / ('canica-' + SLUG)
        self.rel.mkdir(parents=True)
        self.notices, self.panel, self.offers, self.fetched = [], [], [], []
        self.game, self.serve_releases, self.screen_off, self.watchdog_gives_up = False, True, False, False
        self.has_console, self.has_notice, self.screens = True, False, []
        self.restarts = 4000
        self.old = {'system/canica/bin/emulationstation': 'engine 1', 'system/canica/release': 'LABEL=RC35\n',
                    'themes/es-theme-canica/theme.xml': 'theme 1'}
        self.new = {'system/canica/bin/emulationstation': 'engine 2', 'system/canica/release': 'LABEL=RC36\n',
                    'themes/es-theme-canica/theme.xml': 'theme 2'}
        r = self.root
        for rel, text in {
                'usr/share/knulli/knulli.version': FW + '\n', 'proc/device-tree/model': MODEL + '\0',
                'proc/uptime': '100.0 100.0\n', 'proc/sys/kernel/random/boot_id': 'boot-1\n',
                'sys/class/power_supply/battery/type': 'Battery\n', 'sys/class/power_supply/battery/capacity': '80\n',
                'sys/class/power_supply/battery/status': 'Charging\n', 'var/run/emulationstation-standalone': '',
                'services': 'canica\n', 'usr/bin/emulationstation': 'factory menu',
                'userdata/system/knulli.conf': '#system.language=fr_FR\nsystem.language=%s\n' % language}.items():
            (r / rel).parent.mkdir(parents=True, exist_ok=True)
            (r / rel).write_text(text)
        self.seal(self.old)
        kit = r / 'userdata/system/canica'
        shutil.copy(UPDATER, kit / 'updater.py')
        (kit / 'keys').mkdir()
        self.key, self.other_key = r / 'signing.pem', r / 'other.pem'
        for key in (self.key, self.other_key):
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'ed25519', '-out', str(key)], check=True)
        subprocess.run(['openssl', 'pkey', '-in', str(self.key), '-pubout', '-out', str(kit / 'keys/test.pub')], check=True)
        self.old['system/canica/keys/test.pub'] = self.new['system/canica/keys/test.pub'] = (kit / 'keys/test.pub').read_text()
        self.seal(self.old)
        svc = r / 'userdata/system/services/canica'
        svc.parent.mkdir(parents=True)
        svc.write_text(SERVICE.format(root=r))
        subprocess.run(['bash', str(svc), 'start'], check=True)
        self.menu(4000)
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), self.handler())
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        case.addCleanup(self.server.server_close)
        case.addCleanup(self.server.shutdown)
        url = 'http://127.0.0.1:%d' % self.server.server_address[1]
        self.home = r / 'userdata/system/canica-updates'
        self.home.mkdir()
        (self.home / 'config.env').write_text(
            'BASE_URL=%s/releases\nES_API=%s/es\nALLOW_HTTP_LOCALHOST=1\nSTART_TIMEOUT=5\nINSTALL_TIMEOUT=30\n'
            'NOTE_AFTER=0\nBOOT_DELAY=0\nPOLL=1\n' % (url, url))
        if mode:
            (self.home / 'mode').write_text(mode + '\n')
        bin_dir = r / 'bin'
        bin_dir.mkdir()
        for name, body in (('knulli-settings-get', 'cat "%s/services"' % r),
                           ('knulli-services', 'echo "knulli-services $*" >> "%s/calls.log"' % r)):
            (bin_dir / name).write_text('#!/bin/sh\n%s\n' % body)
            (bin_dir / name).chmod(0o755)
        (r / 'calls.log').unlink()      # the start that prepared this console

    def seal(self, files):
        data = self.root / 'userdata'
        for rel, text in files.items():
            (data / rel).parent.mkdir(parents=True, exist_ok=True)
            (data / rel).write_text(text)
        (data / 'system/canica/SHA256SUMS').write_text(''.join(
            '%s  %s\n' % (hashlib.sha256(t.encode()).hexdigest(), rel) for rel, t in sorted(files.items())))

    def inventory(self, files):
        text = ''.join('%s  %s\n' % (hashlib.sha256(t.encode()).hexdigest(), rel) for rel, t in sorted(files.items()))
        return hashlib.sha256(text.encode()).hexdigest()

    def menu(self, pid, frontend='var/run/canica/bin/emulationstation'):
        """Replace the menu process with one whose executable is that file. As on the console,
        its name is cut to 15 characters and the script that relaunches it has the same name."""
        for d in (self.root / 'proc').iterdir():
            if d.name.isdigit():
                shutil.rmtree(d)
        for number, parent, exe in ((100, 1, '/bin/bash'), (pid, 100, self.root / frontend)):
            if number:
                p = self.root / 'proc' / str(number)
                p.mkdir()
                (p / 'comm').write_text('emulationstatio\n')
                (p / 'stat').write_text('%d (emulationstatio) %s %d 1284 0\n' % (number, 'T' if number == 100 and self.screen_off else 'S', parent))
                os.symlink(exe, p / 'exe')

    def handler(console):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def answer(self, status, body=b''):
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == '/es/runningGame':
                    return self.answer(200 if console.game else 201, b'{}')
                if self.path == '/es/caps':
                    return self.answer(200, b'{}')
                if self.path == '/es/quit':
                    console.restarts += 1          # every menu start is another process
                    if console.watchdog_gives_up:
                        state = console.root / 'var/run/canica/state'
                        state.mkdir(parents=True, exist_ok=True)
                        (state / 'disabled').write_text('')
                        console.menu(console.restarts, 'usr/bin/emulationstation')
                    else:
                        console.menu(console.restarts)
                    return self.answer(200)
                target = console.root / self.path.lstrip('/')
                if self.path.startswith('/releases/'):
                    console.fetched.append(self.path.rsplit('/', 1)[1])
                    if console.serve_releases and target.is_file():
                        return self.answer(200, target.read_bytes())
                self.answer(404)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
                if self.path == '/es/notify':
                    console.notices.append(body)
                    return self.answer(200)
                if self.path == '/es/progress-notice' and (console.has_notice or body == 'close'):
                    console.panel.append(body)
                    return self.answer(200)
                if self.path == '/es/job-console' and (console.has_console or body == 'close'):
                    rows = body.split('\n')
                    console.screens.append(rows)
                    if rows[0].startswith('ask '):      # serial, label, the note's rows
                        console.offers.append([rows[0][4:], rows[2].split(' → ')[1], ' '.join(r for r in rows[6:] if '\t' not in r)])
                    return self.answer(200)
                self.answer(404)
        return Handler

    def publish(self, serial, label='RC36', behaviour='install', key=None, age=3 * 86400, **changes):
        payload = self.rel / ('canica-%d.sh' % serial)
        payload.write_text(INSTALLER.format(root=str(self.root), behaviour=behaviour, old=self.old, new=self.new))
        manifest = dict(format=1, kind='canica-kit', model=MODEL, firmware=FW, version='1.0.1-' + label.lower(), label=label,
                        serial=serial, min_serial=serial, inventory_sha256=self.inventory(self.new), created=stamp(age),
                        payload=dict(name=payload.name, sha256=digest(payload), size=payload.stat().st_size))
        manifest.update(changes)
        (self.rel / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
        subprocess.run(['openssl', 'pkeyutl', '-sign', '-rawin', '-inkey', str(key or self.key),
                        '-in', str(self.rel / 'manifest.json'), '-out', str(self.rel / 'manifest.json.sig')], check=True)

    def env(self):
        return dict(os.environ, CANICA_ROOT=str(self.root), CANICA_LOG_ONLY='1',
                    CANICA_PATH='%s/bin:%s' % (self.root, os.environ['PATH']))

    def run(self, cmd='once', request=None):
        if request:
            (self.home / 'request').write_text(request + '\n')
        r = subprocess.run([sys.executable, '-I', str(self.root / 'userdata/system/canica/updater.py'), cmd],
                           env=self.env(), capture_output=True, text=True, timeout=120)
        log = self.root / 'userdata/system/logs/canica-updates.log'
        cycles = [line for line in log.read_text().splitlines() if ' cycle (' in line] if log.exists() else []
        return (cycles[-1].split(': ', 1)[1] if cycles else '') + r.stdout + r.stderr

    def steps(self):
        """The terminal screen's progress, as (gauge, the step under way)."""
        return [(rows[0], rows[-1]) for rows in self.screens if rows[0].startswith('progress ')]

    def state(self):
        return json.loads((self.home / 'state.json').read_text())

    def status(self):
        return dict(line.split('=', 1) for line in (self.home / 'status').read_text().splitlines())

    def calls(self):
        log = self.root / 'calls.log'
        return log.read_text().split('\n')[:-1] if log.exists() else []

    def installed(self):
        return digest(self.root / 'userdata/system/canica/SHA256SUMS') == self.inventory(self.new)


STEPS = [('progress 3', 'kit\tcomprobando'), ('progress 8', 'archivos\tcopiando'), ('progress 15', 'tarjetas\tpreparando'),
         ('progress 15', 'tarjetas\tconsola 1 de 2'), ('progress 52', 'tarjetas\tconsola 2 de 2'),
         ('progress 96', 'menú\treiniciando')]
NOTICE = [['3', 'Actualizando Canica RC36', 'Comprobando el kit. No apagues la consola.'],
          ['8', 'Actualizando Canica RC36', 'Copiando archivos. No apagues la consola.'],
          ['15', 'Actualizando Canica RC36', 'Preparando las tarjetas. No apagues la consola.'],
          ['15', 'Actualizando Canica RC36', 'Tarjetas: consola 1 de 2. No apagues la consola.'],
          ['52', 'Actualizando Canica RC36', 'Tarjetas: consola 2 de 2. No apagues la consola.'],
          ['96', 'Actualizando Canica RC36', 'Reiniciando el menú.']]
DISCLOSE = 'Canica busca actualizaciones en GitHub (START > Canica).'


class AskTest(unittest.TestCase):
    """The default: download, check, ask on the menu; install only on the owner's word."""

    def setUp(self):
        self.c = Console(self)

    def test_says_once_where_it_looks_and_leaves_a_current_kit_alone(self):
        self.c.seal(self.c.new)
        self.c.publish(20)
        self.assertIn('up to date (kit RC36 (20))', self.c.run())
        self.assertEqual((self.c.calls(), self.c.notices, self.c.offers), ([], [DISCLOSE], []))
        self.assertIn('up to date', self.c.run())
        self.assertEqual(self.c.notices, [DISCLOSE])
        st = self.c.status()
        self.assertEqual((st['installed'], st['available'], st['ready'], st['mode']), ('RC36', '', '0', 'ask'))
        self.assertTrue(st['detail'].startswith('Al día. Última búsqueda: '))

    def test_nothing_is_fetched_before_the_menu_could_say_where_it_looks(self):
        self.c.publish(20)
        self.c.game = True
        self.assertIn('waiting for the menu to say where updates come from', self.c.run())
        self.assertEqual((self.c.fetched, self.c.notices), ([], []))

    def test_every_label_leaves_room_before_its_column(self):
        # the terminal screen puts values 12 letters after the label: a label of 12 runs into them
        self.c.publish(20)
        self.c.run()
        self.assertIn('installed and running', self.c.run(request='install 20'))
        steps = [row for rows in self.c.screens for row in rows[5:] if '\t' in row]
        starting = self.c.screens[0][4].split('\t')[2]           # the row the menu adds on «now»
        labels = {row.split('\t')[0] for row in steps} | {starting}
        self.assertTrue(len(labels) > 5 and all(len(label) <= 10 for label in labels), labels)

    def test_a_long_note_is_wrapped_to_the_screen(self):
        note = 'Novedades: el selector usa la ficha de juego y está en Extras.'
        self.c.publish(20, note=note)
        self.assertIn('offered on the menu', self.c.run())
        lines = self.c.screens[-1][9:]
        self.assertEqual(lines, ['Novedades: el selector usa la ficha de juego y', 'está en Extras.'])
        self.assertTrue(all(len(line) <= 46 for line in lines))

    def test_a_newer_kit_is_checked_and_offered_not_installed(self):
        self.c.publish(20, note='Novedades: actualizaciones desde el menú.')
        self.assertIn('kit RC36 (20) offered on the menu', self.c.run())
        self.assertEqual(self.c.offers, [['20', 'RC36', 'Novedades: actualizaciones desde el menú.']])
        rows = self.c.screens[-1]
        self.assertEqual(rows[:7], ['ask 20', 'Canica · Actualización', 'RC35 → RC36', 'Tarda alrededor de un minuto y reinicia el menú.',
                                    'MÁS TARDE\tACTUALIZAR AHORA\tinicio\tarrancando el actualizador', '$ canica update --to rc36',
                                    'firma\ted25519 · test\tok'])
        self.assertRegex(rows[7], r'^descarga\t0\.0 MB · sha256 [0-9a-f]{4}…[0-9a-f]{4}\tok$')
        self.assertEqual(rows[8:], ['prueba\tcabe y no pisa nada tuyo\tok', 'Novedades: actualizaciones desde el menú.'])
        self.assertEqual(self.c.calls(), ['installer --check'])
        self.assertFalse(self.c.installed())
        st = self.c.status()
        self.assertEqual((st['installed'], st['available'], st['serial'], st['ready'], st['detail']),
                         ('RC35', 'RC36', '20', '1', 'RC36 disponible.'))
        # the same boot: asked once, checked once
        self.assertIn('waiting for the owner', self.c.run())
        self.assertEqual((len(self.c.offers), self.c.calls()), (1, ['installer --check']))
        # the dialog was lost with a reboot before any answer: asked again, once
        (self.c.root / 'proc/sys/kernel/random/boot_id').write_text('boot-2\n')
        self.assertIn('offered on the menu', self.c.run())
        self.assertEqual(len(self.c.offers), 2)
        # answered later: only START > Canica offers it from then on
        self.assertIn('waiting for the owner', self.c.run(request='later 20'))
        (self.c.root / 'proc/sys/kernel/random/boot_id').write_text('boot-3\n')
        self.assertIn('waiting for the owner', self.c.run())
        self.assertEqual((len(self.c.offers), self.c.status()['available']), (2, 'RC36'))
        self.assertFalse((self.c.home / 'request').exists())

    def test_now_installs_restarts_the_menu_and_says_what_is_new(self):
        self.c.publish(20, note='Novedades: actualizaciones desde el menú.')
        self.c.run()
        self.assertIn('kit RC36 (20) installed and running', self.c.run(request='install 20'))
        self.assertTrue(self.c.installed())
        self.assertEqual(self.c.calls(), ['installer --check', 'installer --check', 'installer --ota', 'service stop', 'service start'])
        self.assertEqual(self.c.steps(), STEPS)
        last = self.c.screens[-1]
        self.assertEqual((last[2], last[3], last[4]), ('RC35 → RC36', 'No apagues la consola.', ''))
        self.assertEqual(last[-3:], ['archivos\tcopiados\tok', 'tarjetas\tlistas\tok', 'menú\treiniciando'])
        self.assertEqual(self.c.notices, [DISCLOSE, 'Canica RC36 instalada.', 'Novedades: actualizaciones desde el menú.'])
        st = self.c.state()
        self.assertEqual((st['installed']['serial'], st.get('pending'), st.get('available'), st['failed']), (20, None, None, {}))
        self.assertFalse((self.c.home / 'cache/canica-20.sh').exists())
        status = self.c.status()
        self.assertEqual((status['installed'], status['available'], status['ready']), ('RC36', '', '0'))
        self.assertIn('up to date', self.c.run())

    def test_now_is_refused_aloud_during_a_game_or_with_a_low_battery(self):
        self.c.publish(20)
        self.c.run()
        self.c.game = True
        self.assertIn('waiting: a game is running', self.c.run(request='install 20'))
        self.c.game = False
        (self.c.root / 'sys/class/power_supply/battery/status').write_text('Discharging\n')
        (self.c.root / 'sys/class/power_supply/battery/capacity').write_text('12\n')
        self.assertIn('waiting: the battery is low', self.c.run(request='install 20'))
        self.assertEqual(self.c.notices[1:], ['Canica RC36: ahora no, hay un juego abierto. Se instalará al cerrar el juego.',
                                              'Canica RC36: ahora no, batería baja. Se instalará al conectar el cargador.'])
        self.assertFalse(self.c.installed())
        # away from the charger and long after boot, the owner's word is enough
        (self.c.root / 'sys/class/power_supply/battery/capacity').write_text('60\n')
        (self.c.root / 'proc/uptime').write_text('5000.0 5000.0\n')
        self.assertIn('installed and running', self.c.run(request='install 20'))

    def low_battery(self, charging=False):
        (self.c.root / 'sys/class/power_supply/battery/status').write_text('Charging\n' if charging else 'Discharging\n')
        (self.c.root / 'sys/class/power_supply/battery/capacity').write_text('12\n')

    def test_a_yes_that_cannot_start_is_kept_until_it_can(self):
        self.c.publish(20)
        self.assertIn('offered on the menu', self.c.run())
        self.low_battery()
        out = self.c.run(request='install 20')
        self.assertIn('waiting: the battery is low; kit RC36 installs once it can, as the owner asked', out)
        self.assertIn('as the owner asked; next in 120s', out)
        self.assertEqual(self.c.notices[-1], 'Canica RC36: ahora no, batería baja. Se instalará al conectar el cargador.')
        self.assertEqual(self.c.status()['detail'], 'RC36 se instalará al conectar el cargador.')
        # it waits without asking, saying or downloading anything again
        seen = (len(self.c.notices), len(self.c.fetched), len(self.c.offers))
        self.assertIn('installs once it can, as the owner asked', self.c.run())
        self.assertEqual((len(self.c.notices), len(self.c.fetched), len(self.c.offers)), seen)
        self.assertFalse(self.c.installed())
        # on the charger it goes ahead by itself, long after boot
        (self.c.root / 'proc/uptime').write_text('5000.0 5000.0\n')
        self.low_battery(charging=True)
        self.assertIn('installed and running', self.c.run())
        self.assertNotIn('wanted', self.c.state())
        self.assertEqual(len(self.c.offers), seen[2])

    def test_later_or_a_newer_kit_drops_a_kept_yes(self):
        self.c.publish(20)
        self.c.run()
        self.low_battery()
        self.c.run(request='install 20')
        self.assertEqual(self.c.state()['wanted']['serial'], 20)
        self.c.run(request='later 20')
        self.assertNotIn('wanted', self.c.state())
        self.assertIn('waiting for the owner', self.c.run())
        # a kept yes is for that kit only: a newer one is asked about again
        self.c.run(request='install 20')
        self.c.publish(21, label='RC37')
        self.low_battery(charging=True)
        self.assertIn('kit RC37 (21) offered on the menu', self.c.run())
        self.assertNotIn('wanted', self.c.state())
        self.assertFalse(self.c.installed())

    def test_a_theme_without_the_terminal_gets_notices_and_a_pointer_to_the_menu(self):
        self.c.has_console, self.c.has_notice = False, True
        self.c.publish(20)
        self.assertIn('offered on the menu', self.c.run())
        self.assertEqual(self.c.notices[-1], 'Canica RC36 disponible: START > Canica.')
        (self.c.root / 'proc/sys/kernel/random/boot_id').write_text('boot-2\n')
        self.assertIn('waiting for the owner', self.c.run())           # a notice has no answer to wait for
        self.assertIn('installed and running', self.c.run(request='install 20'))
        self.assertEqual([p.split('\n') for p in self.c.panel], NOTICE)
        # the factory menu has neither: plain notices
        self.c.seal(self.c.old)
        self.c.has_notice = False
        self.c.publish(21, label='RC37')
        self.c.run()
        del self.c.notices[:]
        self.assertIn('installed and running', self.c.run(request='install 21'))
        self.assertEqual(self.c.notices, ['Canica RC37: actualizando. No apagues la consola.', 'Canica RC37: reiniciando el menú.',
                                          'Canica RC37 instalada.'])

    def test_an_answer_for_a_kit_that_was_replaced_is_asked_again(self):
        self.c.publish(20)
        self.c.run()
        self.c.publish(21, label='RC37')
        self.assertIn('kit RC37 (21) offered on the menu', self.c.run(request='install 20'))
        self.assertFalse(self.c.installed())
        self.assertEqual(self.c.offers[-1][:2], ['21', 'RC37'])

    def test_a_kit_that_cannot_install_here_is_not_offered(self):
        self.c.publish(20, behaviour='refuse')
        self.assertIn('kit RC36 (20) cannot be installed here (Se conserva tu archivo modificado', self.c.run())
        st = self.c.status()
        self.assertEqual((self.c.offers, st['available'], st['ready']), ([], 'RC36', '0'))
        self.assertTrue(st['detail'].startswith('RC36 no se puede instalar aquí: Se conserva tu archivo modificado'))
        self.assertEqual(self.c.notices, [DISCLOSE])
        self.c.run('check')
        self.assertTrue(self.c.notices[-1].startswith('Canica RC36 no se puede instalar aquí'))
        # an installer without --check is trusted to check when it installs, and the screen does not claim a test
        self.c.publish(21, label='RC37', behaviour='no-check')
        self.assertIn('offered on the menu', self.c.run())
        self.assertFalse([r for r in self.c.screens[-1] if r.startswith('prueba')])

    def test_searching_from_the_menu_answers_on_screen(self):
        self.c.seal(self.c.new)
        self.c.publish(20)
        self.assertIn('up to date', self.c.run(request='check'))
        self.assertEqual(self.c.notices[-1], 'Canica está al día (RC36).')
        self.c.seal(self.c.old)
        self.c.run()
        self.c.run(request='later 20')
        self.assertIn('offered on the menu', self.c.run(request='check'))      # asked for: offered again
        self.assertEqual(len(self.c.offers), 2)
        self.c.serve_releases = False
        (self.c.home / 'cache/canica-20.sh').unlink()
        self.c.run(request='check')
        self.assertEqual(self.c.notices[-1], 'Canica: no hay ninguna actualización publicada.')

    def test_a_withdrawn_kit_is_no_longer_offered(self):
        self.c.publish(20)
        self.c.run()
        self.assertEqual(self.c.status()['available'], 'RC36')
        (self.c.rel / 'manifest.json').unlink()
        self.assertIn('no kit published', self.c.run())
        self.assertEqual((self.c.status()['available'], sorted(p.name for p in (self.c.home / 'cache').iterdir())), ('', []))
        self.assertIn('no kit published', self.c.run(request='install 20'))
        self.assertFalse(self.c.installed())

    def test_other_signers_other_kinds_and_older_kits_are_refused(self):
        self.c.publish(20, key=self.c.other_key)
        self.assertIn('rejected: the manifest signature does not verify', self.c.run())
        self.c.publish(20, kind='knulli-console-fixes')
        self.assertIn('rejected: not a Canica kit manifest', self.c.run())
        self.c.publish(20, firmware='scarab 2027/01/01 00:00')
        self.assertIn('rejected: manifest is for firmware', self.c.run())
        self.c.publish(20, note='dos\nlíneas')
        self.assertIn('rejected: bad note', self.c.run())
        self.c.publish(20, created='ayer')
        self.assertIn('rejected: bad creation time', self.c.run())
        self.c.publish(20)
        payload = self.c.rel / 'canica-20.sh'
        payload.write_bytes(payload.read_bytes()[:-1] + b'#')      # same size, other content
        self.assertIn('rejected: payload sha256 or size differs', self.c.run())
        self.c.seal(self.c.new)
        self.c.publish(20)
        self.c.run()
        self.c.seal(self.c.old)
        self.c.publish(10, label='RC29')
        self.assertIn('rejected: kit 10 is older than 20', self.c.run())
        self.assertEqual((self.c.calls(), self.c.offers, self.c.notices), ([], [], [DISCLOSE]))
        self.assertEqual(self.c.status()['detail'][:38], 'Se rechazó la actualización publicada.')
        # a key dropped into keys/ after the kit was sealed is not trusted
        subprocess.run(['openssl', 'pkey', '-in', str(self.c.other_key), '-pubout', '-out',
                        str(self.c.root / 'userdata/system/canica/keys/dropped.pub')], check=True)
        self.c.publish(30, key=self.c.other_key)
        self.assertIn('rejected: the manifest signature does not verify', self.c.run())
        # nor a sealed key that was changed afterwards
        shutil.copy(self.c.root / 'userdata/system/canica/keys/dropped.pub', self.c.root / 'userdata/system/canica/keys/test.pub')
        self.assertIn('rejected: this kit has no sealed key', self.c.run())

    def test_off_in_services_or_with_the_add_on_nothing_is_done(self):
        self.c.publish(20)
        (self.c.root / 'services').write_text('es_patched\n')
        self.assertIn('Canica is off in Services: nothing done', self.c.run())
        (self.c.root / 'services').write_text('canica canica_updater\n')
        self.assertIn('the canica_updater add-on is on: standing down', self.c.run(request='install 20'))
        self.assertEqual((self.c.fetched, self.c.notices, self.c.calls()), ([], [], []))
        self.assertEqual(self.c.status()['detail'], 'Las actualizaciones las lleva canica_updater.')

    def test_a_console_that_had_the_add_on_keeps_what_it_learned(self):
        old = self.c.root / 'userdata/system/canica-updater'
        old.mkdir()
        (old / 'state.json').write_text(json.dumps(dict(max_serial=30, min_serial=30, bad=[25], failed={})))
        self.c.publish(20)
        self.assertIn('rejected: kit 20 is older than 30', self.c.run())
        self.assertEqual(self.c.notices, [])        # its owner already knows where updates come from


EN_DISCLOSE = 'Canica checks for updates on GitHub (START > Canica).'
EN_STEPS = [('progress 3', 'kit\tchecking'), ('progress 8', 'files\tcopying'), ('progress 15', 'cards\tpreparing'),
            ('progress 15', 'cards\tconsole 1 of 2'), ('progress 52', 'cards\tconsole 2 of 2'),
            ('progress 96', 'menu\trestarting')]


class EnglishTest(unittest.TestCase):
    """A console in any language but Spanish reads every notice, the update screen and START > Canica in
    English; its release note is the manifest's note_en, none without one."""

    def setUp(self):
        self.c = Console(self, language='en_US')

    def test_the_offer_the_install_and_the_status_are_english(self):
        self.c.publish(20, note='Novedades: actualizaciones desde el menú.', note_en='New: updates from the menu.')
        self.assertIn('kit RC36 (20) offered on the menu', self.c.run())
        rows = self.c.screens[-1]
        self.assertEqual(rows[:7], ['ask 20', 'Canica · Update', 'RC35 → RC36', 'It takes about a minute and restarts the menu.',
                                    'LATER\tUPDATE NOW\tstart\tstarting the updater', '$ canica update --to rc36',
                                    'signature\ted25519 · test\tok'])
        self.assertRegex(rows[7], r'^download\t0\.0 MB · sha256 [0-9a-f]{4}…[0-9a-f]{4}\tok$')
        self.assertEqual(rows[8:], ['check\tfits and keeps your changes\tok', 'New: updates from the menu.'])
        # START > Canica: Spanish in detail for a menu that knows no other, English in detail_en
        st = self.c.status()
        self.assertEqual((st['detail'], st['detail_en']), ('RC36 disponible.', 'RC36 available.'))
        self.assertIn('installed and running', self.c.run(request='install 20'))
        self.assertEqual(self.c.steps(), EN_STEPS)
        last = self.c.screens[-1]
        self.assertEqual((last[1], last[3]), ('Canica · Update', 'Do not turn off the console.'))
        self.assertEqual(last[-3:], ['files\tcopied\tok', 'cards\tready\tok', 'menu\trestarting'])
        self.assertEqual(self.c.notices, [EN_DISCLOSE, 'Canica RC36 installed.', 'New: updates from the menu.'])
        st = self.c.status()
        self.assertTrue(st['detail_en'].startswith('Up to date. Last check: ') and st['detail'].startswith('Al día. Última búsqueda: '))
        labels = {row.split('\t')[0] for rows in self.c.screens for row in rows[5:] if '\t' in row}
        self.assertTrue(all(len(label) <= 10 for label in labels), labels)

    def test_a_kit_without_an_english_note_says_nothing_new(self):
        self.c.publish(20, note='Novedades: actualizaciones desde el menú.')
        self.c.run()
        self.assertEqual(self.c.screens[-1][8:], ['check\tfits and keeps your changes\tok'])
        self.assertIn('installed and running', self.c.run(request='install 20'))
        self.assertEqual(self.c.notices, [EN_DISCLOSE, 'Canica RC36 installed.'])

    def test_a_yes_that_cannot_start_and_the_plain_notices_are_english(self):
        self.c.publish(20)
        self.c.run()
        self.c.game = True
        self.assertIn('waiting: a game is running', self.c.run(request='install 20'))
        self.assertEqual(self.c.notices[-1], 'Canica RC36: not now, a game is open. It will install when the game closes.')
        self.assertEqual(self.c.status()['detail_en'], 'RC36 will install when the game closes.')
        self.c.game = False
        self.c.has_console, self.c.has_notice = False, True
        self.assertIn('installed and running', self.c.run(request='install 20'))
        self.assertEqual(self.c.panel[0].split('\n'), ['3', 'Updating Canica RC36', 'Checking the kit. Do not turn off the console.'])
        self.c.run(request='check')
        self.assertEqual(self.c.notices[-1], 'Canica is up to date (RC36).')

    def test_the_language_is_read_for_each_message(self):
        self.c.publish(20)
        self.c.run()
        (self.c.root / 'userdata/system/knulli.conf').write_text('system.language=es_ES\n')
        self.c.run(request='check')
        self.assertEqual(self.c.screens[-1][1], 'Canica · Actualización')
        (self.c.root / 'userdata/system/knulli.conf').write_text('system.language=pt_BR\n')
        self.c.run(request='check')
        self.assertEqual(self.c.screens[-1][1], 'Canica · Update')


class AutoAndOffTest(unittest.TestCase):
    def test_auto_waits_two_days_after_publication_then_installs_by_itself(self):
        c = Console(self, mode='auto')
        c.publish(20, age=3600)
        self.assertIn('waiting: kit RC36 (20) installs by itself in 47 h', c.run())
        self.assertTrue(c.status()['detail'].startswith('RC36 se instalará sola desde el '))
        self.assertEqual((c.offers, c.installed()), ([], False))
        c.publish(20, age=49 * 3600)
        self.assertIn('kit RC36 (20) installed and running', c.run())
        self.assertEqual(c.calls(), ['installer --check', 'installer --ota', 'service stop', 'service start'])
        self.assertEqual(c.steps(), STEPS)
        self.assertEqual(c.offers, [])

    def test_auto_installs_only_at_boot_or_on_the_charger_with_the_menu_free(self):
        c = Console(self, mode='auto')
        c.publish(20)
        (c.root / 'sys/class/power_supply/battery/status').write_text('Discharging\n')
        (c.root / 'proc/uptime').write_text('5000.0 5000.0\n')
        self.assertIn('waiting: not at boot and not charging', c.run())
        (c.root / 'proc/uptime').write_text('100.0 100.0\n')
        c.game = True
        self.assertIn('waiting: a game is running', c.run())
        c.game, c.screen_off = False, True
        c.menu(4000)
        self.assertIn('waiting: the menu is paused', c.run())
        self.assertEqual((c.installed(), c.notices), (False, [DISCLOSE]))      # waiting is silent
        c.screen_off = False
        c.menu(4000)
        self.assertIn('installed and running', c.run())

    def test_auto_still_offers_at_once_to_an_owner_who_searches(self):
        c = Console(self, mode='auto')
        c.publish(20, age=60)
        self.assertIn('offered on the menu', c.run(request='check'))
        self.assertIn('installed and running', c.run(request='install 20'))

    def test_off_fetches_nothing_until_the_owner_searches(self):
        c = Console(self, mode='off')
        c.publish(20)
        self.assertIn('updates are off', c.run())
        self.assertEqual((c.fetched, c.notices, c.status()['detail']), ([], [], 'Actualizaciones desactivadas.'))
        self.assertIn('offered on the menu', c.run(request='check'))
        self.assertIn('updates are off', c.run())
        # the mode is a file anyone can change, and the menu says so with a request
        (c.home / 'mode').write_text('ask\n')
        self.assertIn('waiting for the owner', c.run(request='mode'))
        self.assertEqual(c.status()['mode'], 'ask')
        (c.home / 'mode').write_text('whatever\n')
        self.assertEqual((c.run(request='mode') and c.status()['mode']), 'ask')


class FailureTest(unittest.TestCase):
    def setUp(self):
        self.c = Console(self)
        self.c.publish(20)
        self.c.run()

    def test_a_refusing_installer_leaves_the_kit_and_says_why_once(self):
        self.c.publish(21, label='RC37', behaviour='refuse-late')
        self.c.run()
        for attempt in (1, 2):
            self.assertIn('kit RC37 (21) not installed (Se conserva tu archivo modificado', self.c.run(request='install 21'))
        self.assertEqual(self.c.panel[-1], 'close')
        self.assertEqual([n for n in self.c.notices if 'no se instaló' in n],
                         ['Canica RC37 no se instaló: Se conserva tu archivo modificado: themes/es-theme-canica/theme.xml'])
        self.assertIn('was refused 2 times', self.c.run())
        self.assertTrue(self.c.status()['detail'].startswith('RC37 no se instaló: Se conserva'))
        self.assertNotIn('service stop', self.c.calls())
        self.assertIn('not installed', self.c.run(request='install 21'))        # asked again: one more round

    def test_an_interrupted_installation_is_finished_without_the_network(self):
        self.c.publish(21, label='RC37', behaviour='die-midway')
        self.c.run()
        self.assertIn('not installed (el instalador no terminó)', self.c.run(request='install 21'))
        self.assertEqual(self.c.calls()[-2:], ['installer --ota', 'installer --recover'])
        self.assertEqual(digest(self.c.root / 'userdata/themes/es-theme-canica/theme.xml'),
                         hashlib.sha256(b'theme 1').hexdigest())
        # power lost while installing: the next start resumes from the cache, offline
        self.c.publish(22, label='RC38')
        self.c.run()
        st = self.c.state()
        st['pending'] = dict(serial=22, label='RC38', phase='install', since=1, boot='boot-0', menu=[4000])
        (self.c.home / 'state.json').write_text(json.dumps(st))
        self.c.serve_releases = False
        self.assertIn('kit RC38 (22) installed and running', self.c.run())

    def test_a_kit_whose_menu_does_not_start_is_held_and_the_next_one_installs_by_itself(self):
        self.c.watchdog_gives_up = True
        self.assertIn('kit RC36 (20): the menu did not come back; held, the factory menu runs', self.c.run(request='install 20'))
        kit = digest(self.c.root / 'userdata/system/canica/SHA256SUMS')
        self.assertEqual((self.c.home / 'hold').read_text().strip(), kit)
        self.assertEqual(self.c.calls()[-3:], ['service stop', 'service start', 'service stop'])
        self.assertFalse([c for c in self.c.calls() if c.startswith('knulli-services')])      # the service stays on
        self.assertEqual(self.c.notices[-1], 'Canica RC36 no arrancó: volví al menú de fábrica.')
        self.assertIn('did not start here before', self.c.run())
        self.assertEqual(self.c.status()['detail'], 'RC36 no arrancó aquí; se espera la siguiente.')
        # the fix arrives: no question, no two days of waiting, and the hold is lifted
        self.c.watchdog_gives_up = False
        shutil.rmtree(self.c.root / 'var/run/canica/state')
        self.c.old, self.c.new = self.c.new, dict(self.c.new, **{'system/canica/release': 'LABEL=RC37\n',
                                                                 'system/canica/bin/emulationstation': 'engine 3'})
        self.c.publish(21, label='RC37', age=60)
        offers = len(self.c.offers)
        self.assertIn('kit RC37 (21) installed and running', self.c.run())
        self.assertEqual((len(self.c.offers), (self.c.home / 'hold').exists()), (offers, False))

    def test_a_service_that_refuses_the_new_kit_holds_it_too(self):
        (self.c.root / 'service-refuses').write_text('')
        self.assertIn('its service refused to start; held', self.c.run(request='install 20'))
        self.assertTrue((self.c.home / 'hold').exists())
        self.assertEqual(self.c.state()['bad'], [20])


class LoopTest(unittest.TestCase):
    def test_the_loop_runs_a_first_cycle_serves_requests_at_once_and_runs_alone(self):
        c = Console(self)
        c.publish(20)
        loop = [sys.executable, '-I', str(c.root / 'userdata/system/canica/updater.py'), 'loop']
        p = subprocess.Popen(loop, env=c.env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(p.wait)
        self.addCleanup(p.kill)

        def wait(what, seconds=40):
            end = time.time() + seconds
            while time.time() < end:
                if what():
                    return True
                time.sleep(0.2)
            return False

        self.assertTrue(wait(lambda: c.offers), 'no first cycle')
        self.assertEqual(subprocess.run(loop, env=c.env(), timeout=20).returncode, 0)       # a second loop leaves at once
        (c.home / 'request').write_text('install 20\n')
        self.assertTrue(wait(c.installed), 'the request was not served')
        self.assertTrue(wait(lambda: not (c.home / 'request').exists()))
        (c.home / 'request').write_text('nonsense\n')
        self.assertTrue(wait(lambda: not (c.home / 'request').exists()), 'a bad request stays')
        self.assertIsNone(p.poll())


class SelfTest(unittest.TestCase):
    def test_selftest_needs_keys_and_the_kit_version(self):
        c = Console(self)
        self.assertIn('selftest ok: kit RC35, 1 keys', c.run('selftest'))
        (c.root / 'userdata/system/canica/keys/test.pub').write_text('not a key\n')
        self.assertIn('OpenSSL cannot read test.pub', c.run('selftest'))
        shutil.rmtree(c.root / 'userdata/system/canica/keys')
        self.assertIn('no key in', c.run('selftest'))


if __name__ == '__main__':
    unittest.main()
