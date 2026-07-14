import assert from 'node:assert/strict';
import { api, parseApiError, parseSSEChunk } from './api.js';

assert.deepEqual(parseApiError({ code: 'MODEL_DOWN', message: '模型不可用', request_id: 'req-1' }, 503), {
  code: 'MODEL_DOWN',
  message: '模型不可用',
  requestId: 'req-1',
  status: 503,
  details: undefined,
});

assert.equal(parseApiError({ detail: { message: '参数错误' } }, 422).message, '参数错误');
assert.equal(parseApiError('Bad Gateway', 502).message, 'Bad Gateway');

const parsed = parseSSEChunk(
  'event: stage\ndata: {"stage":"retrieving"}\n\n' +
  'event: token\ndata: {"token":"你好"}\n\n' +
  'data: {"type":"done"}\n\n' +
  'event: token\ndata: {"token":"未完成',
);

assert.deepEqual(parsed.events, [
  { event: 'stage', data: { stage: 'retrieving' } },
  { event: 'token', data: { token: '你好' } },
  { event: 'message', data: { type: 'done' } },
]);
assert.equal(parsed.remainder, 'event: token\ndata: {"token":"未完成');

for (const name of [
  'projects', 'createProject', 'scanProject', 'projectFiles',
  'artifacts', 'generateArtifact', 'modelProviders',
  'createModelProvider', 'updateModelProvider', 'deleteModelProvider', 'compareModels',
]) assert.equal(typeof api[name], 'function', `${name} API helper missing`);

console.log('api contract tests passed');
