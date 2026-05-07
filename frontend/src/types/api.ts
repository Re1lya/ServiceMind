export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
}

export interface HealthStatusData {
  app_name: string;
  app_env: string;
  status: string;
  trace_id: string | null;
  components: Record<string, string>;
}

export interface ChatRequest {
  session_id?: string | null;
  user_id?: string | null;
  channel: string;
  stream: boolean;
  message: string;
}

export interface ChatResponseData {
  session_id: string;
  reply: string;
  route: string;
  answer_source: string;
  trace_id: string | null;
  user_message_id: string;
  assistant_message_id: string;
  knowledge_sources: KnowledgeSource[];
}

export interface KnowledgeSource {
  document_id: string;
  title: string;
  source_type: string;
  source_path: string | null;
  score: number;
  snippet: string;
}

export type ChatRole = "assistant" | "user" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  route?: string;
  answerSource?: string;
  traceId?: string | null;
  knowledgeSources?: KnowledgeSource[];
  createdAt: string;
}
