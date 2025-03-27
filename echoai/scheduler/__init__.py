"""任务调度模块，负责管理和分配智能体之间的任务。"""

from typing import Dict, List, Optional
from pydantic import BaseModel
from ..agents import Agent

class Task(BaseModel):
    """任务类，定义任务的基本属性和状态"""
    id: str
    name: str
    description: str
    status: str = "pending"  # pending, running, completed, failed
    assigned_to: Optional[str] = None
    dependencies: List[str] = []
    result: Optional[Dict] = None

class TaskScheduler:
    """任务调度器，负责任务的创建、分配和执行管理"""
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
    
    def create_task(self, task_id: str, name: str, description: str, dependencies: List[str] = []) -> Task:
        """创建新任务"""
        task = Task(id=task_id, name=name, description=description, dependencies=dependencies)
        self.tasks[task_id] = task
        return task
    
    def assign_task(self, task_id: str, agent_name: str) -> bool:
        """将任务分配给指定智能体"""
        if task_id not in self.tasks:
            return False
        task = self.tasks[task_id]
        task.assigned_to = agent_name
        task.status = "running"
        return True
    
    def complete_task(self, task_id: str, result: Dict) -> bool:
        """标记任务为完成状态"""
        if task_id not in self.tasks:
            return False
        task = self.tasks[task_id]
        task.status = "completed"
        task.result = result
        return True
    
    def get_available_tasks(self) -> List[Task]:
        """获取所有可执行的任务（没有未完成的依赖）"""
        available_tasks = []
        for task in self.tasks.values():
            if task.status == "pending" and self._check_dependencies(task):
                available_tasks.append(task)
        return available_tasks
    
    def _check_dependencies(self, task: Task) -> bool:
        """检查任务的依赖是否都已完成"""
        for dep_id in task.dependencies:
            if dep_id not in self.tasks or self.tasks[dep_id].status != "completed":
                return False
        return True