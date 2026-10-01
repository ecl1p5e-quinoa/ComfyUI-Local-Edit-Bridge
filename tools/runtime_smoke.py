"""Exercise the actual ComfyUI node and SaveImage without loading a model."""
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

base = sys.argv[1].rstrip('/')
if urllib.parse.urlsplit(base).hostname not in {'localhost', '127.0.0.1', '::1'}:
    raise ValueError('Local verification server required.')
output = Path('.test-output')
job_id = json.loads((output / 'browser-report.json').read_text())['job_id']


def request(path, data=None):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(base + path, body, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


job = request('/gpt-local-edit/jobs/' + job_id)['job']
assert job['state'] == 'FINALIZED'
info = request('/object_info/GPTLocalEditJob')['GPTLocalEditJob']
assert info['output'] == ['IMAGE', 'MASK', 'STRING', 'STRING']
extensions = request('/extensions')
plugin_extensions = [value for value in extensions if 'gpt-local-edit-helper' in value]
assert len(plugin_extensions) == 1 and plugin_extensions[0].endswith('/extension.js')
graph = {
    '1': {'class_type': 'GPTLocalEditJob', 'inputs': {'job_id': job_id}},
    '2': {'class_type': 'SaveImage', 'inputs': {'images': ['1', 0], 'filename_prefix': 'node-smoke-composite'}},
    '3': {'class_type': 'MaskToImage', 'inputs': {'mask': ['1', 1]}},
    '4': {'class_type': 'SaveImage', 'inputs': {'images': ['3', 0], 'filename_prefix': 'node-smoke-seam'}},
}
queued = request('/prompt', {'prompt': graph})
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    history = request('/history/' + queued['prompt_id'])
    if queued['prompt_id'] in history:
        break
    time.sleep(.2)
else:
    raise RuntimeError('ComfyUI node smoke test timed out.')
record = history[queued['prompt_id']]
assert record['status']['status_str'] == 'success', record['status']
result = record['outputs']['2']['images'][0]
with urllib.request.urlopen(base + '/view?' + urllib.parse.urlencode(result)) as response:
    pixels = np.array(Image.open(io.BytesIO(response.read())).convert('RGB'))
original = np.array(Image.open(output / 'original.png').convert('RGB'))
mask = np.array(Image.open(output / 'mask.png'))
assert np.array_equal(pixels[mask == 0], original[mask == 0])
assert list(pixels.shape[:2][::-1]) == job['source_size']
report = {'job_id': job_id, 'restored_state': job['state'], 'comfy_node_execution': 'success',
          'outside_mask_max_error': 0, 'extension_scripts': plugin_extensions,
          'source_size': job['source_size'], 'prompt_id': queued['prompt_id']}
(output / 'runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
