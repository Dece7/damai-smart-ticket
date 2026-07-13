import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器：添加Token到请求头
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('damai_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：处理401错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token无效或过期，清除Token并跳转到登录页
      localStorage.removeItem('damai_token')
      // 可以在这里添加跳转逻辑
      console.warn('Token无效，请重新登录')
    }
    return Promise.reject(error)
  }
)

export default api

