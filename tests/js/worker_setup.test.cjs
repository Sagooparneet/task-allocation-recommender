const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../app/static/js/worker-setup.js'), 'utf8');
function run(hash, input, link) {
  const calls = [];
  vm.runInNewContext(source, {
    URL,
    document: { getElementById: id => id === 'invitation-link' ? link : input },
    window: {location: {hash, pathname: '/auth/worker-setup', search: '', href: 'http://localhost:5001/admin/workers/2/setup'}, history: {replaceState: (...args) => calls.push(args)}}
  });
  return calls;
}
test('valid secret fills form and is removed from browser address', () => {
  const input = {value: ''}; const token = 'A'.repeat(43);
  const calls = run('#' + token, input, null);
  assert.equal(input.value, token); assert.equal(calls[0][2], '/auth/worker-setup');
});
test('invalid fragment is removed without entering it into the form', () => {
  const input = {value: ''}; const calls = run('#invalid', input, null);
  assert.equal(input.value, ''); assert.equal(calls.length, 1);
});
test('manual entry remains available without a fragment', () => {
  const input = {value: 'manual'}; assert.deepEqual(run('', input, null), []);
  assert.equal(input.value, 'manual');
});
test('administrator link uses the current website origin and retains secret', () => {
  let focus; let selected = false;
  const link = {dataset: {setupPath: '/auth/worker-setup#' + 'B'.repeat(43)}, addEventListener: (event, fn) => {focus = fn;}, select: () => {selected = true;}};
  run('', null, link);
  assert.equal(link.value, 'http://localhost:5001/auth/worker-setup#' + 'B'.repeat(43));
  focus(); assert.equal(selected, true);
});
