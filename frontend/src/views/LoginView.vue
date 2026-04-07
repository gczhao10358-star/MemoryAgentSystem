<template>
  <div class="login-page">
    <div class="login-shell">
      <section class="hero-panel">
        <div class="hero-badge">Memory workspace</div>
        <div class="hero-brand">
          <div class="hero-mark">
            <el-icon size="34"><Cpu /></el-icon>
          </div>
          <div>
            <h1>智忆助理</h1>
            <p>把聊天、会话上下文、长期记忆和个人偏好放进同一个工作台。</p>
          </div>
        </div>

        <div class="hero-highlights">
          <div class="highlight-card">
            <div class="highlight-title">持续记住上下文</div>
            <div class="highlight-text">每个会话都是独立线程，切换历史不会丢。</div>
          </div>
          <div class="highlight-card">
            <div class="highlight-title">沉淀长期记忆</div>
            <div class="highlight-text">重要事实、任务和文档会逐步形成个人记忆库。</div>
          </div>
          <div class="highlight-card">
            <div class="highlight-title">按你的风格回答</div>
            <div class="highlight-text">回复长度、正式程度、细节深度和主动性都可调整。</div>
          </div>
        </div>

        <div class="hero-footer">
          <div class="feature-item">
            <el-icon><Collection /></el-icon>
            <span>持久记忆</span>
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
      </section>

      <section class="login-card">
        <div class="login-card-head">
          <div class="login-title">开始使用</div>
          <div class="login-subtitle">输入一个名字即可进入你的专属记忆空间。</div>
        </div>

        <el-form @submit.prevent="handleLogin" class="login-form">
          <el-form-item>
            <el-input
              v-model="username"
              placeholder="请输入你的名字"
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
            进入工作台
          </el-button>
        </el-form>

        <div class="login-hints">
          <div class="hint-item">
            <span class="hint-dot"></span>
            相同用户名会回到之前的用户数据
          </div>
          <div class="hint-item">
            <span class="hint-dot"></span>
            这是当前开发版的轻量登录方式
          </div>
        </div>
      </section>
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
  padding: 28px;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.14), transparent 24%),
    radial-gradient(circle at bottom right, rgba(251, 146, 60, 0.08), transparent 22%),
    linear-gradient(180deg, #07111f 0%, #0b1324 52%, #0a1423 100%);
}

.login-shell {
  width: min(1120px, 100%);
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 20px;
  align-items: stretch;
}

.hero-panel,
.login-card {
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 28px;
  background: rgba(8, 18, 34, 0.78);
  box-shadow: 0 24px 60px rgba(2, 6, 23, 0.24);
  backdrop-filter: blur(18px);
}

.hero-panel {
  padding: 32px;
  display: flex;
  flex-direction: column;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  width: fit-content;
  background: rgba(94, 234, 212, 0.08);
  color: #8cf3e3;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-brand {
  display: flex;
  gap: 18px;
  align-items: flex-start;
  margin-top: 22px;

  h1 {
    margin: 0;
    font-size: 42px;
    line-height: 1.05;
    color: #f3f9ff;
  }

  p {
    margin-top: 12px;
    max-width: 520px;
    color: #9db0c8;
    font-size: 16px;
    line-height: 1.75;
  }
}

.hero-mark {
  width: 72px;
  height: 72px;
  border-radius: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.18), rgba(14, 165, 233, 0.2));
  color: #67e8f9;
  flex-shrink: 0;
}

.hero-highlights {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  margin-top: 34px;
}

.highlight-card {
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid rgba(127, 156, 191, 0.12);
  background: linear-gradient(180deg, rgba(13, 24, 40, 0.84) 0%, rgba(10, 19, 33, 0.76) 100%);
}

.highlight-title {
  color: #eef6ff;
  font-size: 16px;
  font-weight: 700;
}

.highlight-text {
  margin-top: 6px;
  color: #8ea3bf;
  font-size: 14px;
  line-height: 1.7;
}

.hero-footer {
  margin-top: auto;
  padding-top: 22px;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.login-card {
  padding: 32px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.login-card-head {
  margin-bottom: 28px;
}

.login-title {
  color: #f3f9ff;
  font-size: 28px;
  font-weight: 700;
}

.login-subtitle {
  margin-top: 8px;
  color: #8ea3bf;
  line-height: 1.7;
}

.login-form {
  :deep(.el-form-item) {
    margin-bottom: 16px;
  }

  :deep(.el-input__wrapper) {
    min-height: 54px;
    background: rgba(15, 23, 42, 0.72);
    box-shadow: none;
    border: 1px solid rgba(127, 156, 191, 0.14);
  }

  :deep(.el-input__wrapper.is-focus) {
    border-color: rgba(94, 234, 212, 0.28);
  }

  :deep(.el-input__inner) {
    color: #eef6ff;

    &::placeholder {
      color: #6f88a7;
    }
  }
}

.login-btn {
  width: 100%;
  height: 54px;
  background: linear-gradient(135deg, #38bdf8, #0ea5e9);
  border: none;
  font-weight: 700;
  border-radius: 16px;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 24px rgba(14, 165, 233, 0.28);
  }
}

.login-hints {
  margin-top: 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hint-item {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #8ea3bf;
  font-size: 13px;
}

.hint-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #5eead4;
  flex-shrink: 0;
}

.feature-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(127, 156, 191, 0.12);
  background: rgba(13, 24, 40, 0.7);
  color: #cfe0f2;
  font-size: 13px;

  .el-icon {
    color: #5eead4;
    font-size: 16px;
  }
}

@media (max-width: 960px) {
  .login-page {
    padding: 12px;
  }

  .login-shell {
    grid-template-columns: 1fr;
  }

  .hero-panel,
  .login-card {
    padding: 22px;
  }

  .hero-brand {
    flex-direction: column;

    h1 {
      font-size: 34px;
    }
  }
}
</style>
