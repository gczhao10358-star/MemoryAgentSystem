import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/chat',
    children: [
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/ChatView.vue'),
        meta: { title: '对话', icon: 'ChatRound' }
      },
      {
        path: 'memories',
        name: 'Memories',
        component: () => import('@/views/MemoriesView.vue'),
        meta: { title: '记忆库', icon: 'Collection' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '用户画像', icon: 'UserFilled' }
      },
      {
        path: 'stats',
        name: 'Stats',
        component: () => import('@/views/StatsView.vue'),
        meta: { title: '统计', icon: 'TrendCharts' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '设置', icon: 'Setting' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory('/app'),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  if (!to.meta.public && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    next('/')
  } else {
    next()
  }
})

export default router
