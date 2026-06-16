<template>
  <div class="app-container">
    <header class="app-header">
      <div>
        <h1>🧠 MIT脑水肿监测系统 (增强版)</h1>
        <div class="subtitle">多频激励 · 时间序列监测 · 电极优化 · DICOM导出</div>
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

          <div v-else-if="simMode === 'electrodeopt'" class="electrode-opt-container">
            <div class="eo-summary" v-if="electrodeOptResult">
              <div class="eo-title">🎯 电极布局优化结果</div>
              <div class="eo-desc">{{ electrodeOptResult.recommendation }}</div>
              <div class="eo-metrics-row">
                <div class="eo-metric-card">
                  <div class="eo-metric-label">适应度分数</div>
                  <div class="eo-metric-val">{{ (electrodeOptResult.fitness_score * 100).toFixed(1) }}%</div>
                </div>
                <div class="eo-metric-card">
                  <div class="eo-metric-label">覆盖度</div>
                  <div class="eo-metric-val">{{ (electrodeOptResult.coverage_score * 100).toFixed(1) }}%</div>
                </div>
                <div class="eo-metric-card">
                  <div class="eo-metric-label">角度分散</div>
                  <div class="eo-metric-val">{{ (electrodeOptResult.spread_score * 100).toFixed(1) }}%</div>
                </div>
                <div class="eo-metric-card">
                  <div class="eo-metric-label">使用均衡</div>
                  <div class="eo-metric-val">{{ (electrodeOptResult.balance_score * 100).toFixed(1) }}%</div>
                </div>
              </div>
              <div v-if="electrodeOptResult.current_quality" class="eo-quality-card">
                <div class="eo-metric-label" style="margin-bottom:6px">📊 当前重建质量评估</div>
                <div class="eo-quality-grid">
                  <div>MSE: {{ electrodeOptResult.current_quality.metrics.mse.toFixed(5) }}</div>
                  <div>RMSE: {{ electrodeOptResult.current_quality.metrics.rmse.toFixed(5) }}</div>
                  <div>SSIM: {{ electrodeOptResult.current_quality.metrics.ssim.toFixed(4) }}</div>
                  <div>PSNR: {{ electrodeOptResult.current_quality.metrics.psnr.toFixed(2) }}dB</div>
                  <div>MAE: {{ electrodeOptResult.current_quality.metrics.mae.toFixed(5) }}</div>
                  <div>Corr: {{ electrodeOptResult.current_quality.metrics.correlation.toFixed(4) }}</div>
                </div>
                <div style="margin-top:8px">
                  <el-tag type="primary">综合质量分数: {{ (electrodeOptResult.current_quality.overall_quality_score * 100).toFixed(1) }}%</el-tag>
                </div>
              </div>
            </div>
            <v-chart class="chart" :option="electrodeLayoutOption" autoresize />
            <div v-if="electrodeOptResult" style="padding:0 10px 10px">
              <div style="font-size:12px;color:#94a3b8;margin-bottom:6px">
                推荐电极对 ({{ electrodeOptResult.num_selected_pairs }}对):
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:4px">
                <el-tag
                  v-for="(p, idx) in electrodeOptResult.selected_pairs"
                  :key="idx"
                  type="warning"
                  size="small"
                  effect="dark">
                  E{{ p[0] }} ↔ E{{ p[1] }}
                </el-tag>
              </div>
            </div>
          </div>

          <div v-else-if="simMode === '3d'" class="sim-3d-container">
            <div class="sim-3d-status">
              <div class="status-row">
                <span class="status-label">连接状态:</span>
                <span :class="['ws-status-tag', wsConnected ? 'ws-connected' : 'ws-disconnected']">
                  {{ wsConnected ? '🟢 已连接' : '🔴 已断开' }}
                </span>
                <span v-if="wsReconnecting" class="ws-reconnecting">🔄 重连中 ({{ wsReconnectAttempt }}/{{ maxReconnectAttempts }})</span>
              </div>
              <div class="status-row" v-if="simulation3d.progress > 0">
                <span class="status-label">仿真进度:</span>
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: simulation3d.progress + '%' }"></div>
                  <span class="progress-text">{{ simulation3d.progress.toFixed(0) }}%</span>
                </div>
              </div>
              <div class="status-row" v-if="simulation3d.stage">
                <span class="status-label">当前阶段:</span>
                <span class="stage-text">{{ simulation3d.stage }}</span>
              </div>
            </div>

            <div class="sim-3d-results" v-if="simulation3d.mid_slice_recon">
              <div class="sim-3d-title">🧠 3D仿真结果 (中轴切片)</div>
              <div class="sim-3d-grid">
                <div class="sim-3d-cell">
                  <div class="freq-title">冠状面 (Z轴中)</div>
                  <v-chart class="chart-sm" :option="midSliceAxialOption" autoresize />
                </div>
                <div class="sim-3d-cell">
                  <div class="freq-title">矢状面 (Y轴中)</div>
                  <v-chart class="chart-sm" :option="midSliceSagittalOption" autoresize />
                </div>
                <div class="sim-3d-cell">
                  <div class="freq-title">横断面 (X轴中)</div>
                  <v-chart class="chart-sm" :option="midSliceCoronalOption" autoresize />
                </div>
              </div>
              <div class="sim-3d-stats">
                <div class="stat-item">
                  <div class="stat-label">体数据维度</div>
                  <div class="stat-val">{{ simulation3d.grid_size }}×{{ simulation3d.grid_size }}×{{ simulation3d.grid_size_z || 16 }}</div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">体素总数</div>
                  <div class="stat-val">{{ (simulation3d.grid_size * simulation3d.grid_size * (simulation3d.grid_size_z || 16)).toLocaleString() }}</div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">平均电导率</div>
                  <div class="stat-val">{{ simulation3d.avg_conductivity ? simulation3d.avg_conductivity.toFixed(4) : '-' }} S/m</div>
                </div>
              </div>
            </div>

            <div v-else class="sim-3d-placeholder">
              <div class="placeholder-icon">🧠</div>
              <div class="placeholder-text">绘制水肿区域后点击"开始3D仿真"</div>
              <div class="placeholder-desc">使用WebSocket实时推送进度，支持断线重连</div>
            </div>
          </div>

          <div class="dicom-export-bar" v-if="hasReconstructionData">
            <span style="font-size:12px;color:#94a3b8;margin-right:8px">📦 导出:</span>
            <button class="btn btn-secondary btn-sm" @click="exportDicom('reconstructed')">DICOM 重建图</button>
            <button class="btn btn-secondary btn-sm" v-if="simMode==='multifreq' || multiReconstructions['1kHz']"
              @click="exportDicom('multifreq_all')">DICOM 三频+融合</button>
            <button class="btn btn-secondary btn-sm" @click="exportDicom('fused')" v-if="fusedReconstruction.length">
              DICOM 融合图
            </button>
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
            <el-radio-button value="electrodeopt">电极优化</el-radio-button>
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

        <div class="toolbar-group" v-if="simMode === 'electrodeopt'">
          <label class="input-label">电极优化参数</label>
          <div class="param-row">
            <span class="param-text">选择对数:</span>
            <el-input-number v-model="numElectrodePairs" size="small" :min="4" :max="16" style="width:90px" />
            <span class="param-text">对</span>
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
const numElectrodePairs = ref(8)
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
const electrodeOptResult = ref(null)
const trueConductivityRef = ref([])

const simulation3d = reactive({
  progress: 0,
  stage: '',
  mid_slice_recon: null,
  mid_slice_true: null,
  grid_size: 32,
  grid_size_z: 16,
  avg_conductivity: 0,
  result_data: null
})

const wsConnected = ref(false)
const wsReconnecting = ref(false)
const wsReconnectAttempt = ref(0)
const maxReconnectAttempts = ref(5)
let wsInstance = null
let wsReconnectTimer = null
let wsHeartbeatTimer = null
let wsLastPongTime = 0
const wsClientId = 'client_' + Math.random().toString(36).substr(2, 9)

const modeText = computed(() => {
  const map = {
    '2d': '标准2D模式',
    'multifreq': '多频激励模式',
    'timeseries': '时间序列监测模式',
    'electrodeopt': '电极优化模式',
    '3d': '3D高精度模式'
  }
  return map[simMode.value] || ''
})

const resultPanelTitle = computed(() => {
  if (simMode.value === '2d') return '📊 电导率分布重建 (单频)'
  if (simMode.value === 'multifreq') return '📊 多频电导率重建 + 融合视图'
  if (simMode.value === 'timeseries') return '📊 时间序列监测 · 动态变化'
  if (simMode.value === 'electrodeopt') return '⚙️ 电极布局优化助手'
  return '📊 重建结果'
})

const runningText = computed(() => {
  if (simMode.value === 'timeseries') {
    return `扫描中 ${currentScanIdx.value}/${numScans.value}...`
  }
  if (simMode.value === 'electrodeopt') {
    return '遗传算法优化中...'
  }
  return '仿真中...'
})

const hasReconstructionData = computed(() => {
  return (
    (singleRecon.value && singleRecon.value.length > 0) ||
    (multiReconstructions.value && Object.keys(multiReconstructions.value).length > 0) ||
    (fusedReconstruction.value && fusedReconstruction.value.length > 0)
  )
})

const severityText = computed(() => {
  if (!predictionData.value) return ''
  const map = { MILD: '轻度 · 可控', MODERATE: '中度 · 关注', SEVERE: '严重 · 紧急处理' }
  return map[predictionData.value.severity_level] || predictionData.value.severity_level
})

const midSliceAxialOption = computed(() => {
  if (!simulation3d.mid_slice_recon) return genHeatmapOption([], '', true)
  const midZ = Math.floor(simulation3d.grid_size_z / 2)
  const slice = simulation3d.mid_slice_recon[midZ] || simulation3d.mid_slice_recon[0]
  return genHeatmapOption(slice, '', true)
})

const midSliceSagittalOption = computed(() => {
  if (!simulation3d.mid_slice_recon) return genHeatmapOption([], '', true)
  const midY = Math.floor(simulation3d.grid_size / 2)
  const slice = []
  for (let z = 0; z < simulation3d.grid_size_z; z++) {
    const row = []
    for (let x = 0; x < simulation3d.grid_size; x++) {
      row.push(simulation3d.mid_slice_recon[z]?.[midY]?.[x] || 0)
    }
    slice.push(row)
  }
  return genHeatmapOption(slice, '', true)
})

const midSliceCoronalOption = computed(() => {
  if (!simulation3d.mid_slice_recon) return genHeatmapOption([], '', true)
  const midX = Math.floor(simulation3d.grid_size / 2)
  const slice = []
  for (let z = 0; z < simulation3d.grid_size_z; z++) {
    const row = []
    for (let y = 0; y < simulation3d.grid_size; y++) {
      row.push(simulation3d.mid_slice_recon[z]?.[y]?.[midX] || 0)
    }
    slice.push(row)
  }
  return genHeatmapOption(slice, '', true)
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

const electrodeLayoutOption = computed(() => {
  const N = 16
  const center = N / 2
  const radius = N / 2 - 0.5
  const allElectrodes = []
  for (let i = 0; i < 16; i++) {
    const angle = 2 * Math.PI * i / 16
    allElectrodes.push({
      idx: i,
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle)
    })
  }
  const selectedSet = new Set()
  const selectedPairs = electrodeOptResult.value ? electrodeOptResult.value.selected_pairs || [] : []
  selectedPairs.forEach(([a, b]) => {
    selectedSet.add(a)
    selectedSet.add(b)
  })
  const series = []
  if (selectedPairs.length > 0) {
    series.push({
      type: 'lines',
      coordinateSystem: 'cartesian2d',
      polyline: false,
      effect: { show: true, period: 4, trailLength: 0.2, symbol: 'arrow', symbolSize: 6 },
      lineStyle: { color: '#fbbf24', width: 3, opacity: 0.8, curveness: 0.15 },
      data: selectedPairs.map(([a, b]) => [
        [allElectrodes[a].x, allElectrodes[a].y],
        [allElectrodes[b].x, allElectrodes[b].y]
      ])
    })
  }
  const brainData = []
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const cx = N / 2, cy = N / 2, r = N / 2 - 0.5
      const dist = Math.sqrt((i - cx + 0.5) ** 2 + (j - cy + 0.5) ** 2)
      if (dist <= r) brainData.push([j, i, 0.05])
    }
  }
  series.push({
    type: 'heatmap',
    data: brainData,
    itemStyle: { color: '#1e293b' },
    emphasis: { disabled: true }
  })
  series.push({
    type: 'scatter',
    symbolSize: 28,
    data: allElectrodes.map(e => ({
      value: [e.x, e.y],
      name: 'E' + e.idx,
      itemStyle: {
        color: selectedSet.has(e.idx) ? '#f59e0b' : '#475569',
        borderColor: selectedSet.has(e.idx) ? '#fbbf24' : '#334155',
        borderWidth: 2
      },
      label: { show: true, color: '#fff', fontSize: 10, fontWeight: 'bold', formatter: 'E' + e.idx }
    })),
    label: { show: true, position: 'inside', color: '#fff', fontSize: 10, fontWeight: 'bold' },
    zlevel: 10
  })
  return {
    tooltip: {
      trigger: 'item',
      formatter: p => {
        if (p.seriesType === 'scatter') return p.data.name + ': ' + (selectedSet.has(parseInt(p.data.name.slice(1))) ? '✅ 已选用' : '未选用')
        if (p.seriesType === 'lines') return '激励-测量对'
        return ''
      }
    },
    grid: { left: '4%', right: '4%', top: '12%', bottom: '4%' },
    xAxis: { type: 'value', min: -0.5, max: N - 0.5, show: false },
    yAxis: { type: 'value', min: -0.5, max: N - 0.5, show: false, inverse: false },
    series
  }
})

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
  electrodeOptResult.value = null
  trueConductivityRef.value = []
  simulation3d.progress = 0
  simulation3d.stage = ''
  simulation3d.mid_slice_recon = null
  simulation3d.result_data = null
}

function wsConnect() {
  if (wsInstance && wsInstance.readyState === WebSocket.OPEN) return

  const wsUrl = `ws://localhost:8001/ws/3d-simulation?client_id=${wsClientId}`
  wsInstance = new WebSocket(wsUrl)

  wsInstance.onopen = () => {
    console.log('[WS] 连接建立')
    wsConnected.value = true
    wsReconnecting.value = false
    wsReconnectAttempt.value = 0
    wsLastPongTime = Date.now()
    wsStartHeartbeat()
  }

  wsInstance.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      wsHandleMessage(msg)
    } catch (e) {
      console.error('[WS] 消息解析失败:', e)
    }
  }

  wsInstance.onclose = (event) => {
    console.log('[WS] 连接关闭:', event.code, event.reason)
    wsConnected.value = false
    wsStopHeartbeat()
    if (!wsReconnecting.value && wsReconnectAttempt.value < maxReconnectAttempts.value) {
      wsScheduleReconnect()
    }
  }

  wsInstance.onerror = (error) => {
    console.error('[WS] 连接错误:', error)
  }
}

function wsStartHeartbeat() {
  wsStopHeartbeat()
  wsHeartbeatTimer = setInterval(() => {
    if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
    }
    const elapsed = Date.now() - wsLastPongTime
    if (elapsed > 45000) {
      console.warn('[WS] 心跳超时，断开重连')
      wsInstance?.close()
    }
  }, 15000)
}

function wsStopHeartbeat() {
  if (wsHeartbeatTimer) {
    clearInterval(wsHeartbeatTimer)
    wsHeartbeatTimer = null
  }
}

function wsScheduleReconnect() {
  wsReconnecting.value = true
  wsReconnectAttempt.value++
  const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempt.value - 1), 30000)
  console.log(`[WS] ${delay / 1000}秒后第${wsReconnectAttempt.value}次重连...`)
  wsReconnectTimer = setTimeout(() => {
    wsConnect()
  }, delay)
}

function wsHandleMessage(msg) {
  switch (msg.type) {
    case 'pong':
      wsLastPongTime = Date.now()
      break
    case 'progress':
      simulation3d.progress = msg.progress || 0
      simulation3d.stage = msg.stage || ''
      break
    case 'result':
      simulation3d.progress = 100
      simulation3d.stage = '完成'
      simulation3d.mid_slice_recon = msg.mid_slice_recon
      simulation3d.mid_slice_true = msg.mid_slice_true
      simulation3d.grid_size = msg.grid_size || 32
      simulation3d.grid_size_z = msg.grid_size_z || 16
      simulation3d.avg_conductivity = msg.avg_conductivity || 0
      simulation3d.result_data = msg
      simulationRunning.value = false
      ElMessage.success('3D仿真完成!')
      break
    case 'error':
      simulationRunning.value = false
      ElMessage.error('3D仿真失败: ' + (msg.message || '未知错误'))
      break
    case 'cache_replay':
      if (msg.results && msg.results.length > 0) {
        msg.results.forEach(r => {
          if (r.type === 'progress') {
            simulation3d.progress = r.progress || 0
            simulation3d.stage = r.stage || ''
          } else if (r.type === 'result') {
            simulation3d.progress = 100
            simulation3d.stage = '完成'
            simulation3d.mid_slice_recon = r.mid_slice_recon
            simulation3d.grid_size = r.grid_size || 32
            simulation3d.grid_size_z = r.grid_size_z || 16
            simulation3d.avg_conductivity = r.avg_conductivity || 0
            simulation3d.result_data = r
          }
        })
        if (simulation3d.progress >= 100) {
          simulationRunning.value = false
        }
      }
      break
  }
}

function wsDisconnect() {
  wsStopHeartbeat()
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }
  wsReconnecting.value = false
  wsReconnectAttempt.value = 0
  if (wsInstance) {
    wsInstance.close()
    wsInstance = null
  }
  wsConnected.value = false
}

async function start3DSimulation() {
  try {
    simulationRunning.value = true
    simulation3d.progress = 0
    simulation3d.stage = '初始化连接...'
    simulation3d.mid_slice_recon = null

    wsConnect()

    const maxWait = 5000
    const start = Date.now()
    while (!wsConnected.value && Date.now() - start < maxWait) {
      await new Promise(r => setTimeout(r, 100))
    }

    if (!wsConnected.value) {
      throw new Error('WebSocket连接失败')
    }

    simulation3d.stage = '提交仿真任务...'
    wsInstance.send(JSON.stringify({
      type: 'start_simulation',
      grid_size: 32,
      grid_size_z: 16,
      drawn_mask: drawnMask.value,
      edema_regions: []
    }))
  } catch (err) {
    simulationRunning.value = false
    ElMessage.error('3D仿真启动失败: ' + err.message)
  }
}

async function runSimulation() {
  simulationRunning.value = true
  currentScanIdx.value = 0
  try {
    if (simMode.value === '3d') {
      await start3DSimulation()
      return
    }
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
    } else if (simMode.value === 'electrodeopt') {
      let trueMat = null
      let recMat = null
      if (singleRecon.value.length) {
        recMat = singleRecon.value
      } else if (fusedReconstruction.value.length) {
        recMat = fusedReconstruction.value
      }
      const resp = await simulationApi.optimizeElectrodes({
        grid_size: GRID_SIZE,
        num_pairs_to_select: numElectrodePairs.value,
        true_conductivity: trueMat,
        reconstructed_conductivity: recMat
      })
      electrodeOptResult.value = resp.data
      ElMessage.success('电极布局优化完成! 适应度:' + (resp.data.fitness_score * 100).toFixed(1) + '%')
    }
    await loadTasks()
  } catch (err) {
    ElMessage.error('仿真失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    simulationRunning.value = false
  }
}

function base64ToBlob(b64, contentType = 'application/octet-stream') {
  const byteChars = atob(b64)
  const bytes = new Uint8Array(byteChars.length)
  for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i)
  return new Blob([bytes], { type: contentType })
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

async function exportDicom(exportType, frequency = null) {
  try {
    const simResult = {
      task_id: 'MIT-' + Date.now().toString(36),
      reconstructed_conductivity: singleRecon.value,
      true_conductivity: trueConductivityRef.value,
      fused_reconstruction: fusedReconstruction.value,
      reconstructions: multiReconstructions.value,
      cole_cole_params: coleColeParams.value
    }
    const resp = await simulationApi.exportDicom({
      simulation_result: simResult,
      export_type: exportType,
      frequency
    })
    if (resp.data.status === 'success') {
      resp.data.files.forEach(f => {
        const blob = base64ToBlob(f.dicom_bytes_base64, f.content_type)
        downloadBlob(blob, f.filename)
      })
      ElMessage.success(`已导出 ${resp.data.num_files} 个DICOM文件`)
    }
  } catch (err) {
    ElMessage.error('DICOM导出失败: ' + (err.response?.data?.detail || err.message))
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
  } else if (task.task_type === 'ElectrodeOpt') {
    simMode.value = 'electrodeopt'
    electrodeOptResult.value = rd
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
  return { '2D': '标准2D', 'MultiFreq': '多频激励', 'TimeSeries': '时间序列', '3D': '3D仿真', 'ElectrodeOpt': '电极优化' }[t] || t
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

.electrode-opt-container {
  display: flex; flex-direction: column; gap: 8px;
  padding: 6px;
}
.eo-summary {
  background: linear-gradient(135deg, #0c1929, #1e293b);
  border: 1px solid #fbbf24; border-radius: 8px;
  padding: 10px 12px; display: flex; flex-direction: column; gap: 8px;
}
.eo-title { font-size: 14px; font-weight: 700; color: #fbbf24; }
.eo-desc { font-size: 12px; color: #cbd5e1; line-height: 1.5; }
.eo-metrics-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.eo-metric-card {
  background: rgba(0,0,0,0.3); border-radius: 6px;
  padding: 6px; text-align: center;
  border: 1px solid #334155;
}
.eo-metric-label { font-size: 10px; color: #94a3b8; margin-bottom: 3px; }
.eo-metric-val { font-size: 14px; font-weight: 700; color: #60a5fa; }
.eo-quality-card {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid #3b82f6; border-radius: 6px;
  padding: 8px 10px;
}
.eo-quality-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 4px 12px;
  font-size: 12px; color: #cbd5e1;
}

.dicom-export-bar {
  margin-top: 8px; padding: 8px 10px;
  background: #1e293b; border: 1px solid #334155;
  border-radius: 8px; display: flex; gap: 8px; align-items: center;
  flex-wrap: wrap;
}
.btn-sm { padding: 4px 10px; font-size: 12px; }

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

.sim-3d-container {
  display: flex; flex-direction: column; gap: 10px; padding: 4px;
}
.sim-3d-status {
  background: #0f172a; border: 1px solid #334155;
  border-radius: 8px; padding: 10px 12px;
  display: flex; flex-direction: column; gap: 8px;
}
.status-row {
  display: flex; align-items: center; gap: 10px;
}
.status-label {
  font-size: 12px; color: #94a3b8; min-width: 80px;
}
.ws-status-tag {
  font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 10px;
}
.ws-connected { background: rgba(16, 185, 129, 0.2); color: #10b981; }
.ws-disconnected { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
.ws-reconnecting {
  font-size: 12px; color: #f59e0b;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.progress-bar {
  flex: 1; height: 20px; background: #1e293b;
  border-radius: 10px; position: relative; overflow: hidden;
  border: 1px solid #334155;
}
.progress-fill {
  height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 10px; transition: width 0.3s ease;
}
.progress-text {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  font-size: 11px; font-weight: 600; color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}
.stage-text {
  font-size: 12px; color: #cbd5e1; font-weight: 500;
}
.sim-3d-results {
  display: flex; flex-direction: column; gap: 10px;
}
.sim-3d-title {
  font-size: 14px; font-weight: 700; color: #93c5fd;
  padding-left: 4px;
}
.sim-3d-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.sim-3d-cell {
  background: #0f172a; border: 1px solid #334155;
  border-radius: 8px; padding: 8px;
  display: flex; flex-direction: column;
}
.sim-3d-stats {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.sim-3d-placeholder {
  background: #0f172a; border: 1px dashed #475569;
  border-radius: 8px; padding: 40px 20px;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.placeholder-icon { font-size: 48px; opacity: 0.5; }
.placeholder-text { font-size: 14px; color: #94a3b8; }
.placeholder-desc { font-size: 11px; color: #64748b; }
</style>
