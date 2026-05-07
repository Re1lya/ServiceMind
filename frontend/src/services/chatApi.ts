import { http } from "@/services/http";
import type { ApiResponse, ChatRequest, ChatResponseData, HealthStatusData } from "@/types/api";

export async function fetchHealth(): Promise<HealthStatusData> {
  const response = await http.get<ApiResponse<HealthStatusData>>("/health");
  if (!response.data.data) {
    throw new Error(response.data.message || "health response is empty");
  }
  return response.data.data;
}

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponseData> {
  const response = await http.post<ApiResponse<ChatResponseData>>("/chat/", payload);
  if (!response.data.data) {
    throw new Error(response.data.message || "chat response is empty");
  }
  return response.data.data;
}
