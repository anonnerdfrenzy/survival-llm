"""Offline updater checks using existing Git history; creates no commits."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'local-tools' / 'source-update.ps1'


def git(directory, *args):
    result = subprocess.run(['git', '-C', str(directory), *args], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'git {args}: {result.stderr}')
    return result.stdout.strip()


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell updater')
class SourceUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the existing source history instead of manufacturing commits.
        cls.base = git(ROOT, 'rev-list', '--max-parents=0', 'HEAD').splitlines()[0]
        cls.tip = git(ROOT, 'rev-parse', 'HEAD')
        cls.ahead = git(ROOT, 'rev-list', '--count', f'{cls.base}..{cls.tip}')
        cls.added = git(ROOT, 'diff', '--name-only', '--diff-filter=A', cls.base, cls.tip).splitlines()[0]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='survival sync test ')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.upstream = self.directory / 'author.git'
        self.checkout = self.directory / 'fork checkout'
        git(ROOT, 'clone', '--bare', '--no-hardlinks', str(ROOT), str(self.upstream))
        git(self.upstream, 'update-ref', 'refs/heads/main', self.tip)
        git(ROOT, 'clone', '--no-hardlinks', '--no-checkout', str(self.upstream), str(self.checkout))
        git(self.checkout, 'checkout', '-b', 'feature/local-work', self.base)
        # A fork's origin must not be fetched or rewritten by the updater.
        git(self.checkout, 'remote', 'set-url', 'origin', 'https://example.invalid/my-fork.git')

    def run_update(self, source=None, divergent=False):
        env = os.environ.copy()
        env.update(SYNC_HELPER=str(HELPER), SYNC_ROOT=str(self.checkout),
                   SYNC_SOURCE=str(source or self.upstream))
        # The repository only has linear history. Exercise the divergence
        # decision with a count response; all other Git operations stay real.
        boundary = '''
        function git {
            if ($args -contains 'rev-list') {
                $global:LASTEXITCODE = 0
                return "1`t1"
            }
            & git.exe @args
            $global:LASTEXITCODE = $LASTEXITCODE
        }
        ''' if divergent else ''
        command = boundary + '''
        $ErrorActionPreference = 'Stop'
        . $env:SYNC_HELPER
        try { Invoke-SourceUpdate -Root $env:SYNC_ROOT -Source $env:SYNC_SOURCE }
        catch { Write-Output $_.Exception.Message; exit 1 }
        '''
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
            env=env, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(git(self.checkout, 'remote', 'get-url', 'origin'),
                         'https://example.invalid/my-fork.git')
        return result

    def test_feature_branch_fast_forward_without_touching_fork_origin(self):
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD'), self.tip)
        self.assertEqual(git(self.checkout, 'branch', '--show-current'), 'feature/local-work')
        self.assertEqual(git(self.checkout, 'status', '--porcelain'), '')

    def test_local_commits_are_preserved_when_upstream_is_already_included(self):
        git(self.checkout, 'reset', '--hard', self.tip)
        git(self.upstream, 'update-ref', 'refs/heads/main', self.base)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'Local commits preserved: {self.ahead}', result.stdout)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD'), self.tip)

    def test_dirty_tracked_file_is_preserved(self):
        readme = self.checkout / 'README.md'
        content = readme.read_bytes() + b'\nLOCAL EDIT\n'
        readme.write_bytes(content)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Tracked files have local changes', result.stdout)
        self.assertEqual(readme.read_bytes(), content)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD'), self.base)

    def test_untracked_collision_is_preserved(self):
        collision = self.checkout / self.added
        collision.parent.mkdir(parents=True, exist_ok=True)
        collision.write_text('LOCAL FILE', encoding='utf-8')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(collision.read_text(encoding='utf-8'), 'LOCAL FILE')
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD'), self.base)

    def test_detached_head_is_refused(self):
        git(self.checkout, 'checkout', '--detach', self.base)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Detached HEAD', result.stdout)

    def test_pending_merge_is_refused(self):
        marker = self.checkout / '.git' / 'MERGE_HEAD'
        marker.write_text(self.tip + '\n', encoding='ascii')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Finish the current Git operation', result.stdout)
        self.assertTrue(marker.exists())

    def test_failed_fetch_leaves_head_unchanged(self):
        result = self.run_update(self.directory / 'missing.git')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD'), self.base)

    def test_divergence_decision_never_merges_or_resets(self):
        result = self.run_update(divergent=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Histories diverged', result.stdout)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD'), self.base)
        self.assertEqual(git(self.checkout, 'status', '--porcelain'), '')
        self.assertFalse((self.checkout / '.git' / 'MERGE_HEAD').exists())

    def test_check_only_reports_author_without_fetching(self):
        before = git(ROOT, 'rev-parse', 'HEAD')
        fetch_path = ROOT / '.git' / 'FETCH_HEAD'
        fetch_before = fetch_path.read_bytes() if fetch_path.exists() else None
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-File', str(ROOT / 'local-tools' / 'windows.ps1'), '-Action', 'Update', '-CheckOnly'],
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads(result.stdout)
        self.assertEqual(state['upstream'], 'https://github.com/anonnerdfrenzy/survival-llm.git')
        self.assertTrue(state['dryRun'])
        self.assertEqual(git(ROOT, 'rev-parse', 'HEAD'), before)
        self.assertEqual(fetch_path.read_bytes() if fetch_path.exists() else None, fetch_before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
