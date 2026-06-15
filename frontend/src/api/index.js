import axios from 'axios'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 180000
})

export const simulationApi = {
  simulate2D: (data) => api.post('/simulation/2d', data),
  simulateMultifrequency: (data) => api.post('/simulation/multifrequency', data),
  simulateTimeseries: (data) => api.post('/simulation/timeseries', data),
  simulate3D: (data) => api.post('/simulation/3d', data),
  get3DStatus: (taskId) => api.get(`/simulation/3d/${taskId}/status`),
  optimizeElectrodes: (data) => api.post('/simulation/electrode_optimization', data),
  evaluateQuality: (trueMat, recMat) => api.post('/simulation/evaluate_quality',
    { true_conductivity: trueMat, reconstructed_conductivity: recMat }),
  exportDicom: (data) => api.post('/simulation/export_dicom', data)
}

export const taskApi = {
  listTasks: (limit = 50) => api.get(`/tasks?limit=${limit}`),
  getTask: (taskId) => api.get(`/tasks/${taskId}`),
  deleteTask: (taskId) => api.delete(`/tasks/${taskId}`),
  addNote: (taskId, note) => api.post(`/tasks/${taskId}/notes`, note),
  getNotes: (taskId) => api.get(`/tasks/${taskId}/notes`)
}

export default api
