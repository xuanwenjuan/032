import axios from 'axios'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000
})

export const simulationApi = {
  simulate2D: (data) => api.post('/simulation/2d', data),
  simulate3D: (data) => api.post('/simulation/3d', data),
  get3DStatus: (taskId) => api.get(`/simulation/3d/${taskId}/status')
}

export const taskApi = {
  listTasks: (limit = 50) => api.get(`/tasks?limit=${limit}`),
  getTask: (taskId) => api.get(`/tasks/${taskId}`),
  deleteTask: (taskId) => api.delete(`/tasks/${taskId}`),
  addNote: (taskId, note) => api.post(`/tasks/${taskId}/notes`, note),
  getNotes: (taskId) => api.get(`/tasks/${taskId}/notes`)
}

export default api
