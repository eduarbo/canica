#!/usr/bin/env python3
"""Two small duties of the Canica kit while the console runs. Standard library only.

The Canica service starts it before any of its own checks (python3 -I, as root, in its own
session):
  loop      both duties, until Canica is turned off in Services
  selftest  this program, the gamepad and the battery can be read

FN + SELECT during a game opens the game switcher. The menu leaves /var/run/canica/
game-autosaves while the running game writes its automatic state when it is closed. Then the
game is closed the way the system closes one (knulli-es-swissknife --emukill), which writes
that state, and the menu opens the switcher when it is back. Without it two short rumbles say
that the shortcut would lose progress in this game, and nothing else happens.

When the battery runs out while discharging (the system's reading or the battery's own gauge at
or below LOW_PERCENT, or the cell under LOW_VOLTS, READINGS readings in a row) it says so on screen and shuts the
console down the system's way (knulli-shutdown): a running game is closed first, which saves
its automatic state, and the system's quick resume brings it back at the next start. Before
that, at WARN_PERCENT, one notice on the menu.

A new kit replaces this file: the running guard starts its new version by itself.
Log: logs/canica-guard.log.
"""
import fcntl
import os
import select
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = os.environ.get('CANICA_ROOT', '')
RUN = ROOT + '/var/run/canica'
AUTOSAVES = RUN + '/game-autosaves'
REQUEST = RUN + '/switcher-request'
LOCK = ROOT + '/var/run/canica-guard.lock'
LOG = ROOT + '/userdata/system/logs/canica-guard.log'
POWER = ROOT + '/sys/class/power_supply'
SHOWN = ROOT + '/tmp/battery.percent'          # the percentage the system shows (batteryplus)
INPUT = ROOT + '/dev/input'
GAMEPAD = os.environ.get('CANICA_GAMEPAD', '')       # tests name one
ES_API = os.environ.get('CANICA_ES_API', 'http://127.0.0.1:1234')
ENV = dict(PATH=os.environ.get('CANICA_PATH', '/usr/sbin:/usr/bin:/sbin:/bin'), HOME='/userdata/system', LANG='C.UTF-8')

# The RG35XX-H's buttons, as its kernel names them (event codes)
FN, SELECT = 312, 310
EV_KEY = 1
EVENT = struct.Struct('llHHi')                  # struct input_event on a 64-bit kernel
EVIOCGBIT_KEY = (2 << 30) | (96 << 16) | (ord('E') << 8) | (0x20 + EV_KEY)

PERIOD = float(os.environ.get('CANICA_GUARD_PERIOD', '20'))
READINGS = 3
LOW_PERCENT = 2
LOW_VOLTS = 3.40        # the RG35XX-H logs 3.50 V at 13 % on its gauge; under a game's load it sags further
WARN_PERCENT = 5
SETTLE = 120            # seconds after boot before the battery counts: the reading settles
SERVICES_EVERY = 300    # seconds between checks that Canica is still on in Services
CHORD_PAUSE = 4.0       # one chord per this many seconds


def now():
    return time.time()


def log(msg):
    line = '%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), msg)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 256 * 1024:
            os.replace(LOG, LOG + '.1')
        with open(LOG, 'a') as f:
            f.write(line)
    except OSError:
        pass


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
    os.replace(tmp, path)


def es(path, data=None):
    """(status, body) from the menu's web API, (0, b'') when it does not answer."""
    req = urllib.request.Request(ES_API + path, data=data,
                                 headers={'Content-Type': 'text/plain; charset=utf-8'} if data is not None else {})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b''
    except (urllib.error.URLError, OSError):
        return 0, b''


def run(*command, wait=True):
    try:
        if wait:
            return subprocess.run(list(command), env=ENV, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=120).returncode
        subprocess.Popen(list(command), env=ENV, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return 0
    except (OSError, subprocess.TimeoutExpired) as e:
        log('%s: %s' % (command[0], e))
        return None


def uptime():
    try:
        return float(read(ROOT + '/proc/uptime').split()[0])
    except (IndexError, ValueError):
        return 0.0


# --- FN + SELECT during a game -----------------------------------------------------------------

def gamepad():
    """The event device with FN and SELECT."""
    if GAMEPAD:
        return GAMEPAD
    for name in sorted(os.listdir(INPUT)) if os.path.isdir(INPUT) else []:
        if not name.startswith('event'):
            continue
        path = os.path.join(INPUT, name)
        try:
            with open(path, 'rb', buffering=0) as dev:
                bits = bytearray(96)
                fcntl.ioctl(dev, EVIOCGBIT_KEY, bits)
        except OSError:
            continue
        if all(bits[code // 8] >> (code % 8) & 1 for code in (FN, SELECT)):
            return path
    return None


def chord():
    """FN + SELECT was pressed. Returns what was done, for the log."""
    if es('/runningGame')[0] in (0, 201):         # the menu has its own FN + SELECT; no game, nothing here
        return None
    if not read(AUTOSAVES).strip():
        run('knulli-rumble', '0.08')
        time.sleep(0.15)
        run('knulli-rumble', '0.08')
        return 'game without an automatic state: left running'
    write(REQUEST, read(AUTOSAVES))
    run('knulli-es-swissknife', '--emukill', wait=False)
    return 'game closed for the switcher'


def watch_gamepad():
    """Forever: open the gamepad, follow FN and SELECT, act on the chord."""
    last = 0.0
    while True:
        path = gamepad()
        if path is None:
            time.sleep(30)
            continue
        held = set()
        try:
            with open(path, 'rb', buffering=0) as dev:
                while True:
                    ready, _, _ = select.select([dev], [], [], 60)
                    if not ready:
                        continue
                    data = dev.read(EVENT.size * 16)
                    if not data:
                        break
                    for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
                        _, _, kind, code, value = EVENT.unpack_from(data, offset)
                        if kind != EV_KEY or code not in (FN, SELECT):
                            continue
                        if value == 0:
                            held.discard(code)
                            continue
                        held.add(code)
                        if held == {FN, SELECT} and now() - last >= CHORD_PAUSE:
                            last = now()
                            done = chord()
                            if done:
                                log('FN + SELECT: ' + done)
        except OSError as e:
            log('gamepad %s: %s' % (path, e))
        time.sleep(2)


# --- the battery -------------------------------------------------------------------------------

def battery():
    """(shown percent or None, physical percent or None, volts or None, discharging)"""
    base = None
    for name in sorted(os.listdir(POWER)) if os.path.isdir(POWER) else []:
        if read(os.path.join(POWER, name, 'type')).strip() == 'Battery':
            base = os.path.join(POWER, name)
            break
    if base is None:
        return None, None, None, False

    def number(text):
        try:
            return int(text.strip())
        except ValueError:
            return None

    physical = number(read(base + '/capacity'))
    shown = number(read(SHOWN))
    micro = number(read(base + '/voltage_now'))
    volts = None if micro is None else (micro / 1e6 if micro > 100000 else micro / 1e3)
    discharging = read(base + '/status').strip() == 'Discharging'
    return (shown if shown is not None else physical), physical, volts, discharging


class Battery:
    """Counts low readings in a row; acts once."""

    def __init__(self):
        self.low = 0
        self.warned = False
        self.done = False

    def check(self):
        shown, physical, volts, discharging = battery()
        if not discharging or shown is None:
            self.low = 0
            if shown is not None and shown > WARN_PERCENT + 3:
                self.warned = False
            return None
        if shown <= WARN_PERCENT and not self.warned and uptime() > SETTLE:
            self.warned = True
            es('/notify', ('Batería al %d %%: Canica guardará la partida y apagará la consola antes de que se agote.' % shown).encode())
        empty = (shown <= LOW_PERCENT or (physical is not None and physical <= LOW_PERCENT)
                 or (volts is not None and volts < LOW_VOLTS))
        self.low = self.low + 1 if empty else 0
        if self.low < READINGS or self.done or uptime() <= SETTLE:
            return None
        self.done = True
        log('battery empty (shown %s %%, gauge %s %%, %s V): saving and shutting down' % (shown, physical, volts))
        es('/notify', 'Batería agotada: guardando la partida y apagando.'.encode())
        time.sleep(3)
        run('knulli-shutdown', '--shutdown')
        return 'shutdown'


# --- the loop ----------------------------------------------------------------------------------

def canica_on():
    try:
        r = subprocess.run(['knulli-settings-get', 'system.services'], env=ENV, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return True                                 # unknown: keep guarding
    if r.returncode not in (0, 1) or r.stderr.strip():
        return True
    return 'canica' in r.stdout.split()


def loop():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, 'w')                          # not inherited: a new version takes it after exec
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                    # already running
    me = os.path.abspath(__file__)
    version = os.stat(me).st_mtime
    log('guard started (pid %d)' % os.getpid())
    threading.Thread(target=watch_gamepad, daemon=True).start()
    guard = Battery()
    checked = now()
    while True:
        time.sleep(PERIOD)
        try:
            guard.check()
        except Exception as e:                      # never stop guarding over one bad reading
            log('battery: %r' % e)
        if now() - checked >= SERVICES_EVERY:
            checked = now()
            if not canica_on():
                log('Canica is off in Services: guard stopped')
                return 0
        try:
            if os.stat(me).st_mtime != version:     # a new kit: its own guard takes over
                log('a new version of the guard: restarting')
                os.execv(sys.executable, [sys.executable, '-I', me, 'loop'])
        except OSError:
            pass


def selftest():
    if EVENT.size != 24:
        print('selftest: input events are %d bytes here, not 24' % EVENT.size)
        return 1
    shown, physical, volts, discharging = battery()
    pad = gamepad()
    print('selftest ok: gamepad %s, battery %s %% (gauge %s %%, %s V, %s)' % (
        pad or 'not found', shown, physical, volts, 'discharging' if discharging else 'not discharging'))
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'loop':
        return loop()
    if cmd == 'selftest':
        return selftest()
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
