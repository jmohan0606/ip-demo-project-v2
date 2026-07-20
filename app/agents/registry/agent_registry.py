from app.agents.nodes.ai_assistant_agent import AiAssistantAgent
from app.agents.nodes.coaching_agent import CoachingAgent
from app.agents.nodes.compliance_agent import ComplianceAgent
from app.agents.nodes.context_retrieval_agent import ContextRetrievalAgent
from app.agents.nodes.explainability_agent import ExplainabilityAgent
from app.agents.nodes.feedback_learning_agent import FeedbackLearningAgent
from app.agents.nodes.opportunity_agent import OpportunityAgent
from app.agents.nodes.prediction_agent import PredictionAgent
from app.agents.nodes.rag_knowledge_agent import RagKnowledgeAgent
from app.agents.nodes.recommendation_agent import RecommendationAgent
from app.agents.nodes.revenue_agent import RevenueAgent
from app.agents.nodes.supervisor_agent import SupervisorAgent
from app.agents.nodes.tigergraph_graph_agent import TigerGraphGraphAgent
class AgentRegistry:
    def __init__(self):
        agents=[SupervisorAgent(),ContextRetrievalAgent(),TigerGraphGraphAgent(),RagKnowledgeAgent(),RevenueAgent(),PredictionAgent(),OpportunityAgent(),RecommendationAgent(),ComplianceAgent(),CoachingAgent(),FeedbackLearningAgent(),ExplainabilityAgent(),AiAssistantAgent()]
        self._agents={a.name:a for a in agents}
    def get(self,name): return self._agents[name]
    def list_agents(self): return [{'name':a.name,'description':a.description,'class':a.__class__.__name__} for a in self._agents.values()]
