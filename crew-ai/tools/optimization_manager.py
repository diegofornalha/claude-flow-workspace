"""
Optimization Manager for CrewAI with Neo4j
Handles caching, parallel execution, and intelligent retry
"""

import time
import json
import hashlib
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from neo4j import GraphDatabase
import os


class DecisionCache:
    """Cache for frequent decisions to avoid recomputation"""
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.local_cache = {}  # In-memory cache for fast access
        self.cache_ttl = 3600  # 1 hour TTL
        self._load_cache_from_neo4j()
    
    def _load_cache_from_neo4j(self):
        """Load cached decisions from Neo4j"""
        if not self.driver:
            return
            
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:CachedDecision)
                WHERE c.expires_at > datetime()
                RETURN c.key as key, c.value as value, c.metadata as metadata
                """
            )
            
            for record in result:
                self.local_cache[record['key']] = {
                    'value': record['value'],
                    'metadata': json.loads(record['metadata'])
                }
    
    def get(self, context: Dict[str, Any]) -> Optional[Any]:
        """Get cached decision for given context"""
        cache_key = self._generate_key(context)
        
        # Check local cache first
        if cache_key in self.local_cache:
            self._update_hit_count(cache_key)
            return self.local_cache[cache_key]['value']
        
        # Check Neo4j if not in local cache
        if self.driver:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (c:CachedDecision {key: $key})
                    WHERE c.expires_at > datetime()
                    SET c.hit_count = c.hit_count + 1,
                        c.last_accessed = datetime()
                    RETURN c.value as value
                    """,
                    key=cache_key
                )
                
                record = result.single()
                if record:
                    value = record['value']
                    self.local_cache[cache_key] = {'value': value}
                    return value
        
        return None
    
    def set(self, context: Dict[str, Any], value: Any, metadata: Dict[str, Any] = {}):
        """Cache a decision"""
        cache_key = self._generate_key(context)
        
        # Store in local cache
        self.local_cache[cache_key] = {
            'value': value,
            'metadata': metadata
        }
        
        # Store in Neo4j for persistence
        if self.driver:
            with self.driver.session() as session:
                session.run(
                    """
                    MERGE (c:CachedDecision {key: $key})
                    SET c.value = $value,
                        c.context = $context,
                        c.metadata = $metadata,
                        c.created_at = coalesce(c.created_at, datetime()),
                        c.updated_at = datetime(),
                        c.expires_at = datetime() + duration('PT1H'),
                        c.hit_count = coalesce(c.hit_count, 0),
                        c.last_accessed = datetime()
                    """,
                    key=cache_key,
                    value=str(value),
                    context=json.dumps(context),
                    metadata=json.dumps(metadata)
                )
    
    def _generate_key(self, context: Dict[str, Any]) -> str:
        """Generate cache key from context"""
        context_str = json.dumps(context, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()
    
    def _update_hit_count(self, cache_key: str):
        """Update hit count for cache analytics"""
        if self.driver:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (c:CachedDecision {key: $key})
                    SET c.hit_count = c.hit_count + 1,
                        c.last_accessed = datetime()
                    """,
                    key=cache_key
                )
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        if self.driver:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (c:CachedDecision)
                    WHERE c.expires_at < datetime()
                    DELETE c
                    """
                )


class ParallelExecutor:
    """Manages parallel execution of independent tasks"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.task_dependencies = {}
        self.execution_results = {}
    
    def analyze_dependencies(self, tasks: List[Any]) -> Dict[str, List[str]]:
        """Analyze task dependencies and identify parallelizable groups"""
        dependencies = {}
        
        for task in tasks:
            task_id = getattr(task, 'id', str(task))
            deps = getattr(task, 'dependencies', [])
            dependencies[task_id] = [getattr(d, 'id', str(d)) for d in deps]
        
        return dependencies
    
    def get_execution_groups(self, dependencies: Dict[str, List[str]]) -> List[List[str]]:
        """Group tasks that can be executed in parallel"""
        groups = []
        completed = set()
        remaining = set(dependencies.keys())
        
        while remaining:
            # Find tasks with no dependencies or only completed dependencies
            current_group = []
            for task_id in remaining:
                task_deps = dependencies[task_id]
                if all(dep in completed for dep in task_deps):
                    current_group.append(task_id)
            
            if not current_group:
                # Circular dependency or error
                print(f"⚠️ Warning: Circular dependency detected in tasks: {remaining}")
                current_group = list(remaining)  # Force execution
            
            groups.append(current_group)
            completed.update(current_group)
            remaining -= set(current_group)
        
        return groups
    
    def execute_parallel(self, tasks: List[Any], execute_func) -> List[Any]:
        """Execute tasks in parallel based on dependencies"""
        # Analyze dependencies
        task_map = {getattr(t, 'id', str(t)): t for t in tasks}
        dependencies = self.analyze_dependencies(tasks)
        groups = self.get_execution_groups(dependencies)
        
        results = []
        
        for group_idx, group in enumerate(groups):
            print(f"\n🔄 Executing group {group_idx + 1}/{len(groups)} with {len(group)} tasks in parallel")
            
            # Submit tasks in current group
            futures = {}
            for task_id in group:
                task = task_map[task_id]
                future = self.executor.submit(execute_func, task)
                futures[future] = task_id
            
            # Wait for completion
            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    result = future.result()
                    self.execution_results[task_id] = result
                    results.append(result)
                    print(f"  ✅ Task {task_id} completed")
                except Exception as e:
                    print(f"  ❌ Task {task_id} failed: {e}")
                    self.execution_results[task_id] = None
                    results.append(None)
        
        return results
    
    def shutdown(self):
        """Shutdown the executor"""
        self.executor.shutdown(wait=True)


class SmartRetryManager:
    """Intelligent retry system based on failure patterns"""
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.retry_strategies = self._load_retry_strategies()
    
    def _load_retry_strategies(self) -> Dict[str, Dict]:
        """Load retry strategies from Neo4j based on failure patterns"""
        strategies = {
            'default': {
                'max_retries': 3,
                'backoff_factor': 2,
                'initial_delay': 1
            }
        }
        
        if self.driver:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (p:Pattern {type: 'failure'})
                    WHERE p.occurrences > 5
                    RETURN p.error as error_type, 
                           p.occurrences as occurrences,
                           p.context as context
                    ORDER BY p.occurrences DESC
                    LIMIT 20
                    """
                )
                
                for record in result:
                    error_type = record['error_type']
                    occurrences = record['occurrences']
                    
                    # Adjust retry strategy based on failure frequency
                    if occurrences > 20:
                        strategies[error_type] = {
                            'max_retries': 1,  # Don't retry frequently failing tasks
                            'backoff_factor': 1,
                            'initial_delay': 0.5
                        }
                    elif occurrences > 10:
                        strategies[error_type] = {
                            'max_retries': 2,
                            'backoff_factor': 1.5,
                            'initial_delay': 1
                        }
        
        return strategies
    
    def should_retry(self, error: Exception, attempt: int) -> Tuple[bool, float]:
        """Determine if task should be retried and delay before retry"""
        error_type = type(error).__name__
        strategy = self.retry_strategies.get(error_type, self.retry_strategies['default'])
        
        if attempt >= strategy['max_retries']:
            return False, 0
        
        # Calculate delay with exponential backoff
        delay = strategy['initial_delay'] * (strategy['backoff_factor'] ** attempt)
        
        # Check if this error pattern has been successful after retry
        if self.driver:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (p:Pattern {type: 'success'})
                    WHERE p.context CONTAINS $error_type
                    RETURN count(p) as success_count
                    """,
                    error_type=error_type
                )
                
                record = result.single()
                if record and record['success_count'] > 0:
                    # Previous retries have been successful
                    return True, delay
        
        return True, delay
    
    def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with intelligent retry"""
        attempt = 0
        last_error = None
        
        while True:
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Record success
                if self.driver and attempt > 0:
                    with self.driver.session() as session:
                        session.run(
                            """
                            CREATE (p:Pattern {
                                type: 'retry_success',
                                attempts: $attempts,
                                execution_time: $exec_time,
                                timestamp: datetime()
                            })
                            """,
                            attempts=attempt + 1,
                            exec_time=execution_time
                        )
                
                return result
                
            except Exception as e:
                last_error = e
                should_retry, delay = self.should_retry(e, attempt)
                
                if not should_retry:
                    # Record final failure
                    if self.driver:
                        with self.driver.session() as session:
                            session.run(
                                """
                                CREATE (p:Pattern {
                                    type: 'retry_failure',
                                    error: $error,
                                    attempts: $attempts,
                                    timestamp: datetime()
                                })
                                """,
                                error=str(e),
                                attempts=attempt + 1
                            )
                    raise e
                
                print(f"⚠️ Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
                attempt += 1


class OptimizationOrchestrator:
    """Main orchestrator for all optimization strategies"""
    
    def __init__(self):
        # Neo4j connection
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            print("✅ Optimization Manager connected to Neo4j")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            self.driver = None
        
        # Initialize components
        self.cache = DecisionCache(self.driver)
        self.parallel_executor = ParallelExecutor(max_workers=4)
        self.retry_manager = SmartRetryManager(self.driver)
    
    def optimize_execution(self, tasks: List[Any], execute_func) -> List[Any]:
        """Execute tasks with all optimizations"""
        print("\n🚀 Starting optimized execution...")
        
        # Clean up expired cache
        self.cache.cleanup_expired()
        
        # Execute with parallelization and retry
        def wrapped_execute(task):
            # Check cache first
            context = {'task': str(task), 'type': getattr(task, '__class__.__name__', 'Task')}
            cached_result = self.cache.get(context)
            
            if cached_result:
                print(f"  💾 Using cached result for {task}")
                return cached_result
            
            # Execute with retry
            result = self.retry_manager.execute_with_retry(execute_func, task)
            
            # Cache successful result
            if result:
                self.cache.set(context, result)
            
            return result
        
        # Execute tasks in parallel
        results = self.parallel_executor.execute_parallel(tasks, wrapped_execute)
        
        # Analyze performance
        self._analyze_performance(results)
        
        return results
    
    def _analyze_performance(self, results):
        """Analyze and store performance metrics"""
        if not self.driver:
            return
            
        with self.driver.session() as session:
            # Calculate optimization metrics
            metrics = session.run(
                """
                MATCH (c:CachedDecision)
                WITH sum(c.hit_count) as cache_hits, count(c) as cache_size
                MATCH (p:Pattern {type: 'retry_success'})
                WITH cache_hits, cache_size, count(p) as retry_successes
                MATCH (p2:Pattern {type: 'retry_failure'})
                RETURN cache_hits, cache_size, retry_successes, count(p2) as retry_failures
                """
            ).single()
            
            if metrics:
                print("\n📊 Optimization Metrics:")
                print(f"  Cache Hits: {metrics['cache_hits']}")
                print(f"  Cache Size: {metrics['cache_size']}")
                print(f"  Retry Successes: {metrics['retry_successes']}")
                print(f"  Retry Failures: {metrics['retry_failures']}")
                
                # Store optimization report
                session.run(
                    """
                    CREATE (r:OptimizationReport {
                        timestamp: datetime(),
                        cache_hits: $cache_hits,
                        cache_size: $cache_size,
                        retry_successes: $retry_successes,
                        retry_failures: $retry_failures,
                        total_tasks: $total_tasks
                    })
                    """,
                    cache_hits=metrics['cache_hits'],
                    cache_size=metrics['cache_size'],
                    retry_successes=metrics['retry_successes'],
                    retry_failures=metrics['retry_failures'],
                    total_tasks=len(results)
                )
    
    def close(self):
        """Clean up resources"""
        self.parallel_executor.shutdown()
        if self.driver:
            self.driver.close()


# Convenience function
def setup_optimization(crew) -> OptimizationOrchestrator:
    """Setup optimization for a crew"""
    orchestrator = OptimizationOrchestrator()
    
    # Monkey-patch crew execution to use optimization
    original_kickoff = crew.kickoff
    
    def optimized_kickoff(inputs={}):
        # Use optimization for task execution
        if hasattr(crew, 'tasks'):
            results = orchestrator.optimize_execution(
                crew.tasks,
                lambda task: task.execute() if hasattr(task, 'execute') else task
            )
        return original_kickoff(inputs)
    
    crew.kickoff = optimized_kickoff
    
    return orchestrator