export async function loadTasks() {
  return fetch('/api/tasks').then(response => response.json());
}
