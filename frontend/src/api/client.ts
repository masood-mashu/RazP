import type {
  DashboardStats,
  SystemStatus,
  PaymentCase,
  LedgerResponse,
  MerchantPolicy,
  SingleEvalRequest,
  SingleEvalResponse,
  BenchmarkSummary
} from './types';

const BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || '/api';

export class ApiError extends Error {
  status: number;
  data: any;
  correlationId?: string;
  constructor(message: string, status: number, data?: any, correlationId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
    this.correlationId = correlationId;
  }
}

// Token & Role Store
const TOKEN_KEY = 'razp_auth_token';
export const DEFAULT_DEMO_ADMIN_KEY = 'razp_master_admin_demo';

export function getAuthToken(): string {
  const stored = localStorage.getItem(TOKEN_KEY);
  if (stored) return stored.trim();
  // Allow demo fallback only when explicitly enabled or in local development
  const allowDemo = (import.meta as any).env?.VITE_ALLOW_DEMO_KEYS === 'true' || (import.meta as any).env?.DEV;
  if (allowDemo) {
    return DEFAULT_DEMO_ADMIN_KEY;
  }
  return '';
}

export function setAuthToken(token: string) {
  if (!token || !token.trim()) {
    localStorage.removeItem(TOKEN_KEY);
  } else {
    localStorage.setItem(TOKEN_KEY, token.trim());
  }
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getAuthToken());
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  const token = getAuthToken();

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': token,
        'Authorization': `Bearer ${token}`,
        ...options.headers,
      },
    });

    clearTimeout(timeoutId);
    const correlationId = response.headers.get('X-Correlation-ID') || undefined;

    if (!response.ok) {
      let errData: any;
      try {
        errData = await response.json();
      } catch {
        errData = await response.text();
      }

      let errorMsg = `HTTP ${response.status}`;
      if (typeof errData === 'object' && errData !== null) {
        if (errData.detail) errorMsg = errData.detail;
        else if (errData.error?.message) errorMsg = errData.error.message;
      } else if (typeof errData === 'string') {
        errorMsg = errData;
      }

      if (response.status === 401) {
        errorMsg = `[401 Unauthenticated] ${errorMsg}. Check your API Key.`;
      } else if (response.status === 403) {
        errorMsg = `[403 Forbidden] ${errorMsg}`;
      } else if (response.status === 429) {
        errorMsg = `[429 Rate Limit Exceeded] ${errorMsg}`;
      } else if (response.status === 503) {
        errorMsg = `[503 Service Unavailable] Database or downstream service unavailable.`;
      }

      throw new ApiError(errorMsg, response.status, errData, correlationId);
    }

    return await response.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out after 20s', 408);
    }
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err.message || 'Network connection failed', 0);
  }
}

export const api = {
  // System & Health
  getHealth: () => request<{ status: string; service: string; persistence: string }>('/health'),
  getSystemStatus: () => request<SystemStatus>('/system/status'),

  // Dashboard & Cases
  getDashboardStats: () => request<DashboardStats>('/dashboard/stats'),
  getCases: (params?: { search?: string; status?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.search) query.append('search', params.search);
    if (params?.status) query.append('status', params.status);
    if (params?.limit) query.append('limit', String(params.limit));
    if (params?.offset) query.append('offset', String(params.offset));
    const qs = query.toString();
    return request<{ cases: PaymentCase[]; total: number }>(`/cases${qs ? `?${qs}` : ''}`);
  },
  getCaseDetail: (paymentId: string) => request<PaymentCase>(`/cases/${encodeURIComponent(paymentId)}`),
  getCaseTrace: (paymentId: string) => request<{ payment_id: string; case: any; audit_blocks: any[] }>(`/cases/${encodeURIComponent(paymentId)}/trace`),

  // Evaluation & Single Case Run
  evaluateSingle: (req: SingleEvalRequest) => request<SingleEvalResponse>('/evaluate/single', {
    method: 'POST',
    body: JSON.stringify(req),
  }),

  // Audit Ledger
  getLedger: () => request<LedgerResponse>('/ledger'),
  tamperTestLedger: () => request<any>('/ledger/tamper-test', {
    method: 'POST',
    headers: { 'X-Confirm-Destructive': 'true' }
  }),
  restoreLedger: () => request<any>('/ledger/restore', {
    method: 'POST',
    headers: { 'X-Confirm-Destructive': 'true' }
  }),

  // Policy
  getPolicy: () => request<MerchantPolicy>('/policy'),
  updatePolicy: (policy: Partial<MerchantPolicy>) => request<any>('/policy', {
    method: 'POST',
    body: JSON.stringify(policy),
  }),

  // Benchmark
  getBenchmarkSummary: () => request<BenchmarkSummary>('/benchmark/summary'),
  getBenchmarkCases: () => request<any[]>('/benchmark/cases'),
  runBenchmark: () => request<BenchmarkSummary>('/benchmark/run', { method: 'POST' }),

  // Webhook & Multi-Event Demo
  simulateWebhookReplay: (req: { event_id: string; payment_id: string; amount_inr: number; gateway_error_code: string; bank_raw_response_code: string }) => request<any>('/webhook/simulate-replay', {
    method: 'POST',
    body: JSON.stringify(req),
  }),
  runMultiEventDemo: () => request<any>('/demo/run-multi-event', { method: 'POST' }),
};
