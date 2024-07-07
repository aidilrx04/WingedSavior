export const DEBUG_VIDEO = false;
export const DEBUG_ANDROID = false;

export let BACKEND_URL;
if (DEBUG_VIDEO) {
  BACKEND_URL = "127.0.0.1";
} else if (DEBUG_ANDROID) {
  BACKEND_URL = "10.0.2.2";
} else {
  BACKEND_URL = "192.168.11.34";
}

export const WEB_PORT = "8766";
export const WS_PORT = "8765";

export function ws() {
  return `ws://${BACKEND_URL}:${WS_PORT}`;
}

export function api(path) {
  return `http://${BACKEND_URL}:${WEB_PORT}${path}`;
}

export async function checkProjectExist(projectId) {
  try {
    // server should respond 200 if exists 404 if not found
    const r = await fetch(api(`/check_project?project=${projectId}`));
    if (r.status !== 200) return false;
    return true;
  } catch (e) {
    return false;
  }
}

export async function requiredProject(cb) {
  const params = new URLSearchParams(window.location.search);
  let projectId = params.get("project");

  const projectId2 = localStorage.getItem("project");

  // TODO: redirect user to project list page

  if (!projectId && !projectId2) alert("No valid project found");

  if (!projectId) projectId = projectId2;

  const exist = await checkProjectExist(projectId);
  if (!exist) {
    alert("Invalid project");
    return;
  }

  cb(projectId);
}
