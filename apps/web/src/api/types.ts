export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T;
}

export interface PageResponse<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface CaptchaPayload {
  captchaId: string;
  imgUrl: string;
}

export interface LoginByPasswordPayload {
  phoneNumber: string;
  password: string;
  captcha: string;
  captchaId: string;
}

export interface LoginBySmsPayload {
  phoneNumber: string;
  verifyCode: string;
  verifyCodeId: string;
  captcha: string;
  captchaId: string;
}

export interface RegisterPayload {
  phoneNumber: string;
  userName: string;
  password: string;
  captchaId: string;
  captcha: string;
  verifyCodeId: string;
  verifyCode: string;
}

export interface ResetPasswordPayload {
  phoneNumber: string;
  verifyCodeId: string;
  verifyCode: string;
  newPassword: string;
}

export interface LoginResponse {
  id: number | string | null;
  phoneNumber: string;
  userName?: string | null;
}

export interface RegisterResponse {
  info: string;
}

export interface SmsResponse {
  smsId: string;
}

export type SmsPurpose =
  | "REGISTER"
  | "LOGIN"
  | "PASSWORD_CHANGE"
  | "PHONE_CHANGE"
  | "PASSWORD_RESET";

export interface CsrfTokenResponse {
  token: string;
  headerName: string;
  parameterName: string;
}

export interface AuthUser {
  id: number | string;
  phoneNumber: string;
  userName: string;
  roles?: string[];
  email?: string | null;
  timezone?: string;
  notificationPreferences?: string;
}

export interface NotificationRecord {
  id: number | string;
  workspaceId: number | string;
  projectId?: number | string | null;
  kind: string;
  title: string;
  body: string;
  routeName?: string | null;
  read: boolean;
  createdAt: string;
}

export interface Workspace {
  id: number | string;
  name: string;
  code?: string;
  currentRole?: string;
  description?: string;
  plan?: string;
  initials?: string;
  preferences?: string;
  [key: string]: unknown;
}

export interface WorkspaceMember {
  id: number | string;
  userId?: number | string;
  userName?: string;
  phoneNumber?: string;
  role?: string;
  createdAt: string;
  status?: string;
  department?: string;
  title?: string;
  lastActiveAt?: string;
  [key: string]: unknown;
}

export interface WorkspaceInvitation {
  id: number | string;
  workspaceId: number | string;
  workspaceName?: string;
  phoneNumber: string;
  role: string;
  department?: string;
  title?: string;
  inviteNote?: string;
  invitedBy?: number | string;
  status: string;
  expiresAt: string;
  createdAt: string;
}

export interface Project {
  id: number;
  name: string;
  code?: string;
  description?: string;
  color?: string;
  chunkingConfig?: ChunkingConfig | string;
  [key: string]: unknown;
}

export interface ChunkingConfig {
  strategy: "natural" | "paragraph" | "fixed" | string;
  chunkSize: number;
  chunkOverlap: number;
  preserveSections: boolean;
}

export interface ProjectPlan {
  projectId: number | string;
  workspaceId: number | string;
  objective: string;
  problem?: string;
  successMetrics?: string;
  constraints?: string;
  owner?: string;
  deadline?: string | null;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface ProjectReviewPolicy {
  projectId: number | string;
  workspaceId: number | string;
  requireCitations: boolean;
  verifyNumbers: boolean;
  escalateConflicts: boolean;
  labelExternal: boolean;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface ProjectReviewRun {
  id: number | string;
  projectId: number | string;
  workspaceId: number | string;
  status: string;
  blockedCount: number;
  reviewCount: number;
  indexedAssetCount: number;
  assetCount: number;
  researchRunCount: number;
  reportCount: number;
  evaluationCaseCount: number;
  actionItemCount: number;
  detail: string;
  createdAt?: string;
  [key: string]: unknown;
}

export type AssetParseStatus =
  "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED" | string;
export type AssetIndexStatus =
  "PENDING" | "INDEXING" | "SUCCESS" | "FAILED" | string;

export interface KnowledgeAsset {
  id: number | string;
  name: string;
  assetType: string;
  mimeType?: string;
  language?: string;
  fileSize?: number;
  parseStatus: AssetParseStatus;
  indexStatus: AssetIndexStatus;
  chunkCount: number;
  errorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface KnowledgeSearchPayload {
  query: string;
  topK?: number;
  retrievalMode?: "VECTOR" | "KEYWORD" | "HYBRID" | string;
  useReranker?: boolean;
  filters?: {
    assetIds?: Array<number | string>;
    [key: string]: unknown;
  };
}

export interface KnowledgeSearchItem {
  chunkId: number | string;
  assetId: number | string;
  assetName: string;
  pageNumber?: number;
  sectionTitle?: string;
  content: string;
  vectorScore?: number;
  keywordScore?: number;
  fusionScore?: number;
  rerankScore?: number;
  [key: string]: unknown;
}

export interface KnowledgeSearchResponse {
  query: string;
  rewrittenQueries: string[];
  items: KnowledgeSearchItem[];
}

export interface KnowledgeAnswerPayload {
  question: string;
  topK?: number;
  answerLanguage?: string;
}

export interface KnowledgeAnswerResponse {
  answer: string;
  citations: Array<{
    evidenceId: string;
    chunkId: number | string;
    assetName: string;
    pageNumber?: number;
    quote: string;
  }>;
  insufficientEvidence: boolean;
}

export type AgentMessageRole = "user" | "assistant";

export type AgentEventKind =
    "chat" | "plan" | "search" | "tool" | "file" | "evidence" | "synthesis" | "reflection";

export type AgentEventStatus = "pending" | "running" | "completed" | "failed";

export interface AgentCitation {
  id: string;
  title: string;
  source: string;
  quote: string;
  content?: string;
  sourceType?: "internal" | "graph" | "web" | string;
  assetId?: number | string;
  chunkId?: number | string;
  score?: string;
  pageNumber?: number;
  url?: string;
  contentKind?: "fulltext" | "abstract" | "search_snippet" | string;
}

export type AgentAttachmentKind =
  | "image"
  | "video"
  | "audio"
  | "pdf"
  | "document"
  | "spreadsheet"
  | "presentation"
  | "file";

export interface AgentAttachment {
  id: string;
  name: string;
  kind: AgentAttachmentKind;
  mimeType: string;
  size?: string;
  url?: string;
  previewUrl?: string;
  uploadId?: string | number;
  /** 浏览器待上传文件，仅用于前端状态，不会发送给后端。 */
  file?: File;
  generated?: boolean;
}

export interface AgentAttachmentUploadResponse {
  uploadId: string | number;
  name: string;
  kind: AgentAttachmentKind;
  mimeType: string;
  size: number;
  url: string;
}

export interface AgentMedia {
  id: string;
  kind: "image" | "video";
  name: string;
  mimeType?: string;
  url: string;
  uploadId?: string | number;
}

export interface AgentMessage {
  id: string;
  role: AgentMessageRole;
  content: string;
  createdAt: string;
  status?: "streaming" | "completed" | "failed";
  citations?: AgentCitation[];
  attachments?: AgentAttachment[];
  media?: AgentMedia[];
}

export interface AgentEvent {
  id: string;
  kind: AgentEventKind;
  title: string;
  detail: string;
  status: AgentEventStatus;
  startedAt?: string;
  completedAt?: string;
  duration?: string;
  meta?: Record<string, unknown>;
}

export interface AgentThreadSummary {
  id: string;
  title: string;
  preview: string;
  updatedAt: string;
  messageCount: number;
}

export interface AgentThreadHistory extends AgentThreadSummary {
  messages: AgentMessage[];
  events?: AgentEvent[];
  eventHistory?: AgentEvent[];
  citations?: AgentCitation[];
  tokenUsage?: TokenUsage;
  contextUsage?: ContextCompression;
  status?: "idle" | "running" | "completed" | "failed" | string;
  runId?: string | null;
  runStartedAt?: string;
  runFinishedAt?: string;
  runDurationMs?: number;
}

export interface AgentSendMessagePayload {
  threadId: string;
  messageId: string;
  content: string;
  context?: {
    assetIds?: Array<number | string>;
    runId?: number | string;
    mode?: string;
  };
  config?: AgentRunConfig;
  attachments?: Array<
    Pick<
      AgentAttachment,
      "id" | "name" | "kind" | "mimeType" | "size" | "uploadId"
    >
  >;
  contextMessages?: Array<Pick<AgentMessage, "role" | "content">>;
}

export interface AgentRunConfig {
  allowWebSearch?: boolean;
  reflectionEnabled?: boolean;
  strategy?: "AUTO" | "REACT" | "PLAN_AND_SOLVE" | "REFLECTION";
  multiAgentMode?: "AUTO" | "ON" | "OFF";
  maxResearchRounds?: number;
  topK?: number;
  retrievalMode?: "VECTOR" | "KEYWORD" | "HYBRID";
  useReranker?: boolean;
  outputLanguage?: string;
  temperature?: number;
  topP?: number;
  modelTopK?: number | null;
  maxTokens?: number;
  frequencyPenalty?: number;
  reasoningEffort?: "none" | "low" | "medium" | "high";
  modelConfigId?: number | string;
}

export interface AgentRunAccepted {
  runId: number | string;
  messageId: number | string;
  status: string;
  eventsUrl?: string;
}

export interface AgentRunMetrics {
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
  latencyMs?: number;
  usage?: TokenUsage;
  contextCompression?: ContextCompression;
  multiAgent?: {
    enabled?: boolean;
    requested?: boolean;
    fallback?: boolean;
    reason?: string;
  };
  delta?: boolean;
}

export type AgentStreamEvent = { eventId?: string } & (
  | { type: "run.started"; runId: string; startedAt?: string; data?: AgentRunMetrics }
  | { type: "event.updated"; runId: string; event: AgentEvent }
  | { type: "message.delta"; runId: string; messageId: string; delta: string }
  | { type: "message.replace"; runId: string; messageId: string; content: string }
  | { type: "citation.added"; runId: string; citation: AgentCitation }
  | { type: "media.added"; runId: string; messageId: string; media: AgentMedia }
  | { type: "artifact.added"; runId: string; messageId: string; artifact: AgentAttachment }
  | { type: "message.completed"; runId: string; messageId: string }
  | { type: "usage.updated"; runId: string; usage?: TokenUsage; latencyMs?: number; delta?: boolean }
  | { type: "run.completed"; runId: string; data?: AgentRunMetrics; startedAt?: string; finishedAt?: string; durationMs?: number; usage?: TokenUsage; contextCompression?: ContextCompression }
  | { type: "run.failed"; runId: string; message: string; startedAt?: string; durationMs?: number });

export type RunStatus =
  "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | string;

export type AgentQueueStatus =
  "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";

export type AgentQueuePriority = "low" | "normal" | "high";

export interface AgentQueueTask {
  id: string;
  runId?: number | string;
  projectId: number | string;
  projectName: string;
  title: string;
  source: "agent-chat" | "research";
  status: AgentQueueStatus;
  priority: AgentQueuePriority;
  progress: number;
  currentStep: string;
  time: string;
  duration: string;
  tokens: string;
  threadId?: string;
  errorMessage?: string;
}

export interface ResearchRun {
  id?: number | string;
  runId: number | string;
  runNo: string;
  status: RunStatus;
  currentNode?: string;
  progress?: number;
  currentStep?: string;
  durationSeconds?: number;
  tokenCount?: number;
  finalSummary?: string;
  eventsUrl?: string;
  [key: string]: unknown;
}

export interface ResearchPlanStep {
  id: string;
  objective: string;
  action: "SEARCH_INTERNAL" | "SEARCH_GRAPH" | "SEARCH_WEB" | "SYNTHESIZE";
  query?: string;
}

export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  model?: string;
  available?: boolean;
  estimated?: boolean;
}

export interface ContextCompression {
  providedContextMessages?: number;
  selectedContextMessages?: number;
  filteredMessages?: number;
  modelContextWindow?: number;
  contextTokenBudget?: number;
  compressionTriggered?: number;
  originalChars?: number;
  finalChars?: number;
  compressedMessages?: number;
  originalTokenEstimate?: number;
  finalTokenEstimate?: number;
  finalMessageCount?: number;
  compressedContextTokens?: number;
}

export interface TokenUsageSummary {
  totalTokens: number;
  inputTokens: number;
  outputTokens: number;
  compressedContextTokens: number;
  runCount: number;
}

export interface TokenUsageTrendPoint {
  date: string;
  tokens: number;
  runs: number;
}

export interface TokenUsageUser {
  userId: number | string;
  userName: string;
  totalTokens: number;
  runCount: number;
}

export interface TokenUsageBreakdown {
  projectId: number | string;
  projectName: string;
  userId: number | string;
  userName: string;
  modelName: string;
  totalTokens: number;
  inputTokens: number;
  outputTokens: number;
  runCount: number;
}

export interface RunEvent<T = Record<string, unknown>> {
  eventId?: string;
  runId: number | string;
  timestamp?: string;
  data?: T;
  [key: string]: unknown;
}

export interface Report {
  id: number | string;
  title: string;
  reportType?: string;
  status: string;
  versionNo?: number | string;
  lead?: string;
  summary?: string;
  recommendation?: string;
  recommendationDetail?: string;
  markdownContent?: string;
  citations?: number;
  createdAt?: string;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface ActionItem {
  id: number | string;
  title: string;
  description?: string;
  priority: string;
  status: string;
  ownerId?: number | string;
  dueAt?: string;
  [key: string]: unknown;
}

export interface EvaluationRun {
  id: number | string;
  status: string;
  metrics?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface StatisticsSummary {
  projectCount: number;
  activeProjectCount: number;
  assetCount: number;
  indexedAssetCount: number;
  failedAssetCount: number;
  chunkCount: number;
  runCount: number;
  queuedRunCount: number;
  runningRunCount: number;
  completedRunCount: number;
  failedRunCount: number;
  cancelledRunCount: number;
  reportCount: number;
  publishedReportCount: number;
  actionItemCount: number;
  openActionItemCount: number;
  overdueActionItemCount: number;
  evaluationCaseCount: number;
  avgRecall?: number | null;
  avgCitation?: number | null;
  avgJsonScore?: number | null;
  unreadNotificationCount: number;
}

export interface StatisticsTrendPoint {
  date: string;
  assets: number;
  runs: number;
  reports: number;
  actionItems: number;
  recall?: number | null;
  citation?: number | null;
  jsonScore?: number | null;
}

export interface StatisticsBreakdown {
  status: string;
  count: number;
}

export interface StatisticsResponse {
  summary: StatisticsSummary;
  dailyTrend: StatisticsTrendPoint[];
  runStatuses: StatisticsBreakdown[];
  assetStatuses: StatisticsBreakdown[];
  actionItemStatuses: StatisticsBreakdown[];
  tokenUsage?: TokenUsageSummary;
  tokenDaily?: TokenUsageTrendPoint[];
  tokenUsers?: TokenUsageUser[];
  tokenBreakdown?: TokenUsageBreakdown[];
}
