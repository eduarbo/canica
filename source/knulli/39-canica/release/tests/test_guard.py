#!/usr/bin/env python3
"""Off-device tests of the kit's guard (release/guard.py): FN + SELECT during a game, and the
battery running out. A console under a temporary folder (CANICA_ROOT) with its battery files,
a gamepad that is a named pipe, the menu's web API on localhost and stand-ins for the
system's commands, which only note that they were called.

Run on the build computer:  python3 -B release/tests/test_guard.py
"""
import http.server
import importlib.util
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / 'guard.py'
FN, SELECT, A = 312, 310, 304


class Console:
    def __init__(self, case):
        self.root = Path(tempfile.mkdtemp()).resolve()
        case.addCleanup(shutil.rmtree, self.root, True)
        self.notices, self.game = [], False
        for rel, text in {'sys/class/power_supply/axp2202-battery/type': 'Battery\n',
                          'sys/class/power_supply/axp2202-battery/capacity': '60\n',
                          'sys/class/power_supply/axp2202-battery/voltage_now': '3900000\n',
                          'sys/class/power_supply/axp2202-battery/status': 'Discharging\n',
                          'sys/class/power_supply/ac/type': 'Mains\n',
                          'tmp/battery.percent': '70\n', 'proc/uptime': '600.0 600.0\n', 'services': 'canica\n',
                          'userdata/system/knulli.conf': 'system.language=es_MX\n'}.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text)
        (self.root / 'var/run/canica').mkdir(parents=True)
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        for name in ('knulli-rumble', 'knulli-es-swissknife', 'knulli-shutdown'):
            (bin_dir / name).write_text('#!/bin/sh\necho "%s $*" >> "%s/calls.log"\n' % (name, self.root))
            (bin_dir / name).chmod(0o755)
        (bin_dir / 'knulli-settings-get').write_text('#!/bin/sh\ncat "%s/services"\n' % self.root)
        (bin_dir / 'knulli-settings-get').chmod(0o755)
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), self.handler())
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        case.addCleanup(self.server.server_close)
        case.addCleanup(self.server.shutdown)
        self.pad = self.root / 'gamepad'
        os.mkfifo(self.pad)
        os.environ.update(CANICA_ROOT=str(self.root), CANICA_GAMEPAD=str(self.pad),
                          CANICA_ES_API='http://127.0.0.1:%d' % self.server.server_address[1],
                          CANICA_PATH='%s:%s' % (bin_dir, os.environ['PATH']))
        spec = importlib.util.spec_from_file_location('guard_%d' % id(self), GUARD)
        self.guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.guard)
        self.guard.CHORD_PAUSE = 0.3

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
                if self.path == '/runningGame':
                    return self.answer(200 if console.game else 201, b'{}')
                self.answer(404)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
                if self.path == '/notify':
                    console.notices.append(body)
                    return self.answer(200)
                self.answer(404)
        return Handler

    def calls(self):
        log = self.root / 'calls.log'
        return log.read_text().splitlines() if log.exists() else []

    def set(self, rel, text):
        (self.root / rel).write_text(text + '\n')

    def watch(self):
        threading.Thread(target=self.guard.watch_gamepad, daemon=True).start()
        self.writer = open(self.pad, 'wb', buffering=0)

    def press(self, *codes):
        for code in codes:
            self.writer.write(self.guard.EVENT.pack(0, 0, 1, code, 1))
        for code in reversed(codes):
            self.writer.write(self.guard.EVENT.pack(0, 0, 1, code, 0))
        time.sleep(0.6)

    def wait_calls(self, count, seconds=5):
        end = time.time() + seconds
        while time.time() < end and len(self.calls()) < count:
            time.sleep(0.05)
        return self.calls()


class ChordTest(unittest.TestCase):
    def setUp(self):
        self.c = Console(self)
        self.c.watch()
        self.addCleanup(self.c.writer.close)

    def test_a_game_with_an_automatic_state_closes_for_the_switcher(self):
        self.c.game = True
        self.c.set('var/run/canica/game-autosaves', '/userdata/roms/gb/Link.zip')
        self.c.press(FN, SELECT)
        self.assertEqual(self.c.wait_calls(1), ['knulli-es-swissknife --emukill'])
        self.assertEqual((self.c.root / 'var/run/canica/switcher-request').read_text().strip(), '/userdata/roms/gb/Link.zip')
        self.assertIn('FN + SELECT: game closed for the switcher', (self.c.root / 'userdata/system/logs/canica-guard.log').read_text())

    def test_a_game_without_one_is_left_running_with_two_rumbles(self):
        self.c.game = True
        self.c.press(FN, SELECT)
        self.assertEqual(self.c.wait_calls(2), ['knulli-rumble 0.08', 'knulli-rumble 0.08'])
        self.assertFalse((self.c.root / 'var/run/canica/switcher-request').exists())

    def test_the_menu_and_other_buttons_do_nothing(self):
        self.c.set('var/run/canica/game-autosaves', '/userdata/roms/gb/Link.zip')
        self.c.press(FN, SELECT)                    # in the menu: the frontend's own shortcut
        self.c.game = True
        self.c.press(FN)
        self.c.press(SELECT)
        self.c.press(FN, A)
        time.sleep(0.5)
        self.assertEqual(self.c.calls(), [])
        self.c.press(SELECT, FN)                    # either order
        self.assertEqual(self.c.wait_calls(1), ['knulli-es-swissknife --emukill'])


class BatteryTest(unittest.TestCase):
    def setUp(self):
        self.c = Console(self)
        self.b = self.c.guard.Battery()

    def test_three_empty_readings_save_and_shut_down_once(self):
        self.c.set('tmp/battery.percent', '2')
        self.assertIsNone(self.b.check())
        self.assertIsNone(self.b.check())
        self.assertEqual(self.b.check(), 'shutdown')
        self.assertEqual(self.c.calls(), ['knulli-shutdown --shutdown'])
        self.assertEqual(self.c.notices[-1], 'Batería agotada: guardando la partida y apagando.')
        self.assertIsNone(self.b.check())
        self.assertEqual(len(self.c.calls()), 1)

    def test_a_dip_a_charger_or_the_first_minutes_change_nothing(self):
        self.c.set('tmp/battery.percent', '1')
        self.b.check()
        self.b.check()
        self.c.set('tmp/battery.percent', '9')
        self.b.check()                              # a dip under load, then back
        self.c.set('tmp/battery.percent', '1')
        self.b.check()
        self.b.check()
        self.assertEqual(self.c.calls(), [])
        self.c.set('sys/class/power_supply/axp2202-battery/status', 'Charging')
        for _ in range(4):
            self.b.check()
        self.assertEqual(self.c.calls(), [])
        self.c.set('sys/class/power_supply/axp2202-battery/status', 'Discharging')
        self.c.set('proc/uptime', '30.0 30.0')
        for _ in range(4):
            self.b.check()
        self.assertEqual(self.c.calls(), [])
        self.c.set('proc/uptime', '600.0 600.0')
        self.assertEqual(self.b.check(), 'shutdown')

    def test_a_low_cell_counts_even_when_the_percentage_lags(self):
        self.c.set('tmp/battery.percent', '11')
        self.c.set('sys/class/power_supply/axp2202-battery/voltage_now', '3280000')
        for _ in range(2):
            self.assertIsNone(self.b.check())
        self.assertEqual(self.b.check(), 'shutdown')

    def test_the_gauge_reaching_empty_counts_even_when_the_shown_percentage_lags(self):
        self.c.set('tmp/battery.percent', '14')
        self.c.set('sys/class/power_supply/axp2202-battery/capacity', '2')
        for _ in range(2):
            self.assertIsNone(self.b.check())
        self.assertEqual(self.b.check(), 'shutdown')

    def test_one_warning_at_five_percent(self):
        self.c.set('tmp/battery.percent', '5')
        self.b.check()
        self.b.check()
        self.assertEqual(self.c.notices, ['Batería al 5 %: Canica guardará la partida y apagará la consola antes de que se agote.'])
        self.c.set('sys/class/power_supply/axp2202-battery/status', 'Charging')
        self.c.set('tmp/battery.percent', '40')
        self.b.check()
        self.c.set('sys/class/power_supply/axp2202-battery/status', 'Discharging')
        self.c.set('tmp/battery.percent', '4')
        self.b.check()
        self.assertEqual(len(self.c.notices), 2)    # charged in between: warned again

    def test_an_english_console_reads_english_notices(self):
        self.c.set('userdata/system/knulli.conf', 'system.language=en_US')
        self.c.set('tmp/battery.percent', '5')
        self.b.check()
        self.c.set('tmp/battery.percent', '2')
        for _ in range(3):
            self.b.check()
        self.assertEqual(self.c.notices, ['Battery at 5%: Canica will save your game and turn the console off before it runs out.',
                                          'Battery empty: saving your game and turning off.'])

    def test_without_the_shown_percentage_the_gauge_is_used(self):
        (self.c.root / 'tmp/battery.percent').unlink()
        self.c.set('sys/class/power_supply/axp2202-battery/capacity', '1')
        for _ in range(3):
            self.b.check()
        self.assertEqual(self.c.calls(), ['knulli-shutdown --shutdown'])


class ServiceTest(unittest.TestCase):
    def test_canica_off_in_services_stops_the_guard_and_selftest_reports(self):
        c = Console(self)
        self.assertTrue(c.guard.canica_on())
        c.set('services', 'samba')
        self.assertFalse(c.guard.canica_on())
        self.assertEqual(c.guard.selftest(), 0)


if __name__ == '__main__':
    unittest.main()
