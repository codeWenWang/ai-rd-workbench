export async function loadHealth() {
  return fetch('/health').then(response => response.json());
}
