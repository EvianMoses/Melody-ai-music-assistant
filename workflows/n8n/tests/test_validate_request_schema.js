/**
 * Contract test for the WF-001 `Validate Request Schema` Code node (N8N-005 / N8N-009).
 *
 * Extracts the jsCode straight out of the exported workflow JSON, so the test
 * always runs the code that ships — not a copy that can drift.
 *
 *   node workflows/n8n/tests/test_validate_request_schema.js
 *
 * Exit code 0 = all cases behave as specified, 1 = a case regressed.
 */

const fs = require('fs');
const path = require('path');

const WF_PATH = path.join(
  __dirname, '..', 'MELODY — WF-001 — Main Request Router.json'
);

function loadNodeCode(file, nodeName) {
  const wf = JSON.parse(fs.readFileSync(file, 'utf8'));
  const node = wf.nodes.find((n) => n.name === nodeName);
  if (!node) throw new Error(`node "${nodeName}" not found in ${path.basename(file)}`);
  return node.parameters.jsCode;
}

const jsCode = loadNodeCode(WF_PATH, 'Validate Request Schema');

// Minimal stand-ins for the n8n Code-node sandbox globals.
const $execution = { id: 'exec_999' };
const runNode = new Function('$input', '$execution', jsCode);
const run = (items) => runNode({ all: () => items }, $execution);

const envelope = (over = {}) => [{
  json: {
    api_version: 'v1',
    request_id: 'req-1',
    intent: 'text_recommendation',
    locale: 'en',
    identity: { guest_id: 'guest-1' },
    body: { prompt: 'something mellow' },
    ...over,
  },
}];

/** @type {{name:string, items:any, expect:'accept'|'reject', check?:Function}[]} */
const CASES = [
  // --- accepted ---------------------------------------------------------
  {
    name: 'flat envelope (manual test path)',
    items: envelope(),
    expect: 'accept',
    check: (r) => r.requestId === 'req-1' && r.intent === 'text_recommendation',
  },
  {
    name: 'webhook-wrapped envelope',
    items: [{ json: { body: envelope()[0].json } }],
    expect: 'accept',
    check: (r) => r.requestId === 'req-1' && r.message === 'something mellow',
  },
  {
    name: 'Hebrew locale is supported',
    items: envelope({ locale: 'he', body: { prompt: 'מוזיקה שקטה' } }),
    expect: 'accept',
    check: (r) => r.locale === 'he',
  },
  {
    name: 'missing request_id falls back to the execution id (N8N-004)',
    items: envelope({ request_id: undefined }),
    expect: 'accept',
    check: (r) => r.requestId === 'exec_999',
  },
  {
    name: 'playlist_export WITH an idempotency key (N8N-009)',
    items: envelope({ intent: 'playlist_export', idempotency_key: 'key-abc', body: {} }),
    expect: 'accept',
    check: (r) => r.idempotencyKey === 'key-abc',
  },
  {
    name: 'the full envelope is forwarded to the sub-workflow',
    items: envelope(),
    expect: 'accept',
    check: (r) => r.envelope && r.envelope.body.prompt === 'something mellow',
  },

  // --- rejected ---------------------------------------------------------
  {
    name: 'unknown intent is rejected (N8N-005)',
    items: envelope({ intent: 'delete_everything' }),
    expect: 'reject',
  },
  {
    name: 'unsupported api_version is rejected',
    items: envelope({ api_version: 'v2' }),
    expect: 'reject',
  },
  {
    name: 'unsupported locale is rejected',
    items: envelope({ locale: 'fr' }),
    expect: 'reject',
  },
  {
    name: 'unknown discovery_mode is rejected',
    items: envelope({ body: { prompt: 'p', recommendation_context: { discovery_mode: 'wild' } } }),
    expect: 'reject',
  },
  {
    name: 'playlist_export WITHOUT an idempotency key is rejected (N8N-009)',
    items: envelope({ intent: 'playlist_export', body: {} }),
    expect: 'reject',
  },
  {
    name: 'feedback WITHOUT an idempotency key is rejected (N8N-009)',
    items: envelope({ intent: 'feedback', body: {} }),
    expect: 'reject',
  },
  {
    name: 'text_recommendation without a prompt is rejected',
    items: envelope({ body: {} }),
    expect: 'reject',
  },
  {
    name: 'an over-long prompt is rejected',
    items: envelope({ body: { prompt: 'x'.repeat(1001) } }),
    expect: 'reject',
  },
  {
    name: 'a missing intent is rejected',
    items: envelope({ intent: '' }),
    expect: 'reject',
  },
];

let failed = 0;
for (const c of CASES) {
  let outcome, detail = '';
  try {
    const result = run(c.items)[0].json;
    outcome = 'accept';
    if (c.check && !c.check(result)) {
      outcome = 'accept(bad-shape)';
      detail = JSON.stringify(result);
    }
  } catch (err) {
    outcome = 'reject';
    detail = err.message;
  }

  const ok = outcome === c.expect;
  if (!ok) failed++;
  console.log(
    `${ok ? 'ok  ' : 'FAIL'}  ${c.name}\n        expected ${c.expect}, got ${outcome}${detail ? ` — ${detail}` : ''}`
  );
}

console.log(`\n${CASES.length - failed}/${CASES.length} cases passed`);
process.exit(failed === 0 ? 0 : 1);
