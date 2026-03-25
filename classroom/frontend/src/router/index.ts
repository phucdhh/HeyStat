import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory('/classroom/'),
  routes: [
    // ── Auth ──────────────────────────────────────────────────────
    { path: '/login', name: 'Login', component: () => import('@/pages/LoginPage.vue'), meta: { guest: true } },
    { path: '/register', name: 'Register', component: () => import('@/pages/RegisterPage.vue'), meta: { guest: true } },
    { path: '/forgot-password', name: 'ForgotPassword', component: () => import('@/pages/ForgotPasswordPage.vue'), meta: { guest: true } },
    { path: '/reset-password', name: 'ResetPassword', component: () => import('@/pages/ResetPasswordPage.vue'), meta: { guest: true } },

    // ── Authenticated layout ──────────────────────────────────────
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'Dashboard', component: () => import('@/pages/DashboardPage.vue') },
        { path: 'classes', name: 'ClassList', component: () => import('@/pages/ClassListPage.vue') },
        { path: 'classes/:classId', name: 'ClassDetail', component: () => import('@/pages/ClassDetailPage.vue') },
        { path: 'classes/:classId/assignments/:assignmentId', name: 'AssignmentDetail', component: () => import('@/pages/AssignmentDetailPage.vue') },
        { path: 'classes/:classId/assignments/:assignmentId/submit', name: 'SubmitWork', component: () => import('@/pages/SubmitWorkPage.vue') },
        { path: 'classes/:classId/lessons/:lessonId', name: 'LessonView', component: () => import('@/pages/LessonViewPage.vue') },
        { path: 'classes/:classId/quizzes/new', name: 'QuizBuilder', component: () => import('@/pages/QuizBuilderPage.vue'), meta: { requiresTeacher: true } },
        { path: 'classes/:classId/quizzes/:quizId', name: 'QuizView', component: () => import('@/pages/QuizViewPage.vue') },
        { path: 'files', name: 'MyFiles', component: () => import('@/pages/MyFilesPage.vue') },
        { path: 'teacher', name: 'TeacherDashboard', component: () => import('@/pages/TeacherDashboardPage.vue'), meta: { requiresTeacher: true } },
        { path: 'admin', name: 'AdminPanel', component: () => import('@/pages/AdminPanelPage.vue'), meta: { requiresAdmin: true } },
        { path: 'profile', name: 'Profile', component: () => import('@/pages/ProfilePage.vue') },
      ],
    },

    // ── Public shared file view ───────────────────────────────────
    { path: '/shared/:token', name: 'SharedView', component: () => import('@/pages/SharedViewPage.vue') },

    // ── 404 ───────────────────────────────────────────────────────
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.guest && auth.isLoggedIn) return { name: 'Dashboard' }
  if (to.meta.requiresAuth && !auth.isLoggedIn) return { name: 'Login', query: { redirect: to.fullPath } }
  if (to.meta.requiresTeacher && !auth.isTeacher) return { name: 'Dashboard' }
  if (to.meta.requiresAdmin && !auth.isAdmin) return { name: 'Dashboard' }
})

export default router
