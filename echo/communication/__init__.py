"""通信模块，负责智能体之间的消息传递和交互。"""

from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime

class AgentMessage(BaseModel):
    """消息类，定义智能体之间传递的消息格式"""
    id: str
    sender: str
    receiver: str
    content: str
    type: str  # text, command, result, error
    timestamp: datetime = datetime.now()
    metadata: Optional[Dict] = None

class CommunicationHub:
    """通信中心，管理所有智能体之间的消息传递"""
    def __init__(self):
        self.message_history: List[AgentMessage] = []
        self.subscribers: Dict[str, List[str]] = {}
    
    def send_message(self, message: AgentMessage) -> bool:
        """发送消息到指定接收者"""
        self.message_history.append(message)
        return True
    
    def get_messages(self, agent_name: str, limit: int = 10) -> List[AgentMessage]:
        """获取发送给指定智能体的最新消息"""
        return [msg for msg in reversed(self.message_history)
                if msg.receiver == agent_name][:limit]
    
    def subscribe(self, subscriber: str, topic: str) -> bool:
        """订阅特定主题的消息"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        if subscriber not in self.subscribers[topic]:
            self.subscribers[topic].append(subscriber)
        return True
    
    def broadcast(self, sender: str, topic: str, content: str) -> bool:
        """向所有订阅者广播消息"""
        if topic not in self.subscribers:
            return False
        for receiver in self.subscribers[topic]:
            message = AgentMessage(
                id=f"{datetime.now().timestamp()}",
                sender=sender,
                receiver=receiver,
                content=content,
                type="broadcast"
            )
            self.send_message(message)
        return True