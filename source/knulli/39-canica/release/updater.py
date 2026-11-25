#!/usr/bin/env python3
"""Keep this console's Canica kit current. Part of the kit; standard library only.

The Canica service starts it before any of its own checks (python3 -I, as root):
  loop      the background job: a first cycle soon after boot, the next one when the last one
            said, and one at once when the menu leaves a request
  once      one cycle; prints the seconds until the next one
  check     one cycle now, as when the owner searches from the menu
  status    what is installed, available, pending or refused (JSON)
  selftest  this program, its keys and the firmware's OpenSSL are usable

Who decides: canica-updates/mode holds ask (the default), auto or off. START > Canica writes
it; so can anyone by hand, the folder is on the console's network share.
  ask   a newer kit is downloaded and checked, then the menu asks: now or later. After the
        answer only START > Canica offers that kit.
  auto  it installs by itself SOAK_HOURS after it was published, at boot or on the charger.
  off   nothing is fetched until the owner searches from the menu.
Nothing is done while the Canica service is off in Services, nor while the console's own
canica_updater add-on is on.

Trust: a kit is used only when manifest.json verifies (Ed25519, the firmware's OpenSSL) with
any key sealed in this kit's keys/, is of kind canica-kit, names this model and the exact
knulli.version, and is not below the highest serial seen here. Its payload is that kit's own
installer, named in the manifest with its size and sha256. A new signing key arrives inside a
kit. A kit withdrawn from the channel (no manifest) is no longer offered.

Install: never during a game, with the menu answering and the battery not low; by itself
only at boot (BOOT_WINDOW s) or on the charger. The installer is a transaction: it replaces
only untouched files of a known earlier kit and undoes an interrupted run. Then the service
is started again and the menu restarted; the update counts once the new menu answers. An
update a power loss interrupted is finished at the next start, before any network.

A kit whose menu does not start is held, not removed: its inventory digest goes to
canica-updates/hold, the service then leaves the factory menu alone for that kit, and this
program stays on to bring the next one, which installs by itself. The service is never
turned off from here. There is no downgrade. Log: logs/canica-updates.log.
"""
import calendar
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import ssl
import subprocess
import sys
import textwrap
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.environ.get('CANICA_ROOT', '')
KIT = ROOT + '/userdata/system/canica'
HOME = ROOT + '/userdata/system/canica-updates'
LOG = ROOT + '/userdata/system/logs/canica-updates.log'
LOCK = ROOT + '/var/run/canica-updater.lock'        # the canica_updater add-on takes the same one
LOOP_LOCK = ROOT + '/var/run/canica-updates.loop'
OTHER_LOCK = ROOT + '/var/run/fix-updater.lock'     # a console with firmware fixes: one job at a time
SERVICE = ROOT + '/userdata/system/services/canica'
RUN = ROOT + '/var/run/canica'
JOURNAL = ROOT + '/userdata/system/.canica-installer-v1'
LEGACY = ROOT + '/userdata/system/canica-updater/state.json'
REQUEST = HOME + '/request'
ENV = dict(PATH=os.environ.get('CANICA_PATH', '/usr/sbin:/usr/bin:/sbin:/bin'), HOME='/userdata/system', LANG='C.UTF-8')
DEFAULTS = dict(
    BASE_URL='https://github.com/eduarbo/knulli-console-bundles/releases/download',
    TAG_PREFIX='canica-',
    CA_FILE='/etc/ssl/certs/ca-certificates.crt',
    ES_API='http://127.0.0.1:1234',
    ALLOW_HTTP_LOCALHOST='0',
    BOOT_DELAY='60',
    POLL='3',
    CHECK_INTERVAL='21600',
    RETRY_MIN='600',
    RETRY_MAX='21600',
    BUSY_RETRY='600',
    BOOT_WINDOW='900',
    MIN_BATTERY='20',
    SOAK_HOURS='48',
    MAX_ATTEMPTS='2',
    PAYLOAD_MAX='67108864',
    INSTALL_TIMEOUT='900',
    CHECK_TIMEOUT='300',
    START_TIMEOUT='180',
    NOTE_AFTER='7',
    MAX_RESTARTS='2',
)
SHA256 = re.compile(r'^[0-9a-f]{64}$')
LABEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 .]{0,23}$')
VERSION = re.compile(r'^[0-9a-z][0-9a-z.+-]{0,39}$')
NOTE = re.compile(r'^[^\x00-\x1f\x7f]{1,90}$')
CREATED = '%Y-%m-%dT%H:%M:%SZ'
MENU_EXE = re.compile(r'/emulationstation(\.stock)?( \(deleted\))?$')
DISCLOSE = 'Canica busca actualizaciones en GitHub (START > Canica).'
TITLE = 'Canica · Actualización'
# why an install cannot start now: (for the log, for the owner who asked)
WHY = dict(
    menu=('the menu does not answer', 'el menú no responde'),
    game=('a game is running', 'hay un juego abierto'),
    battery=('the battery is low', 'batería baja; conecta el cargador'),
    window=('not at boot and not charging', 'espera al cargador o al próximo arranque'),
    paused=('the menu is paused or its launcher is', 'la pantalla está apagada'),
    launcher=('the menu is not the one the system relaunches', 'el menú no se puede reiniciar ahora'),
    other=('another updater is working', 'otra actualización está en curso'),
)


class Offline(Exception):
    pass


class NotFound(Exception):
    pass


class Reject(Exception):
    """The published kit must not be used (bad signature, other firmware, bad file...)."""


def read(path, default=''):
    try:
        with open(path) as f:
            return f.read()
    except (OSError, ValueError):
        return default


def write(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def env_file(path):
    found = {}
    for line in read(path).splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            found[k.strip()] = v.strip().strip('"').strip("'")
    return found


CFG = dict(DEFAULTS, **env_file(HOME + '/config.env'))


def num(key):
    try:
        return int(CFG[key])
    except ValueError:
        return int(DEFAULTS[key])


def now():
    return int(time.time())


def log(msg):
    line = '%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), msg)
    if not os.environ.get('CANICA_LOG_ONLY'):
        sys.stderr.write(line)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 512 * 1024:
            os.replace(LOG, LOG + '.1')
        with open(LOG, 'a') as f:
            f.write(line)
    except OSError:
        pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def slug(version):
    return re.sub(r'[^a-z0-9]+', '-', version.lower()).strip('-')


def firmware():
    return read(ROOT + '/usr/share/knulli/knulli.version').rstrip('\n')


def model():
    try:
        with open(ROOT + '/proc/device-tree/model', 'rb') as f:
            return f.read().replace(b'\0', b'').decode()
    except OSError:
        return ''


def boot_id():
    return read(ROOT + '/proc/sys/kernel/random/boot_id').strip() or 'unknown'


def uptime():
    try:
        return float(read(ROOT + '/proc/uptime').split()[0])
    except (IndexError, ValueError):
        return 0.0


def services():
    """The user services turned on in KNULLI, None when that cannot be read."""
    try:
        r = subprocess.run(['knulli-settings-get', 'system.services'], env=ENV, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1) or r.stderr.strip():     # 1 without a word: the key was never set
        return None
    return r.stdout.split()


def mode():
    word = read(HOME + '/mode').strip()
    return word if word in ('ask', 'auto', 'off') else 'ask'


# --- state ---------------------------------------------------------------------------------

def load_state():
    try:
        with open(HOME + '/state.json') as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
        try:        # this console had the add-on: what it learned about the channel still holds
            with open(LEGACY) as f:
                old = json.load(f)
            st = dict(max_serial=int(old.get('max_serial', 0)), min_serial=int(old.get('min_serial', 0)),
                      bad=[s for s in old.get('bad', []) if type(s) is int], disclosed=now())
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    for key, empty in (('max_serial', 0), ('min_serial', 0), ('failed', {}), ('bad', []), ('fail_streak', 0)):
        st.setdefault(key, empty)
    return st


def save_state(st):
    write(HOME + '/state.json', json.dumps(st, indent=1, sort_keys=True))


def write_status(st, detail):
    """What START > Canica shows: key=value lines, one value each."""
    a = st.get('available') or {}
    rows = (('installed', kit_label() or (st.get('installed') or {}).get('label', '')),
            ('available', a.get('label', '')), ('serial', a.get('serial', '')),
            ('ready', '1' if a.get('ready') else '0'), ('note', a.get('note', '')),
            ('detail', detail), ('mode', mode()), ('checked', st.get('checked', 0)))
    write(HOME + '/status', ''.join('%s=%s\n' % (k, re.sub(r'[\x00-\x1f\x7f]+', ' ', str(v))) for k, v in rows))


def last_check(st):
    if not st.get('checked'):
        return ''
    return ' Última búsqueda: %s.' % time.strftime('%d/%m %H:%M', time.localtime(st['checked']))


# --- HTTP ----------------------------------------------------------------------------------

def allowed_url(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme == 'https':
        return True
    return u.scheme == 'http' and CFG['ALLOW_HTTP_LOCALHOST'] == '1' and u.hostname in ('127.0.0.1', 'localhost', '::1')


class HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise Reject('redirect to a non-HTTPS URL refused: %s' % newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, dest, limit):
    """Download url to dest (at most limit bytes). NotFound on 404, Offline on network errors."""
    if not allowed_url(url):
        raise Reject('not an HTTPS URL: %s' % url)
    ctx = ssl.create_default_context(cafile=CFG['CA_FILE'] if os.path.exists(CFG['CA_FILE']) else None)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), HttpsOnlyRedirect())
    tmp = dest + '.part'
    try:
        with opener.open(urllib.request.Request(url, headers={'User-Agent': 'canica-updater'}), timeout=60) as r:
            size = 0
            with open(tmp, 'wb') as f:
                while True:
                    block = r.read(1 << 16)
                    if not block:
                        break
                    size += len(block)
                    if size > limit:
                        raise Reject('%s is larger than %d bytes' % (url, limit))
                    f.write(block)
    except BaseException as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        if isinstance(e, urllib.error.HTTPError):
            if e.code == 404:
                raise NotFound(url)
            raise Offline('%s: HTTP %d' % (url, e.code))
        if isinstance(e, (urllib.error.URLError, OSError, ssl.SSLError)):
            raise Offline('%s: %s' % (url, getattr(e, 'reason', e)))
        raise
    os.replace(tmp, dest)


# --- the menu, the battery, games ------------------------------------------------------------

def es(path, data=None):
    """(status, body) from the menu's web API, (0, b'') when it does not answer."""
    req = urllib.request.Request(CFG['ES_API'] + path, data=data,
                                 headers={'Content-Type': 'text/plain; charset=utf-8'} if data is not None else {})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b''
    except (urllib.error.URLError, OSError):
        return 0, b''


def notify(text, tries=20):
    for _ in range(tries):
        if es('/notify', text.encode())[0] in (200, 201, 204):
            log('notified: ' + text)
            return True
        time.sleep(3)
    log('could not notify: ' + text)
    return False


def game_process():
    try:
        pids = [p for p in os.listdir(ROOT + '/proc') if p.isdigit()]
    except OSError:
        return None
    for pid in pids:
        try:
            with open('%s/proc/%s/cmdline' % (ROOT, pid), 'rb') as f:
                if b'emulatorlauncher' in f.read():
                    return pid
        except OSError:
            continue
    return None


def battery():
    """(capacity or None, charging)"""
    base_dir = ROOT + '/sys/class/power_supply'
    for d in sorted(os.listdir(base_dir)) if os.path.isdir(base_dir) else []:
        base = '%s/%s/' % (base_dir, d)
        try:
            if read(base + 'type').strip() != 'Battery':
                continue
            return int(read(base + 'capacity').strip()), read(base + 'status').strip() in ('Charging', 'Full')
        except ValueError:
            continue
    return None, True


def menu_pids():
    """(all menu processes, those running this kit's frontend). A menu is known by its
    executable: the kernel cuts its name to 15 characters, and the script that relaunches it
    carries the same name."""
    try:
        kit = os.stat(RUN + '/bin/emulationstation')
    except OSError:
        kit = None
    every, ours = [], []
    for pid in os.listdir(ROOT + '/proc') if os.path.isdir(ROOT + '/proc') else []:
        link = '%s/proc/%s/exe' % (ROOT, pid)
        try:
            if not pid.isdigit() or not MENU_EXE.search(os.readlink(link)):
                continue
            every.append(int(pid))
            if kit and os.path.samestat(os.stat(link), kit):
                ours.append(int(pid))
        except OSError:
            continue
    return every, ours


def proc_state(pid):
    """(state letter, parent pid) of a process, ('', '0') when it is gone."""
    fields = read('%s/proc/%s/stat' % (ROOT, pid)).rsplit(')', 1)[-1].split()
    return (fields[0], fields[1]) if len(fields) >= 2 else ('', '0')


def paused(pid):
    """The menu or a process above it is stopped (a battery saver with the screen off): after a
    restart nothing would start the menu again."""
    for _ in range(8):
        state, parent = proc_state(pid)
        if state == 'T':
            return True
        if parent in ('0', '1'):
            return False
        pid = parent
    return False


def busy(window):
    """Key of WHY when an install cannot start now, or None. window: only at boot or charging."""
    code = es('/runningGame')[0]
    if code == 0:
        return 'menu'
    if code != 201 or game_process():
        return 'game'
    if not os.path.exists(ROOT + '/var/run/emulationstation-standalone'):
        return 'launcher'
    if any(paused(pid) for pid in menu_pids()[0]):
        return 'paused'
    capacity, charging = battery()
    if capacity is not None and not charging and capacity < num('MIN_BATTERY'):
        return 'battery'
    if window and not charging and uptime() > num('BOOT_WINDOW'):
        return 'window'
    return None


# --- the kit on this console -----------------------------------------------------------------

def kit_digest():
    """sha256 of the installed kit's inventory (what its service seals), None without a kit."""
    path = KIT + '/SHA256SUMS'
    return sha256(path) if os.path.isfile(path) else None


def kit_label():
    return env_file(KIT + '/release').get('LABEL', '')


def sealed():
    """Every file of the installed kit matches its inventory, as the service checks at boot."""
    try:
        return subprocess.run(['sha256sum', '--status', '-c', 'system/canica/SHA256SUMS'], cwd=ROOT + '/userdata',
                              env=ENV, stdin=subprocess.DEVNULL, timeout=300).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def held():
    """The installed kit is the one whose menu did not start here."""
    digest = kit_digest()
    return bool(digest) and read(HOME + '/hold').strip() == digest


# --- manifest and payload --------------------------------------------------------------------

def sealed_keys():
    """The kit's public keys that its inventory lists, unchanged: a file dropped into keys/ later (the
    folder is on the network share) is not trusted."""
    keys = []
    for line in read(KIT + '/SHA256SUMS').splitlines():
        digest, _, name = line.partition('  ')
        if not re.fullmatch(r'system/canica/keys/[A-Za-z0-9._-]+\.pub', name):
            continue
        path = ROOT + '/userdata/' + name
        if os.path.isfile(path) and sha256(path) == digest:
            keys.append(path)
    return sorted(keys)


def verify_signature(manifest, sig):
    keys = sealed_keys()
    if not keys:
        raise Reject('this kit has no sealed key in keys/')
    if os.path.getsize(sig) != 64:
        raise Reject('signature is not 64 bytes')
    for key in keys:
        try:
            r = subprocess.run(['openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', key, '-rawin', '-in', manifest,
                                '-sigfile', sig], env=ENV, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise Reject('OpenSSL could not run: %s' % e)
        if r.returncode == 0:
            return os.path.basename(key)
    raise Reject('the manifest signature does not verify with any key of this kit')


def check_manifest(m, fw):
    if not isinstance(m, dict) or m.get('kind') != 'canica-kit' or m.get('format') != 1:
        raise Reject('not a Canica kit manifest of format 1')
    if m.get('model') != model():
        raise Reject('manifest is for %r, this is %r' % (m.get('model'), model()))
    if m.get('firmware') != fw:
        raise Reject('manifest is for firmware %r' % m.get('firmware'))
    if type(m.get('serial')) is not int or m['serial'] <= 0 or type(m.get('min_serial', 0)) is not int:
        raise Reject('manifest has no serial')
    if not LABEL.match(str(m.get('label', ''))) or not VERSION.match(str(m.get('version', ''))):
        raise Reject('bad kit name')
    if not SHA256.match(str(m.get('inventory_sha256', ''))):
        raise Reject('bad inventory digest')
    if 'note' in m and not (isinstance(m['note'], str) and NOTE.match(m['note'])):
        raise Reject('bad note')
    if 'created' in m:
        try:
            time.strptime(m['created'], CREATED)
        except (TypeError, ValueError):
            raise Reject('bad creation time')
    p = m.get('payload')
    if (not isinstance(p, dict) or p.get('name') != 'canica-%d.sh' % m['serial'] or not SHA256.match(str(p.get('sha256', '')))
            or type(p.get('size')) is not int or not 0 < p['size'] <= num('PAYLOAD_MAX')):
        raise Reject('bad payload entry')


def read_manifest(folder, fw, st):
    key = verify_signature(folder + '/manifest.json', folder + '/manifest.json.sig')
    try:
        with open(folder + '/manifest.json') as f:
            m = json.load(f)
    except ValueError:
        raise Reject('manifest is not JSON')
    check_manifest(m, fw)
    floor = max(st['min_serial'], st['max_serial'])
    if m['serial'] < floor:
        raise Reject('kit %d is older than %d, already seen here (revoked or replayed)' % (m['serial'], floor))
    return m, key


def base_url(fw):
    return '%s/%s%s' % (CFG['BASE_URL'].rstrip('/'), CFG['TAG_PREFIX'], slug(fw))


def get_manifest(fw, st):
    """The newest verified manifest: from the network, kept in cache/ with its signature."""
    work = HOME + '/cache/new'
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    try:
        fetch(base_url(fw) + '/manifest.json', work + '/manifest.json', 65536)
        fetch(base_url(fw) + '/manifest.json.sig', work + '/manifest.json.sig', 1024)
        m, key = read_manifest(work, fw, st)
        for name in ('manifest.json', 'manifest.json.sig'):
            os.replace(work + '/' + name, HOME + '/cache/' + name)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    forget_cache(keep=m['payload']['name'])
    return m, key


def forget_cache(keep=None, manifest=False):
    """Drop payloads of other kits; with manifest, the cached manifest too (a withdrawn kit)."""
    for name in os.listdir(HOME + '/cache') if os.path.isdir(HOME + '/cache') else []:
        payload = re.fullmatch(r'canica-[0-9]+\.sh(\.part)?', name) and name != keep
        if payload or (manifest and name in ('manifest.json', 'manifest.json.sig')):
            os.remove(HOME + '/cache/' + name)


def payload_path(m):
    return HOME + '/cache/' + m['payload']['name']


def payload_ready(m):
    path = payload_path(m)
    return os.path.isfile(path) and os.path.getsize(path) == m['payload']['size'] and sha256(path) == m['payload']['sha256']


def get_payload(fw, m):
    if payload_ready(m):
        return
    free = shutil.disk_usage(HOME).free
    if free < 4 * m['payload']['size'] + 50 * 1024 * 1024:
        raise Offline('not enough free space on /userdata (%d MB)' % (free // 2 ** 20))
    fetch(base_url(fw) + '/' + m['payload']['name'], payload_path(m), m['payload']['size'])
    if not payload_ready(m):
        os.remove(payload_path(m))
        raise Reject('payload sha256 or size differs from the manifest')
    os.chmod(payload_path(m), 0o600)


def soak_left(m):
    """Seconds until a kit may install by itself: SOAK_HOURS after it was published."""
    try:
        created = calendar.timegm(time.strptime(m.get('created', ''), CREATED))
    except (TypeError, ValueError):
        return 0
    return created + num('SOAK_HOURS') * 3600 - now()


# --- install and activation ------------------------------------------------------------------

def settled(m):
    """What is already known about a kit, as finished rows of the terminal screen."""
    p = m['payload']
    rows = [('firma', 'ed25519 · %s' % m.get('_key', 'llave del kit')),
            ('descarga', '%.1f MB · sha256 %s…%s' % (p['size'] / 1e6, p['sha256'][:4], p['sha256'][-4:]))]
    if m.get('_checked'):
        rows.append(('prueba', 'cabe y no pisa nada tuyo'))
    return rows


def console(m, head, footer, rows, answers=''):
    """The update's terminal screen on the menu: a title bar, the command, the rows given and a
    footer. False when this menu or its theme has no such screen."""
    body = '\n'.join([head, TITLE, '%s → %s' % (m.get('_from') or kit_label() or '?', m['label']), footer, answers,
                      '$ canica update --to %s' % m['label'].lower()] + rows)
    return es('/job-console', body.encode())[0] == 200


def panel(m, percent, now, done=(), plain=''):
    """The update's progress on the running menu, until the menu restarts: the terminal screen
    where the theme has one (the step under way after the finished ones), else a notice that
    stays with the plain sentence. False when the menu has neither."""
    rows = ['%s\t%s\tok' % step for step in settled(m) + list(done)] + ['%s\t%s' % now]
    if console(m, 'progress %d' % percent, 'No apagues la consola.', rows):
        return True
    body = '%d\nActualizando Canica %s\n%s' % (percent, m['label'], plain)
    return es('/progress-notice', body.encode())[0] == 200


def panel_close():
    for path in ('/job-console', '/progress-notice'):
        es(path, b'close')


def follow(m):
    """Turn the installer's progress lines into the screen's rows and gauge."""
    copied = [('archivos', 'copiados')]

    def line(text):
        words = text.split()
        if words[:3] == ['@canica', 'step', 'files']:
            panel(m, 8, ('archivos', 'copiando'), plain='Copiando archivos. No apagues la consola.')
        elif words[:3] == ['@canica', 'step', 'cards']:
            panel(m, 15, ('tarjetas', 'preparando'), copied, 'Preparando las tarjetas. No apagues la consola.')
        elif words[:2] == ['@canica', 'cards'] and len(words) == 4 and words[2].isdigit() and words[3].isdigit() and int(words[3]):
            done, total = int(words[2]), int(words[3])
            step = 'consola %d de %d' % (done + 1, total)
            panel(m, 15 + min(75, 75 * done // total), ('tarjetas', step), copied, 'Tarjetas: %s. No apagues la consola.' % step)
    return line


def run_installer(m, how, on_line=None):
    """The published kit's own installer, unattended: (exit status or None, its JSON result).
    on_line gets each progress line as it is printed."""
    limit = num('CHECK_TIMEOUT' if how == '--check' else 'INSTALL_TIMEOUT')
    try:
        p = subprocess.Popen([sys.executable or '/usr/bin/python3', '-I', payload_path(m), how], env=ENV,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        log('  installer %s: %s' % (how, e))
        return None, {}
    lines = []

    def pump():
        for raw in p.stdout:
            text = raw.decode(errors='replace').rstrip('\n')
            lines.append(text)
            if on_line and text.startswith('@canica '):
                on_line(text)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    try:
        p.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        lines.append('[timeout]')
    reader.join(5)
    said = [text for text in lines if text.strip() and not text.startswith('@canica ')]
    for text in said[-12:]:
        log('    | ' + text)
    try:
        result = json.loads(said[-1]) if said else {}
    except ValueError:
        result = {}
    log('  installer %s: exit %s' % (how, p.returncode))
    return p.returncode, result if isinstance(result, dict) else {}


def precheck(m):
    """Would this kit install here? (yes, the installer's reason, worth trying again soon, really
    checked). An installer without --check (exit 2) checks when it installs."""
    status, result = run_installer(m, '--check')
    if status in (0, 2):
        return True, '', False, status == 0
    if status == 75:
        return False, 'otra instalación de Canica está en curso', True, False
    return False, str(result.get('reason') or 'el instalador no pudo comprobarlo'), False, False


def service(action):
    try:
        r = subprocess.run(['bash', SERVICE, action], env=ENV, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        log('  canica %s: %s' % (action, e))
        return False
    for line in r.stdout.decode(errors='replace').strip().splitlines()[-4:]:
        log('    | ' + line)
    log('  canica %s: exit %d' % (action, r.returncode))
    return r.returncode == 0


def wait_for_menu(old_pids):
    """'ok': the kit's frontend, started after the restart, answers its web API. 'failed': the
    kit's own watchdog gave up on it and runs the factory menu. None: not known yet."""
    end = time.time() + num('START_TIMEOUT')
    while time.time() < end:
        if [p for p in menu_pids()[1] if p not in old_pids] and es('/caps')[0] == 200:
            return 'ok'
        if os.path.exists(RUN + '/state/disabled'):
            return 'failed'
        time.sleep(2)
    return None


def give_up(st, m, why):
    """The new kit does not start: hold it, back to the factory menu, and wait for the next
    kit. The service stays on, so this program does too."""
    log('kit %s: %s; holding it and returning to the factory menu' % (m['label'], why))
    write(HOME + '/hold', (kit_digest() or '') + '\n')
    service('stop')
    for pid in menu_pids()[1]:
        if ROOT:            # a console under a test root: its process numbers are not this machine's
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    st['bad'].append(m['serial'])
    st.pop('pending', None)
    st.pop('available', None)
    save_state(st)
    notify('Canica %s no arrancó: volví al menú de fábrica.' % m['label'])
    return 'kit %s (%d): %s; held, the factory menu runs' % (m['label'], m['serial'], why)


def activate(st, m, restart=True):
    """Make the installed kit the running one. Returns (result, seconds until the next pass).
    restart=False: the menu has started again since the installation; only confirm it."""
    pend = st['pending']
    later = 'kit %s installed; it starts with the next menu start (%%s)' % m['label']
    if restart:
        why = busy(window=False)
        if why:
            return later % WHY[why][0], num('BUSY_RETRY')
        if pend.get('restarts', 0) < num('MAX_RESTARTS'):
            pend['restarts'] = pend.get('restarts', 0) + 1
            m['_from'] = pend.get('from')
            if not (pend.get('panel') and panel(m, 96, ('menú', 'reiniciando'), [('archivos', 'copiados'), ('tarjetas', 'listas')],
                                                 'Reiniciando el menú.')):
                notify('Canica %s: reiniciando el menú.' % m['label'])
            time.sleep(3)
            old = pend['menu'] = menu_pids()[0]
            save_state(st)
            service('stop')
            if not service('start'):
                return give_up(st, m, 'its service refused to start'), num('CHECK_INTERVAL')
            if set(menu_pids()[0]) & set(old):   # the service restarts only a factory menu
                es('/quit')
    pend['tries'] = pend.get('tries', 0) + 1
    save_state(st)
    verdict = wait_for_menu(pend.get('menu', []))
    if verdict == 'failed':
        return give_up(st, m, 'the menu did not come back'), num('CHECK_INTERVAL')
    if verdict != 'ok' and pend['tries'] <= num('MAX_RESTARTS'):
        return later % 'the new menu has not answered yet', num('BUSY_RETRY')
    st['installed'] = dict(serial=m['serial'], version=m['version'], label=m['label'], at=now())
    for key in ('pending', 'available', 'asked'):
        st.pop(key, None)
    st['failed'].pop(str(m['serial']), None)
    save_state(st)
    if verdict == 'ok':
        notify('Canica %s instalada.' % m['label'])
        if m.get('note'):          # one line about what is new, once the first notice has been read
            time.sleep(num('NOTE_AFTER'))
            notify(m['note'])
    for path in (payload_path(m), HOME + '/hold'):
        if os.path.exists(path):
            os.remove(path)
    write_status(st, 'Al día.' + last_check(st))
    if verdict != 'ok':    # in place and sealed, and restarted: nothing more to do or to say
        return 'kit %s (%d) installed; its menu could not be confirmed' % (m['label'], m['serial']), num('CHECK_INTERVAL')
    return 'kit %s (%d) installed and running' % (m['label'], m['serial']), num('CHECK_INTERVAL')


def failed(st, m, reason, attempts):
    """The kit is as it was before. One notice per kit, in the installer's own words."""
    entry = st['failed'].setdefault(str(m['serial']), {})
    entry.update(reason=reason, attempts=attempts, at=now())
    st.pop('pending', None)
    text = 'Canica %s no se instaló: %s' % (m['label'], reason)
    if not entry.get('noticed'):
        entry['noticed'] = True
        save_state(st)
        notify(text[:160])
    save_state(st)
    write_status(st, text[9:])
    last = attempts >= num('MAX_ATTEMPTS')
    return 'kit %s (%d) not installed (%s); attempt %d' % (m['label'], m['serial'], reason, attempts), \
        num('CHECK_INTERVAL') if last else num('BUSY_RETRY')


def install(st, m, by_owner=False, resumed=False):
    """Install and activate. by_owner: asked for at the menu, so the boot window does not apply
    and a refusal is said on screen. Returns (result, seconds)."""
    if not resumed:
        why = busy(window=not by_owner)
        if why:
            if by_owner:
                notify('Canica %s: ahora no; %s.' % (m['label'], WHY[why][1]))
            return 'waiting: %s' % WHY[why][0], num('BUSY_RETRY')
    other = None
    if os.path.exists(OTHER_LOCK):
        other = open(OTHER_LOCK, 'a')
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            other.close()
            if by_owner:
                notify('Canica %s: ahora no; %s.' % (m['label'], WHY['other'][1]))
            return 'waiting: %s' % WHY['other'][0], num('BUSY_RETRY')
    try:
        entry = st['failed'].setdefault(str(m['serial']), {})
        attempts = entry['attempts'] = entry.get('attempts', 0) + 1     # counted before the try
        m['_from'] = kit_label()
        st['pending'] = dict(serial=m['serial'], label=m['label'], phase='install', since=now(),
                             boot=boot_id(), menu=menu_pids()[0])
        st['pending']['from'] = m['_from']
        save_state(st)
        if attempts > num('MAX_ATTEMPTS'):     # only put the previous kit back
            run_installer(m, '--recover')
            service('start')
            return failed(st, m, 'no se pudo completar', attempts - 1)
        shown = panel(m, 3, ('kit', 'comprobando'), plain='Comprobando el kit. No apagues la consola.')
        if not shown and not resumed:      # the factory menu has no such notice: a plain one
            notify('Canica %s: actualizando. No apagues la consola.' % m['label'])
        st['pending']['panel'] = shown
        status, result = run_installer(m, '--ota', follow(m) if shown else None)
        if kit_digest() != m['inventory_sha256']:
            panel_close()
        if status == 75:                       # the owner has the installer open
            entry['attempts'] = attempts - 1
            st.pop('pending', None)
            save_state(st)
            return 'waiting: another Canica installer is running', num('BUSY_RETRY')
        if kit_digest() != m['inventory_sha256'] or os.path.exists(JOURNAL) or not sealed():
            if os.path.exists(JOURNAL):
                run_installer(m, '--recover')
            if resumed:
                service('start')               # the previous kit, as it was
            return failed(st, m, str(result.get('reason') or 'el instalador no terminó'), attempts)
        st['pending']['phase'] = 'activate'
        save_state(st)
        return activate(st, m)
    finally:
        if other:
            other.close()


def resume(st, fw):
    """An update was under way when this program last stopped. No network needed."""
    pend = st['pending']
    try:
        m, key = read_manifest(HOME + '/cache', fw, dict(min_serial=0, max_serial=0))
        m['_key'], m['_checked'] = key[:-4], bool((st.get('available') or {}).get('checked'))
    except (Reject, OSError) as e:
        m = None
        log('pending kit %s: its manifest is gone (%s)' % (pend.get('label'), e))
    if m is None or m['serial'] != pend.get('serial'):
        st.pop('pending', None)
        save_state(st)
        return None
    if pend['phase'] == 'install':
        if not payload_ready(m):
            st.pop('pending', None)
            save_state(st)
            return None                            # downloaded and tried again by this cycle
        log('kit %s: finishing the interrupted installation' % m['label'])
        return install(st, m, resumed=True)
    if pend.get('boot') != boot_id():
        pend['menu'] = []                          # every menu process is newer than the kit
    if not set(menu_pids()[0]) & set(pend.get('menu', [])):
        return activate(st, m, restart=False)      # the menu started again since: only confirm
    return activate(st, m)


def offer(st, m):
    """Ask on the menu: now or later. The answer comes back as a request. A menu or a theme
    without the terminal screen gets one notice that points at START > Canica."""
    if es('/runningGame')[0] != 201:
        return False
    # 46 monospaced letters fit between the screen's indent and its «ok» column (640 × 480)
    rows = ['%s\t%s\tok' % step for step in settled(m)] + textwrap.wrap(m.get('note', ''), 46)
    asked = console(m, 'ask %d' % m['serial'], 'Tarda alrededor de un minuto y reinicia el menú.', rows,
                    'MÁS TARDE\tACTUALIZAR AHORA\tactualizador\tarrancando')
    if not asked and not notify('Canica %s disponible: START > Canica.' % m['label'], tries=2):
        return False
    st['asked'] = dict(serial=m['serial'], boot=boot_id(), answered=not asked)
    log('offered kit %s (%d) on the menu' % (m['label'], m['serial']))
    return True


def cycle(st, fw, verb=None, arg=None):
    """One pass. verb: the menu's request (check, install N, later N, mode). Returns (result,
    seconds until the next pass)."""
    owner = verb in ('check', 'install')            # the owner is at the menu, waiting for an answer
    on = services()
    if on is None:
        return 'the services of this console could not be read', num('RETRY_MIN')
    if 'canica' not in on:
        write_status(st, 'Canica está apagado en Servicios.')
        return 'Canica is off in Services: nothing done', num('CHECK_INTERVAL')
    if 'canica_updater' in on:
        write_status(st, 'Las actualizaciones las lleva canica_updater.')
        return 'the canica_updater add-on is on: standing down', num('CHECK_INTERVAL')
    os.makedirs(HOME + '/cache', exist_ok=True)
    if verb == 'later' and (st.get('asked') or {}).get('serial') == arg:
        st['asked']['answered'] = True
        log('kit %d: the owner chose later' % arg)

    def backoff(result):
        st['fail_streak'] += 1
        return result, min(num('RETRY_MAX'), num('RETRY_MIN') * 2 ** (st['fail_streak'] - 1))

    if st.get('pending'):
        done = resume(st, fw)
        if done:
            return done
    how = mode()
    if how == 'off' and not owner and not held():
        write_status(st, 'Actualizaciones desactivadas.')
        return 'updates are off', num('CHECK_INTERVAL')
    if not st.get('disclosed'):         # say once, before the first request, where it looks
        if es('/runningGame')[0] != 201 or not notify(DISCLOSE, tries=2):
            return 'waiting for the menu to say where updates come from', num('BUSY_RETRY')
        st['disclosed'] = now()
        save_state(st)
    try:
        m, key = get_manifest(fw, st)
    except NotFound:
        st.pop('available', None)
        forget_cache(manifest=True)
        st['checked'] = now()
        if verb == 'check':
            notify('Canica: no hay ninguna actualización publicada.', tries=2)
        write_status(st, 'Al día.' + last_check(st))
        return 'no kit published for %s' % slug(fw), num('CHECK_INTERVAL')
    except Reject as e:
        if owner:
            notify('Canica: la actualización publicada no es válida.', tries=2)
        write_status(st, 'Se rechazó la actualización publicada.' + last_check(st))
        return 'rejected: %s' % e, num('CHECK_INTERVAL')
    except Offline as e:
        try:                                       # a kit downloaded earlier installs offline
            m, key = read_manifest(HOME + '/cache', fw, st)
            if not payload_ready(m):
                raise Reject('no payload')
        except (Reject, OSError):
            if owner:
                notify('Canica: sin conexión, no se pudo buscar.', tries=2)
            write_status(st, 'Sin conexión.' + last_check(st))
            return backoff('offline: %s' % e)
    else:
        st['checked'] = now()
    m['_key'] = key[:-4] if key.endswith('.pub') else key
    st['fail_streak'] = 0
    st['max_serial'] = max(st['max_serial'], m['serial'])
    st['min_serial'] = max(st['min_serial'], m.get('min_serial', 0))
    name = '%s (%d)' % (m['label'], m['serial'])
    if m['serial'] in st['bad']:
        write_status(st, '%s no arrancó aquí; se espera la siguiente.' % m['label'])
        return 'kit %s did not start here before; waiting for a later one' % name, num('CHECK_INTERVAL')
    installed = kit_digest()
    if installed == m['inventory_sha256']:
        if (st.get('installed') or {}).get('serial') != m['serial']:
            st['installed'] = dict(serial=m['serial'], version=m['version'], label=m['label'], at=now())
        st.pop('available', None)
        if os.path.exists(payload_path(m)):
            os.remove(payload_path(m))
        if verb == 'check':
            notify('Canica está al día (%s).' % m['label'], tries=2)
        write_status(st, 'Al día.' + last_check(st))
        return 'up to date (kit %s)' % name, num('CHECK_INTERVAL')
    log('manifest %d (kit %s) verified with %s' % (m['serial'], m['label'], key))
    if installed is None:
        return 'Canica is not installed here; nothing to update', num('CHECK_INTERVAL')
    f = st['failed'].get(str(m['serial']))
    if f and f.get('attempts', 0) >= num('MAX_ATTEMPTS'):
        if verb != 'install' or arg != m['serial']:
            write_status(st, '%s no se instaló: %s' % (m['label'], f.get('reason')))
            if verb == 'check':
                notify('Canica %s no se instaló: %s' % (m['label'], f.get('reason')), tries=2)
            return 'kit %s was refused %d times (%s)' % (name, f['attempts'], f.get('reason')), num('CHECK_INTERVAL')
        st['failed'].pop(str(m['serial']))          # the owner asks again: one more round
    try:
        get_payload(fw, m)
    except Offline as e:
        if owner:
            notify('Canica: sin conexión, no se pudo descargar %s.' % m['label'], tries=2)
        write_status(st, 'Sin conexión.' + last_check(st))
        return backoff('offline: %s' % e)
    except (Reject, NotFound) as e:
        write_status(st, 'Se rechazó la actualización publicada.' + last_check(st))
        return 'rejected: %s' % e, num('CHECK_INTERVAL')
    a = st.get('available') or {}
    if a.get('serial') != m['serial'] or not a.get('ready') or owner:
        ok, reason, soon, checked = precheck(m)
        a = st['available'] = dict(serial=m['serial'], label=m['label'], note=m.get('note', ''), ready=ok, reason=reason,
                                   checked=checked)
        save_state(st)
        if not ok:
            text = '%s no se puede instalar aquí: %s' % (m['label'], reason)
            if owner:
                notify(('Canica ' + text)[:160], tries=2)
            write_status(st, text)
            return 'kit %s cannot be installed here (%s)' % (name, reason), num('BUSY_RETRY' if soon else 'CHECK_INTERVAL')
    m['_checked'] = bool(a.get('checked'))
    if verb == 'install' and arg == m['serial']:
        if st.get('asked'):
            st['asked']['answered'] = True
        return install(st, m, by_owner=True)
    if held() or (how == 'auto' and verb != 'check'):
        left = 0 if held() else soak_left(m)
        if left > 0:
            write_status(st, '%s se instalará sola desde el %s.' % (
                m['label'], time.strftime('%d/%m %H:%M', time.localtime(now() + left))))
            return 'waiting: kit %s installs by itself in %d h' % (name, (left + 3599) // 3600), min(left, num('CHECK_INTERVAL'))
        write_status(st, '%s se instalará al cargar o al arrancar.' % m['label'])
        return install(st, m)
    write_status(st, '%s disponible.' % m['label'])
    asked = st.get('asked') or {}
    again = asked.get('serial') != m['serial'] or (not asked.get('answered') and asked.get('boot') != boot_id())
    if verb == 'check' or again:
        if offer(st, m):
            return 'kit %s offered on the menu' % name, num('CHECK_INTERVAL')
        return 'kit %s is ready; the menu could not ask now' % name, num('BUSY_RETRY')
    return 'kit %s is ready; waiting for the owner' % name, num('CHECK_INTERVAL')


# --- commands --------------------------------------------------------------------------------

def take_request():
    """(verb, serial or None) left by the menu, (None, None) without a usable one."""
    words = read(REQUEST).split()
    try:
        os.remove(REQUEST)
    except OSError:
        pass
    if words[:1] in (['check'], ['mode']) and len(words) == 1:
        return words[0], None
    if words[:1] in (['install'], ['later']) and len(words) == 2 and re.fullmatch(r'[0-9]{1,12}', words[1]):
        return words[0], int(words[1])
    return None, None


def loop():
    """The service's background job. It only waits and starts cycles, each in a fresh process
    of the kit's current program, so an updated kit is served by its own code at once."""
    os.makedirs(os.path.dirname(LOOP_LOCK), exist_ok=True)
    held_lock = open(LOOP_LOCK, 'w')
    try:
        fcntl.flock(held_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                   # already running
    due = time.time() + num('BOOT_DELAY')
    while True:
        if os.path.exists(REQUEST) or time.time() >= due:
            started = time.time()
            delay = num('RETRY_MAX')
            try:
                r = subprocess.run([sys.executable or '/usr/bin/python3', '-I', KIT + '/updater.py', 'once'],
                                   env=dict(os.environ, CANICA_LOG_ONLY='1'), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                last = r.stdout.decode(errors='replace').strip().splitlines()[-1:]
                if last and last[0].isdigit():
                    delay = int(last[0])
                else:
                    log('loop: the cycle ended without a delay (exit %s)' % r.returncode)
            except OSError as e:
                log('loop: the cycle could not start (%s)' % e)
            try:        # a request the cycle did not take must not start cycles forever
                if os.path.getmtime(REQUEST) < started:
                    os.remove(REQUEST)
            except OSError:
                pass
            due = time.time() + max(1, delay)
        time.sleep(max(1, num('POLL')))


def selftest():
    keys = [k for k in os.listdir(KIT + '/keys') if k.endswith('.pub')] if os.path.isdir(KIT + '/keys') else []
    if not keys:
        print('selftest: no key in %s/keys' % KIT)
        return 1
    for key in keys:
        r = subprocess.run(['openssl', 'pkey', '-pubin', '-in', os.path.join(KIT, 'keys', key), '-noout'],
                           env=ENV, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        if r.returncode:
            print('selftest: OpenSSL cannot read %s' % key)
            return 1
    if not kit_label():
        print('selftest: the kit does not say its version (release)')
        return 1
    print('selftest ok: kit %s, %d keys, Python %d.%d' % (kit_label(), len(keys), sys.version_info[0], sys.version_info[1]))
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'once'
    if cmd not in ('loop', 'once', 'check', 'status', 'selftest'):
        sys.exit(__doc__)
    if cmd == 'selftest':
        return selftest()
    if cmd == 'loop':
        os.chdir('/')      # the folder it was started from may be removed (an install); its cycles inherit /
        return loop()
    os.makedirs(HOME, exist_ok=True)
    st = load_state()
    fw = firmware()
    if cmd == 'status':
        print(json.dumps(dict(firmware=fw, kit=kit_label(), kit_inventory=kit_digest(), mode=mode(), held=held(),
                              installed=st.get('installed'), available=st.get('available'), pending=st.get('pending'),
                              failed=st['failed'], bad=st['bad'], max_serial=st['max_serial']), indent=1, sort_keys=True))
        return 0
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(num('BUSY_RETRY') if cmd == 'once' else 'busy: another updater run holds %s' % LOCK)
        return 0 if cmd == 'once' else 1
    verb, arg = ('check', None) if cmd == 'check' else take_request()
    try:
        result, delay = cycle(st, fw, verb, arg)
    except Exception as e:   # never leave the loop without a delay; the error is logged
        result, delay = 'error: %r' % e, num('RETRY_MAX')
    save_state(st)
    log('cycle (%s) on %s: %s; next in %ds' % (verb or cmd, fw, result, delay))
    print(delay if cmd == 'once' else result)
    return 0 if not result.startswith(('error', 'rejected')) else 1


if __name__ == '__main__':
    sys.exit(main())
