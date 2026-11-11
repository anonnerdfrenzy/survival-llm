"""Offline Windows launcher checks using a real venv and a harmless server fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows launcher')
class StartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='survival start ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        tools = self.root / 'local-tools'
        tools.mkdir()
        for name in ('windows.ps1', 'source-update.ps1'):
            shutil.copy2(Path(__file__).parent / name, tools / name)
        # Empty requirements and import fixtures keep these tests offline.
        (tools / 'requirements.txt').write_text('', encoding='utf-8')
        for name in ('pypdf', 'truststore'):
            (self.root / (name + '.py')).write_text('', encoding='utf-8')
        (self.root / 'app').mkdir()
        (self.root / 'app/server.py').write_text(
            "import json,os,sys\nfrom pathlib import Path\n"
            "Path('started.json').write_text(json.dumps({'args':sys.argv[1:],"
            "'python':sys.executable,'dev':os.environ.get('SURVIVAL_LLM_DEV')}))\n",
            encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)

    def launch(self, *args):
        env = os.environ.copy()
        env['PIP_NO_INDEX'] = '1'
        return subprocess.run([
            'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', str(self.root / 'local-tools/windows.ps1'),
            '-Action', 'Start', '-PythonPath', sys.executable, *args],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=90)

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
