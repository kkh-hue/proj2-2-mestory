export type AuthResponse = {
  access_token: string;
  token_type: string;
};

export type AuthUser = {
  id: number;
  email: string;
};

function getBaseUrl(): string {
  let baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!baseUrl) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다.");
    }
    baseUrl = "http://localhost:8000";
  }
  return baseUrl.replace(/\/+$/, "");
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${getBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const body = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> };
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((item) => item.msg ?? "입력값을 확인해 주세요.").join(" ");
    } catch {
      // 서버가 JSON이 아닌 오류 본문을 보내도 원문을 사용자에게 전달한다.
    }
    throw new Error(detail || `인증 요청에 실패했습니다. (HTTP ${response.status})`);
  }

  return (await response.json()) as T;
}

export function signup(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe(token: string): Promise<AuthUser> {
  return request<AuthUser>("/auth/me", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}
