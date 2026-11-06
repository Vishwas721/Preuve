// Typed client for the Preuve API. All API calls from the web app go through here.

// Always same-origin: Next proxies /api/* to the API (next.config.ts, PREUVE_API_INTERNAL_URL),
// so the session cookie is first-party (Phase 5A). A cross-site API URL would break sign-in,
// so the old NEXT_PUBLIC_API_URL setting is deliberately ignored.
export const API_URL = "/api";

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

export type EvidenceOrigin = "research" | "reply" | "interview";

export interface Evidence {
  id: string;
  /** Null for first-party evidence (replies, interviews). */
  import_id: string | null;
  origin: EvidenceOrigin;
  response_id: string | null;
  interview_id: string | null;
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

// ---------- research score (Phase 6) ----------

export type ResearchBand = "strong" | "promising" | "weak";

export interface ResearchDimension {
  key: "problem" | "pain" | "balance" | "questions" | "open_space" | "reachability";
  label: string;
  points: number;
  max: number;
  reason: string;
  gaps: string[];
}

export interface ResearchScore {
  total: number;
  band: ResearchBand;
  dimensions: ResearchDimension[];
  version: number;
}

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
  validation: {
    score: number;
    recommendation: Recommendation;
    headline: string;
    validated_conversations: number;
    stale: boolean;
    computed_at: string;
  } | null;
  research_score: { total: number; band: ResearchBand; version: number };
  funnel: { sent: number; replies: number; interviews_done: number; pilot_or_better: number };
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
  /** Stuck in drafting (lost job): can be redrafted. */
  stale: boolean;
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

// ---------- replies, interviews, WTP (Phase 3) ----------

export type ResponseStatus = "queued" | "analyzing" | "done" | "failed";
export type Willingness = "unknown" | "none" | "low" | "some" | "strong";
export type Commitment = "none" | "verbal" | "pilot" | "signed" | "paid";

export interface Quoted<V extends string = string> {
  value: V;
  quote: string;
}

export interface ResponseClassification {
  sentiment: "positive" | "neutral" | "negative";
  problem_confirmed: Quoted<"yes" | "no" | "unclear">;
  pain: Quoted;
  frequency: Quoted;
  current_solution: Quoted;
  time_or_cost: Quoted;
  severity: Quoted<"high" | "medium" | "low" | "unclear">;
  solution_satisfaction: Quoted<"high" | "medium" | "low" | "unclear">;
  interest: Quoted<"high" | "medium" | "low" | "unclear">;
  willingness_to_pay: Quoted<Willingness>;
  recommended_action: { value: "interview" | "follow_up" | "close" | "none"; reason: string };
}

export interface ReplySummary {
  id: string;
  idea_id: string;
  message_id: string | null;
  contact_id: string | null;
  company_id: string | null;
  from_name: string;
  from_email: string | null;
  subject: string;
  received_at: string;
  channel: "paste" | "imap";
  status: ResponseStatus;
  opt_out: boolean;
  classification: ResponseClassification | null;
  error: string | null;
  created_at: string;
}

export interface Reply extends ReplySummary {
  raw_text: string;
  dropped: { label: string; quote: string; reason: string }[];
  analyzed_at: string | null;
  company_name: string | null;
  original: {
    id: string;
    campaign_id: string;
    subject: string;
    sent_at: string | null;
    status: MessageStatus;
    body: string;
  } | null;
  evidence_ids: string[];
}

export interface ReplyDashboard {
  sent: number;
  replies: number;
  reply_rate: number | null;
  positive: number;
  neutral: number;
  negative: number;
  opt_outs: number;
  problem_confirmed: number;
  interview_recommended: number;
  interviews_done: number;
  pilot_or_better: number;
  stated_strong: number;
  top_pains: { quote: string; from: string; id: string }[];
  frequencies: { value: string; count: number }[];
  current_solutions: { value: string; count: number }[];
}

export interface InboxStatus {
  enabled: boolean;
  mailbox: string;
  last_poll: {
    at: string;
    seen: number;
    reply: number;
    bounce: number;
    duplicate: number;
    unmatched: number;
    errors: number;
    error: string | null;
  } | null;
}

export type InterviewStatus = "planned" | "done" | "cancelled";
export type JobState = "none" | "queued" | "running" | "done" | "failed";

export interface GuideQuestion {
  unknown_id: string;
  unknown: string;
  question: string;
  follow_ups: string[];
  flags: string[];
  follow_up_flags: string[][];
}

export interface InterviewGuide {
  known: Claim[];
  questions: GuideQuestion[];
  uncovered?: { unknown_id: string; unknown: string }[];
  skipped?: number;
  note?: string;
}

export interface AnsweredProposal {
  unknown_id: string;
  unknown: string;
  answer: string;
  quote: string;
  evidence_id: string;
  confirmed: boolean;
}

export interface InterviewExtraction {
  problem: Quoted;
  workflow: Quoted;
  frequency: Quoted;
  cost: Quoted;
  alternatives: Quoted;
  trigger: Quoted;
  buyer: Quoted;
  decision_process: Quoted;
  objections: Quoted;
  desired_solution: Quoted;
  willingness_to_pay: Quoted<Willingness>;
  answered_unknowns: AnsweredProposal[];
}

export interface InterviewSummary {
  id: string;
  idea_id: string;
  contact_id: string | null;
  company_id: string | null;
  response_id: string | null;
  interviewee_name: string;
  interviewee_role: string;
  company_name: string;
  scheduled_at: string | null;
  status: InterviewStatus;
  guide_state: JobState;
  extraction_state: JobState;
  created_at: string;
  updated_at: string;
}

export interface InterviewNote {
  id: string;
  kind: "live" | "post";
  text: string;
  created_at: string;
}

export interface Interview extends InterviewSummary {
  scheduling_note: string;
  guide: InterviewGuide | null;
  extraction: InterviewExtraction | null;
  dropped: { label: string; quote: string; reason: string }[];
  error: string | null;
  notes: InterviewNote[];
  evidence_ids: string[];
}

export interface InterviewInput {
  contact_id?: string | null;
  response_id?: string | null;
  interviewee_name?: string;
  interviewee_role?: string;
  company_name?: string;
  scheduled_at?: string | null;
  scheduling_note?: string;
}

export type InterviewPatch = Partial<
  Pick<
    Interview,
    "interviewee_name" | "interviewee_role" | "company_name" | "scheduled_at" | "status" | "scheduling_note"
  >
>;

export interface WtpSignal {
  id: string;
  idea_id: string;
  contact_id: string | null;
  company_id: string | null;
  response_id: string | null;
  interview_id: string | null;
  customer_label: string;
  current_spend: string;
  problem_cost: string;
  expected_price: string;
  stated_willingness: Willingness;
  stated_quote: string;
  stated_evidence_id: string | null;
  commitment: Commitment;
  commitment_note: string;
  committed_at: string | null;
  source: "user" | "ai";
  created_at: string;
  updated_at: string;
}

export type WtpInput = Partial<
  Pick<
    WtpSignal,
    | "customer_label"
    | "contact_id"
    | "current_spend"
    | "problem_cost"
    | "expected_price"
    | "stated_willingness"
    | "stated_quote"
    | "commitment"
    | "commitment_note"
    | "committed_at"
  >
>;

export interface ReplyPaste {
  text: string;
  message_id?: string | null;
  contact_id?: string | null;
  from_name?: string;
  from_email?: string | null;
}

// ---------- validation & decision (Phase 4) ----------

export type Recommendation = "build" | "iterate" | "investigate" | "abandon";

export interface ScoreDimension {
  key: string;
  label: string;
  points: number;
  max: number;
  reason: string;
  evidence_ids: string[];
  record_ids: string[]; // "wtp:…", "competitor:…", "interview:…"
  gaps: string[];
}

export interface DecisionPoint {
  text: string;
  evidence_ids: string[];
  record_ids: string[];
}

export interface ValidationScore {
  id: string;
  idea_id: string;
  total: number;
  dimensions: ScoreDimension[];
  state: ValidationState;
  recommendation: Recommendation;
  decision: {
    recommendation: Recommendation;
    headline: string;
    why: string;
    strong: DecisionPoint[];
    weak: DecisionPoint[];
    uncertainty: string;
    next_actions: string[];
  };
  metrics: {
    validated_conversations: number;
    response_rate: number | null;
    problem_confirmation_rate: number | null;
    interview_conversion: number | null;
    commercial_validation: number | null;
  };
  facts: Record<string, number>;
  inputs_hash: string;
  scoring_version: number;
  created_at: string;
}

export interface ScoreStatus {
  score: ValidationScore | null;
  stale: boolean;
}

export interface Cohort {
  label: string;
  campaign_ids: string[];
  icp_id: string | null;
  role_contains: string;
}

export interface CohortResult {
  label: string;
  sent: number;
  replies: number;
  reply_rate: number | null;
  positive: number;
  problem_confirmed: number;
  interview_recommended: number;
  interviews_done: number;
  small_sample: boolean;
}

export interface Experiment {
  id: string;
  idea_id: string;
  hypothesis: string;
  cohort_a: Cohort;
  cohort_b: Cohort | null;
  status: "running" | "concluded";
  conclusion: string;
  concluded_at: string | null;
  created_at: string;
  result: { a: CohortResult; b: CohortResult | null; comparison: string[]; computed_at: string };
}

export interface ExperimentInput {
  hypothesis: string;
  cohort_a: Cohort;
  cohort_b?: Cohort | null;
}

export type ExperimentPatch = Partial<ExperimentInput> & {
  conclusion?: string;
  status?: "running" | "concluded";
};

export interface ValidationReport {
  id: string;
  idea_id: string;
  validation_score_id: string;
  status: "queued" | "running" | "done" | "failed";
  content: string;
  summary: { statement: string; kind: string; evidence_ids: string[]; evidence_uuids: string[] }[];
  dropped: { statement: string; reason: string }[];
  exhibits: Record<string, string>;
  summary_provider: string | null;
  error: string | null;
  generated_at: string | null;
  created_at: string;
  total: number | null;
  recommendation: Recommendation | null;
}

// ---------- auth & workspaces (Phase 5A) ----------

export type Role = "owner" | "member";

export interface AuthStatus {
  needs_setup: boolean;
  signup_open: boolean;
  signed_in: boolean;
}

export interface Me {
  user: { id: string; email: string; name: string; is_instance_owner: boolean };
  workspaces: { id: string; name: string; role: Role }[];
  active_workspace_id: string | null;
  via: "session" | "token";
}

export interface Member {
  user_id: string;
  name: string;
  email: string;
  role: Role;
  joined_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  expires_at: string;
  created_at: string;
}

export interface InvitationPublic {
  workspace_name: string;
  email: string;
  role: Role;
  expires_at: string;
  account_exists: boolean;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  is_instance_owner: boolean;
  workspaces: string[];
  last_login_at: string | null;
}

export interface ApiTokenRow {
  id: string;
  name: string;
  token_prefix: string;
  workspace_id: string;
  last_used_at: string | null;
  created_at: string;
}

// ---------- privacy (Phase 5B) ----------

export interface PersonSummary {
  email: string | null;
  addresses: string[];
  contacts: {
    id: string;
    idea_id: string;
    idea_title: string;
    name: string;
    role: string;
    company: string;
    email: string | null;
    source_url: string;
    collected_at: string;
  }[];
  messages: number;
  replies: number;
  interviews: number;
  wtp_records: number;
  suppressed: boolean;
  nothing_found: boolean;
}

export interface PrivacyFinding {
  kind: "provenance" | "minimisation" | "retention";
  severity: "high" | "medium" | "low";
  message: string;
  ids: string[];
  contacts?: { id: string; name: string; company: string; idea_id: string }[];
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

// Called when the API says the session is missing or expired (set by the session provider).
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (res.status === 401 && !path.startsWith("/auth/") && onUnauthorized) onUnauthorized();
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
  authStatus: () => request<AuthStatus>("/auth/status"),
  me: () => request<Me>("/auth/me"),
  setup: (data: { email: string; name: string; password: string }) =>
    request<Me>("/auth/setup", json("POST", data)),
  login: (data: { email: string; password: string }) => request<Me>("/auth/login", json("POST", data)),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  switchWorkspace: (workspaceId: string) =>
    request<Me>("/auth/workspace", json("POST", { workspace_id: workspaceId })),
  changePassword: (current: string, next: string) =>
    request<void>("/auth/password", json("POST", { current, new: next })),
  listTokens: () => request<ApiTokenRow[]>("/auth/tokens"),
  createToken: (name: string) =>
    request<ApiTokenRow & { token: string }>("/auth/tokens", json("POST", { name })),
  revokeToken: (tokenId: string) => request<void>(`/auth/tokens/${tokenId}`, { method: "DELETE" }),

  adminUsers: () => request<AdminUser[]>("/admin/users"),
  createResetLink: (userId: string) =>
    request<{ token: string; expires_in_minutes: number }>(`/admin/users/${userId}/reset-link`, {
      method: "POST",
    }),
  resetInfo: (token: string) => request<{ email: string }>(`/password-reset/${token}`),
  useResetLink: (token: string, password: string) =>
    request<void>(`/password-reset/${token}`, json("POST", { password })),

  createWorkspace: (name: string) =>
    request<{ id: string; name: string }>("/workspaces", json("POST", { name })),
  renameWorkspace: (workspaceId: string, name: string) =>
    request<{ id: string; name: string }>(`/workspaces/${workspaceId}`, json("PATCH", { name })),
  listMembers: (workspaceId: string) => request<Member[]>(`/workspaces/${workspaceId}/members`),
  setMemberRole: (workspaceId: string, userId: string, role: Role) =>
    request<void>(`/workspaces/${workspaceId}/members/${userId}`, json("PATCH", { role })),
  removeMember: (workspaceId: string, userId: string) =>
    request<void>(`/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" }),
  listInvitations: (workspaceId: string) => request<Invitation[]>(`/workspaces/${workspaceId}/invitations`),
  invite: (workspaceId: string, email: string, role: Role) =>
    request<Invitation & { token: string }>(
      `/workspaces/${workspaceId}/invitations`,
      json("POST", { email, role }),
    ),
  revokeInvitation: (workspaceId: string, invitationId: string) =>
    request<void>(`/workspaces/${workspaceId}/invitations/${invitationId}`, { method: "DELETE" }),
  getInvitation: (token: string) => request<InvitationPublic>(`/invitations/${token}`),
  acceptInvitation: (token: string) => request<Me>(`/invitations/${token}/accept`, { method: "POST" }),
  signupWithInvitation: (token: string, data: { name: string; password: string }) =>
    request<Me>(`/invitations/${token}/signup`, json("POST", data)),

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
  listReplies: (ideaId: string) => request<ReplySummary[]>(`/ideas/${ideaId}/responses`),
  replyDashboard: (ideaId: string) => request<ReplyDashboard>(`/ideas/${ideaId}/responses/dashboard`),
  getReply: (ideaId: string, replyId: string) => request<Reply>(`/ideas/${ideaId}/responses/${replyId}`),
  pasteReply: (ideaId: string, data: ReplyPaste) =>
    request<Reply>(`/ideas/${ideaId}/responses`, json("POST", data)),
  reanalyzeReply: (ideaId: string, replyId: string) =>
    request<Reply>(`/ideas/${ideaId}/responses/${replyId}/reanalyze`, { method: "POST" }),
  deleteReply: (ideaId: string, replyId: string) =>
    request<void>(`/ideas/${ideaId}/responses/${replyId}`, { method: "DELETE" }),
  inboxStatus: () => request<InboxStatus>("/outreach/inbox"),
  checkInbox: () => request<{ queued: boolean }>("/outreach/inbox/check", { method: "POST" }),

  listInterviews: (ideaId: string) => request<InterviewSummary[]>(`/ideas/${ideaId}/interviews`),
  getInterview: (ideaId: string, interviewId: string) =>
    request<Interview>(`/ideas/${ideaId}/interviews/${interviewId}`),
  createInterview: (ideaId: string, data: InterviewInput) =>
    request<Interview>(`/ideas/${ideaId}/interviews`, json("POST", data)),
  updateInterview: (ideaId: string, interviewId: string, data: InterviewPatch) =>
    request<Interview>(`/ideas/${ideaId}/interviews/${interviewId}`, json("PATCH", data)),
  deleteInterview: (ideaId: string, interviewId: string) =>
    request<void>(`/ideas/${ideaId}/interviews/${interviewId}`, { method: "DELETE" }),
  addInterviewNote: (ideaId: string, interviewId: string, data: { text: string; kind: "live" | "post" }) =>
    request<Interview>(`/ideas/${ideaId}/interviews/${interviewId}/notes`, json("POST", data)),
  deleteInterviewNote: (ideaId: string, interviewId: string, noteId: string) =>
    request<Interview>(`/ideas/${ideaId}/interviews/${interviewId}/notes/${noteId}`, { method: "DELETE" }),
  generateGuide: (ideaId: string, interviewId: string) =>
    request<Interview>(`/ideas/${ideaId}/interviews/${interviewId}/guide`, { method: "POST" }),
  extractInterview: (ideaId: string, interviewId: string) =>
    request<Interview>(`/ideas/${ideaId}/interviews/${interviewId}/extract`, { method: "POST" }),
  confirmAnswered: (ideaId: string, interviewId: string, unknownId: string) =>
    request<Interview>(`/ideas/${ideaId}/interviews/${interviewId}/unknowns/${unknownId}/confirm`, {
      method: "POST",
    }),

  listWtp: (ideaId: string) => request<WtpSignal[]>(`/ideas/${ideaId}/wtp`),
  createWtp: (ideaId: string, data: WtpInput) => request<WtpSignal>(`/ideas/${ideaId}/wtp`, json("POST", data)),
  updateWtp: (ideaId: string, wtpId: string, data: WtpInput) =>
    request<WtpSignal>(`/ideas/${ideaId}/wtp/${wtpId}`, json("PATCH", data)),
  deleteWtp: (ideaId: string, wtpId: string) => request<void>(`/ideas/${ideaId}/wtp/${wtpId}`, { method: "DELETE" }),

  getScore: (ideaId: string) => request<ScoreStatus>(`/ideas/${ideaId}/score`),
  getResearchScore: (ideaId: string) => request<ResearchScore>(`/ideas/${ideaId}/research-score`),
  recomputeScore: (ideaId: string) => request<ValidationScore>(`/ideas/${ideaId}/score`, { method: "POST" }),

  listExperiments: (ideaId: string) => request<Experiment[]>(`/ideas/${ideaId}/experiments`),
  createExperiment: (ideaId: string, data: ExperimentInput) =>
    request<Experiment>(`/ideas/${ideaId}/experiments`, json("POST", data)),
  updateExperiment: (ideaId: string, experimentId: string, data: ExperimentPatch) =>
    request<Experiment>(`/ideas/${ideaId}/experiments/${experimentId}`, json("PATCH", data)),
  deleteExperiment: (ideaId: string, experimentId: string) =>
    request<void>(`/ideas/${ideaId}/experiments/${experimentId}`, { method: "DELETE" }),

  listReports: (ideaId: string) => request<ValidationReport[]>(`/ideas/${ideaId}/reports`),
  createReport: (ideaId: string) => request<ValidationReport>(`/ideas/${ideaId}/reports`, { method: "POST" }),
  getReport: (reportId: string) => request<ValidationReport>(`/reports/${reportId}`),
  deleteReport: (reportId: string) => request<void>(`/reports/${reportId}`, { method: "DELETE" }),
  reportMarkdownUrl: (reportId: string) => `${API_URL}/reports/${reportId}/markdown`,

  findPerson: (email: string) =>
    request<PersonSummary>(`/privacy/people?email=${encodeURIComponent(email)}`),
  personExportUrl: (email: string) => `${API_URL}/privacy/people/export?email=${encodeURIComponent(email)}`,
  erasePerson: (email: string) =>
    request<Record<string, number>>("/privacy/people/erase", json("POST", { email })),
  privacyCheck: () => request<{ findings: PrivacyFinding[]; ok: boolean }>("/privacy/check"),
};
