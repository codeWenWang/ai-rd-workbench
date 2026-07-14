import assert from 'node:assert/strict';
import test from 'node:test';

import { groupConversations } from './js/conversation-groups.js';


test('groups generic and project conversations while preserving API order', () => {
  const conversations = [
    { id: 'p1-latest', project_id: 'project-1' },
    { id: 'general-latest', project_id: null },
    { id: 'p2-only', project_id: 'project-2' },
    { id: 'p1-older', project_id: 'project-1' },
    { id: 'general-older' },
  ];
  const names = new Map([['project-1', '测试项目']]);

  const result = groupConversations(conversations, projectId => names.get(projectId));

  assert.deepEqual(result.general.map(item => item.id), ['general-latest', 'general-older']);
  assert.deepEqual(result.projects.map(group => group.projectId), ['project-1', 'project-2']);
  assert.deepEqual(result.projects[0].conversations.map(item => item.id), ['p1-latest', 'p1-older']);
  assert.equal(result.projects[0].name, '测试项目');
  assert.equal(result.projects[1].name, '已移除项目');
});
