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

const sourceDefinitions = [
  ['local', '本地项目'],
  ['gitee', 'Gitee 项目'],
  ['github', 'GitHub 项目'],
];

export function groupWorkspaceConversations(conversations, projects = []) {
  const grouped = groupConversations(conversations, projectId => (
    projects.find(project => String(project.id) === String(projectId))?.name
  ));
  const conversationsByProject = new Map(
    grouped.projects.map(project => [String(project.projectId), project.conversations]),
  );
  const knownProjectIds = new Set(projects.map(project => String(project.id)));
  const sources = sourceDefinitions.map(([key, label]) => ({
    key,
    label,
    projects: projects
      .filter(project => (project.source_type || 'local') === key)
      .map(project => ({
        projectId: String(project.id),
        name: project.name || '未命名项目',
        sourceType: key,
        project,
        conversations: conversationsByProject.get(String(project.id)) || [],
      })),
  }));
  const removed = grouped.projects.filter(project => !knownProjectIds.has(String(project.projectId)));
  if (removed.length) {
    sources.push({
      key: 'removed',
      label: '已移除项目',
      projects: removed.map(project => ({ ...project, sourceType: 'removed', project: null })),
    });
  }
  return { daily: grouped.general, sources };
}
