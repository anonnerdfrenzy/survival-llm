"""Offline Windows launcher checks using a real venv and a harmless server fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


@unittest.skipUnless(os.name == 'nt', 'Windows launcher')
class StartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='survival start ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        tools = self.root / 'local-tools'
        tools.mkdir()
        for name in ('windows.ps1', 'source-update.ps1', 'check_environment.py'):
            shutil.copy2(Path(__file__).parent / name, tools / name)
        for name in ('Start.cmd', 'Setup.cmd', 'Update.cmd'):
            shutil.copy2(Path(__file__).parent.parent / name, self.root / name)
        # Small local wheels exercise actual pip installation without network access.
        requirements = []
        for name in ('pypdf', 'truststore'):
            wheel = tools / f'{name}-1.0-py3-none-any.whl'
            with zipfile.ZipFile(wheel, 'w') as archive:
                archive.writestr(f'{name}.py', '')
                archive.writestr(f'{name}-1.0.dist-info/METADATA',
                                 f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n')
                archive.writestr(f'{name}-1.0.dist-info/WHEEL',
                                 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
                archive.writestr(f'{name}-1.0.dist-info/RECORD', '')
            requirements.append(str(wheel))
        (tools / 'requirements.txt').write_text('\n'.join(requirements), encoding='utf-8')
        (self.root / 'app').mkdir()
        (self.root / 'app/server.py').write_text(
            "import json,os,sys\nfrom pathlib import Path\n"
            "Path('started.json').write_text(json.dumps({'args':sys.argv[1:],"
            "'python':sys.executable,'dev':os.environ.get('SURVIVAL_LLM_DEV')}))\n",
            encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)

    def launch(self, *args, action='Start'):
        env = os.environ.copy()
        env['PIP_NO_INDEX'] = '1'
        command = f'""{self.root / (action + ".cmd")}" -PythonPath "{sys.executable}"'
        command += ''.join(f' {arg}' for arg in args) + '"'
        return subprocess.run(f'"{os.environ["COMSPEC"]}" /d /s /c {command}',
            cwd=self.root.parent, env=env, input='\n', capture_output=True,
            text=True, timeout=90)

    def test_first_start_prepares_environment_and_second_start_reuses_it(self):
        first = self.launch()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        started = json.loads((self.root / 'started.json').read_text())
        self.assertEqual(started['args'], ['--browser'])
        self.assertEqual(started['dev'], 'source checkout')
        self.assertEqual(Path(started['python']), self.root / '.venv/Scripts/python.exe')
        self.assertIn('Installing browser-mode dependencies', first.stdout)
        second = self.launch()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotIn('Installing browser-mode dependencies', second.stdout)

    def test_check_only_neither_prepares_nor_launches(self):
        result = self.launch('-CheckOnly')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)['environmentReady'])
        self.assertFalse((self.root / '.venv').exists())
        self.assertFalse((self.root / 'started.json').exists())

    def test_check_only_detects_broken_dependencies(self):
        result = self.launch(action='Setup')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        package = self.root / '.venv/Lib/site-packages/pypdf.py'
        package.write_text("raise RuntimeError('broken dependency')", encoding='utf-8')
        result = self.launch('-CheckOnly')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)['environmentReady'])
        self.assertFalse((self.root / 'started.json').exists())

    def test_setup_is_repeatable_and_update_preflight_does_not_fetch(self):
        for _ in range(2):
            result = self.launch(action='Setup')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.launch('-CheckOnly')
        self.assertTrue(json.loads(result.stdout)['environmentReady'])
        result = self.launch('-CheckOnly', action='Update')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['action'], 'Update')
        self.assertFalse((self.root / '.git/FETCH_HEAD').exists())

    def test_start_repairs_missing_dependency(self):
        result = self.launch(action='Setup')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        python = self.root / '.venv/Scripts/python.exe'
        subprocess.run([str(python), '-m', 'pip', 'uninstall', '-y', 'pypdf'],
                       check=True, capture_output=True, timeout=30)
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'started.json').exists())
        self.assertIn('Installing browser-mode dependencies', result.stdout)

    def test_server_failure_returns_nonzero_from_cmd(self):
        (self.root / 'app/server.py').write_text('raise SystemExit(7)\n', encoding='utf-8')
        result = self.launch()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Survival LLM exited with an error', result.stderr)

    def test_incomplete_environment_is_preserved(self):
        (self.root / '.venv').mkdir()
        sentinel = self.root / '.venv/keep.txt'
        sentinel.write_text('preserve', encoding='utf-8')
        result = self.launch()
        self.assertEqual(result.returncode, 1)
        self.assertIn('Existing .venv is incomplete', result.stderr)
        self.assertNotIn('WriteErrorException', result.stderr)
        self.assertEqual(sentinel.read_text(), 'preserve')
        self.assertFalse((self.root / 'started.json').exists())


if __name__ == '__main__':
    unittest.main()
