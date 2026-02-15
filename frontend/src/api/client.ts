const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function apiGet<T>(path: string, token: string | null = null): Promise<T> {
  const headers: HeadersInit | undefined = token
    ? { Authorization: `Bearer ${token}` }
    : undefined;
  const response = await fetch(`${API_BASE_URL}${path}`, { headers });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}
