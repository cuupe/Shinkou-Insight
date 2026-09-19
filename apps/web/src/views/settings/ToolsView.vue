<script setup lang="ts">
import { computed, onMounted, reactive, ref, type Component } from "vue";
import {
  CheckCircle2,
  Database,
  Globe2,
  KeyRound,
  Link2,
  ListChecks,
  Plus,
  PlugZap,
  RefreshCw,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Timer,
  Zap,
} from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";
import {
  settingsApi,
  type LocalToolsStatus,
  type LocalToolSpec,
  type ProjectToolConfig,
} from "@/api/settings";
import { projectApi } from "@/api/projects";
import { workspaceApi } from "@/api/workspace";
import { getLastProjectId } from "@/utils/lastProject";

type OperationKey = "read" | "search" | "create" | "update";
type AgentAutonomy = "受控模式" | "自主模式" | "仅建议不执行";
type AgentFallback = "暂停并请求确认" | "自动重试后暂停" | "降级为只读";
type AgentPolicy = {
  autonomy: AgentAutonomy;
  requireApproval: boolean;
  maxCalls: number;
  fallback: AgentFallback;
};

type ToolRecord = {
  id?: number | string;
  name: string;
  description: string;
  icon: Component;
  enabled: boolean;
  lastChecked: string;
  connectorType: string;
  endpoint: string;
  authType: string;
  credential: string;
  sharingScope: "PERSONAL" | "TEAM";
  scope: string;
  method: string;
  timeout: number;
  retries: number;
  rateLimit: number;
  allowAutonomous: boolean;
  requireApproval: boolean;
  operations: Record<OperationKey, boolean>;
  note: string;
};

const { notify, workspaceId, projectId, selectedProject } = useWorkspace();
const settingsProjectId = ref(-1);
const hasProject = computed(() => settingsProjectId.value > 0);
const toolIcons = { database: Database, globe: Globe2, list: ListChecks };
const defaultOperations = (): Record<OperationKey, boolean> => ({
  read: true,
  search: true,
  create: false,
  update: false,
});
const emptyOperations = (): Record<OperationKey, boolean> => ({
  read: false,
  search: false,
  create: false,
  update: false,
});
const iconFor = (icon: string) =>
  toolIcons[icon as keyof typeof toolIcons] ?? Globe2;

const tools = ref<ToolRecord[]>([]);
const connectorOpen = ref(false);
const selectedTool = ref<ToolRecord | null>(null);
const editingExisting = ref(false);
const connectorError = ref("");
const defaultAgentPolicy: AgentPolicy = {
  autonomy: "受控模式",
  requireApproval: true,
  maxCalls: 10,
  fallback: "暂停并请求确认",
};
const agentPolicy = reactive<AgentPolicy>({ ...defaultAgentPolicy });
const workspacePreferences = reactive<Record<string, unknown>>({});
const localTools = ref<LocalToolSpec[]>([]);
const localToolFiles = ref<LocalToolsStatus["files"] | null>(null);
const localToolsLoading = ref(false);
const localToolsReloading = ref(false);
const localToolsError = ref("");
const localToolEnabled = reactive<Record<string, boolean>>({});
const localToolPreferences = reactive<Record<string, boolean>>({});
const connectorForm = reactive({
  name: "",
  description: "",
  connectorType: "REST API",
  endpoint: "",
  authType: "API Key",
  credential: "",
  sharingScope: "TEAM" as "PERSONAL" | "TEAM",
  scope: "当前工作区",
  method: "GET",
  timeout: 30,
  retries: 2,
  rateLimit: 60,
  allowAutonomous: false,
  requireApproval: true,
  operations: defaultOperations(),
  note: "",
});
const connectedCount = computed(
  () => tools.value.filter((tool) => tool.enabled).length,
);
const autonomousCount = computed(
  () =>
    tools.value.filter((tool) => tool.enabled && tool.allowAutonomous).length,
);
const localEnabledCount = computed(
  () => localTools.value.filter((tool) => localToolEnabled[tool.name] !== false).length,
);

function applyAgentPolicy(value: unknown) {
  const stored = value && typeof value === "object" ? value as Partial<AgentPolicy> : {};
  const maxCalls = Number(stored.maxCalls);
  agentPolicy.autonomy =
    stored.autonomy === "自主模式" || stored.autonomy === "仅建议不执行"
      ? stored.autonomy
      : defaultAgentPolicy.autonomy;
  agentPolicy.requireApproval =
    typeof stored.requireApproval === "boolean"
      ? stored.requireApproval
      : defaultAgentPolicy.requireApproval;
  agentPolicy.maxCalls =
    Number.isInteger(maxCalls) && maxCalls >= 1 && maxCalls <= 50
      ? maxCalls
      : defaultAgentPolicy.maxCalls;
  agentPolicy.fallback =
    stored.fallback === "自动重试后暂停" || stored.fallback === "降级为只读"
      ? stored.fallback
      : defaultAgentPolicy.fallback;
}

function applyLocalToolPreferences(value: unknown) {
  for (const name of Object.keys(localToolPreferences)) delete localToolPreferences[name];
  if (!value || typeof value !== "object") return;
  for (const [name, enabled] of Object.entries(value as Record<string, unknown>)) {
    if (typeof enabled === "boolean") localToolPreferences[name] = enabled;
  }
}

function applyLocalTools(status: LocalToolsStatus) {
  localTools.value = status.tools || [];
  localToolFiles.value = status.files || null;
  for (const name of Object.keys(localToolEnabled)) {
    if (!localTools.value.some((tool) => tool.name === name)) delete localToolEnabled[name];
  }
  for (const tool of localTools.value) {
    localToolEnabled[tool.name] = localToolPreferences[tool.name] !== false;
  }
}

async function loadLocalTools() {
  if (settingsProjectId.value <= 0) return;
  localToolsLoading.value = true;
  localToolsError.value = "";
  try {
    applyLocalTools(await settingsApi.localTools.get(workspaceId.value, settingsProjectId.value));
  } catch (error) {
    localToolsError.value = error instanceof Error ? error.message : "本地工具系统加载失败";
  } finally {
    localToolsLoading.value = false;
  }
}

async function reloadLocalTools() {
  if (settingsProjectId.value <= 0) return;
  localToolsReloading.value = true;
  localToolsError.value = "";
  try {
    applyLocalTools(await settingsApi.localTools.reload(workspaceId.value, settingsProjectId.value));
    notify("本地工具已重载");
  } catch (error) {
    localToolsError.value = error instanceof Error ? error.message : "本地工具重载失败";
  } finally {
    localToolsReloading.value = false;
  }
}

function toggleLocalTool(name: string, event: Event) {
  const enabled = (event.target as HTMLInputElement).checked;
  localToolEnabled[name] = enabled;
  localToolPreferences[name] = enabled;
}

async function saveLocalTools() {
  const preferences = Object.fromEntries(
    localTools.value.map((tool) => [tool.name, localToolEnabled[tool.name] !== false]),
  );
  try {
    const remote = await workspaceApi.updatePreferences(workspaceId.value, {
      ...workspacePreferences,
      localTools: preferences,
    });
    if (remote.preferences) {
      try {
        Object.assign(workspacePreferences, JSON.parse(remote.preferences));
        applyLocalToolPreferences((JSON.parse(remote.preferences) as Record<string, unknown>).localTools);
      } catch {
        // Keep the values already shown when the server returns malformed data.
      }
    }
    notify("本地工具启用范围已保存");
  } catch (error) {
    notify(error instanceof Error ? error.message : "本地工具设置保存失败");
  }
}

function localToolSourceLabel(source: string) {
  if (source === "custom") return "自定义 Python 工具";
  if (source === "mcp") return "MCP 工具";
  return "内置工具";
}

function readyLabel(value: boolean) {
  return value ? "就绪" : "缺失";
}

onMounted(async () => {
  try {
    const remoteWorkspace = await workspaceApi.detail(workspaceId.value);
    try {
      const preferences = remoteWorkspace.preferences
        ? JSON.parse(remoteWorkspace.preferences)
        : {};
      Object.assign(workspacePreferences, preferences);
      applyAgentPolicy(preferences.agentPolicy);
      applyLocalToolPreferences(preferences.localTools);
    } catch {
      // Malformed legacy preferences are treated as unavailable data.
    }
    const projects = await projectApi.list(workspaceId.value);
    const resolvedProjectId =
      projectId.value > 0
        ? projectId.value
        : selectedProject.value?.id ||
          projects.find((project) => project.id === getLastProjectId(workspaceId.value))?.id ||
          projects[0]?.id ||
          -1;
    settingsProjectId.value = resolvedProjectId;
    if (resolvedProjectId <= 0) return;
    await loadLocalTools();
    const remoteTools = await settingsApi.tools.list(
      workspaceId.value,
      resolvedProjectId,
    );
    tools.value = remoteTools.map((tool: ProjectToolConfig) => {
      let config: Record<string, unknown> = {};
      try {
        config = tool.config ? JSON.parse(tool.config) : {};
      } catch {
        config = {};
      }
      return {
        id: tool.id,
        name: tool.name,
        description: String(config.description || "—"),
        icon: Globe2,
        enabled: tool.enabled,
        lastChecked: tool.hasCredential ? "已配置凭证" : "未配置凭证",
        connectorType: tool.connectorType,
        endpoint: tool.endpoint,
        authType: tool.authType,
        credential: "",
        sharingScope: tool.scope === "PERSONAL" ? "PERSONAL" : String(config.sharingScope || "TEAM") === "PERSONAL" ? "PERSONAL" : "TEAM",
        scope: String(config.scope || "—"),
        method: String(config.method || "—"),
        timeout: Number(config.timeout || 0),
        retries: Number(config.retries || 0),
        rateLimit: Number(config.rateLimit || 0),
        allowAutonomous: Boolean(config.allowAutonomous),
        requireApproval: config.requireApproval == null ? false : Boolean(config.requireApproval),
        operations: { ...emptyOperations(), ...(config.operations as Partial<Record<OperationKey, boolean>> | undefined) },
        note: String(config.note || ""),
      };
    });
  } catch {
    notify("工具配置加载失败");
  }
});

function resetConnectorForm() {
  Object.assign(connectorForm, {
    name: "",
    description: "",
    connectorType: "REST API",
    endpoint: "",
    authType: "API Key",
    credential: "",
    sharingScope: "TEAM",
    scope: "当前工作区",
    method: "GET",
    timeout: 30,
    retries: 2,
    rateLimit: 60,
    allowAutonomous: false,
    requireApproval: true,
    operations: defaultOperations(),
    note: "",
  });
  connectorError.value = "";
}

function openConnector(tool: ToolRecord) {
  selectedTool.value = tool;
  editingExisting.value = true;
  Object.assign(connectorForm, {
    name: tool.name,
    description: tool.description,
    connectorType: tool.connectorType,
    endpoint: tool.endpoint,
    authType: tool.authType,
    credential: tool.credential || "",
    sharingScope: tool.sharingScope,
    scope: tool.scope,
    method: tool.method,
    timeout: tool.timeout,
    retries: tool.retries,
    rateLimit: tool.rateLimit,
    allowAutonomous: tool.allowAutonomous,
    requireApproval: tool.requireApproval,
    operations: { ...tool.operations },
    note: tool.note,
  });
  connectorError.value = "";
  connectorOpen.value = true;
}

function openNewConnector() {
  selectedTool.value = null;
  editingExisting.value = false;
  resetConnectorForm();
  connectorOpen.value = true;
}

function savePolicy() {
  if (agentPolicy.maxCalls < 1 || agentPolicy.maxCalls > 50) {
    notify("单次运行调用上限需要在 1–50 次之间");
    return;
  }
  workspaceApi
    .updatePreferences(workspaceId.value, {
      ...workspacePreferences,
      agentPolicy: { ...agentPolicy },
    })
    .then((remote) => {
      if (remote.preferences) {
        try {
          Object.assign(workspacePreferences, JSON.parse(remote.preferences));
        } catch {
          // Keep the values already shown when the server returns malformed data.
        }
      }
      notify("Agent 调用策略已保存");
    })
    .catch((error) => {
      notify(error instanceof Error ? error.message : "Agent 调用策略保存失败");
    });
}

async function saveConnector() {
  if (!hasProject.value) {
    connectorError.value = "请先创建项目后配置连接器";
    return;
  }
  if (!connectorForm.name.trim() || !connectorForm.description.trim()) {
    connectorError.value = "请填写连接器名称和用途说明";
    return;
  }
  if (!/^(https?|internal|mcp):\/\//.test(connectorForm.endpoint.trim())) {
    connectorError.value =
      "服务地址必须以 http://、https://、internal:// 或 mcp:// 开头";
    return;
  }
  if (
    connectorForm.authType !== "无需认证" &&
    !connectorForm.credential.trim()
  ) {
    connectorError.value = "当前认证方式需要填写访问凭证";
    return;
  }
  if (
    connectorForm.timeout < 1 ||
    connectorForm.timeout > 600 ||
    connectorForm.retries < 0 ||
    connectorForm.retries > 5 ||
    connectorForm.rateLimit < 1
  ) {
    connectorError.value = "请检查超时、重试次数和限流配置";
    return;
  }
  if (
    !editingExisting.value &&
    tools.value.some(
      (tool) =>
        tool.name.toLowerCase() === connectorForm.name.trim().toLowerCase(),
    )
  ) {
    connectorError.value = "已存在同名连接器，请换一个名称";
    return;
  }

  const config = {
    name: connectorForm.name.trim(),
    description: connectorForm.description.trim(),
    connectorType: connectorForm.connectorType,
    endpoint: connectorForm.endpoint.trim(),
    authType: connectorForm.authType,
    credential: connectorForm.credential.trim(),
    sharingScope: connectorForm.sharingScope,
    scope: connectorForm.scope,
    method: connectorForm.method,
    timeout: connectorForm.timeout,
    retries: connectorForm.retries,
    rateLimit: connectorForm.rateLimit,
    allowAutonomous: connectorForm.allowAutonomous,
    requireApproval: connectorForm.requireApproval,
    operations: { ...connectorForm.operations },
    note: connectorForm.note.trim(),
  };
  const payload = {
    name: config.name,
    endpoint: config.endpoint,
    connectorType: config.connectorType,
    authType: config.authType,
    credential: config.credential || undefined,
    scope: config.sharingScope,
    config: JSON.stringify({
      description: config.description,
      sharingScope: config.sharingScope,
      scope: config.scope,
      method: config.method,
      timeout: config.timeout,
      retries: config.retries,
      rateLimit: config.rateLimit,
      allowAutonomous: config.allowAutonomous,
      requireApproval: config.requireApproval,
      operations: config.operations,
      note: config.note,
    }),
    enabled: true,
  };
  let savedId: number | string | undefined = selectedTool.value?.id;
  try {
    if (selectedTool.value?.id)
      await settingsApi.tools.update(
        workspaceId.value,
        settingsProjectId.value,
        selectedTool.value.id,
        payload,
      );
    else
      savedId = (
        await settingsApi.tools.create(
          workspaceId.value,
          settingsProjectId.value,
          payload,
        )
      ).id;
  } catch (error) {
    connectorError.value =
      error instanceof Error ? error.message : "连接器保存失败";
    return;
  }
  if (selectedTool.value) {
    Object.assign(selectedTool.value, config, {
      enabled: true,
      lastChecked: config.credential ? "已配置凭证" : "未配置凭证",
    });
  } else {
    tools.value.push({
      ...config,
      id: savedId,
      icon: Globe2,
      enabled: true,
      lastChecked: config.credential ? "已配置凭证" : "未配置凭证",
    });
  }
  const savedName = config.name;
  connectorOpen.value = false;
  notify(`${savedName} 配置已保存并连接`);
}

async function disconnectTool() {
  if (!selectedTool.value) return;
  const tool = selectedTool.value;
  if (tool.id) {
    try {
      await settingsApi.tools.update(
        workspaceId.value,
        settingsProjectId.value,
        tool.id,
        {
          name: tool.name,
          endpoint: tool.endpoint,
          connectorType: tool.connectorType,
          authType: tool.authType,
          enabled: false,
        },
      );
    } catch {
      notify("工具断开失败");
      return;
    }
  }
  tool.enabled = false;
  tool.lastChecked = "未连接";
  connectorOpen.value = false;
  notify(`${tool.name} 已断开`);
}

async function removeTool(tool: ToolRecord) {
  if (!hasProject.value) {
    notify("请先创建项目");
    return;
  }
  if (!tool.id) {
    tools.value = tools.value.filter((item) => item !== tool);
    return;
  }
  try {
    await settingsApi.tools.remove(
      workspaceId.value,
      settingsProjectId.value,
      tool.id,
    );
  } catch {
    notify("工具配置删除失败");
    return;
  }
  tools.value = tools.value.filter((item) => item.id !== tool.id);
  notify(`${tool.name} 已删除`);
}

</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="工具与连接器"
    subtitle="配置工作区的基础能力、外部服务和 Agent 自主调用权限"
  >
    <div class="settings-section connector-overview">
      <div class="overview-copy">
        <span class="overview-icon"><PlugZap :size="18" /></span>
        <div>
          <h2>连接器状态</h2>
          <p>
            {{ connectedCount }} 个工具已连接，其中 {{ autonomousCount }} 个允许
            Agent 自主调用。
          </p>
        </div>
      </div>
      <span class="status-badge" :class="tools.length ? 'status-indexed' : 'status-muted'"><i />{{ tools.length ? "已加载配置" : "暂无连接器" }}</span>
    </div>

    <div class="settings-section policy-section">
      <div class="section-intro">
        <div>
          <h2>Agent 自主调用策略</h2>
          <p>
            控制 Agent 是否可以直接使用连接器，以及写入类操作是否必须经过确认。
          </p>
        </div>
        <span class="permission-note"
          ><ShieldCheck :size="13" />工作区级策略</span
        >
      </div>
      <div class="policy-grid">
        <label class="field-label"
          >默认调用模式<select v-model="agentPolicy.autonomy">
            <option value="受控模式">受控模式</option>
            <option value="自主模式">自主模式</option>
            <option value="仅建议不执行">仅建议不执行</option></select
          ><small>受控模式会在写入操作前请求确认，自主模式仅适用于已授权工具。</small></label
        ><label class="field-label"
          >单次运行调用上限<input
            v-model.number="agentPolicy.maxCalls"
            type="number"
            min="1"
            max="50"
          /><small>用于防止循环调用和意外消耗。</small></label
        ><label class="policy-toggle"
          ><input
            v-model="agentPolicy.requireApproval"
            type="checkbox"
            class="switch-input"
          /><span class="switch-ui" /><span
            ><strong>写入操作需要确认</strong
            ><small>创建、更新或发送数据前弹出确认。</small></span
          ></label
        ><label class="field-label"
          >失败后的处理<select v-model="agentPolicy.fallback">
            <option value="暂停并请求确认">暂停并请求确认</option>
            <option value="自动重试后暂停">自动重试后暂停</option>
            <option value="降级为只读">降级为只读</option>
          </select></label
        >
      </div>
      <div class="policy-actions">
        <span><Zap :size="13" />当前策略不会改变连接器本身的权限范围</span
        ><button
          class="button button-secondary button-sm"
          type="button"
          @click="savePolicy"
        >
          保存调用策略
        </button>
      </div>
    </div>

    <div class="settings-section local-tools-section">
      <div class="section-intro">
        <div>
          <h2>本地工具系统</h2>
          <p>
            这里显示 Python AI 服务当前注册的内置工具和自定义工具。可按工作区手动启用或停用；新增自定义工具仍需放入 AI 服务的受信任目录。
          </p>
        </div>
        <div class="section-actions">
          <span class="permission-note"><Database :size="13" />{{ localEnabledCount }}/{{ localTools.length }} 个工具启用</span>
          <button class="button button-secondary button-sm" type="button" :disabled="localToolsLoading" @click="loadLocalTools">
            <RefreshCw :size="14" :class="{ spinning: localToolsLoading }" />刷新状态
          </button>
          <button class="button button-secondary button-sm" type="button" :disabled="localToolsReloading" @click="reloadLocalTools">
            <RefreshCw :size="14" :class="{ spinning: localToolsReloading }" />{{ localToolsReloading ? "重载中…" : "重载自定义工具" }}
          </button>
        </div>
      </div>
      <p v-if="localToolsError" class="local-tools-error" role="alert">{{ localToolsError }}</p>
      <div v-if="!hasProject" class="local-tools-empty">请先创建项目后查看项目可用的 Python 工具。</div>
      <div v-else-if="localToolsLoading && !localTools.length" class="local-tools-empty">正在读取 Python 工具注册表…</div>
      <div v-else-if="localTools.length" class="local-tool-grid">
        <article v-for="tool in localTools" :key="tool.name" class="local-tool-card">
          <div class="local-tool-card-heading">
            <span class="config-icon"><Settings2 :size="16" /></span>
            <div>
              <strong>{{ tool.name }}</strong>
              <small>{{ localToolSourceLabel(tool.source) }} · {{ tool.permission === "WRITE" ? "写入工具" : "只读工具" }}</small>
            </div>
            <label class="local-tool-toggle">
              <input
                type="checkbox"
                :checked="localToolEnabled[tool.name] !== false"
                @change="toggleLocalTool(tool.name, $event)"
              />
              <span>启用</span>
            </label>
          </div>
          <p>{{ tool.description || "暂无描述" }}</p>
          <div class="local-tool-meta">
            <span>超时 {{ tool.timeoutSeconds }} 秒</span>
            <span>并发 {{ tool.maxConcurrency }}</span>
            <span v-if="tool.requiresConfirmation">需要确认</span>
          </div>
        </article>
      </div>
      <div v-else class="local-tools-empty">Python 服务没有返回可用工具，请检查 AI 服务是否已启动。</div>
      <div v-if="localToolFiles" class="local-file-tools">
        <div>
          <strong>本地文件分析工具</strong>
          <small>附件解析使用本机工具链，不会把原始文件直接交给模型。</small>
        </div>
        <div class="local-file-status">
          <span :class="{ ready: localToolFiles.ocr.tesseract && localToolFiles.ocr.poppler }">OCR {{ readyLabel(localToolFiles.ocr.tesseract && localToolFiles.ocr.poppler) }}</span>
          <span :class="{ ready: localToolFiles.media.ffmpeg && localToolFiles.media.ffprobe }">媒体 {{ readyLabel(localToolFiles.media.ffmpeg && localToolFiles.media.ffprobe) }}</span>
          <span :class="{ ready: localToolFiles.office.libreoffice }">Office {{ readyLabel(localToolFiles.office.libreoffice) }}</span>
        </div>
      </div>
      <div v-if="localTools.length" class="local-tools-actions">
        <span><ShieldCheck :size="13" />停用后会在下一次 Agent 运行中生效；不会删除本地 Python 文件。</span>
        <button class="button button-primary button-sm" type="button" @click="saveLocalTools">保存本地工具设置</button>
      </div>
    </div>

    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>已配置连接器</h2>
          <p>
            每个连接器都可以独立配置认证方式、权限范围、执行策略和自主调用规则。
          </p>
        </div>
        <div class="section-actions">
          <span class="permission-note"><KeyRound :size="13" />密钥已加密</span
          ><span v-if="!hasProject" class="permission-note">请先创建项目</span
          ><button
            v-if="hasProject"
            class="button button-secondary button-sm"
            type="button"
            @click="openNewConnector"
          >
            <Plus :size="14" />添加连接器
          </button>
        </div>
      </div>
      <div class="config-list tool-list">
        <div v-for="tool in tools" :key="tool.name" class="config-row tool-row">
          <span class="config-icon"
            ><component :is="tool.icon" :size="17" /></span
          ><span class="tool-copy"
            ><strong>{{ tool.name }}</strong
            ><small
              >{{ tool.description }} · {{ tool.connectorType }} ·
              {{ tool.sharingScope === "PERSONAL" ? "个人凭证" : "项目共享" }} · {{ tool.scope }}</small
            ></span
          ><span
            class="tool-policy"
            :class="{ autonomous: tool.allowAutonomous && tool.enabled }"
            ><Zap :size="12" />{{
              tool.allowAutonomous && tool.enabled ? "可自主调用" : "需确认"
            }}</span
          ><span class="tool-check" :class="{ connected: tool.enabled }"
            ><CheckCircle2 :size="13" />{{ tool.lastChecked }}</span
          ><span
            class="status-badge"
            :class="tool.enabled ? 'status-indexed' : 'status-muted'"
            ><i />{{ tool.enabled ? "已连接" : "未连接" }}</span
          ><button
            class="button button-secondary button-sm"
            type="button"
            @click="openConnector(tool)"
          >
            {{ tool.enabled ? "管理配置" : "连接配置" }}</button
          ><button
            class="icon-button small danger-icon-button"
            type="button"
            :aria-label="`删除${tool.name}`"
            @click="removeTool(tool)"
          >
            ×
          </button>
        </div>
        <div v-if="!tools.length" class="empty-state">
          <PlugZap :size="18" />
          <strong>暂无连接器配置</strong>
          <span>{{ hasProject ? "添加连接器后，这里会显示后端保存的接入和权限配置。" : "创建项目后，才能按项目配置连接器。" }}</span>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>权限与安全边界</h2>
          <p>
            自主调用不等于无限权限，连接器仍然受到工作区、项目和操作类型三层限制。
          </p>
        </div>
        <Link2 :size="18" class="section-icon" />
      </div>
      <div class="boundary-grid">
        <div class="boundary-card">
          <span class="boundary-icon"><ShieldCheck :size="15" /></span>
          <div>
            <strong>最小权限</strong>
            <p>默认只开启读取和检索，写入操作需要单独勾选。</p>
          </div>
        </div>
        <div class="boundary-card">
          <span class="boundary-icon"><Timer :size="15" /></span>
          <div>
            <strong>执行保护</strong>
            <p>每个连接器独立限制超时、重试和每分钟调用次数。</p>
          </div>
        </div>
        <div class="boundary-card">
          <span class="boundary-icon"><Settings2 :size="15" /></span>
          <div>
            <strong>可审计配置</strong>
            <p>连接类型、权限范围和自主调用开关都会记录在配置中。</p>
          </div>
        </div>
      </div>
    </div>

    <Dialog v-model:open="connectorOpen"
      ><DialogContent class="connector-dialog sm:max-w-4xl"
        ><DialogHeader
          ><DialogTitle>{{
            editingExisting ? `${selectedTool?.name}连接设置` : "添加连接器"
          }}</DialogTitle
          ><DialogDescription
            >配置连接器的接入方式、权限边界和 Agent
            调用策略。</DialogDescription
          ></DialogHeader
        >
        <div class="connector-form-scroll">
          <p v-if="connectorError" class="form-error" role="alert">
            {{ connectorError }}
          </p>
          <section class="connector-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><Settings2 :size="15" /></span>
              <div>
                <strong>连接器信息</strong
                ><small>定义工具名称、类型和用途</small>
              </div>
            </div>
            <div class="connector-form-grid">
              <label class="field-label"
                >连接器名称<input
                  v-model="connectorForm.name"
                  maxlength="50"
                  placeholder="例如：企业搜索 API" /></label
              ><label class="field-label"
                >连接类型<select v-model="connectorForm.connectorType">
                  <option>内置连接器</option>
                  <option>REST API</option>
                  <option>WEB_SEARCH</option>
                  <option>MCP Server</option>
                  <option>Webhook</option>
                </select></label
              ><label class="field-label field-wide"
                >用途说明<textarea
                  v-model="connectorForm.description"
                  rows="2"
                  maxlength="160"
                  placeholder="说明 Agent 什么时候应该使用这个连接器"
                ></textarea>
              </label>
            </div>
          </section>
          <section class="connector-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><KeyRound :size="15" /></span>
              <div>
                <strong>接入与认证</strong
                ><small>支持 REST、MCP 和内部服务</small>
              </div>
            </div>
            <div class="connector-form-grid">
              <label class="field-label field-wide"
                >服务地址<input
                  v-model="connectorForm.endpoint"
                  placeholder="https://api.example.com/v1 或 mcp://server-name"
                /><small
                  >支持 http://、https:// 和 internal:// 地址。</small
                ></label
              ><label class="field-label"
                >认证方式<select v-model="connectorForm.authType">
                  <option>API Key</option>
                  <option>Bearer Token</option>
                  <option>OAuth 2.0</option>
                  <option>Workspace Token</option>
                  <option>无需认证</option>
                </select></label
              ><label class="field-label"
                >请求方法<select v-model="connectorForm.method">
                  <option>GET</option>
                  <option>POST</option>
                  <option>PUT</option>
                  <option>DELETE</option>
                </select></label
              ><label class="field-label field-wide"
                >访问凭证<input
                  v-model="connectorForm.credential"
                  type="password"
                  autocomplete="new-password"
                  placeholder="输入 API Key、Token 或 OAuth 凭证"
              /></label>
            </div>
          </section>
          <section class="connector-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><ShieldCheck :size="15" /></span>
              <div>
                <strong>权限与自主调用</strong
                ><small>把“能连接”与“能做什么”拆开控制</small>
              </div>
            </div>
            <div class="connector-form-grid">
              <label class="field-label"
                >权限范围<select v-model="connectorForm.scope">
                  <option>当前工作区</option>
                  <option>当前项目</option>
                  <option>仅限读取</option>
                  <option>指定资源</option>
                </select></label
              ><label class="field-label"
                >凭证归属<select v-model="connectorForm.sharingScope">
                  <option value="TEAM">项目共享</option>
                  <option value="PERSONAL">仅自己使用</option>
                </select><small>个人凭证只对本人可见；项目执行默认优先使用项目创建者的凭证。</small></label
              ><label class="policy-toggle"
                ><input
                  v-model="connectorForm.allowAutonomous"
                  type="checkbox"
                  class="switch-input"
                /><span class="switch-ui" /><span
                  ><strong>允许自主调用</strong
                  ><small>Agent 可在任务中直接使用。</small></span
                ></label
              ><label class="policy-toggle"
                ><input
                  v-model="connectorForm.requireApproval"
                  type="checkbox"
                  class="switch-input"
                /><span class="switch-ui" /><span
                  ><strong>写入前需要确认</strong
                  ><small>创建、更新和删除操作需确认。</small></span
                ></label
              ><label class="field-label field-wide"
                >允许的操作
                <div class="operation-list">
                  <label
                    ><input
                      v-model="connectorForm.operations.read"
                      type="checkbox"
                    />读取</label
                  ><label
                    ><input
                      v-model="connectorForm.operations.search"
                      type="checkbox"
                    />搜索</label
                  ><label
                    ><input
                      v-model="connectorForm.operations.create"
                      type="checkbox"
                    />创建</label
                  ><label
                    ><input
                      v-model="connectorForm.operations.update"
                      type="checkbox"
                    />更新</label
                  >
                </div></label
              >
            </div>
          </section>
          <section class="connector-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><Timer :size="15" /></span>
              <div>
                <strong>执行策略</strong
                ><small>避免慢请求、无限重试和调用失控</small>
              </div>
            </div>
            <div class="connector-form-grid">
              <label class="field-label"
                >超时时间（秒）<input
                  v-model.number="connectorForm.timeout"
                  type="number"
                  min="1"
                  max="600" /></label
              ><label class="field-label"
                >失败重试次数<input
                  v-model.number="connectorForm.retries"
                  type="number"
                  min="0"
                  max="5" /></label
              ><label class="field-label"
                >每分钟调用上限<input
                  v-model.number="connectorForm.rateLimit"
                  type="number"
                  min="1"
                  max="10000" /></label
              ><label class="field-label field-wide"
                >内部备注<textarea
                  v-model="connectorForm.note"
                  rows="2"
                  maxlength="160"
                  placeholder="例如：仅用于同步当前项目的 Jira 行动项"
                ></textarea>
              </label>
            </div>
          </section>
        </div>
        <DialogFooter
          ><span class="dialog-security-note"
            ><ShieldCheck :size="13" />凭证只在当前会话中用于连接测试</span
          ><button
            v-if="editingExisting && selectedTool?.enabled"
            class="button button-danger"
            type="button"
            @click="disconnectTool"
          >
            断开连接</button
          ><span class="footer-spacer" /><button
            class="button button-secondary"
            type="button"
            @click="connectorOpen = false"
          >
            取消</button
          ><button
            class="button button-primary"
            type="button"
            @click="saveConnector"
          >
            保存并连接
          </button></DialogFooter
        ></DialogContent
      ></Dialog
    >
  </Layout>
</template>

<style scoped>
.section-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.section-icon {
  color: var(--teal-dark);
}
.section-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.connector-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: linear-gradient(
    110deg,
    color-mix(in oklab, var(--teal) 7%, var(--surface)),
    var(--surface)
  );
}
.overview-copy {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.overview-icon {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.5625rem;
  color: var(--teal-dark);
  background: #e2f7f3;
}
.overview-copy h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.875rem;
}
.overview-copy p {
  margin: 0.3125rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.permission-note {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.policy-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.875rem;
  max-width: 52rem;
}
.policy-toggle {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  min-height: 2.25rem;
  cursor: pointer;
}
.policy-toggle > span:last-child {
  display: grid;
  gap: 0.1875rem;
}
.policy-toggle strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.policy-toggle small,
.field-label small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  font-weight: 400;
  line-height: 1.35;
}
.switch-input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.switch-ui {
  width: 2.125rem;
  height: 1.1875rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #d8e2e2;
  transition: background 0.16s;
}
.switch-ui::after {
  display: block;
  width: 0.875rem;
  height: 0.875rem;
  margin: 0.15625rem;
  border-radius: 50%;
  background: #fff;
  content: "";
  transition: transform 0.16s;
  box-shadow: 0 0.0625rem 0.125rem rgba(0, 0, 0, 0.12);
}
.switch-input:checked + .switch-ui {
  background: var(--teal);
}
.switch-input:checked + .switch-ui::after {
  transform: translateX(0.9375rem);
}
.policy-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  max-width: 52rem;
  margin-top: 1rem;
}
.policy-actions > span {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  flex: 1;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.tool-list {
  max-width: none;
}
.tool-row {
  min-height: 4.5rem;
}
.tool-copy {
  min-width: 0;
  flex: 1;
}
.tool-copy strong,
.tool-copy small {
  display: block;
}
.tool-copy strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.tool-copy small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-policy,
.tool-check {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 4.5rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.tool-policy.autonomous {
  color: var(--teal-dark);
}
.tool-check.connected {
  color: var(--teal-dark);
}
.tool-row .icon-button {
  flex: 0 0 auto;
}
.boundary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  max-width: 52rem;
}
.boundary-card {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-soft);
}
.boundary-icon {
  display: grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 auto;
  border-radius: 0.4375rem;
  color: var(--teal-dark);
  background: #e4f6f3;
}
.boundary-card strong,
.boundary-card p {
  display: block;
}
.boundary-card strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.boundary-card p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.4;
}
.connector-dialog {
  max-width: 56rem !important;
}
.connector-form-scroll {
  display: grid;
  gap: 0.75rem;
  max-height: min(70vh, 44rem);
  overflow: auto;
  padding: 0.125rem 0.25rem 0.125rem 0;
}
.connector-form-section {
  padding: 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: #fbfdfd;
}
.form-section-heading {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  margin-bottom: 0.875rem;
}
.form-section-heading > div {
  display: grid;
  gap: 0.1875rem;
}
.form-section-heading strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.form-section-heading small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.form-section-icon {
  display: grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 0.4375rem;
  color: var(--teal-dark);
  background: #e4f6f3;
}
.connector-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  max-width: none;
}
.connector-form-grid .field-wide {
  grid-column: 1 / -1;
}
.form-error {
  margin: 0;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid #f0caca;
  border-radius: 0.4375rem;
  color: #a14d4d;
  background: #fff5f5;
  font-size: 0.75rem;
}
.operation-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem 0.875rem;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  background: var(--surface-soft);
  font-size: 0.75rem;
  font-weight: 400;
}
.operation-list label {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  cursor: pointer;
}
.operation-list input {
  accent-color: var(--teal);
}
.dialog-security-note {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-right: auto;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.footer-spacer {
  flex: 1;
}
.spinning {
  animation: spin 800ms linear infinite;
}
.local-tools-section .section-intro {
  align-items: flex-start;
}
.local-tools-section .section-actions {
  align-items: center;
  justify-content: flex-end;
}
.local-tool-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.local-tool-card {
  min-width: 0;
  padding: 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface-soft);
}
.local-tool-card-heading {
  display: flex;
  align-items: flex-start;
  gap: 0.5625rem;
}
.local-tool-card-heading > div {
  min-width: 0;
  flex: 1;
}
.local-tool-card strong,
.local-tool-card small,
.local-tool-card p {
  display: block;
}
.local-tool-card strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.local-tool-card small {
  margin-top: 0.2rem;
  color: var(--workspace-muted);
  font-size: 0.7rem;
}
.local-tool-card p {
  margin: 0.75rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.45;
}
.local-tool-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex: 0 0 auto;
  color: var(--teal-dark);
  font-size: 0.7rem;
  cursor: pointer;
}
.local-tool-toggle input {
  accent-color: var(--teal);
}
.local-tool-meta,
.local-file-status,
.local-tools-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem 0.75rem;
}
.local-tool-meta {
  margin-top: 0.7rem;
  color: var(--workspace-subtle);
  font-size: 0.68rem;
}
.local-tools-empty {
  padding: 1rem;
  border: 0.0625rem dashed var(--workspace-border);
  border-radius: 0.5rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.local-tools-error {
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid #f0caca;
  border-radius: 0.4375rem;
  color: #a14d4d !important;
  background: #fff5f5;
  font-size: 0.75rem;
}
.local-file-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.875rem;
  padding-top: 0.875rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.local-file-tools strong,
.local-file-tools small {
  display: block;
}
.local-file-tools strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.local-file-tools small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.7rem;
}
.local-file-status span {
  color: #a14d4d;
  font-size: 0.7rem;
}
.local-file-status span.ready {
  color: var(--teal-dark);
}
.local-tools-actions {
  justify-content: space-between;
  margin-top: 0.875rem;
  color: var(--workspace-muted);
  font-size: 0.7rem;
}
.local-tools-actions > span {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 47.5rem) {
  .connector-overview {
    align-items: flex-start;
    flex-direction: column;
  }
  .section-actions {
    align-items: flex-start;
    flex-direction: column;
  }
  .policy-grid,
  .connector-form-grid {
    grid-template-columns: 1fr;
  }
  .connector-form-grid .field-wide {
    grid-column: auto;
  }
  .policy-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .policy-actions .button {
    width: 100%;
  }
  .tool-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .tool-policy,
  .tool-check {
    margin-left: 2.625rem;
  }
  .tool-row .button {
    margin-left: auto;
  }
  .boundary-grid {
    grid-template-columns: 1fr;
  }
  .local-tool-grid {
    grid-template-columns: 1fr;
  }
  .local-file-tools,
  .local-tools-actions {
    align-items: flex-start;
    flex-direction: column;
  }
  .connector-form-section {
    padding: 0.8125rem;
  }
  .dialog-security-note {
    display: none;
  }
}
</style>
