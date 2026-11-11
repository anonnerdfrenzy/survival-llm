"""Exercise relocated browser assets and the packaging copy, without Ollama."""
import http.client
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StaticAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='survival-static-')
        cls.addClassCleanup(cls.temp.cleanup)
        scratch = Path(cls.temp.name)
        cls.env_before = os.environ.copy()
        cls.addClassCleanup(lambda: (os.environ.clear(), os.environ.update(cls.env_before)))
        os.environ.update(SURVIVAL_LLM_APP_DIR=str(scratch / 'settings'),
                          SURVIVAL_LLM_FILES=str(scratch / 'files'),
                          SURVIVAL_LLM_LIBRARY=str(scratch / 'library'),
                          OLLAMA_HOST='127.0.0.1:9')
        sys.path.insert(0, str(ROOT / 'app'))
        import server
        cls.app = server
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        server.PORT = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.stop_server)

    @classmethod
    def stop_server(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)
        cls.httpd.server_close()

    def get(self, path, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.app.PORT, timeout=5)
        try:
            connection.request('GET', path, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()

    def test_html_references_load_the_actual_css_and_javascript(self):
        status, _, page = self.get('/')
        self.assertEqual(status, 200)
        self.assertNotIn(b'{{TOKEN}}', page)
        for url, content_type in [('/static/src/css/app.css', 'text/css'),
                                  ('/static/src/js/app.js', 'text/javascript')]:
            self.assertIn(url.encode(), page)
            status, mime, data = self.get(url)
            self.assertEqual(status, 200)
            self.assertIn(content_type, mime)
            self.assertEqual(data, (ROOT / 'app' / url.lstrip('/')).read_bytes())

    def test_unknown_assets_and_parent_paths_are_not_served(self):
        for url in ['/static/not-found.js', '/static/../server.py', '/static/src/js/../../../../memory.py',
                    '/static/%2e%2e/server.py']:
            self.assertEqual(self.get(url)[0], 404, url)

    def test_host_check_still_protects_assets(self):
        self.assertEqual(self.get('/static/src/js/app.js', {'Host': 'example.com'})[0], 403)

    def test_documentation_asset_links_exist(self):
        page = (ROOT / 'docs/index.html').read_text(encoding='utf-8')
        assets = re.findall(r'(?:href|src)="(\./src/[^\"]+)"', page)
        self.assertEqual(set(assets), {'./src/css/index.css', './src/js/index.js'})
        for asset in assets:
            self.assertTrue((ROOT / 'docs' / asset).is_file(), asset)

    def test_packaging_copies_nested_static_assets(self):
        if os.name == 'nt':
            git = shutil.which('git')
            bash = str(Path(git).resolve().parents[1] / 'bin/bash.exe') if git else ''
        else:
            bash = shutil.which('bash') or ''
        if not Path(bash).is_file():
            self.skipTest('Bash is required to exercise packaging copy_app')
        source = (ROOT / 'packaging/build.sh').read_text(encoding='utf-8')
        function = re.search(r'^copy_app\(\).*?^}', source, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(function)
        with tempfile.TemporaryDirectory(prefix='survival package assets ') as scratch:
            script = Path(scratch) / 'copy.sh'
            target = Path(scratch) / 'app output'
            # Execute only copy_app, not the full build/download workflow.
            script.write_text('set -eu\nREPO="$SLLM_TEST_ROOT"\nVERSION=test\n' + function.group()
                              + '\ncopy_app "$SLLM_TEST_DEST"\n', encoding='utf-8', newline='\n')
            result = subprocess.run([bash, '--noprofile', '--norc', script.as_posix()],
                                    env={**os.environ, 'SLLM_TEST_ROOT': ROOT.as_posix(),
                                         'SLLM_TEST_DEST': target.as_posix()},
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for asset in (ROOT / 'app/static').rglob('*'):
                if asset.is_file():
                    copied = target / 'app/static' / asset.relative_to(ROOT / 'app/static')
                    self.assertEqual(copied.read_bytes(), asset.read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
