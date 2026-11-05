"""Exercise the real draw prelude without a native window or external side effects."""
import pathlib
import subprocess
import unittest


class NewSpaceRender(unittest.TestCase):
    def test_initial_and_delivered_icon_requests(self):
        main = pathlib.Path(__file__).resolve().parents[1] / "mods/newspace/main.js"
        program = r"""
const assert = require('node:assert/strict');
const source = require('node:fs').readFileSync(process.argv[1], 'utf8');
const prelude = source.split('  draw(cx) {')[1].split('    const rows =')[0];
const draw = new Function('theme', 'shared', 'props', 'PICK', 'cx', prelude);
function render(request, overlay, picked = 0) {
  let focused = 0;
  const state = { picked, icon: null, input: { focus() { focused++; } } };
  draw.call(state, () => ({}), () => request, () => overlay === undefined ? undefined : ({ overlay }), 'pick',
    { timer: { after(_ms, callback) { callback(); } } });
  return { picked: state.picked, icon: state.icon, focused };
}
assert.deepEqual(render(null), { picked: 0, icon: null, focused: 0 });
assert.deepEqual(render(undefined, 'newspace'), { picked: 0, icon: null, focused: 0 });
assert.deepEqual(render({ for: 'another', at: 10, emoji: 'x' }, 'newspace'),
  { picked: 0, icon: null, focused: 0 });
assert.deepEqual(render({ for: 'newspace', at: 10, emoji: 'x' }, 'newspace'),
  { picked: 10, icon: 'x', focused: 1 });
assert.deepEqual(render({ for: 'newspace', at: 10, emoji: 'x' }, 'newspace', 10),
  { picked: 10, icon: null, focused: 0 });
"""
        result = subprocess.run(["node", "-e", program, str(main)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
