<template>
  <div class="settings-container">
    <h1>设置</h1>

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

const userId = localStorage.getItem('memorymate_user_id') || 'test'
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

// 获取平台状态
async function loadPlatformStatus() {
  try {
    const res = await fetch(`${API_URL}/api/platform/status?user_id=${userId}`)
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
        user_id: userId,
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
  testing.value = true
  testResult.value = null

  try {
    const res = await fetch(`${API_URL}/api/platform/lark/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
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
  try {
    await ElMessageBox.confirm('确定要删除飞书配置吗？', '确认删除', {
      type: 'warning'
    })

    const res = await fetch(`${API_URL}/api/platform/lark/config?user_id=${userId}`, {
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
})
</script>

<style scoped>
.settings-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

h1 {
  margin-bottom: 30px;
  color: #333;
}

.setting-section {
  background: white;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0;
  color: #333;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
}

.status-badge.enabled {
  background: #e6f7e6;
  color: #52c41a;
}

.status-badge.disabled {
  background: #f5f5f5;
  color: #999;
}

.description {
  color: #666;
  margin-bottom: 20px;
}

.description a {
  color: #1890ff;
}

.config-form {
  max-width: 500px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #333;
}

.form-group .required {
  color: #ff4d4f;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #1890ff;
}

.form-group .help {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #999;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.config-display {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 4px;
  padding: 20px;
}

.info-row {
  display: flex;
  margin-bottom: 12px;
}

.info-row .label {
  width: 100px;
  color: #666;
}

.info-row .value {
  color: #333;
  font-weight: 500;
}

.config-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

button {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: #1890ff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #40a9ff;
}

.btn-secondary {
  background: white;
  color: #666;
  border: 1px solid #d9d9d9;
}

.btn-secondary:hover {
  color: #1890ff;
  border-color: #1890ff;
}

.btn-danger {
  background: white;
  color: #ff4d4f;
  border: 1px solid #ff4d4f;
}

.btn-danger:hover {
  background: #ff4d4f;
  color: white;
}

.test-result {
  margin-top: 16px;
  padding: 12px;
  border-radius: 4px;
}

.test-result.success {
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.test-result.error {
  background: #fff2f0;
  color: #ff4d4f;
  border: 1px solid #ffccc7;
}

.help-content {
  color: #666;
}

.help-content h4 {
  color: #333;
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
</style>
