const {test} = require('node:test');
const assert = require('node:assert/strict');
const {History, segments, sumKnown} = require('../static/js/history.js');
test('aggregate requires complete rates; unknown is not zero', () => {
    assert.equal(sumKnown([{up: 1}, {up: null}], 'up'), null);
    assert.equal(sumKnown([], 'up'), 0);
    assert.equal(sumKnown([{up: 1}, {up: 2}], 'up'), 3);
    assert.equal(sumKnown([{up: 1e308}, {up: 1e308}], 'up'), null);
});
test('bounded history retains gaps and can be cleared', () => {
    const h = new History(2);
    h.add([{mac_address: 'example', bandwidth_up: 5}], 0);
    h.add(null, 10000); h.add([], 20000);
    assert.equal(h.samples.length, 2);
    assert.deepEqual(h.series().map(s => s.up), [null, 0]);
    assert.deepEqual(h.series('example').map(s => s.up), [null, null]);
    h.clear(); assert.equal(h.samples.length, 0);
});
test('client series distinguish zero from missing client', () => {
    const h = new History();
    h.add([{mac_address: 'example', bandwidth_down: 0}], 0); h.add([], 10000);
    assert.deepEqual(h.series('example').map(s => s.down), [0, null]);
});
test('paths split on missing samples and long pauses', () => {
    const samples = [{time: 0, up: 1}, {time: 10000, up: null},
        {time: 20000, up: 2}, {time: 80000, up: 3}];
    assert.deepEqual(segments(samples, 'up', n => n, n => n), ['M0,1', 'M20000,2', 'M80000,3']);
});
test('invalid rates stay unknown', () => {
    for (const value of [-1, '2', NaN, Infinity, undefined]) {
        const h = new History(); h.add([{mac_address: 'x', bandwidth_up: value}]);
        assert.equal(h.series('x')[0].up, null);
    }
});
