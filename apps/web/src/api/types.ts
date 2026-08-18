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

export interface CsrfTokenResponse {
  token: string;
  headerName: string;
  parameterName: string;
}

export interface AuthUser {
  id: number | string;
  phoneNumber: string;
  userName: string;
  avatarUrl?: string;
  roles?: string[];
}

export interface Workspace {
  id: number | string;
  name: string;
  code?: string;
  description?: string;
  plan?: string;
  initials?: string;
  [key: string]: unknown;
}

export interface WorkspaceMember {
  id: number | string;
  userId?: number | string;
  userName?: string;
  phoneNumber?: string;
  role?: string;
  status?: string;
  [key: string]: unknown;
}

export interface Project {
  id: number | string;
  name: string;
  code?: string;
  description?: string;
  [key: string]: unknown;
}

export type AssetParseStatus =
  | "PENDING"
  | "PROCESSING"
  | "SUCCESS"
  | "FAILED"
  | string;
export type AssetIndexStatus =
  | "PENDING"
  | "INDEXING"
  | "SUCCESS"
  | "FAILED"
  | string;

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

export interface CreateRunPayload {
  goal: string;
  allowWebSearch?: boolean;
  maxResearchRounds?: number;
  reportTemplate?: string;
  outputLanguage?: string;
  [key: string]: unknown;
}

export type RunStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | string;

export interface ResearchRun {
  id?: number | string;
  runId: number | string;
  runNo: string;
  status: RunStatus;
  currentNode?: string;
  progress?: number;
  finalSummary?: string;
  eventsUrl?: string;
  [key: string]: unknown;
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
  versionNo?: number;
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
