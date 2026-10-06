// Typed client for the Preuve API. All API calls from the web app go through here.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type ValidationState =
  | "unvalidated"
  | "researching"
  | "early_signal"
  | "problem_validated"
  | "solution_validation"
  | "commercial_validation"
  | "mvp_ready";

export interface Idea {
  id: string;
  title: string;
  description: string;
  target_market: string;
  why_it_matters: string | null;
  industry: string | null;
  customer_type: string | null;
  business_model: string | null;
  known_competitors: string | null;
  assumptions: string | null;
  state: ValidationState;
  created_at: string;
  updated_at: string;
}

export interface Health {
  status: "ok" | "degraded";
  checks: Record<string, boolean>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new ApiError(res.status, `${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/health"),
  listIdeas: () => request<Idea[]>("/ideas"),
  getIdea: (id: string) => request<Idea>(`/ideas/${id}`),
};
