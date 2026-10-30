const test = require('node:test');
const assert = require('node:assert/strict');
const preferences = require('../../app/static/js/accessibility-preferences.js');

test('missing and malformed storage use usable defaults', () => {
    const defaults = {textSize: 'default', contrast: false, reducedMotion: false, bold: false, appearance: 'light'};
    assert.deepEqual(preferences.read(null), defaults);
    assert.deepEqual(preferences.read({getItem: () => '{bad json'}), defaults);
    assert.deepEqual(preferences.read({getItem: () => {throw new Error('blocked');}}), defaults);
});

test('stored settings accept only supported values and discard unrelated data', () => {
    assert.deepEqual(preferences.normalize({textSize: 'giant', contrast: 'true', reducedMotion: 1, role: 'administrator'}),
        {textSize: 'default', contrast: false, reducedMotion: false, bold: false, appearance: 'light'});
});

test('preferences survive reload and resetting preserves unrelated storage', () => {
    const entries = new Map([['unrelated', 'keep me']]);
    const storage = {getItem: key => entries.get(key) || null, setItem: (key, value) => entries.set(key, value)};
    const choice = {textSize: 'largest', contrast: true, reducedMotion: true};
    assert.equal(preferences.write(storage, choice), true);
    assert.deepEqual(preferences.read(storage), preferences.normalize(choice));
    assert.equal(preferences.write(storage, preferences.normalize(null)), true);
    assert.equal(preferences.read(storage).textSize, 'default');
    assert.equal(entries.get('unrelated'), 'keep me');
});

test('blocked or full browser storage reports failure instead of throwing', () => {
    assert.equal(preferences.write(null, {}), false);
    assert.equal(preferences.write({setItem: () => {throw new Error('quota');}}, {}), false);
});


test('earlier settings remain valid and new choices persist', () => {
    const old = preferences.normalize({textSize: 'largest', contrast: true});
    assert.equal(old.textSize, 'largest');
    assert.equal(old.contrast, true);
    assert.equal(old.bold, false);
    assert.equal(old.appearance, 'light');
    let saved;
    const storage = {setItem: (_, value) => {saved = value;}, getItem: () => saved};
    const choice = preferences.normalize({textSize: 'huge', bold: true, appearance: 'system'});
    preferences.write(storage, choice);
    assert.deepEqual(preferences.read(storage), choice);
});

test('system appearance follows the device, explicit choices override it', () => {
    assert.equal(preferences.resolveAppearance({appearance: 'system'}, true), 'dark');
    assert.equal(preferences.resolveAppearance({appearance: 'system'}, false), 'light');
    assert.equal(preferences.resolveAppearance({appearance: 'light'}, true), 'light');
    assert.equal(preferences.resolveAppearance({appearance: 'dark'}, false), 'dark');
});
