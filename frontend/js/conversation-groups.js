export function groupConversations(conversations, projectNameForId = () => '') {
  const general = [];
  const projectMap = new Map();

  for (const conversation of conversations) {
    const projectId = conversation?.project_id || '';
    if (!projectId) {
      general.push(conversation);
      continue;
    }
    if (!projectMap.has(projectId)) projectMap.set(projectId, []);
    projectMap.get(projectId).push(conversation);
  }

  return {
    general,
    projects: [...projectMap.entries()].map(([projectId, items]) => ({
      projectId,
      name: projectNameForId(projectId) || '已移除项目',
      conversations: items,
    })),
  };
}
