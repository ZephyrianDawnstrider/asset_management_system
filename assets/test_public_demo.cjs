const test = require('node:test');
const assert = require('node:assert/strict');

const demo = require('./static/assets/js/public-demo.js');

test('search selects synthetic assets without changing custody', () => {
  const state = demo.createDemoState();
  assert.deepEqual(demo.searchAssets(state, 'headset').map(asset => asset.id), ['headset']);
  assert.deepEqual(demo.searchAssets(state, 'DEMO-LAP-001').map(asset => asset.id), ['laptop']);
  assert.equal(demo.searchAssets(state, 'missing').length, 0);
  assert.equal(demo.selectAsset(state, 'headset'), true);
  assert.equal(demo.selectedAsset(state).holder, null);
  assert.equal(demo.selectAsset(state, 'unknown'), false);
  assert.equal(state.selectedId, 'headset');
});

test('return is required before reassignment and timeline records both steps', () => {
  const state = demo.createDemoState();
  const before = [...demo.selectedAsset(state).events];
  assert.equal(demo.assignSelected(state, 'morgan').ok, false);
  assert.equal(demo.selectedAsset(state).holder, 'avery');
  assert.deepEqual(demo.selectedAsset(state).events, before);
  assert.equal(demo.returnSelected(state).ok, true);
  assert.equal(demo.selectedAsset(state).holder, null);
  assert.match(demo.offboardingMessage(state), /No sample assets remain held by Avery/);
  assert.equal(demo.assignSelected(state, 'morgan').ok, true);
  assert.equal(demo.selectedAsset(state).holder, 'morgan');
  assert.deepEqual(demo.selectedAsset(state).events, [
    'Assigned to Avery Example', 'Returned from Avery Example', 'Assigned to Morgan Example',
  ]);
});

test('reset creates independent initial state', () => {
  const changed = demo.createDemoState();
  demo.returnSelected(changed);
  demo.assignSelected(changed, 'morgan');
  const reset = demo.createDemoState();
  assert.equal(demo.selectedAsset(reset).holder, 'avery');
  assert.deepEqual(demo.selectedAsset(reset).events, ['Assigned to Avery Example']);
  assert.equal(demo.searchAssets(reset, '').length, 2);
});
