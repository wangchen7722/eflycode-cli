# EchoAI 测试用例

这个目录包含了 EchoAI 项目核心模块的完整测试用例。

## 测试文件结构

```
tests/
├── __init__.py                 # 测试包初始化
├── README.md                   # 测试文档（本文件）
├── run_tests.py               # 测试运行脚本
├── test_compressors.py        # 压缩器模块测试
├── test_retrievers.py         # 检索器模块测试
├── test_memory.py             # 记忆管理模块测试
└── test_token_calculator.py   # Token计算器测试
```

## 测试覆盖范围

### 1. 压缩器测试 (`test_compressors.py`)

- **CompressionResult**: 压缩结果数据结构测试
- **SummaryCompressor**: 摘要压缩器测试
  - 空消息处理
  - 少量消息处理
  - 摘要生成功能
  - 提示生成测试
- **SlidingWindowCompressor**: 滑动窗口压缩器测试
  - 限制范围内压缩
  - 超出限制压缩
- **KeyExtractionCompressor**: 关键信息提取压缩器测试
  - 关键消息提取
  - 关键模式检测
  - 重要性分数计算
- **HybridCompressor**: 混合压缩器测试
  - 策略选择逻辑
  - 不同场景下的压缩
- **create_compressor**: 工厂函数测试
  - 各种压缩器创建
  - 错误处理

### 2. 检索器测试 (`test_retrievers.py`)

- **RetrievalResult**: 检索结果数据结构测试
- **SemanticRetriever**: 语义检索器测试
  - 空上下文处理
  - 相似度计算
  - 余弦相似度算法
  - 阈值过滤
- **KeywordRetriever**: 关键词检索器测试
  - 精确匹配
  - 大小写不敏感
  - 关键词分数计算
  - 关键词提取
- **HybridRetriever**: 混合检索器测试
  - 结果合并
  - 去重处理
  - 分数排序
- **TimeBasedRetriever**: 时间检索器测试
  - 最近消息检索
  - 时间排序
  - 时间戳处理
  - 新旧分数计算
- **create_retriever**: 工厂函数测试

### 3. 记忆管理测试 (`test_memory.py`)

- **MemoryItem**: 记忆项数据结构测试
  - 创建和属性访问
  - 字典转换（to_dict/from_dict）
- **InMemoryStore**: 内存存储器测试
  - 存储和检索
  - 搜索功能
  - 类型过滤
  - 删除操作
  - 列表功能
  - 过期清理
- **SQLiteMemoryStore**: SQLite存储器测试
  - 数据库操作
  - 持久化存储
  - 查询功能
- **MemoryManager**: 记忆管理器测试
  - 记忆添加和检索
  - 重要性评估
  - 搜索和更新
  - 记忆整合
  - 容量限制
  - 统计信息

### 4. Token计算器测试 (`test_token_calculator.py`)

- **TokenCalculator**: Token计算器测试
  - 字符串token计算
  - 消息token计算
  - 消息列表处理
  - 不同模型支持
  - 特殊字符处理
  - 代码内容处理
  - 多语言支持
  - 一致性验证
  - 错误处理

## 运行测试

### 基本用法

```bash
# 运行所有测试
python tests/run_tests.py

# 列出所有可用测试
python tests/run_tests.py --list

# 运行特定模块的测试
python tests/run_tests.py --module test_compressors

# 运行特定测试类
python tests/run_tests.py --module test_compressors --class TestSummaryCompressor

# 运行特定测试方法
python tests/run_tests.py --module test_compressors --class TestSummaryCompressor --method test_compress_empty_messages
```

### 高级选项

```bash
# 使用模式匹配运行测试
python tests/run_tests.py --pattern "test_comp*"

# 第一个失败时停止
python tests/run_tests.py --failfast

# 静默模式（最小输出）
python tests/run_tests.py --quiet

# 详细模式（最大输出）
python tests/run_tests.py --verbose
```

### 使用标准unittest运行

```bash
# 运行所有测试
python -m unittest discover tests

# 运行特定测试文件
python -m unittest tests.test_compressors

# 运行特定测试类
python -m unittest tests.test_compressors.TestSummaryCompressor

# 运行特定测试方法
python -m unittest tests.test_compressors.TestSummaryCompressor.test_compress_empty_messages
```

## 测试环境要求

### Python版本
- Python 3.8+

### 依赖包
- unittest (标准库)
- unittest.mock (标准库)
- tempfile (标准库)
- datetime (标准库)

### 项目依赖
确保已安装项目的所有依赖：
```bash
pip install -r requirements.txt
```

## 测试数据和Mock

测试用例使用了以下Mock策略：

1. **LLM引擎Mock**: 模拟大语言模型的响应
2. **嵌入模型Mock**: 模拟向量嵌入计算
3. **数据库Mock**: 使用临时文件进行SQLite测试
4. **时间Mock**: 控制时间相关的测试场景

## 测试最佳实践

### 1. 测试隔离
- 每个测试方法都是独立的
- 使用setUp()和tearDown()管理测试状态
- 临时文件自动清理

### 2. 断言策略
- 使用具体的断言方法（assertEqual, assertGreater等）
- 验证返回值类型和范围
- 测试边界条件和异常情况

### 3. Mock使用
- 只Mock外部依赖
- 验证Mock调用次数和参数
- 模拟真实的返回值

### 4. 测试覆盖
- 正常流程测试
- 边界条件测试
- 异常情况测试
- 性能相关测试

## 持续集成

测试用例设计为可以在CI/CD环境中运行：

```yaml
# GitHub Actions 示例
- name: Run Tests
  run: |
    python tests/run_tests.py --failfast
```

## 贡献指南

### 添加新测试

1. 在相应的测试文件中添加测试类
2. 继承unittest.TestCase
3. 使用描述性的测试方法名
4. 添加详细的文档字符串
5. 确保测试的独立性

### 测试命名规范

- 测试文件：`test_<module_name>.py`
- 测试类：`Test<ClassName>`
- 测试方法：`test_<specific_behavior>`

### 示例测试结构

```python
class TestNewFeature(unittest.TestCase):
    """新功能测试"""
    
    def setUp(self):
        """设置测试环境"""
        pass
    
    def tearDown(self):
        """清理测试环境"""
        pass
    
    def test_normal_case(self):
        """测试正常情况"""
        pass
    
    def test_edge_case(self):
        """测试边界情况"""
        pass
    
    def test_error_handling(self):
        """测试错误处理"""
        pass
```

## 故障排除

### 常见问题

1. **导入错误**: 确保项目根目录在Python路径中
2. **依赖缺失**: 安装所有必需的依赖包
3. **权限问题**: 确保有创建临时文件的权限
4. **路径问题**: 使用绝对路径或正确设置工作目录

### 调试技巧

```bash
# 运行单个测试进行调试
python -m unittest tests.test_compressors.TestSummaryCompressor.test_compress_empty_messages -v

# 使用pdb调试
python -m pdb tests/run_tests.py --module test_compressors
```

## 性能测试

虽然当前测试主要关注功能正确性，但也包含了一些性能相关的测试：

- 大量数据处理测试
- 长文本token计算测试
- 内存使用测试

## 测试报告

运行测试后会生成详细的报告，包括：

- 测试通过/失败统计
- 失败测试的详细信息
- 错误堆栈跟踪
- 执行时间统计

---

如有问题或建议，请提交Issue或Pull Request。