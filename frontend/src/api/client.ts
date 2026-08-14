const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export type ApiErrorBody = {
  code?: string;
  detail?: string;
  [field: string]: unknown;
};

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  token?: string | null;
  credentials?: RequestCredentials;
};

export async function apiRequest<T>(
  path: string,
  { method = "GET", body, token = null, credentials }: RequestOptions = {},
): Promise<T> {
  const headers: HeadersInit = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: Object.keys(headers).length ? headers : undefined,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials,
  });

  let responseBody: unknown;
  try {
    responseBody = await response.json();
  } catch {
    responseBody = null;
  }
  if (!response.ok) {
    const errorBody =
      responseBody && typeof responseBody === "object"
        ? (responseBody as ApiErrorBody)
        : {};
    throw new ApiError(response.status, errorBody);
  }
  return responseBody as T;
}

export function apiGet<T>(path: string, token: string | null = null): Promise<T> {
  return apiRequest<T>(path, { token });
}
