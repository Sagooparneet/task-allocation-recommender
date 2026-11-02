const test = require('node:test');
const assert = require('node:assert/strict');
const calendar = require('../../app/static/js/deadline-calendar.js');

test('civil dates reject impossible days and accept leap years', () => {
  assert.ok(calendar.dateParts('2028-02-29'));
  for (const value of ['2027-02-29','2026-04-31','2026-13-01','2026-00-01','2026-01-00','not-a-date']) assert.equal(calendar.dateParts(value), null);
});
test('month navigation clamps end of month without skipping February', () => {
  assert.equal(calendar.shiftMonth('2027-01-31',1),'2027-02-28');
  assert.equal(calendar.shiftMonth('2028-03-31',-1),'2028-02-29');
  assert.equal(calendar.shiftMonth('2026-12-31',1),'2027-01-31');
});
test('keyboard day movement crosses month and year boundaries', () => {
  assert.equal(calendar.shiftDay('2026-12-31',1),'2027-01-01');
  assert.equal(calendar.shiftDay('2028-03-01',-1),'2028-02-29');
  assert.equal(calendar.shiftDay('2026-11-02',7),'2026-11-09');
});
test('Kenya today uses Nairobi midnight rather than the device timezone', () => {
  assert.equal(calendar.kenyaToday(new Date('2026-11-02T20:59:00Z')),'2026-11-02');
  assert.equal(calendar.kenyaToday(new Date('2026-11-02T21:00:00Z')),'2026-11-03');
});
test('submission preserves the exact Kenya civil time and server format', () => {
  assert.equal(calendar.combine('2026-11-03','17:30','2026-11-02'),'2026-11-03T17:30');
  assert.equal(calendar.combine('2026-11-02','00:00','2026-11-02'),'2026-11-02T00:00');
});
test('past dates and missing or invalid times cannot be applied', () => {
  for (const time of ['', '24:00', '12:60', '9:00', '12:00:10']) assert.equal(calendar.combine('2026-11-03',time,'2026-11-02'),null);
  assert.equal(calendar.combine('2026-11-01','17:00','2026-11-02'),null);
  assert.equal(calendar.combine(null,'17:00','2026-11-02'),null);
});
