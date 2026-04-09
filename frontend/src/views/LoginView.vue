<template>
  <div class="login-page">
    <div class="login-box">
      <div class="logo">
        <el-icon size="64" color="#6366f1"><Cpu /></el-icon>
        <h1>智忆助理</h1>
        <p>MemoryMate - 您的个性化记忆助手</p>
      </div>

      <el-form @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="请输入您的名字"
            size="large"
            :prefix-icon="User"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          :loading="userStore.isLoading"
          @click="handleLogin"
          class="login-btn"
        >
          <el-icon><Right /></el-icon>
          开始对话
        </el-button>
      </el-form>

      <div class="features">
        <div class="feature-item">
          <el-icon><Collection /></el-icon>
          <span>长期记忆</span>
        </div>
        <div class="feature-item">
          <el-icon><UserFilled /></el-icon>
          <span>用户画像</span>
        </div>
        <div class="feature-item">
          <el-icon><Search /></el-icon>
          <span>智能检索</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Right, Cpu, Collection, UserFilled, Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const username = ref('')

async function handleLogin() {
  if (!username.value.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }

  const result = await userStore.createUser(username.value.trim())
  if (result.success) {
    ElMessage.success('欢迎回来！')
    router.push('/')
  } else {
    ElMessage.error(result.error || '登录失败')
  }
}
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
  padding: 20px;
}

.login-box {
  width: 100%;
  max-width: 420px;
  text-align: center;
}

.logo {
  margin-bottom: 40px;

  h1 {
    font-size: 36px;
    font-weight: 700;
    margin: 16px 0 8px;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  p {
    color: #94a3b8;
    font-size: 16px;
  }
}

.login-form {
  background: rgba(30, 41, 59, 0.8);
  backdrop-filter: blur(10px);
  padding: 32px;
  border-radius: 16px;
  border: 1px solid rgba(71, 85, 105, 0.5);
  margin-bottom: 32px;

  :deep(.el-input__wrapper) {
    background: rgba(51, 65, 85, 0.5);
    box-shadow: none;
    border: 1px solid #475569;

    &.is-focus {
      border-color: #6366f1;
    }
  }

  :deep(.el-input__inner) {
    color: #f1f5f9;

    &::placeholder {
      color: #64748b;
    }
  }
}

.login-btn {
  width: 100%;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border: none;
  font-weight: 600;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  }
}

.features {
  display: flex;
  justify-content: center;
  gap: 32px;
  flex-wrap: wrap;
}

.feature-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 14px;

  .el-icon {
    font-size: 24px;
    color: #6366f1;
  }
}
</style>
