# Diagramas Técnicos Detalhados - Kingston Otimizado

## 🏗️ Diagrama de Componentes Detalhado

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[React Frontend<br/>- Real-time updates<br/>- Progress tracking<br/>- Agent status]
        API[REST API Clients<br/>- External integrations<br/>- Third-party apps]
        WS[WebSocket Clients<br/>- Live notifications<br/>- Streaming responses]
    end
    
    subgraph "API Gateway Layer"
        NGINX[NGINX Load Balancer<br/>- SSL termination<br/>- Request routing<br/>- Rate limiting]
        AUTH[Auth Middleware<br/>- JWT validation<br/>- Session management<br/>- RBAC]
        CORS[CORS Handler<br/>- Cross-origin support<br/>- Security headers]
    end
    
    subgraph "Core Application Layer"
        AM[AgentManager V2<br/>- Task orchestration<br/>- Agent lifecycle<br/>- Performance tracking]
        
        ORCH[Orchestrator Service<br/>- Complexity analysis<br/>- Task decomposition<br/>- Intelligent routing]
        
        QC[Quality Controller<br/>- Adaptive evaluation<br/>- Improvement loops<br/>- Threshold management]
        
        PE[Parallel Executor<br/>- Concurrent processing<br/>- Result aggregation<br/>- Synchronization]
    end
    
    subgraph "Agent Layer"
        CLAUDE[Claude Agent<br/>- SDK integration<br/>- Structured outputs<br/>- Streaming support]
        
        CREW[CrewAI Agent<br/>- Multi-agent workflows<br/>- Collaborative tasks<br/>- Specialized processing]
        
        BASE[Base Agent<br/>- HTTP endpoints<br/>- Generic processing<br/>- Custom integrations]
        
        CUSTOM[Custom Agents<br/>- Domain-specific<br/>- Business logic<br/>- Specialized tools]
    end
    
    subgraph "Support Services"
        AI_SDK[AI SDK Provider v5<br/>- Model abstraction<br/>- Tool management<br/>- Telemetry collection]
        
        EVAL[Evaluator Service<br/>- Quality assessment<br/>- Criteria validation<br/>- Scoring algorithms]
        
        MEM[Memory Manager<br/>- Session persistence<br/>- Context management<br/>- Cross-session data]
        
        MCP[Neo4j MCP<br/>- Graph database<br/>- Relationship mapping<br/>- Knowledge storage]
    end
    
    subgraph "Infrastructure Layer"
        REDIS[Redis Cache<br/>- Session storage<br/>- Response caching<br/>- Pub/Sub messaging]
        
        PG[PostgreSQL<br/>- Transactional data<br/>- User management<br/>- Audit logs]
        
        QUEUE[Message Queue<br/>- Task distribution<br/>- Event processing<br/>- Async workflows]
        
        METRICS[Monitoring Stack<br/>- Prometheus metrics<br/>- Grafana dashboards<br/>- Alert manager]
    end
    
    %% Connections
    WEB --> NGINX
    API --> NGINX
    WS --> NGINX
    
    NGINX --> AUTH
    AUTH --> CORS
    CORS --> AM
    
    AM <--> ORCH
    AM <--> QC
    AM <--> PE
    
    ORCH --> CLAUDE
    ORCH --> CREW
    ORCH --> BASE
    ORCH --> CUSTOM
    
    QC <--> EVAL
    PE <--> AI_SDK
    
    AM <--> MEM
    MEM <--> MCP
    
    AM <--> REDIS
    AM <--> PG
    AM <--> QUEUE
    AM <--> METRICS
    
    %% Styling
    classDef coreService fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef supportService fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef infrastructure fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef agent fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class AM,ORCH,QC,PE coreService
    class AI_SDK,EVAL,MEM,MCP supportService
    class REDIS,PG,QUEUE,METRICS infrastructure
    class CLAUDE,CREW,BASE,CUSTOM agent
```

## 🔄 Fluxo de Processamento Completo

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant AgentManager
    participant Orchestrator
    participant QualityController
    participant ParallelExecutor
    participant Agents
    participant Evaluator
    participant Cache
    participant Database

    Note over Client,Database: Início do Processamento Inteligente
    
    Client->>Gateway: POST /api/v2/tasks/process/intelligent
    Gateway->>Gateway: Autenticação & Rate Limiting
    Gateway->>AgentManager: processTaskIntelligent(task)
    
    Note over AgentManager: Análise de Complexidade
    AgentManager->>Cache: checkComplexityCache(taskHash)
    alt Cache Hit
        Cache-->>AgentManager: cachedComplexity
    else Cache Miss
        AgentManager->>Orchestrator: analyzeComplexity(message)
        Orchestrator-->>AgentManager: complexityAnalysis
        AgentManager->>Cache: storeComplexity(taskHash, analysis)
    end
    
    Note over AgentManager: Decisão de Workflow
    alt Alta Complexidade (score > 7)
        Note over AgentManager,ParallelExecutor: Decomposição e Processamento Paralelo
        
        AgentManager->>Orchestrator: decomposeTask(message, complexity)
        Orchestrator-->>AgentManager: taskDecomposition
        
        AgentManager->>ParallelExecutor: planParallelExecution(subtasks)
        ParallelExecutor-->>AgentManager: executionPlan
        
        AgentManager->>ParallelExecutor: executeParallel(plan)
        
        loop Para cada subtarefa
            ParallelExecutor->>Orchestrator: selectBestAgent(subtask)
            Orchestrator-->>ParallelExecutor: selectedAgent
            
            ParallelExecutor->>Agents: processSubtask(subtask)
            Agents-->>ParallelExecutor: subtaskResult
            
            ParallelExecutor->>Database: logExecutionMetrics(subtask, result)
        end
        
        ParallelExecutor->>ParallelExecutor: aggregateResults(results)
        ParallelExecutor-->>AgentManager: finalAggregatedResult
        
    else Média Complexidade (score 4-7)
        Note over AgentManager,QualityController: Processamento com Controle de Qualidade
        
        AgentManager->>QualityController: processWithQualityControl(task)
        
        QualityController->>Orchestrator: route(message, context)
        Orchestrator-->>QualityController: routingDecision
        
        QualityController->>Agents: process(task, agent)
        Agents-->>QualityController: initialResult
        
        QualityController->>Evaluator: evaluateQuality(result, requirements)
        Evaluator-->>QualityController: qualityEvaluation
        
        alt Qualidade Abaixo do Threshold
            Note over QualityController: Loop de Melhoria
            
            loop Até qualidade adequada ou max tentativas
                QualityController->>QualityController: generateImprovements(evaluation)
                QualityController->>Agents: reprocess(improvedTask)
                Agents-->>QualityController: improvedResult
                
                QualityController->>Evaluator: evaluateQuality(improvedResult)
                Evaluator-->>QualityController: newEvaluation
                
                QualityController->>Database: logQualityIteration(iteration, scores)
                
                break Qualidade Aceitável
                    Note over QualityController: Threshold atingido
                end
            end
        end
        
        QualityController-->>AgentManager: qualityAssuredResult
        
    else Baixa Complexidade (score < 4)
        Note over AgentManager,Orchestrator: Roteamento Simples Otimizado
        
        AgentManager->>Orchestrator: route(message, context)
        Orchestrator-->>AgentManager: routingDecision
        
        AgentManager->>Agents: process(task, selectedAgent)
        Agents-->>AgentManager: directResult
    end
    
    Note over AgentManager: Pós-processamento
    AgentManager->>Database: logTaskExecution(task, result, metrics)
    AgentManager->>Cache: cacheResult(taskSignature, result)
    
    Note over AgentManager: Aprendizado Contínuo
    AgentManager->>AgentManager: updatePerformanceMetrics(agent, execution)
    AgentManager->>AgentManager: updateRoutingPatterns(decision, outcome)
    
    AgentManager-->>Gateway: taskResponse
    Gateway-->>Client: HTTP 200 + response
    
    Note over Client,Database: WebSocket Notifications (Async)
    Gateway->>Client: WebSocket: task:completed
    Gateway->>Client: WebSocket: metrics:updated
```

## 🧩 Diagrama de Classes Principais

```mermaid
classDiagram
    class AgentManagerV2 {
        -orchestrator: OrchestratorService
        -qualityController: QualityController
        -parallelExecutor: ParallelExecutor
        -performanceMetrics: Map<string, Metrics>
        -routingHistory: RoutingHistory
        
        +processTaskIntelligent(task: Task): Promise<Response>
        +analyzeComplexity(message: string): Promise<ComplexityAnalysis>
        +routeIntelligent(task: Task): Promise<RoutingDecision>
        +selectBestAgent(task: Task): Promise<Agent>
        +optimizeWorkflow(history: SessionHistory): Promise<Optimization>
        +updatePerformanceMetrics(agent: string, metrics: Metrics): void
        +getSystemHealth(): Promise<SystemHealth>
    }
    
    class OrchestratorService {
        -model: LanguageModel
        -routingHistory: Map<string, RoutingDecision>
        -performanceMetrics: Map<string, AgentMetrics>
        
        +analyzeComplexity(message: string, context?: AnalysisContext): Promise<ComplexityAnalysis>
        +decomposeTask(message: string, complexity: ComplexityAnalysis): Promise<TaskDecomposition>
        +route(message: string, context?: RoutingContext): Promise<RoutingDecision>
        +orchestrateExecution(plan: ExecutionPlan): Promise<OrchestrationResult>
        +optimizeRouting(): Promise<RoutingOptimization>
        -buildRoutingContext(message: string, context: Context): RoutingContext
        -trackRoutingDecision(message: string, decision: RoutingDecision): void
    }
    
    class QualityController {
        -evaluator: EvaluatorService
        -qualityMetrics: QualityMetrics
        -adaptiveThresholds: Map<string, number>
        
        +processWithQualityControl(task: Task, config: QualityConfig): Promise<QualityResult>
        +evaluateQuality(content: string, requirements: QualityRequirements): Promise<QualityEvaluation>
        +qualityControlLoop(processor: TaskProcessor, task: Task): Promise<QualityResult>
        +calculateAdaptiveThreshold(context: EvaluationContext): Promise<number>
        +incrementalImprovement(content: string, evaluation: QualityEvaluation): Promise<ImprovementResult>
        -generateImprovementSuggestions(evaluation: QualityEvaluation): ImprovementSuggestion[]
        -updateQualityCriteria(feedback: QualityFeedback): void
    }
    
    class ParallelExecutor {
        -agentManager: AgentManagerV2
        -model: LanguageModel
        -executionStats: Map<string, ExecutionStats>
        -maxConcurrency: number
        
        +planParallelExecution(request: string, agents: Agent[]): Promise<ParallelExecutionPlan>
        +executeParallel(tasks: ParallelTask[], options?: ParallelOptions): Promise<ParallelExecutionResult>
        +aggregateResults(results: ExecutionResults, strategy: AggregationStrategy): Promise<AggregatedResult>
        +mapReduce<T, R>(data: T[], mapFn: MapFunction<T>, reduceFn: ReduceFunction<R>): Promise<R>
        +executePipeline(stages: PipelineStage[], input: any): Promise<PipelineResult>
        +getPerformanceMetrics(): ParallelPerformanceMetrics
        -executeTask(task: ParallelTask): Promise<ExecutionResult>
        -groupByPriority(tasks: ParallelTask[]): Map<number, ParallelTask[]>
        -createBatches(items: any[], batchSize: number): any[][]
    }
    
    class EvaluatorService {
        -model: LanguageModel
        -qualityCriteria: Map<string, QualityCriterion>
        -evaluationHistory: EvaluationHistory
        
        +evaluate(content: string, requirements: QualityRequirements): Promise<QualityEvaluation>
        +qualityControlLoop(processor: Function, request: string, config: QualityConfig): Promise<QualityResult>
        +generateImprovements(content: string, evaluation: QualityEvaluation): Promise<ImprovementSuggestions>
        +updateCriteria(feedback: EvaluationFeedback): void
        -calculateQualityScore(content: string, criteria: QualityCriterion[]): Promise<number>
        -identifyIssues(content: string, evaluation: QualityEvaluation): QualityIssue[]
    }
    
    class Agent {
        <<interface>>
        +id: string
        +name: string
        +type: AgentType
        +capabilities: string[]
        +status: AgentStatus
        +currentLoad: number
        +performance: PerformanceMetrics
        
        +process(task: Task): Promise<AgentResponse>
        +getInfo(): AgentInfo
        +updateStatus(status: AgentStatus): void
        +getHealth(): HealthStatus
    }
    
    class ClaudeAgent {
        -claudeCodeProvider: ClaudeCodeProvider
        -model: LanguageModel
        -systemPrompt: string
        
        +process(task: Task): Promise<AgentResponse>
        +processMessage(message: string, sessionId: string): Promise<string>
        +generateStructuredResponse<T>(prompt: string, schema: ZodSchema<T>): Promise<T>
        +streamResponse(prompt: string): AsyncIterable<string>
        +analyzeIntent(message: string): Promise<IntentAnalysis>
        +formatResponse(message: string, intent: IntentAnalysis, result: any): Promise<FormattedResponse>
    }
    
    class CrewAIAgent {
        -crewConfig: CrewConfig
        -agents: CrewAgent[]
        -tasks: CrewTask[]
        
        +process(task: Task): Promise<AgentResponse>
        +processMessage(message: string, sessionId: string): Promise<string>
        +createCrew(task: Task): Crew
        +executeCrew(crew: Crew): Promise<CrewResult>
        +getCrewMetrics(): CrewMetrics
    }
    
    class TaskDecomposition {
        +originalTask: Task
        +strategy: DecompositionStrategy
        +subtasks: Subtask[]
        +executionPlan: ExecutionPlan
        +estimatedTotalDuration: number
        +criticalPath: string[]
    }
    
    class QualityEvaluation {
        +overallScore: number
        +criteriaScores: Map<string, number>
        +confidence: number
        +issues: QualityIssue[]
        +improvements: ImprovementSuggestion[]
        +passesThreshold: boolean
        +adaptiveThreshold: number
    }
    
    class ExecutionResult {
        +taskId: string
        +agentId: string
        +output: any
        +metadata: ExecutionMetadata
        +status: ExecutionStatus
        +duration: number
        +qualityScore: number
    }
    
    %% Relationships
    AgentManagerV2 *-- OrchestratorService
    AgentManagerV2 *-- QualityController
    AgentManagerV2 *-- ParallelExecutor
    QualityController *-- EvaluatorService
    ParallelExecutor --> Agent
    ClaudeAgent ..|> Agent
    CrewAIAgent ..|> Agent
    OrchestratorService --> TaskDecomposition
    QualityController --> QualityEvaluation
    ParallelExecutor --> ExecutionResult
```

## 📊 Diagrama de Estados do Sistema

```mermaid
stateDiagram-v2
    [*] --> Idle
    
    Idle --> Analyzing : receiveTask()
    
    state Analyzing {
        [*] --> ComplexityAnalysis
        ComplexityAnalysis --> RoutingDecision
        RoutingDecision --> [*]
    }
    
    Analyzing --> SimpleProcessing : lowComplexity
    Analyzing --> QualityControlProcessing : mediumComplexity
    Analyzing --> ParallelProcessing : highComplexity
    
    state SimpleProcessing {
        [*] --> AgentSelection
        AgentSelection --> TaskExecution
        TaskExecution --> ResultValidation
        ResultValidation --> [*]
    }
    
    state QualityControlProcessing {
        [*] --> AgentSelection
        AgentSelection --> InitialProcessing
        InitialProcessing --> QualityEvaluation
        QualityEvaluation --> ThresholdCheck
        ThresholdCheck --> QualityPassed : scoreAboveThreshold
        ThresholdCheck --> ImprovementCycle : scoreBelowThreshold
        
        state ImprovementCycle {
            [*] --> GenerateImprovements
            GenerateImprovements --> ReprocessTask
            ReprocessTask --> ReEvaluateQuality
            ReEvaluateQuality --> CheckConvergence
            CheckConvergence --> [*] : converged
            CheckConvergence --> GenerateImprovements : notConverged
        }
        
        ImprovementCycle --> QualityPassed : maxRetriesReached
        QualityPassed --> [*]
    }
    
    state ParallelProcessing {
        [*] --> TaskDecomposition
        TaskDecomposition --> ExecutionPlanning
        ExecutionPlanning --> ParallelExecution
        
        state ParallelExecution {
            [*] --> fork_execution
            fork_execution --> Subtask1
            fork_execution --> Subtask2
            fork_execution --> SubtaskN
            
            Subtask1 --> join_execution
            Subtask2 --> join_execution
            SubtaskN --> join_execution
            join_execution --> [*]
        }
        
        ParallelExecution --> ResultAggregation
        ResultAggregation --> SynchronizationCheck
        SynchronizationCheck --> [*]
    }
    
    SimpleProcessing --> PostProcessing
    QualityControlProcessing --> PostProcessing
    ParallelProcessing --> PostProcessing
    
    state PostProcessing {
        [*] --> MetricsUpdate
        MetricsUpdate --> CacheUpdate
        CacheUpdate --> LearningUpdate
        LearningUpdate --> [*]
    }
    
    PostProcessing --> ResponseGeneration
    ResponseGeneration --> Idle
    
    %% Error states
    Analyzing --> Error : analysisError
    SimpleProcessing --> Error : processingError
    QualityControlProcessing --> Error : qualityError
    ParallelProcessing --> Error : parallelError
    
    Error --> Recovery : attemptRecovery
    Recovery --> Idle : recoverySuccessful
    Recovery --> Error : recoveryFailed
```

## 🔄 Diagrama de Integração AI SDK Provider v5

```mermaid
graph TB
    subgraph "AI SDK Provider v5"
        PROVIDER[Claude Code Provider<br/>- Model abstraction<br/>- Request management<br/>- Response parsing]
        
        REGISTRY[Model Registry<br/>- Model versions<br/>- Capability mapping<br/>- Load balancing]
        
        TOOLS[Tool Management<br/>- Dynamic tool loading<br/>- Validation<br/>- Execution context]
        
        STREAM[Streaming Engine<br/>- Real-time responses<br/>- Partial objects<br/>- Progress tracking]
        
        TELEMETRY[Telemetry System<br/>- Usage metrics<br/>- Performance data<br/>- Cost tracking]
    end
    
    subgraph "Enhanced Features"
        STRUCT[Structured Outputs<br/>- Zod schema validation<br/>- Type safety<br/>- Response formatting]
        
        VALID[Validation Engine<br/>- Input sanitization<br/>- Output verification<br/>- Error handling]
        
        CACHE[Intelligent Cache<br/>- Response caching<br/>- Semantic similarity<br/>- Cache invalidation]
        
        RETRY[Retry Logic<br/>- Exponential backoff<br/>- Circuit breaker<br/>- Fallback strategies]
    end
    
    subgraph "Agent Integration Layer"
        CLAUDE_SDK[Claude Agent SDK<br/>- generateObject()<br/>- generateText()<br/>- streamObject()]
        
        CREW_SDK[CrewAI Agent SDK<br/>- Multi-agent coordination<br/>- Task distribution<br/>- Result compilation]
        
        CUSTOM_SDK[Custom Agent SDK<br/>- Generic interfaces<br/>- Plugin architecture<br/>- External APIs]
    end
    
    subgraph "Application Layer"
        ORCHESTRATOR[Orchestrator Service]
        QUALITY[Quality Controller]
        PARALLEL[Parallel Executor]
    end
    
    %% Core Provider Connections
    PROVIDER --> STRUCT
    PROVIDER --> VALID
    PROVIDER --> CACHE
    PROVIDER --> RETRY
    
    REGISTRY --> PROVIDER
    TOOLS --> PROVIDER
    STREAM --> PROVIDER
    TELEMETRY --> PROVIDER
    
    %% Enhanced Features to SDK
    STRUCT --> CLAUDE_SDK
    STRUCT --> CREW_SDK
    STRUCT --> CUSTOM_SDK
    
    VALID --> CLAUDE_SDK
    CACHE --> CREW_SDK
    RETRY --> CUSTOM_SDK
    
    %% SDK to Application
    CLAUDE_SDK --> ORCHESTRATOR
    CLAUDE_SDK --> QUALITY
    CLAUDE_SDK --> PARALLEL
    
    CREW_SDK --> ORCHESTRATOR
    CREW_SDK --> PARALLEL
    
    CUSTOM_SDK --> ORCHESTRATOR
    
    %% Styling
    classDef provider fill:#e3f2fd,stroke:#0277bd,stroke-width:2px
    classDef enhanced fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef sdk fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef app fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    
    class PROVIDER,REGISTRY,TOOLS,STREAM,TELEMETRY provider
    class STRUCT,VALID,CACHE,RETRY enhanced
    class CLAUDE_SDK,CREW_SDK,CUSTOM_SDK sdk
    class ORCHESTRATOR,QUALITY,PARALLEL app
```

## 📈 Diagrama de Métricas e Monitoramento

```mermaid
graph TB
    subgraph "Data Collection Layer"
        APP_METRICS[Application Metrics<br/>- Response times<br/>- Error rates<br/>- Throughput]
        
        AGENT_METRICS[Agent Metrics<br/>- Success rates<br/>- Quality scores<br/>- Load distribution]
        
        SYSTEM_METRICS[System Metrics<br/>- CPU usage<br/>- Memory usage<br/>- Network I/O]
        
        BUSINESS_METRICS[Business Metrics<br/>- User satisfaction<br/>- Task completion<br/>- Cost analysis]
    end
    
    subgraph "Metrics Processing"
        COLLECTOR[Metrics Collector<br/>- Data aggregation<br/>- Time-series storage<br/>- Batch processing]
        
        ANALYZER[Metrics Analyzer<br/>- Pattern detection<br/>- Anomaly detection<br/>- Trend analysis]
        
        ALERTER[Alert Engine<br/>- Threshold monitoring<br/>- Notification dispatch<br/>- Escalation logic]
    end
    
    subgraph "Storage Layer"
        PROMETHEUS[Prometheus<br/>- Time-series DB<br/>- Query engine<br/>- Data retention]
        
        ELASTICSEARCH[Elasticsearch<br/>- Log aggregation<br/>- Full-text search<br/>- Complex queries]
        
        REDIS_METRICS[Redis<br/>- Real-time metrics<br/>- Hot data cache<br/>- Pub/Sub events]
    end
    
    subgraph "Visualization Layer"
        GRAFANA[Grafana Dashboards<br/>- Real-time charts<br/>- Custom panels<br/>- Alert visualization]
        
        KIBANA[Kibana<br/>- Log exploration<br/>- Data discovery<br/>- Search interface]
        
        CUSTOM_DASH[Custom Dashboard<br/>- Business metrics<br/>- KPI tracking<br/>- Executive summary]
    end
    
    subgraph "Alerting & Notifications"
        SLACK[Slack Integration<br/>- Team notifications<br/>- Alert channels<br/>- Status updates]
        
        EMAIL[Email Alerts<br/>- Critical notifications<br/>- Daily reports<br/>- SLA breaches]
        
        WEBHOOK[Webhook Endpoints<br/>- External integrations<br/>- Automated responses<br/>- Third-party tools]
    end
    
    %% Data Flow
    APP_METRICS --> COLLECTOR
    AGENT_METRICS --> COLLECTOR
    SYSTEM_METRICS --> COLLECTOR
    BUSINESS_METRICS --> COLLECTOR
    
    COLLECTOR --> PROMETHEUS
    COLLECTOR --> ELASTICSEARCH
    COLLECTOR --> REDIS_METRICS
    
    COLLECTOR --> ANALYZER
    ANALYZER --> ALERTER
    
    PROMETHEUS --> GRAFANA
    ELASTICSEARCH --> KIBANA
    REDIS_METRICS --> CUSTOM_DASH
    
    ALERTER --> SLACK
    ALERTER --> EMAIL
    ALERTER --> WEBHOOK
    
    %% Feedback Loop
    ANALYZER --> APP_METRICS
    ANALYZER --> AGENT_METRICS
    
    style COLLECTOR fill:#e1f5fe
    style ANALYZER fill:#f3e5f5
    style ALERTER fill:#ffebee
```

## 🔧 Diagrama de Deployment e Infraestrutura

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[NGINX/HAProxy<br/>- SSL termination<br/>- Health checks<br/>- Traffic distribution]
    end
    
    subgraph "Application Tier"
        APP1[App Instance 1<br/>- Node.js + Express<br/>- AgentManager V2<br/>- Auto-scaling]
        
        APP2[App Instance 2<br/>- Node.js + Express<br/>- AgentManager V2<br/>- Auto-scaling]
        
        APPN[App Instance N<br/>- Node.js + Express<br/>- AgentManager V2<br/>- Auto-scaling]
    end
    
    subgraph "Service Tier"
        ORCH_SVC[Orchestrator Service<br/>- Complexity analysis<br/>- Task decomposition<br/>- Intelligent routing]
        
        QUALITY_SVC[Quality Service<br/>- Evaluation engine<br/>- Improvement loops<br/>- Adaptive thresholds]
        
        PARALLEL_SVC[Parallel Service<br/>- Concurrent execution<br/>- Result aggregation<br/>- Synchronization]
        
        EVAL_SVC[Evaluator Service<br/>- Quality assessment<br/>- Criteria validation<br/>- Scoring algorithms]
    end
    
    subgraph "Data Tier"
        PRIMARY_DB[(PostgreSQL Primary<br/>- Transactional data<br/>- ACID compliance<br/>- Connection pooling)]
        
        REPLICA_DB[(PostgreSQL Replica<br/>- Read operations<br/>- Load distribution<br/>- Backup source)]
        
        REDIS_CLUSTER[Redis Cluster<br/>- Session storage<br/>- Caching layer<br/>- Pub/Sub messaging]
        
        NEO4J[(Neo4j<br/>- Graph database<br/>- Relationship mapping<br/>- Knowledge storage)]
    end
    
    subgraph "Message Queue"
        QUEUE[RabbitMQ/Apache Kafka<br/>- Event streaming<br/>- Task distribution<br/>- Dead letter queues]
    end
    
    subgraph "Monitoring"
        PROMETHEUS[Prometheus<br/>- Metrics collection<br/>- Alert rules<br/>- Data retention]
        
        GRAFANA[Grafana<br/>- Visualization<br/>- Dashboards<br/>- Alert management]
        
        JAEGER[Jaeger<br/>- Distributed tracing<br/>- Request flow<br/>- Performance analysis]
    end
    
    subgraph "External Services"
        AI_API[AI APIs<br/>- Claude API<br/>- OpenAI API<br/>- Custom models]
        
        MCP_SERVICES[MCP Services<br/>- Neo4j MCP<br/>- Memory MCP<br/>- Custom MCPs]
    end
    
    %% Load Balancer Connections
    LB --> APP1
    LB --> APP2
    LB --> APPN
    
    %% Application to Services
    APP1 --> ORCH_SVC
    APP1 --> QUALITY_SVC
    APP1 --> PARALLEL_SVC
    APP2 --> ORCH_SVC
    APP2 --> QUALITY_SVC
    APP2 --> PARALLEL_SVC
    APPN --> ORCH_SVC
    APPN --> QUALITY_SVC
    APPN --> PARALLEL_SVC
    
    %% Service Dependencies
    QUALITY_SVC --> EVAL_SVC
    
    %% Database Connections
    APP1 --> PRIMARY_DB
    APP1 --> REPLICA_DB
    APP1 --> REDIS_CLUSTER
    APP2 --> PRIMARY_DB
    APP2 --> REPLICA_DB
    APP2 --> REDIS_CLUSTER
    APPN --> PRIMARY_DB
    APPN --> REPLICA_DB
    APPN --> REDIS_CLUSTER
    
    ORCH_SVC --> NEO4J
    QUALITY_SVC --> NEO4J
    
    %% Database Replication
    PRIMARY_DB --> REPLICA_DB
    
    %% Message Queue
    APP1 --> QUEUE
    APP2 --> QUEUE
    APPN --> QUEUE
    ORCH_SVC --> QUEUE
    QUALITY_SVC --> QUEUE
    PARALLEL_SVC --> QUEUE
    
    %% Monitoring
    APP1 --> PROMETHEUS
    APP2 --> PROMETHEUS
    APPN --> PROMETHEUS
    ORCH_SVC --> PROMETHEUS
    QUALITY_SVC --> PROMETHEUS
    PARALLEL_SVC --> PROMETHEUS
    
    PROMETHEUS --> GRAFANA
    APP1 --> JAEGER
    APP2 --> JAEGER
    APPN --> JAEGER
    
    %% External Services
    ORCH_SVC --> AI_API
    QUALITY_SVC --> AI_API
    PARALLEL_SVC --> AI_API
    
    APP1 --> MCP_SERVICES
    APP2 --> MCP_SERVICES
    APPN --> MCP_SERVICES
    
    %% Styling
    classDef app fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef service fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef data fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef monitor fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef external fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    
    class APP1,APP2,APPN app
    class ORCH_SVC,QUALITY_SVC,PARALLEL_SVC,EVAL_SVC service
    class PRIMARY_DB,REPLICA_DB,REDIS_CLUSTER,NEO4J,QUEUE data
    class PROMETHEUS,GRAFANA,JAEGER monitor
    class AI_API,MCP_SERVICES external
```

Estes diagramas técnicos detalhados fornecem uma visão completa da arquitetura Kingston otimizada, mostrando:

1. **Componentes e suas responsabilidades específicas**
2. **Fluxos de processamento completos com decisões condicionais**
3. **Estrutura de classes e relacionamentos**
4. **Estados do sistema e transições**
5. **Integração com AI SDK Provider v5**
6. **Sistema de métricas e monitoramento**
7. **Arquitetura de deployment e infraestrutura**

Cada diagrama serve como uma especificação técnica detalhada para a implementação dos componentes do sistema otimizado.