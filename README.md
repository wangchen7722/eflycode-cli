# EchoAI - AI开发助手框架

## 项目概述
EchoAI是一个基于大语言模型的AI开发助手框架，提供开发者代理(Developer Agent)和丰富的工具集，帮助开发者完成代码编写、调试、重构等任务。支持命令行和Web界面两种交互方式。

## 功能特点
- 🛠️ 开发者代理：内置Developer代理，具备代码理解和生成能力
- 🔧 丰富工具集：文件操作、命令执行、代码分析等工具
- 🌐 多交互方式：支持CLI和Gradio Web界面
- 🔄 工具调用确认：执行工具前需用户确认，确保安全性
- 📦 模块化设计：易于扩展新代理和工具

## 安装方法
1. 克隆仓库：
   ```bash
   git clone https://github.com/dawnwccc/echo.git
   cd echo
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   创建.env文件并设置以下变量：
   ```
   ECHO_MODEL=your-model-name
   ECHO_BASE_URL=your-api-base-url
   ECHO_API_KEY=your-api-key
   ```

## 使用方法
### 命令行模式
```bash
python main.py
```

### Web界面模式
```bash
python gradio_app.py
```
访问 http://127.0.0.1:7860 使用Web界面

## 目录结构
```
echoai/
├── echoai/                # 核心代码
│   ├── agents/            # 代理实现
│   ├── llms/             # 大语言模型集成
│   ├── memory/           # 记忆管理
│   ├── tools/            # 工具实现
│   ├── utils/            # 工具类
│   └── ui/               # 用户界面
├── tests/                # 单元测试
├── gradio_app.py         # Web界面入口
├── main.py               # 命令行入口
├── README.md             # 项目文档
└── requirements.txt      # 依赖列表
```

## 核心功能详解
### Developer代理
- 角色：技术精湛的软件开发者
- 能力：
  - 代码生成与理解
  - 文件操作（创建/编辑/读取文件）
  - 命令执行
  - 代码分析

### 工具集
1. 文件操作工具：
   - ReadFileTool: 读取文件内容
   - CreateFileTool: 创建新文件
   - EditFileTool: 编辑文件内容
   - InsertFileTool: 在指定位置插入内容
   - SearchFilesTool: 搜索文件内容
   - ListFilesTool: 列出目录文件

2. 执行命令工具：
   - ExecuteCommandTool: 执行系统命令

3. 代码分析工具：
   - ListCodeDefinitionsTool: 列出代码定义

## 技术栈
- 核心框架：Python 3.11+
- LLM集成：OpenAI API
- Web界面：Gradio
- API服务：FastAPI
- 向量数据库：ChromaDB
- NLP处理：Sentence Transformers, HuggingFace Transformers
- 深度学习：PyTorch

## 开发指南
### 添加新工具
1. 在`echoai/tools/`目录下创建新工具类
2. 实现工具的核心功能
3. 在Developer代理的`developer_tools`列表中注册新工具

### 添加新代理
1. 继承`Agent`基类
2. 实现代理的特定功能
3. 定义代理的角色和描述

## 贡献指南
欢迎贡献代码！请遵循以下流程：
1. Fork仓库
2. 创建特性分支 (`git checkout -b feature/your-feature`)
3. 提交更改 (`git commit -am 'Add some feature'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建Pull Request

## 许可证
MIT License
