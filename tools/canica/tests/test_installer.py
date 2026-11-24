"""Exercise the install transaction using synthetic files, never handheld data."""
from contextlib import ExitStack, redirect_stdout
import fcntl
from io import BytesIO, StringIO
import json
import multiprocessing
import os
from pathlib import Path
import runpy
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'installer/install.py'))
install = MODULE['install']
namespace = install.__globals__


class Settings:
    def __init__(self, root):
        self.path = root / 'system/services-fixture'
        self.path.write_text('samba')

    def check(self):
        pass

    def services(self):
        return self.path.read_text().split()

    def enable(self, enabled):
        self.path.write_text('samba canica' if enabled else 'samba')


class InstallerTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        work = Path(stack.enter_context(TemporaryDirectory())).resolve()
        self.root = work / 'userdata'
        (self.root / 'system').mkdir(parents=True)
        self.console = Settings(self.root)
        self.save = self.root / 'saves/game.srm'
        self.save.parent.mkdir()
        self.save.write_bytes(b'progress')
        self.theme = self.root / 'themes/es-theme-canica/theme.xml'
        self.adapter = self.root / MODULE['ADAPTER']
        self.data = {str(self.theme.relative_to(self.root)): b'<theme/>', 'system/canica/manifest': b'test', 'system/services/canica': b'test service'}
        kit = BytesIO()
        with ZipFile(kit, 'w') as archive:
            for n, v in self.data.items():
                archive.writestr('share/' + n, v)
        name = 'canica-test.zip'
        self.tool = work / 'Instalar Canica.sh'
        with ZipFile(self.tool, 'w') as app:
            app.writestr('resume-emulatorlauncher', b'adapter')
        self.kit = work / name
        self.kit.write_bytes(kit.getvalue())
        stack.enter_context(patch.dict(namespace, {'PACKAGES': {name: MODULE['digest'](kit.getvalue())}, 'ADAPTER_SHA': MODULE['digest'](b'adapter')}))
        stack.enter_context(patch.object(os, 'sync', create=True))

    def launch(self):
        return install(self.tool, self.root, self.console)

    def tearDown(self):
        self.assertEqual(self.save.read_bytes(), b'progress')

    def test_preserve_unexpected_work_file(self):
        work = self.root / 'system/.canica-installer-v1'
        work.mkdir()
        (work / 'installer-v1').touch()
        note = work / 'nota.txt'
        note.write_text('local')
        with self.assertRaisesRegex(ValueError, 'archivo inesperado'):
            self.launch()
        self.assertEqual(note.read_text(), 'local')
        self.assertFalse(self.theme.exists())

    def test_embedded_install(self):
        with ZipFile(self.tool, 'a') as app:
            app.write(self.kit, self.kit.name)
        self.kit.unlink()
        self.launch()
        self.assertEqual(self.theme.read_bytes(), b'<theme/>')

    def test_install_twice(self):
        self.launch()
        inode = self.theme.stat().st_ino
        self.launch()
        self.assertEqual(self.theme.stat().st_ino, inode)
        self.assertEqual(self.console.services(), ['samba', 'canica'])
        self.assertTrue(os.access(self.adapter, os.X_OK))
        self.assertFalse((self.root / 'system/.canica-installer-v1').exists())

    def test_preserve_custom_adapter(self):
        self.adapter.parent.mkdir(parents=True)
        self.adapter.write_bytes(b'custom')
        self.assertIn('conservó', self.launch())
        self.assertEqual(self.adapter.read_bytes(), b'custom')

    def test_reject_modified_theme_before_install(self):
        self.theme.parent.mkdir(parents=True)
        self.theme.write_bytes(b'custom')
        with self.assertRaisesRegex(ValueError, 'archivo modificado'):
            self.launch()
        self.assertEqual(self.theme.read_bytes(), b'custom')
        self.assertFalse(self.adapter.exists())
        self.assertEqual(self.console.services(), ['samba'])

    def test_reject_incomplete_zip(self):
        self.kit.write_bytes(b'incomplete')
        with self.assertRaisesRegex(ValueError, 'ZIP'):
            self.launch()
        self.assertFalse(self.theme.exists())
        self.assertEqual(self.console.services(), ['samba'])

    def test_reject_linked_theme_directory(self):
        (self.root / 'themes').symlink_to(self.save.parent)
        with self.assertRaisesRegex(ValueError, 'enlace'):
            self.launch()
        self.assertFalse((self.save.parent / 'es-theme-canica').exists())

    def test_restore_after_activation_error(self):
        def fail(value):
            Settings.enable(self.console, value)
            if value:
                raise RuntimeError('interrupted')
        with patch.object(self.console, 'enable', fail), self.assertRaisesRegex(RuntimeError, 'interrupted'):
            self.launch()
        self.assertFalse(self.theme.exists())
        self.assertFalse(self.adapter.exists())
        self.assertEqual(self.console.services(), ['samba'])

    def test_recover_killed_install_then_retry(self):
        self.theme.parent.mkdir(parents=True)
        self.theme.write_bytes(b'previous release')
        earlier = {(str(self.theme.relative_to(self.root)), MODULE['digest'](b'<theme/>')): {MODULE['digest'](b'previous release')}}
        replace = os.replace
        def interrupt(src, dest):
            result = replace(src, dest)
            if dest == self.theme:
                os._exit(37)
            return result
        with patch.dict(namespace, {'PREVIOUS': earlier}):
            with patch.object(os, 'replace', interrupt):
                process = multiprocessing.get_context('fork').Process(target=self.launch)
                process.start()
                process.join(10)
                self.assertEqual(process.exitcode, 37)
            self.assertTrue((self.root / 'system/.canica-installer-v1/pending.json').exists())
            extra = self.root / 'system/.canica-installer-v1/nota'
            extra.write_text('local')
            with self.assertRaisesRegex(ValueError, 'archivo inesperado'):
                self.launch()
            self.assertEqual(self.theme.read_bytes(), b'previous release')
            self.assertEqual(extra.read_text(), 'local')
            extra.unlink()
            self.kit.rename(self.kit.with_suffix('.off'))
            with self.assertRaisesRegex(ValueError, 'ZIP'):
                self.launch()
            self.assertEqual(self.theme.read_bytes(), b'previous release')
            self.assertEqual(self.console.services(), ['samba'])
            self.kit.with_suffix('.off').rename(self.kit)
            self.launch()
        self.assertEqual(self.theme.read_bytes(), b'<theme/>')

    def unattended(self, mode):
        """Run main() as the kit updater does: (exit status, parsed last output line, message boxes)."""
        boxes, output = Mock(), StringIO()
        lock = self.root.parent / 'installer.lock'
        with patch.dict(namespace, {'ROOT': self.root, 'LOCK': str(lock), 'Console': lambda: self.console, 'report': boxes}):
            with patch.object(sys, 'argv', [str(self.tool), mode]), redirect_stdout(output):
                status = MODULE['main']()
        return status, json.loads(output.getvalue().splitlines()[-1]), boxes

    def test_unattended_install_reports_without_a_message_box(self):
        status, result, boxes = self.unattended('--ota')
        self.assertEqual((status, result), (0, dict(ok=True, written=4, adapter_kept=False, cards_failed=False)))
        boxes.assert_not_called()
        self.assertEqual(self.theme.read_bytes(), b'<theme/>')
        self.assertEqual(self.unattended('--ota')[1]['written'], 0)

    def test_unattended_refusal_names_the_kept_file(self):
        self.theme.parent.mkdir(parents=True)
        self.theme.write_bytes(b'custom')
        status, result, boxes = self.unattended('--ota')
        self.assertEqual(status, 1)
        self.assertFalse(result['ok'])
        self.assertIn('archivo modificado', result['reason'])
        boxes.assert_not_called()
        self.assertEqual(self.theme.read_bytes(), b'custom')

    def test_check_says_whether_the_kit_would_install_and_writes_nothing(self):
        self.assertEqual(self.unattended('--check')[:2], (0, dict(ok=True, check=True, files=4)))
        self.assertFalse(self.theme.exists())
        self.assertFalse((self.root / 'system/.canica-installer-v1').exists())
        self.assertNotIn('canica', self.console.services())
        self.theme.parent.mkdir(parents=True)
        self.theme.write_bytes(b'custom')
        status, result, boxes = self.unattended('--check')
        self.assertEqual((status, result['ok']), (1, False))
        self.assertIn('archivo modificado', result['reason'])
        boxes.assert_not_called()
        self.assertEqual(self.theme.read_bytes(), b'custom')
        self.theme.unlink()
        self.unattended('--ota')
        self.assertEqual(self.unattended('--check')[1], dict(ok=True, check=True, files=0))
        with patch.object(shutil, 'disk_usage', return_value=Mock(free=10)):
            self.theme.unlink()
            self.assertIn('Libera espacio', self.unattended('--check')[1]['reason'])
        # an interrupted run is left for the install to undo
        work = self.root / 'system/.canica-installer-v1'
        work.mkdir()
        (work / 'installer-v1').touch()
        self.assertEqual(self.unattended('--check')[1], dict(ok=True, check=True, files=None))
        self.assertTrue((work / 'installer-v1').exists())

    def test_unattended_run_yields_to_another_installer(self):
        with open(self.root.parent / 'installer.lock', 'a') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            status, result, _ = self.unattended('--ota')
        self.assertEqual((status, result['busy']), (75, True))
        self.assertFalse(self.theme.exists())

    def test_recover_only_undoes_a_killed_install(self):
        self.theme.parent.mkdir(parents=True)
        self.theme.write_bytes(b'previous release')
        earlier = {(str(self.theme.relative_to(self.root)), MODULE['digest'](b'<theme/>')): {MODULE['digest'](b'previous release')}}
        replace = os.replace
        def interrupt(src, dest):
            result = replace(src, dest)
            if dest == self.theme:
                os._exit(37)
            return result
        with patch.dict(namespace, {'PREVIOUS': earlier}):
            with patch.object(os, 'replace', interrupt):
                process = multiprocessing.get_context('fork').Process(target=self.launch)
                process.start()
                process.join(10)
            self.assertEqual(self.theme.read_bytes(), b'<theme/>')
            status, result, _ = self.unattended('--recover')
        self.assertEqual((status, result), (0, dict(ok=True, recovered=True)))
        self.assertEqual(self.theme.read_bytes(), b'previous release')
        self.assertFalse((self.root / 'system/.canica-installer-v1').exists())


if __name__ == '__main__':
    unittest.main()
