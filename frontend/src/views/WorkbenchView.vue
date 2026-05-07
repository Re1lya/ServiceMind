<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { Bot, HeartPulse, RotateCcw, Send, Sparkles, Wifi } from "lucide-vue-next";

import { useChatStore } from "@/stores/chat";

const chat = useChatStore();
const messageList = ref<HTMLElement | null>(null);

const componentEntries = computed<[string, string][]>(() => Object.entries(chat.health?.components ?? {}));

async function scrollToBottom() {
  await nextTick();
  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight;
  }
}

function submitOnEnter(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void chat.submitDraft();
  }
}

watch(
  () => chat.messages.length,
  () => void scrollToBottom()
);

onMounted(() => {
  void chat.checkHealth();
  void scrollToBottom();
});
</script>

<template>
  <main class="shell">
    <aside class="sidebar" aria-label="ServiceMind runtime status">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">
          <Bot :size="24" />
        </div>
        <div>
          <p class="eyebrow">ServiceMind</p>
          <h1>客服工作台</h1>
        </div>
      </div>

      <section class="status-panel" aria-label="Backend status">
        <div class="section-title">
          <HeartPulse :size="18" />
          <span>联调状态</span>
        </div>
        <div class="status-line">
          <span :class="['status-dot', chat.healthStatusLabel]"></span>
          <strong>{{ chat.healthStatusLabel }}</strong>
        </div>
        <dl class="status-list">
          <template v-for="[name, value] in componentEntries" :key="name">
            <dt>{{ name }}</dt>
            <dd :class="value">{{ value }}</dd>
          </template>
        </dl>
        <button class="secondary-action" type="button" :disabled="chat.healthLoading" @click="chat.checkHealth">
          <Wifi :size="16" />
          <span>{{ chat.healthLoading ? "检查中" : "重新检查" }}</span>
        </button>
      </section>

      <section class="status-panel" aria-label="Session information">
        <div class="section-title">
          <Sparkles :size="18" />
          <span>会话信息</span>
        </div>
        <dl class="meta-list">
          <dt>session</dt>
          <dd>{{ chat.sessionId ?? "待创建" }}</dd>
          <dt>trace</dt>
          <dd>{{ chat.latestTraceId ?? "等待请求" }}</dd>
        </dl>
        <button class="secondary-action" type="button" @click="chat.resetSession">
          <RotateCcw :size="16" />
          <span>新会话</span>
        </button>
      </section>
    </aside>

    <section class="workspace" aria-label="Chat workspace">
      <header class="workspace-header">
        <div>
          <p class="eyebrow">MVP validation</p>
          <h2>前后端联调工作台</h2>
        </div>
        <div class="quick-prompts" aria-label="Sample prompts">
          <button type="button" @click="chat.draft = '请问退款规则是什么？'">退款规则</button>
          <button type="button" @click="chat.draft = '帮我查一下订单 ORD2026043001 的状态'">订单查询</button>
          <button type="button" @click="chat.draft = '帮我查一下物流 SF2026043001 到哪了'">物流查询</button>
        </div>
      </header>

      <div ref="messageList" class="message-list" aria-live="polite">
        <article
          v-for="message in chat.messages"
          :key="message.id"
          :class="['message', message.role]"
        >
          <div class="message-body">{{ message.content }}</div>
          <footer v-if="message.role === 'assistant'" class="message-meta">
            <span>{{ message.route ?? "assistant" }}</span>
            <span>{{ message.answerSource ?? "runtime" }}</span>
          </footer>
          <div v-if="message.knowledgeSources?.length" class="source-list">
            <article v-for="source in message.knowledgeSources" :key="source.document_id" class="source-item">
              <header>
                <strong>{{ source.title }}</strong>
                <span>{{ source.source_type }} · {{ source.score.toFixed(1) }}</span>
              </header>
              <p>{{ source.snippet }}</p>
            </article>
          </div>
        </article>

        <article v-if="chat.sending" class="message assistant pending">
          <div class="message-body">正在请求后端...</div>
        </article>
      </div>

      <p v-if="chat.error" class="error-banner">{{ chat.error }}</p>

      <form class="composer" @submit.prevent="chat.submitDraft">
        <textarea
          v-model="chat.draft"
          rows="2"
          placeholder="输入客服问题、订单号或物流单号"
          :disabled="chat.sending"
          @keydown="submitOnEnter"
        ></textarea>
        <button class="send-button" type="submit" :disabled="chat.sending || !chat.draft.trim()">
          <Send :size="18" />
          <span>{{ chat.sending ? "发送中" : "发送" }}</span>
        </button>
      </form>
    </section>
  </main>
</template>
