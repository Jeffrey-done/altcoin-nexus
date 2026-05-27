# 前端面板

## 快速开始

### 方式1: PowerShell
```powershell
.\start-frontend.ps1
```

### 方式2: 批处理
```cmd
start-frontend.bat
```

### 方式3: 手动启动
```bash
cd frontend
npm install
npm run dev
```

## 访问地址

- 前端面板: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 功能说明

### 仪表盘
- 持仓概览
- 盈亏统计
- 候选数量
- 盈亏曲线图
- 持仓分布图

### 交易管理
- 查看所有交易
- 按状态/方向/交易所筛选
- 手动平仓

### 候选池
- 查看待确认候选
- 按策略/方向筛选

### 信号日志
- 查看历史信号
- 评分等级

### 风控状态
- 日亏损限制
- 开仓数量限制
- 连续亏损监控
- 持仓集中度

### 系统设置
- 系统信息
- 交易所连接状态
- 风控参数
- 策略参数

## 开发

### 项目结构
```
frontend/
├── src/
│   ├── api/          # API 接口
│   ├── components/   # 可复用组件
│   ├── stores/       # Pinia 状态管理
│   ├── views/        # 页面组件
│   ├── App.vue       # 主应用
│   ├── main.ts       # 入口文件
│   ├── router.ts     # 路由配置
│   └── style.css     # 全局样式
├── index.html
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

### 技术栈
- Vue 3 + TypeScript
- Vite 构建工具
- Tailwind CSS 样式
- Pinia 状态管理
- ECharts 图表
- Axios HTTP 请求
