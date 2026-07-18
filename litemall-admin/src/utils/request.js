import axios from 'axios'
import { Message, MessageBox } from 'element-ui'
import store from '@/store'
import { getToken } from '@/utils/auth'

axios.defaults.withCredentials = true

// create an axios instance
const service = axios.create({
  baseURL: process.env.VUE_APP_BASE_API, // api 的 base_url
  timeout: 5000 // request timeout
})

function cleanParams(params) {
  if (!params) {
    return params
  }
  const cleaned = {}
  Object.keys(params).forEach(key => {
    const value = params[key]
    if (value === undefined || value === null || value === '' || value === 'undefined' || value === 'null') {
      return
    }
    cleaned[key] = value
  })
  return cleaned
}

// request interceptor
service.interceptors.request.use(
  config => {
    // Do something before request is sent
    if (config.params) {
      config.params = cleanParams(config.params)
    }
    if (store.getters.token) {
      // 让每个请求携带token-- ['X-Litemall-Admin-Token']为自定义key 请根据实际情况自行修改
      config.headers['X-Litemall-Admin-Token'] = getToken()
    }
    return config
  },
  error => {
    // Do something with request error
    console.log(error) // for debug
    Promise.reject(error)
  }
)

// response interceptor
service.interceptors.response.use(
  response => {
    const res = response.data

    if (res.errno === 501) {
      MessageBox.alert('系统未登录，请重新登录', '错误', {
        confirmButtonText: '确定',
        type: 'error'
      }).then(() => {
        store.dispatch('FedLogOut').then(() => {
          location.reload()
        })
      })
      return Promise.reject('error')
    } else if (res.errno === 502) {
      MessageBox.alert('服务暂时不可用，请稍后重试或先切换到备用演示路径。', '提示', {
        confirmButtonText: '确定',
        type: 'error'
      })
      return Promise.reject('error')
    } else if (res.errno === 503) {
      MessageBox.alert('请求业务目前未支持', '警告', {
        confirmButtonText: '确定',
        type: 'error'
      })
      return Promise.reject('error')
    } else if (res.errno === 504) {
      MessageBox.alert('更新数据已经失效，请刷新页面重新操作', '警告', {
        confirmButtonText: '确定',
        type: 'error'
      })
      return Promise.reject('error')
    } else if (res.errno === 505) {
      MessageBox.alert('更新失败，请再尝试一次', '警告', {
        confirmButtonText: '确定',
        type: 'error'
      })
      return Promise.reject('error')
    } else if (res.errno === 506) {
      MessageBox.alert('没有操作权限，请联系管理员授权', '错误', {
        confirmButtonText: '确定',
        type: 'error'
      })
      return Promise.reject('error')
    } else if (res.errno !== 0) {
      // 非5xx的错误属于业务错误，留给具体页面处理
      return Promise.reject(response)
    } else {
      return response
    }
  }, error => {
    console.log('err' + error)// for debug
    Message({
      message: '服务连接暂时不可用，请确认本地服务已启动后重试。',
      type: 'error',
      duration: 5 * 1000
    })
    return Promise.reject(error)
  })

export default service
