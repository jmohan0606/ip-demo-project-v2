from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from app.agents.state.agent_state import AgentTask, AgentWorkflowState
from app.shared.ids import timestamp_id

class BaseAgent(ABC):
    name: str
    description: str
    def create_task(self, instruction: str) -> AgentTask:
        return AgentTask(task_id=timestamp_id('agtask'), agent_name=self.name, instruction=instruction, status='running', started_at=datetime.utcnow())
    def complete_task(self, task: AgentTask, result: dict) -> AgentTask:
        task.status='completed'; task.result=result; task.completed_at=datetime.utcnow(); return task
    def fail_task(self, task: AgentTask, error: Exception | str) -> AgentTask:
        task.status='failed'; task.error=str(error); task.completed_at=datetime.utcnow(); return task
    @abstractmethod
    def run(self, state: AgentWorkflowState) -> AgentWorkflowState: ...
