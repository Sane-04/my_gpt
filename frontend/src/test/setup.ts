// 模块说明：前端测试初始化模块，配置组件测试所需的运行环境。
import { beforeEach } from 'vitest'

// 每个测试前清空 localStorage，避免登录态数据串场。
beforeEach(() => {
  localStorage.clear()
})
