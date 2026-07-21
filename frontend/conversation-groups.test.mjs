import assert from 'node:assert/strict';
import test from 'node:test';

import { groupConversations, groupWorkspaceConversations } from './js/conversation-groups.js';


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


test('groups projects by source while keeping daily conversations separate', () => {
  const projects = [
    { id: 'local-1', name: '本地示例', source_type: 'local' },
    { id: 'gitee-1', name: 'Gitee 商城', source_type: 'gitee' },
    { id: 'github-1', name: 'GitHub 示例', source_type: 'github' },
  ];
  const conversations = [
    { id: 'daily', project_id: null },
    { id: 'gitee-chat', project_id: 'gitee-1' },
    { id: 'local-chat', project_id: 'local-1' },
  ];

  const result = groupWorkspaceConversations(conversations, projects);

  assert.deepEqual(result.daily.map(item => item.id), ['daily']);
  assert.deepEqual(result.sources.map(group => group.key), ['local', 'gitee', 'github']);
  assert.deepEqual(result.sources[0].projects.map(project => project.name), ['本地示例']);
  assert.deepEqual(result.sources[1].projects[0].conversations.map(item => item.id), ['gitee-chat']);
  assert.deepEqual(result.sources[2].projects[0].conversations, []);
});
