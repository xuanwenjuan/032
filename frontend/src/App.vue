<template>
  <div class="app-container">
    <header class="app-header">
      <div>
        <h1>🧠 MIT脑水肿监测系统</h1>
        <div class="subtitle">基于磁感应断层成像的无创脑水肿实时监测平台</div>
      </div>
      <button class="btn btn-secondary" @click="showTaskList = true">
        📋 历史任务 ({{ tasks.length }})</button>
    </header>

    <main class="app-main">
      <section class="panel">
        <div class="panel-title">
          <span>🖌️ 脑部模型画布 (16×16)</span>
          <div class="toolbar-small">
            <span style="font-size:12px;color:#94a3b8;margin-right:8px">画笔粗细:</span>
            <el-select v-model="brushSize" size="small" style="width:80px">
              <el-option label="1px" :value="1" />
              <el-option label="2px" :value="2" />
              <el-option label="3px" :value="3" />
            </el-select>
          </div>
        </div>
        <div class="canvas-wrapper">
          <canvas
            ref="canvasRef"
            class="brain-canvas"
            :width="canvasSize"
            :height="canvasSize"
            @mousedown="startDraw"
            @mousemove="draw"
            @mouseup="endDraw"
            @mouseleave="endDraw"
          ></canvas>
        </div>
      </section>

      <section class="panel">
        <div class="panel-title">
          <span>📊 电导率分布重建</span>
          <span v-if="simulationRunning" style="font-size:12px;color:#fbbf24">
            ⏳ 正在计算...
          </span>
        </div>
        <div class="chart-container">
          <v-chart class="chart" :option="chartOption" autoresize />
        </div>
      </section>

      <div class="toolbar">
        <div class="toolbar-left">
          <div class="input-group">
            <label class="input-label">仿真模式</label>
            <el-select v-model="simMode" size="small" style="width:140px">
              <el-option label="2D 快速仿真" value="2d" />
              <el-option label="3D 高精度仿真" value="3d" />
            </el-select>
          </div>

          <div class="input-group" v-if="simMode === '3d'">
            <label class="input-label">3D网格 Z轴</label>
            <el-input-number v-model="grid3dZ" size="small" :min="4" :max="32" style="width:120px" />
          </div>

          <div class="input-group">
            <label class="input-label">电导率倍数</label>
            <el-input-number v-model="conductivityFactor" size="small" :min="1.1" :max="5" :step="0.1" style="width:120px" />
          </div>
        </div>

        <div class="toolbar-right">
          <button class="btn btn-secondary" @click="clearCanvas">🗑️ 清除画布</button>
          <button
            class="btn btn-danger" @click="clearDrawnMask">🧹 清除绘制</button>
          <button
            class="btn btn-primary" :disabled="simulationRunning" @click="runSimulation">
            {{ simulationRunning ? '仿真中...' : '🚀 开始仿真' }}
          </button>
          <button
            v-if="simMode === '3d'"
            class="btn btn-warning"
            :disabled="simulationRunning"
            @click="run3DSimulation"
          >
            {{ simulationRunning ? '仿真中...' : '⚡ 3D仿真 (WebSocket)' }}
          </button>
        </div>
      </div>
    </main>

    <div v-if="showTaskList" class="sidebar-overlay" @click="showTaskList = false"></div>
    <aside :class="['sidebar', showTaskList && 'open']">
      <div class="sidebar-header">
        <h3>📋 仿真任务历史</h3>
        <button class="close-btn" @click="showTaskList = false">×</button>
      </div>

      <div v-if="tasks.length === 0" class="empty-state">暂无任务记录</div>

      <div v-for="task in tasks" :key="task._id" class="task-item">
        <div class="task-item-header">
          <strong style="font-size:14px;">{{ task.task_type }} 仿真</strong>
          <span :class="['status-badge', 'status-' + task.status]">
            {{ getStatusText(task.status) }}
          </span>
        </div>
        <div class="task-meta">ID: {{ task._id?.slice(0, 12) }}...</div>
        <div class="task-meta">{{ formatTime(task.created_at) }}</div>

        <div v-if="task.reconstructed_image_base64" style="margin-top:8px;text-align:center">
          <img
            :src="'data:image/png;base64,' + task.reconstructed_image_base64"
            style="max-width:100%;border-radius:4px;border:1px solid #334155"
          />
        </div>

        <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-secondary" size="small" @click="viewTask(task)">查看</button>
          <button class="btn btn-danger" size="small" @click="deleteTask(task._id)">删除</button>
        </div>

        <div class="section-title">临床注释 ({{ task.clinical_notes?.length || 0 }})</div>

        <div v-if="task.clinical_notes?.length > 0">
          <div v-for="(note, idx) in task.clinical_notes" :key="idx" class="note-item">
            <div class="note-doctor">👨‍⚕️ {{ note.doctor_name }}</div>
            <div class="note-text">{{ note.note }}</div>
            <div class="note-time">{{ formatTime(note.timestamp) }}</div>
          </div>
        </div>

        <div style="margin-top:12px">
          <div class="input-group">
            <label class="input-label">医生姓名</label>
            <el-input v-model="newNote.doctor_name" size="small" placeholder="输入医生姓名" />
          </div>
          <div class="input-group" style="margin-top:8px">
            <label class="input-label">注释内容</label>
            <el-input v-model="newNote.note" type="textarea" :rows="2" size="small" placeholder="输入临床注释..." />
          </div>
          <button
            class="btn btn-success"
            style="margin-top:8px;width:100%"
            @click="addNote(task._id)"
            :disabled="!newNote.doctor_name || !newNote.note"
          >
            💾 添加注释
          </button>
        </div>

        <div v-if="simulationProgress[task._id]" class="progress-bar">
          <div class="progress-fill" :style="{width: simulationProgress[task._id] + '%'}"></div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>import { ref, onMounted, reactive, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart, VisualMapComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { simulationApi, taskApi } from './api'

use([CanvasRenderer, HeatmapChart, VisualMapComponent, TooltipComponent])

const GRID_SIZE = 16
const CELL_SIZE = 28
const canvasSize = GRID_SIZE * CELL_SIZE

const canvasRef = ref(null)
const isDrawing = ref(false)
const drawnMask = ref(Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(0)))
const brushSize = ref(2)
const conductivityFactor = ref(2.0)
const simMode = ref('2d')
const grid3dZ = ref(16)
const simulationRunning = ref(false)
const showTaskList = ref(false)
const tasks = ref([])
const newNote = reactive({ doctor_name: '', note: '' })
const simulationProgress = ref({})

let brainPath = []
let ctx = null
let ws = null
const clientId = 'client-' + Math.random().toString(36).slice(2, 10)

const chartData = ref([])

const chartOption = computed(() => ({
  tooltip: { position: 'top' },
  grid: { left: '10%', right: '10%', top: '5%', bottom: '15%' },
  xAxis: {
    type: 'category', show: false, splitArea: { show: true } },
  yAxis: {
    type: 'category', show: false, splitArea: { show: true } },
  visualMap: {
    min: 0,
    max: 1,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: '0%',
    inRange: {
      color: ['#0c1929', '#1e3a5f', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe']
    },
    textStyle: { color: '#94a3b8' }
  },
  series: [{
    name: '电导率',
    type: 'heatmap',
    data: chartData.value.length ? chartData.value : generateEmptyData(),
    label: { show: false },
    emphasis: {
      itemStyle: { borderColor: '#60a5fa', borderWidth: 1 }
    }
  }]
}))

function generateEmptyData() {
  const data = []
  for (let i = 0; i < GRID_SIZE; i++) {
    for (let j = 0; j < GRID_SIZE; j++) {
      const cx = GRID_SIZE / 2
      const cy = GRID_SIZE / 2
      const r = GRID_SIZE / 2 - 0.5
      const dist = Math.sqrt((i - cx + 0.5) ** 2 + (j - cy + 0.5) ** 2)
      if (dist <= r) {
        data.push([j, i, 0])
      }
    }
  }
  return data
}

function computeBrainPath() {
  brainPath = []
  for (let i = 0; i < GRID_SIZE; i++) {
    for (let j = 0; j < GRID_SIZE; j++) {
      const cx = GRID_SIZE / 2
      const cy = GRID_SIZE / 2
      const r = GRID_SIZE / 2 - 0.5
      const dist = Math.sqrt((i - cx + 0.5) ** 2 + (j - cy + 0.5) ** 2)
      if (dist <= r) {
        brainPath.push([i, j])
      }
    }
  }
}

function drawBrainGrid() {
  if (!ctx) return
  ctx.fillStyle = '#0f172a'
  ctx.fillRect(0, 0, canvasSize, canvasSize)

  brainPath.forEach(([i, j]) => {
    if (drawnMask.value[i][j] > 0) {
      ctx.fillStyle = 'rgba(239, 68, 68, 0.85)'
    } else {
      ctx.fillStyle = '#1e293b'
    }
    ctx.fillRect(j * CELL_SIZE, i * CELL_SIZE, CELL_SIZE - 1, CELL_SIZE - 1)
  })

  ctx.strokeStyle = '#334155'
  ctx.lineWidth = 0.5
  for (let i = 0; i <= GRID_SIZE; i++) {
    ctx.beginPath()
    ctx.moveTo(i * CELL_SIZE, 0)
    ctx.lineTo(i * CELL_SIZE, canvasSize)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(0, i * CELL_SIZE)
    ctx.lineTo(canvasSize, i * CELL_SIZE)
    ctx.stroke()
  }
}

function startDraw(e) {
  isDrawing.value = true
  draw(e)
}

function draw(e) {
  if (!isDrawing.value || !canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  const scaleX = canvasRef.value.width / rect.width
  const scaleY = canvasRef.value.height / rect.height
  const x = Math.floor((e.clientX - rect.left) * scaleX / CELL_SIZE)
  const y = Math.floor((e.clientY - rect.top) * scaleY / CELL_SIZE)
  const bs = brushSize.value
  for (let di = -bs + 1; di < bs; di++) {
    for (let dj = -bs + 1; dj < bs; dj++) {
      const ni = y + di
      const nj = x + dj
      if (ni >= 0 && ni < GRID_SIZE && nj >= 0 && nj < GRID_SIZE) {
        const isBrain = brainPath.some(([bi, bj]) => bi === ni && bj === nj)
        if (isBrain) {
          drawnMask.value[ni][nj] = 1
        }
      }
    }
  }
  drawBrainGrid()
}

function endDraw() {
  isDrawing.value = false
}

function clearDrawnMask() {
  drawnMask.value = Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(0))
  drawBrainGrid()
}

function clearCanvas() {
  clearDrawnMask()
  chartData.value = []
}

async function runSimulation() {
  simulationRunning.value = true
  try {
    const edemaRegions = []
    const resp = await simulationApi.simulate2D({
      grid_size: GRID_SIZE,
      edema_regions: edemaRegions,
      drawn_mask: drawnMask.value
    })

    const recon = resp.data.reconstructed_conductivity
    updateChartData(recon)
    ElMessage.success('2D仿真完成!')
    await loadTasks()
  } catch (err) {
    ElMessage.error('仿真失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    simulationRunning.value = false
  }
}

function updateChartData(matrix) {
  const data = []
  for (let i = 0; i < matrix.length; i++) {
    for (let j = 0; j < matrix[i].length; j++) {
      data.push([j, i, matrix[i][j]])
    }
  }
  chartData.value = data
}

async function run3DSimulation() {
  if (!ws) {
    initWebSocket()
  }
  simulationRunning.value = true
  try {
    const edemaRegions = []
    ws.send(JSON.stringify({
      type: 'start_3d_simulation',
      edema_regions: edemaRegions,
      nx: 32,
      ny: 32,
      nz: grid3dZ.value
    }))
    ElMessage.info('3D仿真任务已提交，请等待结果...')
  } catch (err) {
    simulationRunning.value = false
  }
}

function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/simulation/${clientId}`
  ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.type === 'progress') {
      simulationProgress.value[msg.task_id] = msg.progress
    } else if (msg.type === 'simulation_complete') {
      simulationRunning.value = false
      simulationProgress.value[msg.task_id] = 100
      updateChartData(msg.mid_slice)
      ElMessage.success('3D仿真完成!')
      loadTasks()
    } else if (msg.type === 'task_created') {
      simulationProgress.value[msg.task_id] = 0
    } else if (msg.type === 'error') {
      simulationRunning.value = false
      ElMessage.error(msg.message)
    }
  }

  ws.onerror = () => {
    ElMessage.error('WebSocket连接失败')
    simulationRunning.value = false
  }
}

async function loadTasks() {
  try {
    const resp = await taskApi.listTasks(50)
    tasks.value = resp.data.tasks
  } catch (e) {
    console.error(e)
  }
}

async function viewTask(task) {
  if (task.reconstruction_data?.reconstructed_conductivity) {
    updateChartData(task.reconstruction_data.reconstructed_conductivity)
  } else if (task.reconstruction_data?.mid_slice) {
    updateChartData(task.reconstruction_data.mid_slice)
  }
  showTaskList.value = false
}

async function deleteTask(taskId) {
  try {
    await taskApi.deleteTask(taskId)
    ElMessage.success('删除成功')
    loadTasks()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function addNote(taskId) {
  try {
    await taskApi.addNote(taskId, { ...newNote })
    ElMessage.success('注释已添加')
    newNote.doctor_name = ''
    newNote.note = ''
    loadTasks()
  } catch (e) {
    ElMessage.error('添加失败')
  }
}

function getStatusText(status) {
  const map = { completed: '已完成', running: '运行中', pending: '等待中', failed: '失败', queued: '队列中' }
  return map[status] || status
}

function formatTime(t) {
  if (!t) return ''
  try {
    return new Date(t).toLocaleString('zh-CN')
  } catch { return '' }
}

onMounted(() => {
  ctx = canvasRef.value?.getContext('2d')
  computeBrainPath()
  drawBrainGrid()
  loadTasks()
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}

.toolbar-small {
  display: flex;
  align-items: center;
}
</style>
