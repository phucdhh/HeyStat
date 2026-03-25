<template>
  <div>
    <div v-if="loading">Đang tải…</div>
    <div v-else-if="assignment">
      <RouterLink :to="`/classes/${classId}`" class="back">← Quay lại lớp</RouterLink>
      <h1>{{ assignment.title }}</h1>
      <p class="desc">{{ assignment.description }}</p>
      <div class="meta-row">
        <span>Hạn nộp: <strong>{{ assignment.deadline ? new Date(assignment.deadline).toLocaleString('vi-VN') : '—' }}</strong></span>
        <span>Loại: <strong>{{ assignment.assignment_type }}</strong></span>
        <span v-if="assignment.max_score">Điểm tối đa: <strong>{{ assignment.max_score }}</strong></span>
        <span v-if="assignment.group_size > 1">Nhóm tối đa: <strong>{{ assignment.group_size }} người</strong></span>
      </div>

      <!-- Group management (for group assignments, non-exam) -->
      <div v-if="assignment.group_size > 1 && assignment.assignment_type !== 'exam'" class="section">
        <div class="section-header">
          <h3>Nhóm làm bài</h3>
        </div>

        <!-- Already in a group -->
        <div v-if="myGroup" class="group-box">
          <p><strong>Nhóm:</strong> {{ myGroup.group_name || `Nhóm ${myGroup.id.slice(0,6)}` }}</p>
          <p><strong>Vai trò:</strong>
            <span :class="myGroup.leader_id === currentUserId ? 'badge-writer' : 'badge-observer'">
              {{ myGroup.leader_id === currentUserId ? 'Writer (chỉnh sửa)' : 'Observer (xem)' }}
            </span>
          </p>
          <div class="member-list">
            <div v-for="m in myGroup.members" :key="m.user_id" class="member-row">
              <span>{{ m.full_name || m.user_id }}</span>
              <button
                v-if="myGroup.leader_id === currentUserId && m.user_id !== currentUserId"
                class="small secondary"
                @click="transferLeader(m.user_id)"
              >Chuyển quyền Writer</button>
            </div>
          </div>
        </div>

        <!-- Not in a group yet -->
        <div v-else>
          <div class="group-create">
            <input v-model="newGroupName" placeholder="Tên nhóm (tuỳ chọn)" class="input" />
            <button @click="createGroup">+ Tạo nhóm mới</button>
          </div>
          <div v-if="groups.length" class="group-join-list">
            <p style="margin:0.5rem 0 0.3rem;font-weight:600;">Hoặc tham gia nhóm có sẵn:</p>
            <div v-for="g in groups" :key="g.id" class="group-join-row">
              <span>{{ g.group_name || `Nhóm ${g.id.slice(0,6)}` }}</span>
              <button class="small" @click="joinGroup(g.id)">Tham gia</button>
            </div>
          </div>
          <p v-if="groupError" class="error">{{ groupError }}</p>
        </div>
      </div>

      <!-- Class files available to copy -->
      <div v-if="classFiles.length" class="section">
        <h3>Tệp của lớp</h3>
        <div v-for="f in classFiles" :key="f.id" class="file-row">
          <span>{{ f.filename }}</span>
          <a :href="`/api/v1/classes/${classId}/files/${f.id}/download`" target="_blank">Tải xuống</a>
        </div>
      </div>

      <!-- My submissions -->
      <div class="section">
        <div class="section-header">
          <h3>Bài nộp của tôi</h3>
          <RouterLink v-if="canSubmit" :to="`/classes/${classId}/assignments/${assignmentId}/submit`" class="btn">
            {{ mySubmissions.length ? 'Nộp lại' : 'Nộp bài' }}
          </RouterLink>
        </div>
        <div v-if="mySubmissions.length === 0" class="empty">Chưa có bài nộp.</div>
        <div v-for="s in mySubmissions" :key="s.id" class="sub-row">
          <span>{{ new Date(s.submitted_at).toLocaleString('vi-VN') }}</span>
          <span :class="`status-${s.status}`">{{ s.status }}</span>
          <span v-if="s.score != null">Điểm: {{ s.score }}</span>
          <span v-if="s.is_final" class="final">✓ Bài cuối</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'

const route = useRoute()
const classId = route.params.classId as string
const assignmentId = route.params.assignmentId as string
const auth = useAuthStore()

const loading = ref(true)
const assignment = ref<any>(null)
const classFiles = ref<any[]>([])
const mySubmissions = ref<any[]>([])
const groups = ref<any[]>([])
const myGroup = ref<any>(null)
const newGroupName = ref('')
const groupError = ref('')

const currentUserId = computed(() => auth.user?.id ?? '')

const canSubmit = computed(() => {
  if (!assignment.value) return false
  if (assignment.value.deadline && new Date(assignment.value.deadline) < new Date()) return false
  if (!assignment.value.allow_resubmit && mySubmissions.value.length > 0) return false
  // For group assignments, must be in a group to submit
  if (assignment.value.group_size > 1 && assignment.value.assignment_type !== 'exam' && !myGroup.value) return false
  return true
})

async function loadGroups() {
  if (!assignment.value || assignment.value.group_size <= 1 || assignment.value.assignment_type === 'exam') return
  try {
    const { data } = await api.get(`/classes/${classId}/assignments/${assignmentId}/groups`)
    groups.value = data
    myGroup.value = data.find((g: any) =>
      g.members?.some((m: any) => m.user_id === currentUserId.value)
    ) || null
  } catch {}
}

async function createGroup() {
  groupError.value = ''
  try {
    const { data } = await api.post(`/classes/${classId}/assignments/${assignmentId}/groups`, {
      group_name: newGroupName.value || null,
    })
    await loadGroups()
    newGroupName.value = ''
  } catch (e: any) {
    groupError.value = e?.response?.data?.detail ?? 'Không thể tạo nhóm'
  }
}

async function joinGroup(groupId: string) {
  groupError.value = ''
  try {
    await api.post(`/classes/${classId}/assignments/${assignmentId}/groups/join`, { group_id: groupId })
    await loadGroups()
  } catch (e: any) {
    groupError.value = e?.response?.data?.detail ?? 'Không thể tham gia nhóm'
  }
}

async function transferLeader(userId: string) {
  if (!myGroup.value) return
  if (!confirm('Chuyển quyền Writer cho thành viên này?')) return
  try {
    await api.patch(`/classes/${classId}/assignments/${assignmentId}/groups/${myGroup.value.id}/leader`, {
      new_leader_id: userId,
    })
    await loadGroups()
  } catch (e: any) {
    groupError.value = e?.response?.data?.detail ?? 'Không thể chuyển quyền'
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const [aRes, fRes, sRes] = await Promise.all([
      api.get(`/classes/${classId}/assignments/${assignmentId}`),
      api.get(`/classes/${classId}/files`),
      api.get(`/assignments/${assignmentId}/submissions/my`),
    ])
    assignment.value = aRes.data
    classFiles.value = fRes.data
    mySubmissions.value = sRes.data
    await loadGroups()
  } finally { loading.value = false }
})
</script>

<style scoped>
.back { color: #666; text-decoration: none; font-size: 0.9rem; }
h1 { margin: 0.5rem 0; }
.desc { color: #555; margin-bottom: 1rem; }
.meta-row { display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.9rem; color: #555; margin-bottom: 1.5rem; }
.section { margin-bottom: 1.5rem; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.section h3 { margin: 0; }
.btn { padding: 0.4rem 0.9rem; background: #1a1a2e; color: #fff; border-radius: 4px; text-decoration: none; font-size: 0.9rem; }
.file-row, .sub-row { display: flex; gap: 1rem; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; font-size: 0.9rem; }
.file-row a { color: #1a6ef5; }
.status-submitted { color: #e67e22; } .status-graded { color: #27ae60; } .status-draft { color: #888; }
.final { color: green; font-weight: 700; }
.empty { color: #888; padding: 0.5rem 0; }

/* Group UI */
.group-box { background: #f0f4ff; border-radius: 6px; padding: 1rem; }
.group-box p { margin: 0.3rem 0; font-size: 0.9rem; }
.member-list { margin-top: 0.5rem; }
.member-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0; font-size: 0.88rem; }
.group-create { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.input { flex: 1; padding: 0.4rem 0.6rem; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9rem; }
.group-join-list { margin-top: 0.5rem; }
.group-join-row { display: flex; align-items: center; gap: 0.8rem; padding: 0.3rem 0; font-size: 0.9rem; }
button { padding: 0.5rem 1rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.small { padding: 0.3rem 0.6rem; font-size: 0.8rem; }
.secondary { background: #f0f0f0; color: #333; }
.badge-writer { background: #27ae60; color: #fff; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-observer { background: #e67e22; color: #fff; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.error { color: red; font-size: 0.85rem; margin-top: 0.3rem; }
</style>

