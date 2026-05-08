const TOKEN_KEY = "remember_token";
const USER_KEY = "remember_user";

export function getStoredAuth() {
  return {
    token: localStorage.getItem(TOKEN_KEY) || "",
    user: JSON.parse(localStorage.getItem(USER_KEY) || "null"),
  };
}

export function storeAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearStoredAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function request(path, options = {}, token = "") {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, {
    ...options,
    headers,
    body:
      options.body && !(options.body instanceof FormData)
        ? JSON.stringify(options.body)
        : options.body,
  });

  if (response.status === 204) return null;

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new Error(data?.detail || "请求失败");
  }

  return data;
}

export const authApi = {
  login(payload) {
    return request("/api/v1/auth/login", {
      method: "POST",
      body: payload,
    });
  },
  register(payload) {
    return request("/api/v1/auth/register", {
      method: "POST",
      body: payload,
    });
  },
  logout(token) {
    return request("/api/v1/auth/logout", { method: "POST" }, token);
  },
  changePassword(payload, token) {
    return request(
      "/api/v1/auth/password",
      {
        method: "POST",
        body: payload,
      },
      token,
    );
  },
};

export const chatApi = {
  listThreads(token) {
    return request("/api/v1/chat/threads", {}, token);
  },
  createThread(title, token) {
    return request(
      "/api/v1/chat/threads",
      {
        method: "POST",
        body: { title },
      },
      token,
    );
  },
  deleteThread(threadId, token) {
    return request(
      `/api/v1/chat/threads/${encodeURIComponent(threadId)}`,
      { method: "DELETE" },
      token,
    );
  },
  getMessages(threadId, token) {
    return request(
      `/api/v1/chat/messages?thread_id=${encodeURIComponent(threadId)}`,
      {},
      token,
    );
  },
  clearMessages(threadId, token) {
    return request(
      `/api/v1/chat/messages?thread_id=${encodeURIComponent(threadId)}`,
      { method: "DELETE" },
      token,
    );
  },
};

export const itemApi = {
  list(keyword, token) {
    const query = keyword?.trim();
    const path = `/api/v1/items?limit=100${query ? `&keyword=${encodeURIComponent(query)}` : ""}`;
    return request(path, {}, token);
  },
  create(payload, token) {
    return request(
      "/api/v1/items",
      {
        method: "POST",
        body: payload,
      },
      token,
    );
  },
  update(itemId, payload, token) {
    return request(
      `/api/v1/items/${itemId}`,
      {
        method: "PATCH",
        body: payload,
      },
      token,
    );
  },
  delete(itemId, token) {
    return request(
      `/api/v1/items/${itemId}`,
      { method: "DELETE" },
      token,
    );
  },
};

export const settingsApi = {
  get(token) {
    return request("/api/v1/settings", {}, token);
  },
  update(payload, token) {
    return request(
      "/api/v1/settings",
      {
        method: "PATCH",
        body: payload,
      },
      token,
    );
  },
};

export async function uploadImage(file, token) {
  const presign = await request(
    `/api/v1/oss/presign?filename=${encodeURIComponent(file.name)}`,
    {},
    token,
  );
  const upload = await fetch(presign.uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": presign.contentType },
    body: file,
  });
  if (!upload.ok) throw new Error("图片上传失败");
  return presign.accessUrl;
}
