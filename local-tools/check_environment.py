"""Read-only interpreter and import checks, run by the Windows launcher with -I -B."""
import importlib
import json
import sys

issues = []
runtime_ready = sys.version_info >= (3, 12) and sys.prefix != sys.base_prefix
if not runtime_ready:
    issues.append('A Python 3.12+ virtual environment is required.')
for name in ('pypdf', 'truststore'):
    try:
        importlib.import_module(name)
    except Exception as error:
        issues.append(f'{name}: {type(error).__name__}: {error}')
print(json.dumps({
    'pythonVersion': sys.version.split()[0],
    'runtimeReady': runtime_ready,
    'environmentReady': not issues,
    'issues': issues,
}))
