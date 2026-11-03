// Typed client for the Preuve API. All API calls from the web app go through here.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// ---------- ideas ----------

export type ValidationState =
  | "unvalidated"
  | "researching"
  | "early_signal"
  | "problem_validated"
  | "solution_validation"
  | "commercial_validation"
  | "mvp_ready";

export interface IdeaInput {
  title: string;
  description: string;
  target_market: string;
  why_it_matters?: string | null;
  industry?: string | null;
  customer_type?: string | null;
  business_model?: string | null;
  known_competitors?: string | null;
  assumptions?: string | null;
}

export interface Idea extends Required<IdeaInput> {
  id: string;
  state: ValidationState;
  created_at: string;
  updated_at: string;
}

// ---------- analysis (Phase 1A) ----------

export type Source = "ai" | "user" | "research";
export type RunStatus = "queued" | "running" | "succeeded" | "failed";
export type UnknownCategory =
  | "frequency"
  | "cost"
  | "current_solution"
  | "buyer"
  | "budget"
  | "alternatives"
  | "urgency"
  | "other";
export type Priority = "high" | "medium" | "low";
export type UnknownStatus = "open" | "answered" | "dropped";
export type Criterion =
  | "pain_likelihood"
  | "ability_to_pay"
  | "reachability"
  | "frequency_urgency"
  | "segment_size";

export interface AnalysisRun {
  id: string;
  idea_id: string;
  kind: "full" | "icps";
  status: RunStatus;
  step: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface HypothesisFields {
  problem: string;
  users: string;
  buyer: string;
  decision_maker: string;
  economic_value: string;
  geography: string;
  industry: string;
}

export interface Hypothesis extends HypothesisFields {
  id: string;
  version: number;
  source: Source;
  change_note: string | null;
  created_at: string;
}

export interface Unknown {
  id: string;
  question: string;
  category: UnknownCategory;
  priority: Priority;
  status: UnknownStatus;
  source: Source;
  created_at: string;
}

export interface Rating {
  rating: number;
  rationale: string;
}

export type Ratings = Record<Criterion, Rating>;

export interface ScoreComponent {
  criterion: Criterion;
  weight: number;
  rating: number;
  rationale: string;
  points: number;
}

export interface ICP {
  id: string;
  name: string;
  company_type: string;
  size_min: number | null;
  size_max: number | null;
  geography: string;
  signals: string[];
  roles: { users?: string[]; buyers?: string[] };
  hypothesis_score: number;
  score_breakdown: ScoreComponent[];
  source: Source;
  is_primary: boolean;
  status: "active" | "dismissed";
  created_at: string;
}

export interface ICPInput {
  name: string;
  company_type: string;
  size_min?: number | null;
  size_max?: number | null;
  geography: string;
  signals?: string[];
  user_roles?: string[];
  buyer_roles?: string[];
  ratings: Ratings;
  is_primary?: boolean;
}

export type ICPPatch = Partial<Omit<ICPInput, "ratings">> & {
  ratings?: Ratings;
  status?: "active" | "dismissed";
};

export interface IdeaAnalysis {
  hypothesis: Hypothesis | null;
  unknowns: Unknown[];
  icps: ICP[];
  latest_run: AnalysisRun | null;
}

// ---------- research (Phase 1B) ----------

export type Stance = "supports" | "contradicts" | "neutral";
export type EvidenceKind = "fact" | "inference";
export type Relevance = "high" | "medium" | "low";
export type Verification = "verified" | "unverifiable";
export type FindingStatus = "answered" | "partially_answered" | "no_evidence_found";
export type SourceType =
  | "job_posting"
  | "forum"
  | "review"
  | "news"
  | "industry_publication"
  | "company_site"
  | "report"
  | "directory"
  | "other";

export interface Evidence {
  id: string;
  import_id: string;
  ref: string;
  url: string;
  final_url: string | null;
  title: string | null;
  fetched_at: string;
  quote: string;
  statement: string;
  source_type: SourceType;
  kind: EvidenceKind;
  stance: Stance;
  relevance: Relevance;
  company_name: string | null;
  published_at: string | null;
  verification: Verification;
  verification_note: string | null;
  dismissed: boolean;
  user_edited: boolean;
  original_labels: Record<string, string> | null;
  unknown_ids: string[];
  created_at: string;
}

export interface Claim {
  statement: string;
  kind: "fact" | "inference" | "assumption";
  evidence_ids: string[];
}

export interface Finding {
  unknown_id: string;
  import_id: string;
  status: FindingStatus;
  summary: Claim[];
  created_at: string;
}

export interface ImportReport {
  counts?: { verified: number; unverifiable: number; rejected: number };
  rejected?: { ref: string; url: string; reason: string }[];
  dropped_claims?: { statement: string; missing_refs: string[] }[];
  downgraded_findings?: string[];
  duplicates?: string[];
  hypothesis_version?: number | null;
  hypothesis_skipped?: string | null;
  new_unknowns?: number;
  competitors?: {
    created: string[];
    updated: string[];
    rejected: { ref: string; name: string; reason: string }[];
  };
}

export interface ResearchImport {
  id: string;
  idea_id: string;
  schema_version: string;
  method_version: string;
  researcher: string;
  status: "queued" | "verifying" | "done" | "failed";
  report: ImportReport;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export type CompetitorKind = "direct" | "indirect" | "manual" | "service";

export interface Competitor {
  id: string;
  name: string;
  url: string | null;
  kind: CompetitorKind;
  description: string;
  pricing_note: string | null;
  sentiment: Claim[];
  source: Source;
  status: "active" | "dismissed";
  user_edited: boolean;
  evidence_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface CompetitorInput {
  name: string;
  kind: CompetitorKind;
  url?: string | null;
  description: string;
  pricing_note?: string | null;
}

export interface IdeaResearch {
  evidence: Evidence[];
  findings: Finding[];
  imports: ResearchImport[];
  competitors: Competitor[];
  current_solutions: Claim[];
}

// ---------- prospects (Phase 1D) ----------

export type ProspectStatus = "new" | "shortlisted" | "excluded";

export interface ProspectSummary {
  id: string;
  name: string;
  website: string;
  domain: string;
  location: string | null;
  industry: string | null;
  status: ProspectStatus;
  icp_id: string | null;
  score: number | null;
  contacts: number;
  top_contact_role: string | null;
}

export interface ScoreComponent {
  key: string;
  label: string;
  points: number;
  max: number;
  reason: string;
  evidence_ids: string[];
}

export interface Contact {
  id: string;
  name: string;
  role: string;
  email: string | null;
  evidence_id: string;
  source_url: string;
  collected_at: string;
}

export interface ProspectDetail extends ProspectSummary {
  description: string;
  size_min: number | null;
  size_max: number | null;
  size_signal: string | null;
  in_geo: boolean | null;
  technologies: string[];
  evidence_ids: string[];
  contacts_list: Contact[];
  components: ScoreComponent[];
  scored_at: string | null;
  inputs_hash: string | null;
}

// ---------- portfolio (Phase 1E) ----------

export interface PortfolioItem {
  id: string;
  title: string;
  target_market: string;
  state: ValidationState;
  problem: string | null;
  evidence: {
    supports: number;
    contradicts: number;
    neutral: number;
    verified: number;
    unverifiable: number;
  };
  competitors: number;
  prospects: number;
  top_score: number | null;
  unknowns_open: number;
  unknowns_answered: number;
  busy: boolean;
  created_at: string;
  last_activity: string;
}

export interface Health {
  status: "ok" | "degraded";
  checks: Record<string, boolean>;
}

// ---------- outreach (Phase 2) ----------

export type CampaignStatus = "active" | "paused";
export type MessageStatus = "drafting" | "draft" | "approved" | "rejected" | "sent" | "bounced" | "blocked";
export type SuppressionReason = "unsubscribed" | "bounced" | "manual" | "deletion_request";

export interface CampaignStats {
  drafting: number;
  draft: number;
  approved: number;
  rejected: number;
  sent: number;
  bounced: number;
  blocked: number;
  sent_today: number;
}

export interface Campaign {
  id: string;
  idea_id: string;
  icp_id: string | null;
  name: string;
  purpose: string;
  daily_limit: number;
  status: CampaignStatus;
  created_at: string;
  stats: CampaignStats;
}

export interface CampaignInput {
  name: string;
  purpose: string;
  icp_id?: string | null;
  daily_limit?: number;
}

export interface MessageSummary {
  id: string;
  campaign_id: string;
  contact_id: string | null;
  company_id: string | null;
  to_name: string;
  to_email: string | null;
  subject: string;
  status: MessageStatus;
  checks: string[];
  approved_at: string | null;
  sent_at: string | null;
  updated_at: string;
}

export interface CitedEvidence {
  id: string;
  quote: string;
  statement: string;
  url: string;
  fetched_at: string;
  verification: "verified" | "unverifiable";
  stance: string;
}

export interface OutreachMessage extends MessageSummary {
  to_email_source: "public_page" | "user_entered" | null;
  body: string;
  why_selected: Claim[];
  cited_evidence_ids: string[];
  draft_error: string | null;
  user_edited: boolean;
  rejected_at: string | null;
  sent_body: string | null;
  sent_headers: Record<string, string> | null;
  content_hash: string | null;
  provider_message_id: string | null;
  send_error: string | null;
  blocked_reason: string | null;
  bounced_at: string | null;
  redacted_at: string | null;
  prospect: {
    company_id: string;
    name: string;
    domain: string;
    score: number | null;
    contact_role: string | null;
    contact_source_url: string | null;
  } | null;
  cited_evidence: CitedEvidence[];
}

export interface Recipient {
  contact_id: string;
  name: string;
  role: string;
  email: string | null;
  company_id: string;
  company_name: string;
  score: number | null;
  prospect_status: ProspectStatus;
  suppressed: boolean;
  campaign_ids: string[];
}

export interface Suppression {
  id: string;
  email: string;
  reason: SuppressionReason;
  message_id: string | null;
  note: string | null;
  created_at: string;
}

export interface OutreachSettings {
  sending_enabled: boolean;
  provider: string;
  sender_name: string;
  sender_address: string;
  sender_ready: boolean;
  daily_limit: number;
  cooldown_days: number;
  sent_today: number;
  postal_address: string;
}

// ---------- transport ----------

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
    let detail = `${init?.method ?? "GET"} ${path} failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep the generic message
    }
    throw new ApiError(res.status, detail);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/health"),

  listIdeas: () => request<Idea[]>("/ideas"),
  portfolio: () => request<PortfolioItem[]>("/portfolio"),
  getIdea: (id: string) => request<Idea>(`/ideas/${id}`),
  createIdea: (data: IdeaInput) => request<Idea>("/ideas", json("POST", data)),

  getAnalysis: (ideaId: string) => request<IdeaAnalysis>(`/ideas/${ideaId}/analysis`),
  analyze: (ideaId: string) =>
    request<AnalysisRun>(`/ideas/${ideaId}/analyze`, { method: "POST" }),
  regenerateIcps: (ideaId: string) =>
    request<AnalysisRun>(`/ideas/${ideaId}/icps/generate`, { method: "POST" }),

  hypothesisVersions: (ideaId: string) =>
    request<Hypothesis[]>(`/ideas/${ideaId}/hypothesis/versions`),
  editHypothesis: (ideaId: string, data: HypothesisFields & { change_note?: string }) =>
    request<Hypothesis>(`/ideas/${ideaId}/hypothesis`, json("POST", data)),

  createUnknown: (
    ideaId: string,
    data: { question: string; category?: UnknownCategory; priority?: Priority },
  ) => request<Unknown>(`/ideas/${ideaId}/unknowns`, json("POST", data)),
  updateUnknown: (
    ideaId: string,
    unknownId: string,
    data: Partial<Pick<Unknown, "question" | "category" | "priority" | "status">>,
  ) => request<Unknown>(`/ideas/${ideaId}/unknowns/${unknownId}`, json("PATCH", data)),

  createIcp: (ideaId: string, data: ICPInput) =>
    request<ICP>(`/ideas/${ideaId}/icps`, json("POST", data)),
  updateIcp: (ideaId: string, icpId: string, data: ICPPatch) =>
    request<ICP>(`/ideas/${ideaId}/icps/${icpId}`, json("PATCH", data)),

  getResearch: (ideaId: string) => request<IdeaResearch>(`/ideas/${ideaId}/research`),
  updateEvidence: (
    ideaId: string,
    evidenceId: string,
    data: Partial<Pick<Evidence, "dismissed" | "kind" | "stance" | "relevance">>,
  ) => request<Evidence>(`/ideas/${ideaId}/evidence/${evidenceId}`, json("PATCH", data)),

  createCompetitor: (ideaId: string, data: CompetitorInput) =>
    request<Competitor>(`/ideas/${ideaId}/competitors`, json("POST", data)),
  updateCompetitor: (
    ideaId: string,
    competitorId: string,
    data: Partial<CompetitorInput> & { status?: "active" | "dismissed" },
  ) => request<Competitor>(`/ideas/${ideaId}/competitors/${competitorId}`, json("PATCH", data)),

  listProspects: (
    ideaId: string,
    filters: { status?: ProspectStatus; min_score?: number } = {},
  ) => {
    const qs = new URLSearchParams(
      Object.entries(filters)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)]),
    ).toString();
    return request<ProspectSummary[]>(`/ideas/${ideaId}/prospects${qs ? `?${qs}` : ""}`);
  },
  getProspect: (ideaId: string, companyId: string) =>
    request<ProspectDetail>(`/ideas/${ideaId}/prospects/${companyId}`),
  updateProspect: (ideaId: string, companyId: string, data: { status?: ProspectStatus }) =>
    request<ProspectDetail>(`/ideas/${ideaId}/prospects/${companyId}`, json("PATCH", data)),
  rescoreProspects: (ideaId: string) =>
    request<{ rescored: number }>(`/ideas/${ideaId}/prospects/rescore`, { method: "POST" }),
  deleteContact: (ideaId: string, contactId: string) =>
    request<void>(`/ideas/${ideaId}/contacts/${contactId}`, { method: "DELETE" }),
  outreachSettings: () => request<OutreachSettings>("/outreach/settings"),
  listCampaigns: (ideaId: string) => request<Campaign[]>(`/ideas/${ideaId}/campaigns`),
  createCampaign: (ideaId: string, data: CampaignInput) =>
    request<Campaign>(`/ideas/${ideaId}/campaigns`, json("POST", data)),
  updateCampaign: (
    ideaId: string,
    campaignId: string,
    data: Partial<Pick<Campaign, "name" | "purpose" | "daily_limit" | "status">>,
  ) => request<Campaign>(`/ideas/${ideaId}/campaigns/${campaignId}`, json("PATCH", data)),
  listRecipients: (ideaId: string) => request<Recipient[]>(`/ideas/${ideaId}/outreach/recipients`),
  createDrafts: (ideaId: string, campaignId: string, contactIds: string[]) =>
    request<{ created: string[]; skipped: { contact_id: string; reason: string }[] }>(
      `/ideas/${ideaId}/campaigns/${campaignId}/drafts`,
      json("POST", { contact_ids: contactIds }),
    ),
  listMessages: (ideaId: string, campaignId: string) =>
    request<MessageSummary[]>(`/ideas/${ideaId}/campaigns/${campaignId}/messages`),
  getMessage: (ideaId: string, messageId: string) =>
    request<OutreachMessage>(`/ideas/${ideaId}/messages/${messageId}`),
  updateMessage: (
    ideaId: string,
    messageId: string,
    data: { to_email?: string | null; subject?: string; body?: string },
  ) => request<OutreachMessage>(`/ideas/${ideaId}/messages/${messageId}`, json("PATCH", data)),
  messageAction: (
    ideaId: string,
    messageId: string,
    action: "approve" | "reject" | "reopen" | "bounce" | "redraft",
  ) => request<OutreachMessage>(`/ideas/${ideaId}/messages/${messageId}/${action}`, { method: "POST" }),
  sendCampaign: (ideaId: string, campaignId: string, messageIds?: string[]) =>
    request<{ queued: number }>(
      `/ideas/${ideaId}/campaigns/${campaignId}/send`,
      json("POST", { message_ids: messageIds ?? null }),
    ),
  listSuppressions: () => request<Suppression[]>("/suppressions"),
  addSuppression: (email: string, note?: string) =>
    request<Suppression>("/suppressions", json("POST", { email, note: note || null })),
  deleteSuppression: (suppressionId: string) =>
    request<void>(`/suppressions/${suppressionId}`, { method: "DELETE" }),
};
