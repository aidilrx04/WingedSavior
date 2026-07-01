export const DEBUG_VIDEO = false;
export const DEBUG_ANDROID = false;

export let BACKEND_URL;
if (DEBUG_VIDEO) {
  BACKEND_URL = "127.0.0.1";
} else if (DEBUG_ANDROID) {
  BACKEND_URL = "10.0.2.2";
} else {
  BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
}

export const WEB_PORT = "8766";
export const WS_PORT = "8765";

export const detectionTypes = {
  0: "Person",
  15: "Cat",
  16: "Dog",
};

export function ws() {
  return `ws://${BACKEND_URL}:${WS_PORT}`;
}

export function api(path) {
  return `http://${BACKEND_URL}:${WEB_PORT}${path}`;
}

console.log(BACKEND_URL, api("/test"));

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

  if (!projectId && !projectId2) {
    // alert("No valid project found");
    console.error("No valid project found");
    return;
  }

  if (!projectId) projectId = projectId2;

  const exist = await checkProjectExist(projectId);
  if (!exist) {
    console.error("Invalid project");
    return;
  }

  cb(projectId);
}

export function getUser() {
  let user = localStorage.getItem("user");

  if (!user) {
    console.warn("no user data");
    return;
  }

  try {
    user = JSON.parse(user);
    return user;
  } catch (err) {
    console.error(err);
  }
}
