// 模块说明：Capacitor 配置，用于把现有 Vue 前端打包为 Android 安装包。
import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'bond.cyandsane.saneai',
  appName: 'Sane-AI',
  webDir: 'dist',
  bundledWebRuntime: false,
  server: {
    androidScheme: 'https',
  },
}

export default config
