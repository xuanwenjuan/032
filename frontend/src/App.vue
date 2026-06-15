<template>
  <div class="app-container">
    <header class="app-header">
      <div>
        <h1>🧠 MIT脑水肿监测系统 (增强版)</h1>
        <div class="subtitle">多频激励 · 时间序列监测 · 扩展速度预测</div>
      </div>
      <div style="display:flex;gap:10px;align-items:center">
        <el-tag type="success" effect="dark" v-if="backendStatus">后端已连接</el-tag>
        <el-tag type="info" effect="dark">{{ modeText }}</el-tag>
        <button class="btn btn-secondary" @click="showTaskList = true">
          📋 历史任务 ({{ tasks.length }})</button>
      </div>
    </header>

    <main class="app-main-v2">
      <div class="row-section">
        <section class="panel canvas-panel">
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

        <section class="panel results-panel">
          <div class="panel-title">
            <span>📊 {{ resultPanelTitle }}</span>
            <span v-if="simulationRunning" style="font-size:12px;color:#fbbf24">
              ⏳ {{ runningText }}
            </span>
          </div>

          <div v-if="simMode === '2d'" class="chart-container">
            <v-chart class="chart" :option="singleChartOption" autoresize />
          </div>

          <div v-else-if="simMode === 'multifreq'" class="multifreq-grid">
            <div class="freq-cell" v-for="freq in ['1kHz', '10kHz', '100kHz']" :key="freq">
              <div class="freq-title">{{ freq }}</div>
              <div class="freq-info" v-if="coleColeParams">
                σ_水肿: {{ coleColeParams.edema_conductivity[freq].toFixed(4) }} S/m
              </div>
              <v-chart class="chart-sm" :option="getFreqChartOption(freq)" autoresize />
            </div>
            <div class="freq-cell fused-cell">
              <div class="freq-title">🎨 融合视图 (加权)</div>
              <div class="freq-info">权重: 1kHz(0.2) 10kHz(0.5) 100kHz(0.3)</div>
              <v-chart class="chart-sm" :option="fusedChartOption" autoresize />
            </div>
          </div>

          <div v-else-if="simMode === 'timeseries'" class="timeseries-container">
            <div class="ts-chart">
              <v-chart class="chart" :option="timeSeriesOption" autoresize />
            </div>
            <div class="ts-prediction" v-if="predictionData">
              <div class="pred-card" :class="'sev-' + predictionData.severity_level.toLowerCase()">
                <div class="pred-title">🚨 水肿扩展预测 (线性回归)</div>
                <div class="pred-stats">
                  <div class="stat-item">
                    <div class="stat-label">电导率斜率</div>
                    <div class="stat-val">{{ predictionData.conductivity_slope_per_min }} /min</div>
                    <div class="stat-sub">R² = {{ predictionData.conductivity_r2 }}</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-label">体积斜率</div>
                    <div class="stat-val">{{ predictionData.volume_slope_per_min }} 像素/min</div>
                    <div class="stat-sub">R² = {{ predictionData.volume_r2 }}</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-label">30min预测</div>
                    <div class="stat-val">{{ predictionData.predicted_30min_conductivity }}</div>
                    <div class="stat-sub">{{ predictionData.predicted_30min_volume_pixels }} 像素</div>
                  </div>
                </div>
                <div class="severity-tag" :class="'sev-tag-' + predictionData.severity_level.toLowerCase()">
                  {{ severityText }}
                </div>
                <div class="pred-warnings">
                  <div v-for="(w, i) in warnings" :key="i" class="warn-item">{{ w }}</div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="toolbar-v2">
        <div class="toolbar-group">
          <label class="input-label">工作模式</label>
          <el-radio-group v-model="simMode" size="default">
            <el-radio-button value="2d">标准2D</el-radio-button>
            <el-radio-button value="multifreq">多频激励</el-radio-button>
            <el-radio-button value="timeseries">时间序列监测</el-radio-button>
            <el-radio-button value="3d">3D高精度</el-radio-button>
          </el-radio-group>
        </div>

        <div class="toolbar-group" v-if="simMode === 'timeseries'">
          <label class="input-label">扫描参数</label>
          <div class="param-row">
            <span class="param-text">次数:</span>
            <el-input-number v-model="numScans" size="small" :min="3" :max="20" style="width:100px" />
            <span class="param-text">间隔:</span>
            <el-input-number v-model="intervalSec" size="small" :min="10" :max="120" style="width:100px" />
            <span class="param-text">秒</span>
          </div>
        </div>

        <div class="toolbar-group">
          <label class="input-label">控制</label>
          <div class="btn-row">
            <button class="btn btn-secondary" @click="clearCanvas">🗑️ 清除画布</button>
            <button class="btn btn-danger" @click="clearDrawnMask">🧹 清除绘制</button>
            <button
              class="btn btn-primary"
              :disabled="simulationRunning"
              @click="runSimulation">
              {{ simulationRunning ? runningText : '🚀 运行仿真' }}
            </button>
          </div>
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
          <strong style="font-size:14px;">{{ getTaskTypeLabel(task.task_type) }}</strong>
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
          <button class="btn btn-secondary" @click="viewTask(task)">查看</button>
          <button class="btn btn-danger" @click="deleteTask(task._id)">删除</button>
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
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  HeatmapChart, LineChart, VisualMapComponent, TooltipComponent,
  LegendComponent, GridComponent, MarkLineComponent, MarkPointComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage, ElNotification } from 'element-plus'
import { simulationApi, taskApi } from './api'

use([
  CanvasRenderer, HeatmapChart, LineChart, VisualMapComponent,
  TooltipComponent, LegendComponent, GridComponent,
  MarkLineComponent, MarkPointComponent
])

const GRID_SIZE = 16
const CELL_SIZE = 26
const canvasSize = GRID_SIZE * CELL_SIZE

const canvasRef = ref(null)
const isDrawing = ref(false)
const drawnMask = ref(Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(0)))
const brushSize = ref(2)

const simMode = ref('multifreq')
const numScans = ref(10)
const intervalSec = ref(30)
const simulationRunning = ref(false)
const showTaskList = ref(false)
const tasks = ref([])
const newNote = reactive({ doctor_name: '', note: '' })
const backendStatus = ref(true)

let brainPath = []
let ctx = null

const singleRecon = ref([])
const multiReconstructions = ref({})
const fusedReconstruction = ref([])
const coleColeParams = ref(null)

const tsData = reactive({
  times: [],
  avgSigma: [],
  volume: [],
  globalAvg: [],
  perFreqSigma: {}
})
const predictionData = ref(null)
const warnings = ref([])
const currentScanIdx = ref(0)

const modeText = computed(() => {
  const map = {
    '2d': '标准2D模式',
    'multifreq': '多频激励模式',
    'timeseries': '时间序列监测模式',
    '3d': '3D高精度模式'
  }
  return map[simMode.value] || ''
})

const resultPanelTitle = computed(() => {
  if (simMode.value === '2d') return '📊 电导率分布重建 (单频)'
  if (simMode.value === 'multifreq') return '📊 多频电导率重建 + 融合视图'
  if (simMode.value === 'timeseries') return '📊 时间序列监测 · 动态变化'
  return '📊 重建结果'
})

const runningText = computed(() => {
  if (simMode.value === 'timeseries') {
    return `扫描中 ${currentScanIdx.value}/${numScans.value}...`
  }
  return '仿真中...'
})

const severityText = computed(() => {
  if (!predictionData.value) return ''
  const map = { MILD: '轻度 · 可控', MODERATE: '中度 · 关注', SEVERE: '严重 · 紧急处理' }
  return map[predictionData.value.severity_level] || predictionData.value.severity_level
})

function genHeatmapOption(dataArr, title, showVM = true, colorPal = null) {
  const palette = colorPal || ['#0c1929', '#1e3a5f', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe']
  const data = []
  if (dataArr && dataArr.length) {
    for (let i = 0; i < dataArr.length; i++) {
      for (let j = 0; j < dataArr[i].length; j++) {
        data.push([j, i, dataArr[i][j]])
      }
    }
  }
  return {
    title: title ? { text: title, textStyle: { color: '#cbd5e1', fontSize: 12 } } : undefined,
    tooltip: { position: 'top', formatter: p => `(${p.value[1]},${p.value[0]}) σ=${p.value[2].toFixed(3)}` },
    grid: { left: '6%', right: '6%', top: '12%', bottom: showVM ? '20%' : '5%' },
    xAxis: { type: 'category', show: false },
    yAxis: { type: 'category', show: false },
    visualMap: showVM ? {
      min: 0, max: 1, show: true, orient: 'horizontal', left: 'center', bottom: '0%',
      inRange: { color: palette },
      textStyle: { color: '#94a3b8', fontSize: 9 },
      itemWidth: 10, itemHeight: 8
    } : undefined,
    series: [{
      type: 'heatmap', data,
      label: { show: false },
      emphasis: { itemStyle: { borderColor: '#60a5fa', borderWidth: 1 } }
    }]
  }
}

const singleChartOption = computed(() =>
  genHeatmapOption(singleRecon.value, '', true)
)

const fusedChartOption = computed(() =>
  genHeatmapOption(fusedReconstruction.value, '', true,
    ['#16213e', '#1a1a2e', '#533483', '#e94560', '#ff6b6b', '#ffd56b'])
)

function getFreqChartOption(freq) {
  const data = multiReconstructions.value[freq] || []
  const palettes = {
    '1kHz': ['#0a192f', '#112240', '#233554', '#64ffda', '#a8b2d1'],
    '10kHz': ['#0c1929', '#1e3a5f', '#3b82f6', '#60a5fa', '#93c5fd'],
    '100kHz': ['#2d1b4e', '#533483', '#e94560', '#ff6b9d', '#ffd56b']
  }
  return genHeatmapOption(data, '', false, palettes[freq])
}

const timeSeriesOption = computed(() => {
  const times = tsData.times.map(t => t.toFixed(1) + 'min')
  const series = [
    {
      name: '水肿区平均σ',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      data: tsData.avgSigma,
      itemStyle: { color: '#ef4444' },
      lineStyle: { width: 3 },
      markLine: predictionData.value ? {
        symbol: 'none',
        data: [{
          type: 'linear',
          name: '线性回归',
          xAxis: times,
          yAxis: tsData.times.map(t =>
            predictionData.value.conductivity_slope_per_min * t + predictionData.value.conductivity_intercept
          ),
          lineStyle: { color: '#fbbf24', type: 'dashed', width: 2 }
        }]
      } : undefined
    },
    {
      name: '全脑平均σ',
      type: 'line',
      smooth: true,
      symbol: 'diamond',
      symbolSize: 6,
      data: tsData.globalAvg,
      itemStyle: { color: '#3b82f6' },
      lineStyle: { width: 2 }
    }
  ]

  if (tsData.perFreqSigma['1kHz']) {
    for (const freq of ['1kHz', '10kHz', '100kHz']) {
      series.push({
        name: `水肿σ@${freq}`,
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: tsData.perFreqSigma[freq],
        lineStyle: { width: 1.5, type: 'dotted', opacity: 0.7 }
      })
    }
  }

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name), textStyle: { color: '#cbd5e1' }, top: '2%' },
    grid: { left: '8%', right: '4%', top: '18%', bottom: '12%' },
    xAxis: { type: 'category', data: times, name: '时间',
      axisLabel: { color: '#94a3b8' }, nameTextStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: '归一化电导率',
      axisLabel: { color: '#94a3b8' }, nameTextStyle: { color: '#94a3b8' } },
    series
  }
})

function computeBrainPath() {
  brainPath = []
  for (let i = 0; i < GRID_SIZE; i++) {
    for (let j = 0; j < GRID_SIZE; j++) {
      const cx = GRID_SIZE / 2, cy = GRID_SIZE / 2, r = GRID_SIZE / 2 - 0.5
      const dist = Math.sqrt((i - cx + 0.5) ** 2 + (j - cy + 0.5) ** 2)
      if (dist <= r) brainPath.push([i, j])
    }
  }
}

function drawBrainGrid() {
  if (!ctx) return
  ctx.fillStyle = '#0f172a'
  ctx.fillRect(0, 0, canvasSize, canvasSize)
  brainPath.forEach(([i, j]) => {
    ctx.fillStyle = drawnMask.value[i][j] > 0 ? 'rgba(239, 68, 68, 0.85)' : '#1e293b'
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

function startDraw(e) { isDrawing.value = true; draw(e) }
function draw(e) {
  if (!isDrawing.value || !canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  const sx = canvasRef.value.width / rect.width
  const sy = canvasRef.value.height / rect.height
  const x = Math.floor((e.clientX - rect.left) * sx / CELL_SIZE)
  const y = Math.floor((e.clientY - rect.top) * sy / CELL_SIZE)
  const bs = brushSize.value
  for (let di = -bs + 1; di < bs; di++) {
    for (let dj = -bs + 1; dj < bs; dj++) {
      const ni = y + di, nj = x + dj
      if (ni >= 0 && ni < GRID_SIZE && nj >= 0 && nj < GRID_SIZE) {
        const isBrain = brainPath.some(([bi, bj]) => bi === ni && bj === nj)
        if (isBrain) drawnMask.value[ni][nj] = 1
      }
    }
  }
  drawBrainGrid()
}
function endDraw() { isDrawing.value = false }

function clearDrawnMask() {
  drawnMask.value = Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(0))
  drawBrainGrid()
}
function clearCanvas() {
  clearDrawnMask()
  singleRecon.value = []
  multiReconstructions.value = {}
  fusedReconstruction.value = []
  coleColeParams.value = null
  tsData.times = []
  tsData.avgSigma = []
  tsData.volume = []
  tsData.globalAvg = []
  tsData.perFreqSigma = {}
  predictionData.value = null
  warnings.value = []
}

async function runSimulation() {
  simulationRunning.value = true
  currentScanIdx.value = 0
  try {
    if (simMode.value === '2d') {
      const resp = await simulationApi.simulate2D({
        grid_size: GRID_SIZE, edema_regions: [], drawn_mask: drawnMask.value
      })
      singleRecon.value = resp.data.reconstructed_conductivity
      ElMessage.success('2D仿真完成!')
    } else if (simMode.value === 'multifreq') {
      const resp = await simulationApi.simulateMultifrequency({
        grid_size: GRID_SIZE, edema_regions: [], drawn_mask: drawnMask.value
      })
      multiReconstructions.value = resp.data.reconstructions
      fusedReconstruction.value = resp.data.fused_reconstruction
      coleColeParams.value = resp.data.cole_cole_params
      ElMessage.success('多频仿真完成!')
    } else if (simMode.value === 'timeseries') {
      const resp = await simulationApi.simulateTimeseries({
        grid_size: GRID_SIZE, edema_regions: [], drawn_mask: drawnMask.value,
        num_scans: numScans.value, interval_seconds: intervalSec.value, expansion_rate: 0.08
      })
      tsData.times = resp.data.times_minutes
      tsData.avgSigma = resp.data.time_series.edema_avg_conductivity
      tsData.volume = resp.data.time_series.edema_volume_pixels
      tsData.globalAvg = resp.data.time_series.global_avg_conductivity
      tsData.perFreqSigma = resp.data.time_series.per_frequency_edema_sigma || {}
      predictionData.value = resp.data.prediction
      warnings.value = resp.data.warnings
      if (resp.data.scans && resp.data.scans.length) {
        const lastScan = resp.data.scans[resp.data.scans.length - 1]
        fusedReconstruction.value = lastScan.fused_reconstruction
      }
      if (resp.data.warnings) {
        ElNotification({
          title: '预测分析完成',
          message: resp.data.warnings[0],
          type: predictionData.value.severity_level === 'SEVERE' ? 'error' :
            predictionData.value.severity_level === 'MODERATE' ? 'warning' : 'success',
          duration: 5000
        })
      }
    }
    await loadTasks()
  } catch (err) {
    ElMessage.error('仿真失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    simulationRunning.value = false
  }
}

async function loadTasks() {
  try {
    const resp = await taskApi.listTasks(50)
    tasks.value = resp.data.tasks
  } catch (e) { console.error(e) }
}

function viewTask(task) {
  const rd = task.reconstruction_data
  if (!rd) { showTaskList.value = false; return }
  if (task.task_type === 'MultiFreq') {
    simMode.value = 'multifreq'
    multiReconstructions.value = rd.reconstructions || {}
    fusedReconstruction.value = rd.fused_reconstruction || []
    coleColeParams.value = rd.cole_cole_params || null
  } else if (task.task_type === 'TimeSeries') {
    simMode.value = 'timeseries'
    tsData.times = rd.times || []
    if (rd.time_series) {
      tsData.avgSigma = rd.time_series.edema_avg_conductivity || []
      tsData.volume = rd.time_series.edema_volume_pixels || []
      tsData.globalAvg = rd.time_series.global_avg_conductivity || []
      tsData.perFreqSigma = rd.time_series.per_frequency_edema_sigma || {}
    }
    predictionData.value = rd.prediction || null
    fusedReconstruction.value = rd.last_scan_fused || []
  } else {
    simMode.value = '2d'
    singleRecon.value = rd.reconstructed_conductivity || rd.mid_slice || []
  }
  showTaskList.value = false
}

async function deleteTask(taskId) {
  try {
    await taskApi.deleteTask(taskId)
    ElMessage.success('删除成功')
    loadTasks()
  } catch (e) { ElMessage.error('删除失败') }
}

async function addNote(taskId) {
  try {
    await taskApi.addNote(taskId, { ...newNote })
    ElMessage.success('注释已添加')
    newNote.doctor_name = ''
    newNote.note = ''
    loadTasks()
  } catch (e) { ElMessage.error('添加失败') }
}

function getStatusText(s) {
  return { completed: '已完成', running: '运行中', pending: '等待中', failed: '失败', queued: '队列中' }[s] || s
}
function getTaskTypeLabel(t) {
  return { '2D': '标准2D', 'MultiFreq': '多频激励', 'TimeSeries': '时间序列', '3D': '3D仿真' }[t] || t
}
function formatTime(t) {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN') } catch { return '' }
}

onMounted(() => {
  ctx = canvasRef.value?.getContext('2d')
  computeBrainPath()
  drawBrainGrid()
  loadTasks()
})
</script>

<style scoped>
.app-main-v2 { flex: 1; display: flex; flex-direction: column; padding: 12px; gap: 12px; }
.row-section { flex: 1; display: grid; grid-template-columns: 420px 1fr; gap: 12px; min-height: 0; }
.canvas-panel { overflow: hidden; }
.results-panel { overflow: auto; }

.canvas-wrapper { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 350px; }
.brain-canvas { border: 2px solid #475569; border-radius: 8px; cursor: crosshair; background: #0f172a; }

.toolbar-small { display: flex; align-items: center; }

.chart-container { flex: 1; width: 100%; min-height: 350px; }
.chart { width: 100%; height: 100%; }

.multifreq-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  padding: 4px;
}
.freq-cell {
  background: #0f172a; border: 1px solid #334155;
  border-radius: 8px; padding: 8px;
  display: flex; flex-direction: column;
}
.fused-cell {
  background: linear-gradient(135deg, #0c1929, #16213e);
  border: 1px solid #533483;
}
.freq-title {
  font-size: 13px; font-weight: 600; color: #93c5fd;
  margin-bottom: 2px;
}
.freq-info {
  font-size: 10px; color: #94a3b8; margin-bottom: 4px;
}
.chart-sm { width: 100%; height: 160px; }

.timeseries-container {
  display: grid; grid-template-columns: 1.2fr 1fr; gap: 10px;
  padding: 4px;
}
.ts-chart {
  background: #0f172a; border: 1px solid #334155;
  border-radius: 8px; padding: 6px; min-height: 350px;
}
.ts-prediction { display: flex; align-items: stretch; }
.pred-card {
  width: 100%; border-radius: 8px; padding: 12px;
  display: flex; flex-direction: column; gap: 10px;
}
.sev-mild { background: linear-gradient(135deg, #064e3b, #065f46); border: 1px solid #10b981; }
.sev-moderate { background: linear-gradient(135deg, #78350f, #92400e); border: 1px solid #f59e0b; }
.sev-severe { background: linear-gradient(135deg, #7f1d1d, #991b1b); border: 1px solid #ef4444; }

.pred-title { font-size: 14px; font-weight: 600; color: #fff; }
.pred-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.stat-item {
  background: rgba(0,0,0,0.3); border-radius: 6px; padding: 8px;
  text-align: center;
}
.stat-label { font-size: 11px; color: #cbd5e1; margin-bottom: 4px; }
.stat-val { font-size: 14px; font-weight: 700; color: #fff; }
.stat-sub { font-size: 10px; color: #94a3b8; margin-top: 2px; }

.severity-tag {
  padding: 6px 12px; border-radius: 20px;
  font-weight: 700; text-align: center; font-size: 13px;
}
.sev-tag-mild { background: #10b981; color: #064e3b; }
.sev-tag-moderate { background: #f59e0b; color: #78350f; }
.sev-tag-severe { background: #ef4444; color: #fff; }

.pred-warnings { display: flex; flex-direction: column; gap: 6px; }
.warn-item {
  background: rgba(0,0,0,0.25); padding: 6px 10px;
  border-radius: 4px; font-size: 12px; color: #fff;
  line-height: 1.5;
}

.toolbar-v2 {
  background: #1e293b; border-radius: 12px;
  border: 1px solid #334155; padding: 12px 16px;
  display: flex; gap: 24px; align-items: center; flex-wrap: wrap;
}
.toolbar-group { display: flex; flex-direction: column; gap: 6px; }
.input-label { font-size: 12px; color: #94a3b8; }
.param-row { display: flex; align-items: center; gap: 8px; }
.param-text { font-size: 13px; color: #cbd5e1; }
.btn-row { display: flex; gap: 10px; }

.chart { width: 100%; height: 100%; }
</style>
