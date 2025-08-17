import os
from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import (
	ScrapeWebsiteTool,
	PatronusEvalTool,
	SpiderTool,
	SerperDevTool,
	BraveSearchTool,
	DallETool,
	FirecrawlCrawlWebsiteTool,
	FirecrawlScrapeWebsiteTool,
	VisionTool,
	AIMindTool,
	HyperbrowserLoadTool,
	SerplyScholarSearchTool,
	ComposioTool
)
from crewai_tools import CrewaiEnterpriseTools
from tools.neo4j_tools import (
    Neo4jMemoryTool,
    Neo4jQueryTool,
    Neo4jRelationshipTool,
    Neo4jMetricsTool,
    Neo4jLearningTool
)
from tools.telemetry_callbacks import setup_telemetry
from tools.optimization_manager import setup_optimization
from tools.continuous_learning import setup_continuous_learning
from tools.mcp_integration import integrate_mcp_with_crew


@CrewBase
class SistemaMultiAgenteNeo4jCrew:
    """SistemaMultiAgenteNeo4j crew"""

    
    @agent
    def adaptive_coordinator(self) -> Agent:
        enterprise_actions_tool = CrewaiEnterpriseTools(
            actions_list=[
                
                "slack_send_message",
                
                "teams_send_message_in_channel",
                
                "gmail_send_email",
                
            ],
        )
        
        return Agent(
            config=self.agents_config["adaptive_coordinator"],
            tools=[
                PatronusEvalTool(), 
                ComposioTool(),
                Neo4jMemoryTool(),
                Neo4jQueryTool(),
                Neo4jMetricsTool(),
                *enterprise_actions_tool
            ],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def planner(self) -> Agent:
        enterprise_actions_tool = CrewaiEnterpriseTools(
            actions_list=[
                
                "jira_create_issue",
                
                "linear_create_project",
                
                "notion_create_page",
                
            ],
        )
        
        return Agent(
            config=self.agents_config["planner"],
            tools=[
                ScrapeWebsiteTool(), 
                FirecrawlCrawlWebsiteTool(), 
                FirecrawlScrapeWebsiteTool(), 
                VisionTool(),
                Neo4jMemoryTool(),
                Neo4jRelationshipTool(),
                *enterprise_actions_tool
            ],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def researcher(self) -> Agent:
        
        return Agent(
            config=self.agents_config["researcher"],
            tools=[
                ScrapeWebsiteTool(), 
                SpiderTool(), 
                SerperDevTool(), 
                BraveSearchTool(), 
                DallETool(),
                Neo4jMemoryTool(),
                Neo4jQueryTool()
            ],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def coder(self) -> Agent:
        enterprise_actions_tool = CrewaiEnterpriseTools(
            actions_list=[
                
                "jira_create_issue",
                
                "github_create_issue",
                
                "confluence_create_page",
                
            ],
        )
        
        return Agent(
            config=self.agents_config["coder"],
            tools=[
                AIMindTool(),
                Neo4jMemoryTool(),
                Neo4jLearningTool(),
                *enterprise_actions_tool
            ],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def tester(self) -> Agent:
        
        return Agent(
            config=self.agents_config["tester"],
            tools=[VisionTool()],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def reviewer(self) -> Agent:
        
        return Agent(
            config=self.agents_config["reviewer"],
            tools=[
                VisionTool(), 
                AIMindTool(),
                Neo4jQueryTool(),
                Neo4jMetricsTool()
            ],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def mcp_manager(self) -> Agent:
        
        return Agent(
            config=self.agents_config["mcp_manager"],
            tools=[ScrapeWebsiteTool(), SpiderTool(), FirecrawlCrawlWebsiteTool(), BraveSearchTool(), HyperbrowserLoadTool(), ComposioTool()],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def consensus_builder(self) -> Agent:
        
        return Agent(
            config=self.agents_config["consensus_builder"],
            tools=[AIMindTool(), SerplyScholarSearchTool()],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def a2a_coherence_checker(self) -> Agent:
        
        return Agent(
            config=self.agents_config["a2a_coherence_checker"],
            tools=[VisionTool(), AIMindTool(), SerplyScholarSearchTool()],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def performance_analyzer(self) -> Agent:
        
        return Agent(
            config=self.agents_config["performance_analyzer"],
            tools=[PatronusEvalTool(), VisionTool(), AIMindTool()],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def a2a_agent_template(self) -> Agent:
        
        return Agent(
            config=self.agents_config["a2a_agent_template"],
            tools=[],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    
    @agent
    def a2a_template(self) -> Agent:
        
        return Agent(
            config=self.agents_config["a2a_template"],
            tools=[],
            reasoning=False,
            inject_date=True,
            llm=LLM(
                model="openai/auto",
                temperature=0.7,
            ),
        )
    

    
    @task
    def strategic_planning(self) -> Task:
        return Task(
            config=self.tasks_config["strategic_planning"],
        )
    
    @task
    def research_analysis(self) -> Task:
        return Task(
            config=self.tasks_config["research_analysis"],
        )
    
    @task
    def mcp_coordination(self) -> Task:
        return Task(
            config=self.tasks_config["mcp_coordination"],
        )
    
    @task
    def a2a_template_design(self) -> Task:
        return Task(
            config=self.tasks_config["a2a_template_design"],
        )
    
    @task
    def implementation(self) -> Task:
        return Task(
            config=self.tasks_config["implementation"],
        )
    
    @task
    def consensus_validation(self) -> Task:
        return Task(
            config=self.tasks_config["consensus_validation"],
        )
    
    @task
    def a2a_agent_template_implementation(self) -> Task:
        return Task(
            config=self.tasks_config["a2a_agent_template_implementation"],
        )
    
    @task
    def quality_assurance(self) -> Task:
        return Task(
            config=self.tasks_config["quality_assurance"],
        )
    
    @task
    def code_review(self) -> Task:
        return Task(
            config=self.tasks_config["code_review"],
        )
    
    @task
    def a2a_coherence_validation(self) -> Task:
        return Task(
            config=self.tasks_config["a2a_coherence_validation"],
        )
    
    @task
    def performance_analysis(self) -> Task:
        return Task(
            config=self.tasks_config["performance_analysis"],
        )
    
    @task
    def coordination_summary(self) -> Task:
        return Task(
            config=self.tasks_config["coordination_summary"],
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the SistemaMultiAgenteNeo4j crew"""
        crew_instance = Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.hierarchical,  # Changed from sequential for optimization
            manager_agent=self.adaptive_coordinator(),  # Use coordinator as manager
            verbose=True,
            max_rpm=100,
            memory=True,  # Enable memory
            embedder={
                "provider": "openai",
                "config": {"model": "text-embedding-3-small"}
            },
            planning=True,  # Enable planning
            planning_llm=LLM(model="openai/gpt-4", temperature=0.1)
        )
        
        # Setup all optimizations and integrations
        self.telemetry = setup_telemetry(crew_instance)
        self.optimization = setup_optimization(crew_instance)
        self.learning = setup_continuous_learning(crew_instance)
        self.mcp_bridge = integrate_mcp_with_crew(crew_instance)
        
        print("✅ All systems integrated: Telemetry, Optimization, Learning, MCP")
        
        return crew_instance
