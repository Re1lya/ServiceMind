import { defineStore } from "pinia";

import { fetchHealth, sendChatMessage } from "@/services/chatApi";
import type { ChatMessage, HealthStatusData } from "@/types/api";

interface ChatState {
  sessionId: string | null;
  userId: string;
  draft: string;
  messages: ChatMessage[];
  health: HealthStatusData | null;
  healthLoading: boolean;
  sending: boolean;
  error: string | null;
}

const initialAssistantMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "你好，我是 ServiceMind。可以直接问退款规则，也可以输入订单号或物流单号试试。",
  route: "local_welcome",
  answerSource: "frontend",
  createdAt: new Date().toISOString()
};

function makeMessageId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export const useChatStore = defineStore("chat", {
  state: (): ChatState => ({
    sessionId: null,
    userId: "web_demo_user",
    draft: "",
    messages: [initialAssistantMessage],
    health: null,
    healthLoading: false,
    sending: false,
    error: null
  }),
  getters: {
    healthStatusLabel: (state) => state.health?.status ?? "unknown",
    latestTraceId: (state) => {
      const matched = [...state.messages].reverse().find((message) => message.traceId);
      return matched?.traceId ?? state.health?.trace_id ?? null;
    }
  },
  actions: {
    async checkHealth() {
      this.healthLoading = true;
      this.error = null;
      try {
        this.health = await fetchHealth();
      } catch (error) {
        this.error = error instanceof Error ? error.message : "健康检查请求失败";
      } finally {
        this.healthLoading = false;
      }
    },
    async submitDraft() {
      const content = this.draft.trim();
      if (!content || this.sending) {
        return;
      }

      this.messages.push({
        id: makeMessageId("local_user"),
        role: "user",
        content,
        createdAt: new Date().toISOString()
      });
      this.draft = "";
      this.sending = true;
      this.error = null;

      try {
        const response = await sendChatMessage({
          session_id: this.sessionId,
          user_id: this.userId,
          channel: "web",
          stream: false,
          message: content
        });
        this.sessionId = response.session_id;
        this.messages.push({
          id: response.assistant_message_id,
          role: "assistant",
          content: response.reply,
          route: response.route,
          answerSource: response.answer_source,
          traceId: response.trace_id,
          knowledgeSources: response.knowledge_sources,
          createdAt: new Date().toISOString()
        });
      } catch (error) {
        this.error = error instanceof Error ? error.message : "消息发送失败";
        this.messages.push({
          id: makeMessageId("local_error"),
          role: "assistant",
          content: "前后端联调请求没有成功，请先确认后端服务已经在 8000 端口启动。",
          route: "frontend_error",
          answerSource: "frontend",
          createdAt: new Date().toISOString()
        });
      } finally {
        this.sending = false;
      }
    },
    resetSession() {
      this.sessionId = null;
      this.draft = "";
      this.error = null;
      this.messages = [{ ...initialAssistantMessage, createdAt: new Date().toISOString() }];
    }
  }
});
