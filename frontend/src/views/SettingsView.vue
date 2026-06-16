<template>
  <div class="settings-container">
    <div class="view-header">
      <div>
        <h1>设置</h1>
        <p class="page-subtitle">管理平台集成和外部提醒渠道。</p>
      </div>
      <div class="status-summary">
        <span class="summary-label">飞书状态</span>
        <span :class="['status-badge', larkStatus.enabled ? 'enabled' : 'disabled']">
          {{ larkStatus.enabled ? '已启用' : '未配置' }}
        </span>
      </div>
    </div>

    <!-- 大模型配置 -->
    <div class="setting-section">
      <div class="section-header">
        <h2>大模型 (LLM) 配置</h2>
        <span :class="['status-badge', llmStatus.configured ? 'enabled' : 'disabled']">
          {{ llmStatus.configured ? '已配置' : '未配置' }}
        </span>
      </div>

      <div class="section-content">
        <p class="description">
          配置对话使用的 LLM 服务（兼容 OpenAI 协议，例如 DeepSeek / 阿里云百炼 / OpenAI / 自部署 vLLM 等）。
          保存后立即生效，无需重启服务。
        </p>

        <div class="config-form">
          <h4 class="form-section-title">对话模型</h4>

          <div class="form-group">
            <label>API Key <span class="required">*</span></label>
            <input
              v-model="llmForm.llm_api_key"
              type="password"
              :placeholder="llmStatus.configured ? llmStatus.llm_api_key_masked : 'sk-xxxxxxxx'"
              autocomplete="new-password"
            />
            <span class="help">已保存的 Key 会被脱敏；不填则保留当前值。</span>
          </div>

          <div class="form-group">
            <label>Base URL <span class="required">*</span></label>
            <input
              v-model="llmForm.llm_base_url"
              type="text"
              placeholder="https://api.deepseek.com"
            />
            <span class="help">OpenAI 兼容接口地址，不需要带 /chat/completions。</span>
          </div>

          <div class="form-group">
            <label>Model <span class="required">*</span></label>
            <input
              v-model="llmForm.llm_model"
              type="text"
              placeholder="deepseek-chat"
            />
            <span class="help">如 deepseek-chat、qwen-plus、gpt-4o-mini 等。</span>
          </div>

          <h4 class="form-section-title">向量嵌入（可选）</h4>

          <div class="form-group">
            <label>Embedding API Key</label>
            <input
              v-model="llmForm.embedding_api_key"
              type="password"
              :placeholder="llmStatus.configured ? llmStatus.embedding_api_key_masked : '留空则复用对话模型 Key'"
              autocomplete="new-password"
            />
            <span class="help">不填则与对话模型共用 Key。</span>
          </div>

          <div class="form-group">
            <label>Embedding Base URL</label>
            <input
              v-model="llmForm.embedding_base_url"
              type="text"
              placeholder="留空则复用对话模型 Base URL"
            />
          </div>

          <div class="form-group">
            <label>Embedding Model</label>
            <input
              v-model="llmForm.embedding_model"
              type="text"
              placeholder="text-embedding-v3"
            />
            <span class="help">DeepSeek 暂无嵌入接口；建议改用 DashScope 的 text-embedding-v3。</span>
          </div>

          <div class="form-group">
            <label>Embedding 维度</label>
            <input
              v-model.number="llmForm.embedding_dimension"
              type="number"
              min="64"
              max="4096"
              placeholder="1024"
            />
            <span class="help">需与所选嵌入模型一致；改了之后老向量索引可能不兼容。</span>
          </div>

          <div class="form-actions">
            <button class="btn-primary" :disabled="llmSaving" @click="saveLLMSettings">
              {{ llmSaving ? '保存中...' : '保存配置' }}
            </button>
            <button class="btn-secondary" :disabled="llmTesting" @click="testLLMSettings">
              {{ llmTesting ? '测试中...' : '测试连接' }}
            </button>
          </div>
        </div>

        <div v-if="llmTestResult" class="test-result" :class="llmTestResult.success ? 'success' : 'error'">
          {{ llmTestResult.message }}
        </div>

        <div v-if="llmStatus.configured" class="config-display" style="margin-top: 16px;">
          <div class="info-row">
            <span class="label">当前对话模型:</span>
            <span class="value">{{ llmStatus.llm_model }} @ {{ llmStatus.llm_base_url }}</span>
          </div>
          <div class="info-row">
            <span class="label">当前嵌入模型:</span>
            <span class="value">{{ llmStatus.embedding_model }} ({{ llmStatus.embedding_dimension }}d)</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 飞书配置 -->
    <div class="setting-section">
      <div class="section-header">
        <h2>飞书集成</h2>
        <span v-if="larkStatus.enabled" class="status-badge enabled">已启用</span>
        <span v-else class="status-badge disabled">未配置</span>
      </div>

      <div class="section-content">
        <p class="description">
          配置飞书机器人后，你可以通过飞书接收提醒消息。
          <a href="https://open.feishu.cn/app" target="_blank">去飞书开放平台创建应用 →</a>
        </p>

        <!-- 配置表单 -->
        <div v-if="editing || !larkStatus.enabled" class="config-form">
          <div class="form-group">
            <label>App ID <span class="required">*</span></label>
            <input
              v-model="larkConfig.app_id"
              type="text"
              placeholder="cli_xxxxxxxxxx"
            />
            <span class="help">在飞书应用凭证中获取</span>
          </div>

          <div class="form-group">
            <label>App Secret <span class="required">*</span></label>
            <input
              v-model="larkConfig.app_secret"
              type="password"
              placeholder="输入 App Secret"
            />
            <span class="help">在飞书应用凭证中获取</span>
          </div>

          <div class="form-group">
            <label>接收者 ID <span class="required">*</span></label>
            <input
              v-model="larkConfig.receive_id"
              type="text"
              placeholder="ou_xxxxxxxxxx"
            />
            <span class="help">你的飞书用户 open_id</span>
          </div>

          <div class="form-group">
            <label>ID 类型</label>
            <select v-model="larkConfig.receive_id_type">
              <option value="open_id">open_id（推荐）</option>
              <option value="user_id">user_id</option>
              <option value="union_id">union_id</option>
              <option value="email">email</option>
            </select>
          </div>

          <div class="form-actions">
            <button
              class="btn-primary"
              :disabled="saving"
              @click="saveLarkConfig"
            >
              {{ saving ? '保存中...' : '保存配置' }}
            </button>
            <button
              v-if="larkStatus.enabled"
              class="btn-secondary"
              @click="editing = false"
            >
              取消
            </button>
          </div>
        </div>

        <!-- 已配置显示 -->
        <div v-else class="config-display">
          <div class="info-row">
            <span class="label">App ID:</span>
            <span class="value">{{ maskString(larkStatus.app_id) }}</span>
          </div>
          <div class="info-row">
            <span class="label">ID 类型:</span>
            <span class="value">{{ larkStatus.receive_id_type }}</span>
          </div>
          <div class="info-row">
            <span class="label">配置时间:</span>
            <span class="value">{{ formatDate(larkStatus.created_at) }}</span>
          </div>

          <div class="config-actions">
            <button class="btn-primary" @click="testLark">
              {{ testing ? '发送中...' : '发送测试消息' }}
            </button>
            <button class="btn-secondary" @click="editing = true">
              修改配置
            </button>
            <button class="btn-danger" @click="deleteLarkConfig">
              删除配置
            </button>
          </div>
        </div>

        <!-- 测试结果 -->
        <div v-if="testResult" class="test-result" :class="testResult.success ? 'success' : 'error'">
          {{ testResult.message }}
        </div>
      </div>
    </div>

    <!-- 使用说明 -->
    <div class="setting-section">
      <h2>配置说明</h2>
      <div class="help-content">
        <h4>如何获取飞书配置：</h4>
        <ol>
          <li>访问 <a href="https://open.feishu.cn/app" target="_blank">飞书开放平台</a></li>
          <li>创建企业自建应用</li>
          <li>在「凭证与基础信息」中获取 App ID 和 App Secret</li>
          <li>在「权限管理」中添加权限：
            <ul>
              <li>im:message:send</li>
              <li>im:message.group_msg</li>
              <li>contact:user.base:readonly</li>
            </ul>
          </li>
          <li>在「版本管理与发布」中创建版本并申请发布</li>
          <li>获取你的 open_id（可通过飞书开放平台调试工具）</li>
        </ol>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const userStore = useUserStore()

// 状态
const larkStatus = ref({ enabled: false })
const editing = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)

// 配置表单
const larkConfig = ref({
  app_id: '',
  app_secret: '',
  receive_id: '',
  receive_id_type: 'open_id'
})

// 大模型配置
const llmStatus = ref({
  configured: false,
  llm_api_key_masked: '',
  llm_base_url: '',
  llm_model: '',
  embedding_api_key_masked: '',
  embedding_base_url: '',
  embedding_model: '',
  embedding_dimension: 1024
})
const llmForm = ref({
  llm_api_key: '',
  llm_base_url: '',
  llm_model: '',
  embedding_api_key: '',
  embedding_base_url: '',
  embedding_model: '',
  embedding_dimension: null
})
const llmSaving = ref(false)
const llmTesting = ref(false)
const llmTestResult = ref(null)

async function loadLLMSettings() {
  try {
    const res = await fetch(`${API_URL}/api/settings/llm`)
    const data = await res.json()
    if (!data.success || !data.data) return

    const llm = data.data.llm || {}
    const emb = data.data.embedding || {}
    llmStatus.value = {
      configured: !!(llm.base_url && llm.model),
      llm_api_key_masked: llm.api_key || '',
      llm_base_url: llm.base_url || '',
      llm_model: llm.model || '',
      embedding_api_key_masked: emb.api_key || '',
      embedding_base_url: emb.base_url || '',
      embedding_model: emb.model || '',
      embedding_dimension: emb.dimension || 1024
    }
    // 把当前值预填到表单（api_key 留空避免覆盖）
    llmForm.value = {
      llm_api_key: '',
      llm_base_url: llm.base_url || '',
      llm_model: llm.model || '',
      embedding_api_key: '',
      embedding_base_url: emb.base_url || '',
      embedding_model: emb.model || '',
      embedding_dimension: emb.dimension || null
    }
  } catch (e) {
    console.error('加载 LLM 配置失败:', e)
  }
}

async function saveLLMSettings() {
  if (!llmForm.value.llm_base_url || !llmForm.value.llm_model) {
    ElMessage.error('Base URL 和 Model 必填')
    return
  }
  llmSaving.value = true
  llmTestResult.value = null
  try {
    // 构造 payload，去掉空值
    const payload = {}
    Object.entries(llmForm.value).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) payload[k] = v
    })

    const res = await fetch(`${API_URL}/api/settings/llm`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await res.json()
    if (data.success) {
      ElMessage.success('配置已保存并生效')
      await loadLLMSettings()
    } else {
      ElMessage.error(data.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error('网络错误')
  } finally {
    llmSaving.value = false
  }
}

async function testLLMSettings() {
  if (!llmForm.value.llm_base_url || !llmForm.value.llm_model) {
    ElMessage.error('Base URL 和 Model 必填')
    return
  }
  llmTesting.value = true
  llmTestResult.value = null
  try {
    const res = await fetch(`${API_URL}/api/settings/llm/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: llmForm.value.llm_api_key || undefined,
        base_url: llmForm.value.llm_base_url,
        model: llmForm.value.llm_model
      })
    })
    const data = await res.json()
    if (data.success) {
      llmTestResult.value = { success: true, message: data.data?.message || '连接成功' }
      ElMessage.success('连接成功')
    } else {
      llmTestResult.value = { success: false, message: data.error || '连接失败' }
      ElMessage.error('连接失败')
    }
  } catch (e) {
    llmTestResult.value = { success: false, message: e.message }
    ElMessage.error('网络错误')
  } finally {
    llmTesting.value = false
  }
}

// 获取平台状态
async function loadPlatformStatus() {
  if (!userStore.userId) {
    return
  }
  try {
    const res = await fetch(`${API_URL}/api/platform/status?user_id=${userStore.userId}`)
    const data = await res.json()

    if (data.success) {
      larkStatus.value = data.lark || { enabled: false }

      // 如果已配置，填充表单
      if (data.lark?.enabled) {
        larkConfig.value.receive_id_type = data.lark.receive_id_type
      }
    }
  } catch (e) {
    console.error('加载平台状态失败:', e)
  }
}

// 保存配置
async function saveLarkConfig() {
  if (!userStore.userId) {
    ElMessage.error('用户未登录')
    return
  }

  // 验证
  if (!larkConfig.value.app_id || !larkConfig.value.app_secret || !larkConfig.value.receive_id) {
    ElMessage.error('请填写所有必填项')
    return
  }

  saving.value = true
  testResult.value = null

  try {
    const res = await fetch(`${API_URL}/api/platform/lark/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userStore.userId,
        ...larkConfig.value
      })
    })

    const data = await res.json()

    if (data.success) {
      ElMessage.success('配置已保存')
      editing.value = false
      await loadPlatformStatus()
    } else {
      ElMessage.error(data.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error('网络错误')
  } finally {
    saving.value = false
  }
}

// 测试连接
async function testLark() {
  if (!userStore.userId) {
    ElMessage.error('用户未登录')
    return
  }

  testing.value = true
  testResult.value = null

  try {
    const res = await fetch(`${API_URL}/api/platform/lark/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userStore.userId,
        content: '这是一条测试消息，来自智忆助理！'
      })
    })

    const data = await res.json()
    testResult.value = data

    if (data.success) {
      ElMessage.success('测试消息已发送')
    } else {
      ElMessage.error(data.error || '发送失败')
    }
  } catch (e) {
    ElMessage.error('网络错误')
    testResult.value = { success: false, message: '网络错误' }
  } finally {
    testing.value = false
  }
}

// 删除配置
async function deleteLarkConfig() {
  if (!userStore.userId) {
    ElMessage.error('用户未登录')
    return
  }

  try {
    await ElMessageBox.confirm('确定要删除飞书配置吗？', '确认删除', {
      type: 'warning'
    })

    const res = await fetch(`${API_URL}/api/platform/lark/config?user_id=${userStore.userId}`, {
      method: 'DELETE'
    })

    const data = await res.json()

    if (data.success) {
      ElMessage.success('配置已删除')
      larkStatus.value = { enabled: false }
      larkConfig.value = {
        app_id: '',
        app_secret: '',
        receive_id: '',
        receive_id_type: 'open_id'
      }
    } else {
      ElMessage.error(data.error || '删除失败')
    }
  } catch (e) {
    // 用户取消
  }
}

// 辅助函数
function maskString(str) {
  if (!str || str.length < 8) return '***'
  return str.substring(0, 8) + '...'
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadPlatformStatus()
  loadLLMSettings()
})
</script>

<style scoped>
.settings-container {
  height: 100%;
  overflow-y: auto;
  max-width: 1080px;
  margin: 0 auto;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 22%),
    linear-gradient(180deg, #07111f 0%, #0b1324 50%, #0a1423 100%);
}

h1 {
  margin: 0;
  color: #eef6ff;
}

.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 24px;
  background: rgba(8, 18, 34, 0.78);
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.18);
  backdrop-filter: blur(18px);
  margin-bottom: 18px;
}

.page-subtitle {
  margin-top: 6px;
  color: #8ea3bf;
}

.status-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.summary-label {
  color: #7f93ad;
  font-size: 12px;
}

.setting-section {
  background: linear-gradient(180deg, rgba(13, 24, 40, 0.92) 0%, rgba(10, 19, 33, 0.88) 100%);
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 24px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 18px 36px rgba(2, 6, 23, 0.14);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0;
  color: #eef6ff;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: bold;
}

.status-badge.enabled {
  background: rgba(45, 212, 191, 0.12);
  color: #8cf3e3;
}

.status-badge.disabled {
  background: rgba(127, 156, 191, 0.12);
  color: #a8bfd9;
}

.description {
  color: #9db0c8;
  margin-bottom: 20px;
  line-height: 1.7;
}

.description a {
  color: #67d2fb;
}

.config-form {
  max-width: 500px;
}

.form-section-title {
  margin: 8px 0 16px;
  padding-bottom: 8px;
  color: #cfe0f2;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.4px;
  border-bottom: 1px dashed rgba(127, 156, 191, 0.18);
}

.form-section-title:not(:first-child) {
  margin-top: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #e7f2fd;
}

.form-group .required {
  color: #ff4d4f;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 12px;
  font-size: 14px;
  background: rgba(15, 23, 42, 0.72);
  color: #eef6ff;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #38bdf8;
}

.form-group .help {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #7f93ad;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.config-display {
  background: rgba(14, 28, 42, 0.7);
  border: 1px solid rgba(94, 234, 212, 0.14);
  border-radius: 18px;
  padding: 20px;
}

.info-row {
  display: flex;
  margin-bottom: 12px;
}

.info-row .label {
  width: 100px;
  color: #8ea3bf;
}

.info-row .value {
  color: #eef6ff;
  font-weight: 500;
}

.config-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

button {
  padding: 10px 20px;
  border: 1px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, #38bdf8, #0ea5e9);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn-secondary {
  background: rgba(15, 23, 42, 0.72);
  color: #cfe0f2;
  border-color: rgba(127, 156, 191, 0.14);
}

.btn-secondary:hover {
  color: #67d2fb;
  border-color: rgba(103, 210, 251, 0.36);
}

.btn-danger {
  background: rgba(15, 23, 42, 0.72);
  color: #fb7185;
  border-color: rgba(251, 113, 133, 0.4);
}

.btn-danger:hover {
  background: rgba(251, 113, 133, 0.12);
}

.test-result {
  margin-top: 16px;
  padding: 12px;
  border-radius: 12px;
}

.test-result.success {
  background: rgba(45, 212, 191, 0.08);
  color: #8cf3e3;
  border: 1px solid rgba(94, 234, 212, 0.24);
}

.test-result.error {
  background: rgba(251, 113, 133, 0.08);
  color: #fda4af;
  border: 1px solid rgba(251, 113, 133, 0.24);
}

.help-content {
  color: #9db0c8;
  line-height: 1.7;
}

.help-content h4 {
  color: #eef6ff;
  margin-bottom: 12px;
}

.help-content ol {
  padding-left: 20px;
}

.help-content li {
  margin-bottom: 8px;
}

.help-content ul {
  margin-top: 4px;
  padding-left: 20px;
}

@media (max-width: 960px) {
  .settings-container {
    padding: 12px;
  }

  .view-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .status-summary {
    align-items: flex-start;
  }

  .config-actions,
  .form-actions {
    flex-direction: column;
  }
}
</style>
