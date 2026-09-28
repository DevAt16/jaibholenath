import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateReview } from '../src/review.js';
import { passwordHash, passwordMatches } from '../src/security.js';
import { draft, verified } from './fixtures.js';
test('draft allows uncertainty; verification gates cannot be bypassed by a status or confidence score', () => {
  assert.equal(validateReview(draft()).status, 'in_review');
  assert.throws(() => validateReview({ ...draft(), status: 'verified', confidence: 'high' }));
  assert.equal(validateReview(verified()).status, 'verified');
  for (const key of ['shivaAssociation', 'state', 'district', 'settlement', 'latitude', 'longitude', 'locationEvidence', 'rationale']) assert.throws(() => validateReview({ ...verified(), [key]: '' }));
  assert.throws(() => validateReview({ ...verified(), precision: 'approximate' }));
  assert.throws(() => validateReview({ ...verified(), duplicateChecked: false }));
  const copied = verified(); copied.sources[1].origin = copied.sources[0].origin;
  assert.throws(() => validateReview(copied));
  const weak = verified(); weak.sources.forEach(source => source.type = 'other');
  assert.throws(() => validateReview(weak));
});
test('decisions require reasons; reopening final records preserves a reason', () => {
  for (const status of ['needs_evidence', 'rejected']) assert.throws(() => validateReview({ ...draft(), status }));
  assert.throws(() => validateReview(draft(), 'verified'));
  assert.throws(() => validateReview(draft(), 'rejected'));
  assert.equal(validateReview({ ...draft(), reopenReason: 'New contradictory evidence' }, 'verified').status, 'in_review');
  assert.throws(() => validateReview({ ...draft(), status: 'duplicate' }));
});
test('input types, coordinates, source bounds and unsupported fields are controlled', () => {
  assert.throws(() => validateReview({ ...draft(), latitude: 'NaN' }));
  assert.throws(() => validateReview({ ...draft(), longitude: '181' }));
  assert.throws(() => validateReview({ ...draft(), sources: Array(21).fill({}) }));
  assert.throws(() => validateReview({ ...draft(), sources: [null] }));
  assert.throws(() => validateReview({ ...draft(), name: {} }));
  const impossibleDate = verified(); impossibleDate.sources[0].accessed = '2026-02-30';
  assert.throws(() => validateReview(impossibleDate));
  const result = validateReview({ ...draft(), author: 'forged', methodology: 'officially certified' });
  assert.equal(result.author, undefined); assert.equal(result.methodology, 'pilot-v1-proposed');
});
test('passwords are salted, verified and reject bad or oversized credentials', async () => {
  const password = 'A long local testing password';
  const a = await passwordHash(password); const b = await passwordHash(password);
  assert.notEqual(a, b); assert.equal(await passwordMatches(password, a), true);
  assert.equal(await passwordMatches('incorrect', a), false);
  assert.equal(await passwordMatches('x'.repeat(300), a), false);
  await assert.rejects(passwordHash('short'));
});
