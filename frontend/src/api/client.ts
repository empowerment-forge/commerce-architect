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
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  token?: string | null;
  credentials?: RequestCredentials;
};

export const SESSION_EXPIRED_MESSAGE = "Your session has expired. Please log in again.";

export class SessionExpiredError extends Error {
  constructor() {
    super(SESSION_EXPIRED_MESSAGE);
    this.name = "SessionExpiredError";
  }
}

export type AuthenticatedRequester = <T>(
  path: string,
  options?: Omit<RequestOptions, "token" | "credentials">,
) => Promise<T>;

type AuthenticatedRequesterOptions = {
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<{ access: string }>;
  onAccessToken: (access: string) => void;
  onSessionExpired: () => void;
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

export function createAuthenticatedRequester({
  getAccessToken,
  refreshAccessToken,
  onAccessToken,
  onSessionExpired,
}: AuthenticatedRequesterOptions): AuthenticatedRequester {
  let refreshInFlight: Promise<string> | null = null;

  async function refreshOnce(): Promise<string> {
    if (!refreshInFlight) {
      refreshInFlight = refreshAccessToken()
        .then(({ access }) => {
          onAccessToken(access);
          return access;
        })
        .finally(() => {
          refreshInFlight = null;
        });
    }
    return refreshInFlight;
  }

  return async function authenticatedRequest<T>(
    path: string,
    options: Omit<RequestOptions, "token" | "credentials"> = {},
  ): Promise<T> {
    const access = getAccessToken();
    if (!access) {
      onSessionExpired();
      throw new SessionExpiredError();
    }

    try {
      return await apiRequest<T>(path, { ...options, token: access });
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
    }

    let replacementAccess = getAccessToken();
    try {
      if (!replacementAccess || replacementAccess === access) {
        replacementAccess = await refreshOnce();
      }
    } catch {
      onSessionExpired();
      throw new SessionExpiredError();
    }

    try {
      return await apiRequest<T>(path, { ...options, token: replacementAccess });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        onSessionExpired();
        throw new SessionExpiredError();
      }
      throw error;
    }
  };
}
