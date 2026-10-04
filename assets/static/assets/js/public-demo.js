(function () {
  'use strict';

  const people = { avery: 'Avery Example', morgan: 'Morgan Example' };
  const startingAssets = [
    { id: 'laptop', name: 'Example laptop', category: 'Laptop', identifier: 'DEMO-LAP-001', holder: 'avery', events: ['Assigned to Avery Example'] },
    { id: 'headset', name: 'Example headset', category: 'Headset', identifier: 'DEMO-HDS-002', holder: null, events: ['Registered as available'] },
  ];

  function createDemoState() {
    return { selectedId: 'laptop', assets: startingAssets.map(asset => ({ ...asset, events: [...asset.events] })) };
  }

  function selectedAsset(state) {
    return state.assets.find(asset => asset.id === state.selectedId);
  }

  function searchAssets(state, query) {
    const term = query.trim().toLowerCase();
    return state.assets.filter(asset => [asset.name, asset.category, asset.identifier].some(value => value.toLowerCase().includes(term)));
  }

  function selectAsset(state, id) {
    if (!state.assets.some(asset => asset.id === id)) return false;
    state.selectedId = id;
    return true;
  }

  function returnSelected(state) {
    const asset = selectedAsset(state);
    if (!asset.holder) return { ok: false, message: 'This sample asset is already available.' };
    const previousHolder = people[asset.holder];
    asset.holder = null;
    asset.events.push(`Returned from ${previousHolder}`);
    return { ok: true, message: `${asset.name} is available. Choose a person to assign it in the demo.` };
  }

  function assignSelected(state, personId) {
    const asset = selectedAsset(state);
    if (!people[personId]) return { ok: false, message: 'Choose a sample person.' };
    if (asset.holder) return { ok: false, message: 'Return this asset before reassigning it. No custody event was added.' };
    asset.holder = personId;
    asset.events.push(`Assigned to ${people[personId]}`);
    return { ok: true, message: `${asset.name} is now assigned to ${people[personId]} in this simulation.` };
  }

  function offboardingMessage(state) {
    const held = state.assets.filter(asset => asset.holder === 'avery').length;
    return held
      ? `Across this sample register, Avery's final active day is approaching and ${held} sample asset${held === 1 ? '' : 's'} remain held. Review custody before closing the record; the final day is not a return due date.`
      : 'No sample assets remain held by Avery. Staff would review the real record before deactivation; this simulation changes no staff data.';
  }

  function mountDemo(root) {
    let state = createDemoState();
    const search = root.querySelector('#demo-search');
    const results = root.querySelector('#demo-results');
    const empty = root.querySelector('#demo-empty');
    const target = root.querySelector('#demo-target');
    const feedback = root.querySelector('#demo-feedback');
    const timeline = root.querySelector('#demo-timeline');

    function render() {
      const asset = selectedAsset(state);
      results.replaceChildren();
      const matches = searchAssets(state, search.value);
      empty.hidden = matches.length !== 0;
      root.querySelector('#demo-selection-note').hidden = matches.length !== 0;
      matches.forEach(item => {
        const row = document.createElement('li');
        const button = document.createElement('button');
        const title = document.createElement('span');
        const name = document.createElement('strong');
        const identifier = document.createElement('small');
        const status = document.createElement('span');
        button.type = 'button';
        button.dataset.demoAsset = item.id;
        button.setAttribute('aria-pressed', String(item.id === state.selectedId));
        name.textContent = item.name;
        identifier.textContent = `${item.identifier} · ${item.category}`;
        status.textContent = item.holder ? 'Assigned' : 'Available';
        title.append(name, identifier);
        button.append(title, status);
        row.append(button);
        results.append(row);
      });
      root.querySelector('#demo-name').textContent = asset.name;
      root.querySelector('#demo-category').textContent = asset.category;
      root.querySelector('#demo-identifier').textContent = asset.identifier;
      root.querySelector('#demo-holder').textContent = asset.holder ? people[asset.holder] : 'No current holder';
      root.querySelector('#demo-offboarding').textContent = offboardingMessage(state);
      const status = root.querySelector('#demo-status');
      status.textContent = asset.holder ? 'Assigned' : 'Available';
      status.className = `pill ${asset.holder ? 'pill-green' : 'pill-amber'}`;
      root.querySelector('#demo-return').disabled = !asset.holder;
      timeline.replaceChildren();
      asset.events.forEach(event => {
        const item = document.createElement('li');
        item.textContent = event;
        timeline.append(item);
      });
    }

    search.addEventListener('input', () => {
      const matches = searchAssets(state, search.value);
      if (matches.length && !matches.some(asset => asset.id === state.selectedId)) {
        selectAsset(state, matches[0].id);
        feedback.textContent = `Showing the synthetic custody record for ${selectedAsset(state).name}.`;
      }
      render();
    });
    results.addEventListener('click', event => {
      const button = event.target.closest('button[data-demo-asset]');
      if (!button || !results.contains(button)) return;
      selectAsset(state, button.dataset.demoAsset);
      feedback.textContent = `Showing the synthetic custody record for ${selectedAsset(state).name}.`;
      render();
    });
    root.querySelector('#demo-return').addEventListener('click', () => {
      feedback.textContent = returnSelected(state).message;
      render();
    });
    root.querySelector('#demo-assign').addEventListener('click', () => {
      feedback.textContent = assignSelected(state, target.value).message;
      render();
    });
    root.querySelector('#demo-reset').addEventListener('click', () => {
      state = createDemoState();
      search.value = '';
      target.value = 'morgan';
      feedback.textContent = 'Scenario reset. Try returning the laptop, then assign it to Morgan.';
      render();
    });
    render();
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { createDemoState, selectedAsset, searchAssets, selectAsset, returnSelected, assignSelected, offboardingMessage };
  }
  if (typeof document !== 'undefined') {
    const root = document.querySelector('[data-public-demo]');
    if (root) mountDemo(root);
  }
})();
