import unittest
from unittest.mock import Mock

from eflycode.agent.core.agent import ConversationAgent
from eflycode.agent.registry import (
    register_agent,
    create_agent,
    list_agents,
    get_agent_class,
    AgentRegistry
)
from eflycode.llm.llm_engine import LLMEngine


class TestAgentRegistry(unittest.TestCase):
    """Agent注册系统的测试用例"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 清空注册表
        AgentRegistry._agents.clear()
        
        # 创建模拟的LLM引擎
        self.mock_llm_engine = Mock(spec=LLMEngine)
    
    def tearDown(self):
        """测试后的清理工作"""
        # 清空注册表
        AgentRegistry._agents.clear()
    
    def test_register_agent_decorator(self):
        """测试Agent注册装饰器"""
        @register_agent("test_agent")
        class TestConversationAgent(ConversationAgent):
            ROLE = "test"
            DESCRIPTION = "测试Agent"
        
        # 验证Agent已注册
        agents = list_agents()
        self.assertIn("test_agent", agents)
        self.assertEqual(agents["test_agent"], TestConversationAgent)
        
        # 验证类添加了注册信息
        self.assertEqual(TestConversationAgent._registry_name, "test_agent")
    
    def test_register_agent_with_default_name(self):
        """测试使用默认名称注册Agent"""
        @register_agent()
        class DefaultConversationAgent(ConversationAgent):
            ROLE = "default"
            DESCRIPTION = "默认Agent"
        
        # 验证使用ROLE作为默认名称
        agents = list_agents()
        self.assertIn("default", agents)
        self.assertEqual(agents["default"], DefaultConversationAgent)
    
    def test_register_agent_duplicate_name_error(self):
        """测试重复注册相同名称的Agent会报错"""
        @register_agent("duplicate")
        class FirstConversationAgent(ConversationAgent):
            pass
        
        # 尝试注册相同名称的Agent应该抛出ValueError
        with self.assertRaises(ValueError) as context:
            @register_agent("duplicate")
            class SecondConversationAgent(ConversationAgent):
                pass
        
        self.assertIn("Agent名称 'duplicate' 已存在", str(context.exception))
    
    def test_register_non_agent_class_error(self):
        """测试注册非Agent子类会报错"""
        with self.assertRaises(TypeError) as context:
            @register_agent("invalid")
            class NotAnAgent:
                pass
        
        self.assertIn("必须继承自 Agent", str(context.exception))
    
    def test_get_agent_class(self):
        """测试获取Agent类"""
        @register_agent("get_test")
        class GetTestConversationAgent(ConversationAgent):
            pass
        
        # 测试成功获取
        agent_class = get_agent_class("get_test")
        self.assertEqual(agent_class, GetTestConversationAgent)
        
        # 测试获取不存在的Agent
        with self.assertRaises(KeyError) as context:
            get_agent_class("nonexistent")
        
        self.assertIn("未找到名称为 'nonexistent' 的Agent", str(context.exception))
    
    def test_create_agent(self):
        """测试创建Agent实例"""
        @register_agent("create_test")
        class CreateTestConversationAgent(ConversationAgent):
            ROLE = "create_test"
            DESCRIPTION = "创建测试Agent"
        
        # 创建Agent实例
        agent = create_agent("create_test", self.mock_llm_engine)
        
        # 验证实例类型和属性
        self.assertIsInstance(agent, CreateTestConversationAgent)
        self.assertEqual(agent.llm_engine, self.mock_llm_engine)
        self.assertEqual(agent._name, "create_test")
    
    def test_create_agent_with_kwargs(self):
        """测试使用额外参数创建Agent实例"""
        @register_agent("kwargs_test")
        class KwargsTestConversationAgent(ConversationAgent):
            pass
        
        # 使用额外参数创建Agent
        agent = create_agent(
            "kwargs_test", 
            self.mock_llm_engine,
            name="custom_name",
            description="自定义描述"
        )
        
        # 验证参数传递
        self.assertEqual(agent._name, "custom_name")
        self.assertEqual(agent._description, "自定义描述")
    
    def test_create_nonexistent_agent_error(self):
        """测试创建不存在的Agent会报错"""
        with self.assertRaises(KeyError) as context:
            create_agent("nonexistent", self.mock_llm_engine)
        
        self.assertIn("未找到名称为 'nonexistent' 的Agent", str(context.exception))
    
    def test_list_agents(self):
        """测试列出所有已注册的Agent"""
        @register_agent("list_test1")
        class ListTest1ConversationAgent(ConversationAgent):
            pass
        
        @register_agent("list_test2")
        class ListTest2ConversationAgent(ConversationAgent):
            pass
        
        agents = list_agents()
        
        # 验证返回的是副本
        self.assertIsNot(agents, AgentRegistry._agents)
        
        # 验证包含所有注册的Agent
        self.assertEqual(len(agents), 2)
        self.assertIn("list_test1", agents)
        self.assertIn("list_test2", agents)
        self.assertEqual(agents["list_test1"], ListTest1ConversationAgent)
        self.assertEqual(agents["list_test2"], ListTest2ConversationAgent)
    
    def test_registry_singleton(self):
        """测试AgentRegistry是单例模式"""
        registry1 = AgentRegistry()
        registry2 = AgentRegistry()
        
        # 验证是同一个实例
        self.assertIs(registry1, registry2)


if __name__ == "__main__":
    unittest.main()