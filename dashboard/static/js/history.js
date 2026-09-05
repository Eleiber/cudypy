/* Bounded, tab-local observations. No storage or external chart dependencies. */
(function (root) {
    'use strict';
    const valid = n => typeof n === 'number' && Number.isFinite(n) && n >= 0;
    function sumKnown(devices, field) {
        if (!devices.every(d => valid(d[field]))) return null;
        const total = devices.reduce((sum, d) => sum + d[field], 0);
        return valid(total) ? total : null;
    }
    class History {
        constructor(limit = 180) { this.limit = limit; this.samples = []; }
        add(devices, time = Date.now()) {
            const sample = {time, clients: {}, up: null, down: null, active: null};
            if (devices !== null) {
                sample.up = sumKnown(devices, 'bandwidth_up');
                sample.down = sumKnown(devices, 'bandwidth_down');
                sample.active = devices.filter(d => d.is_online === true).length;
                sample.clients = Object.fromEntries(devices.map(d => [d.mac_address, {
                    up: valid(d.bandwidth_up) ? d.bandwidth_up : null,
                    down: valid(d.bandwidth_down) ? d.bandwidth_down : null,
                }]));
            }
            this.samples.push(sample);
            this.samples = this.samples.slice(-this.limit);
        }
        series(client = '') {
            return this.samples.map(s => ({time: s.time,
                up: client ? (s.clients[client]?.up ?? null) : s.up,
                down: client ? (s.clients[client]?.down ?? null) : s.down}));
        }
        clear() { this.samples = []; }
    }
    function segments(samples, field, x, y, maxGap = 30000) {
        const paths = []; let path = ''; let previous = null;
        for (const sample of samples) {
            if (!valid(sample[field])) { if (path) paths.push(path); path = ''; previous = null; continue; }
            if (previous !== null && sample.time - previous > maxGap) {
                if (path) paths.push(path); path = '';
            }
            path += `${path ? ' L' : 'M'}${x(sample.time)},${y(sample[field])}`;
            previous = sample.time;
        }
        if (path) paths.push(path);
        return paths;
    }
    const api = {History, segments, sumKnown};
    if (typeof module !== 'undefined') module.exports = api;
    root.CudyHistory = api;
})(globalThis);
