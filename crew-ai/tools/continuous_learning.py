"""
Continuous Learning System for CrewAI with Neo4j
Implements pattern recognition, quality scoring, and feedback loops
"""

import time
import json
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from neo4j import GraphDatabase
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import os


class QualityScorer:
    """Scores outputs based on historical performance"""
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.scoring_weights = {
            'execution_time': 0.3,
            'success_rate': 0.3,
            'output_quality': 0.2,
            'resource_efficiency': 0.2
        }
    
    def score_output(self, task_id: str, output: Any, execution_time: float, 
                    resources_used: Dict[str, Any] = {}) -> float:
        """Calculate quality score for an output"""
        scores = {}
        
        # Score execution time (faster is better)
        avg_time = self._get_average_execution_time(task_id)
        if avg_time > 0:
            time_score = min(1.0, avg_time / execution_time) if execution_time > 0 else 1.0
        else:
            time_score = 0.5  # Neutral score if no history
        scores['execution_time'] = time_score
        
        # Score based on success rate
        success_rate = self._get_task_success_rate(task_id)
        scores['success_rate'] = success_rate
        
        # Score output quality (based on similarity to successful outputs)
        quality_score = self._score_output_quality(task_id, output)
        scores['output_quality'] = quality_score
        
        # Score resource efficiency
        efficiency_score = self._score_resource_efficiency(resources_used)
        scores['resource_efficiency'] = efficiency_score
        
        # Calculate weighted average
        total_score = sum(scores[k] * self.scoring_weights[k] for k in scores)
        
        # Store score in Neo4j
        self._store_score(task_id, total_score, scores)
        
        return total_score
    
    def _get_average_execution_time(self, task_id: str) -> float:
        """Get average execution time for similar tasks"""
        if not self.driver:
            return 0
            
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:ExecutionTask)
                WHERE t.id CONTAINS $task_pattern AND t.success = true
                RETURN avg(t.execution_time) as avg_time
                """,
                task_pattern=task_id.split('_')[0]  # Match by task type
            )
            
            record = result.single()
            return record['avg_time'] if record and record['avg_time'] else 0
    
    def _get_task_success_rate(self, task_id: str) -> float:
        """Get success rate for similar tasks"""
        if not self.driver:
            return 0.5
            
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:ExecutionTask)
                WHERE t.id CONTAINS $task_pattern
                WITH count(CASE WHEN t.success THEN 1 END) as successes,
                     count(t) as total
                RETURN toFloat(successes) / toFloat(total) as success_rate
                """,
                task_pattern=task_id.split('_')[0]
            )
            
            record = result.single()
            return record['success_rate'] if record and record['success_rate'] else 0.5
    
    def _score_output_quality(self, task_id: str, output: Any) -> float:
        """Score output quality based on similarity to successful outputs"""
        if not self.driver:
            return 0.5
            
        # Get successful outputs for comparison
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:ExecutionTask)
                WHERE t.id CONTAINS $task_pattern AND t.success = true
                RETURN t.output as output
                LIMIT 10
                """,
                task_pattern=task_id.split('_')[0]
            )
            
            successful_outputs = [record['output'] for record in result]
            
            if not successful_outputs:
                return 0.5  # Neutral score if no history
            
            # Calculate similarity using TF-IDF
            try:
                output_str = str(output)
                all_outputs = successful_outputs + [output_str]
                
                vectorizer = TfidfVectorizer()
                tfidf_matrix = vectorizer.fit_transform(all_outputs)
                
                # Calculate similarity between new output and successful outputs
                similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])
                avg_similarity = np.mean(similarities)
                
                return float(avg_similarity)
            except:
                return 0.5  # Default score on error
    
    def _score_resource_efficiency(self, resources: Dict[str, Any]) -> float:
        """Score resource efficiency"""
        # Simple scoring based on resource usage
        if not resources:
            return 0.7  # Default score
        
        score = 1.0
        
        # Penalize high memory usage
        if 'memory_mb' in resources:
            memory_mb = resources['memory_mb']
            if memory_mb > 500:
                score -= 0.2
            elif memory_mb > 200:
                score -= 0.1
        
        # Penalize high CPU usage
        if 'cpu_percent' in resources:
            cpu_percent = resources['cpu_percent']
            if cpu_percent > 80:
                score -= 0.2
            elif cpu_percent > 50:
                score -= 0.1
        
        return max(0, score)
    
    def _store_score(self, task_id: str, total_score: float, component_scores: Dict[str, float]):
        """Store quality score in Neo4j"""
        if not self.driver:
            return
            
        with self.driver.session() as session:
            session.run(
                """
                CREATE (q:QualityScore {
                    task_id: $task_id,
                    total_score: $total_score,
                    execution_time_score: $exec_score,
                    success_rate_score: $success_score,
                    output_quality_score: $quality_score,
                    efficiency_score: $efficiency_score,
                    timestamp: datetime()
                })
                WITH q
                MATCH (t:ExecutionTask {id: $task_id})
                CREATE (t)-[:HAS_QUALITY_SCORE]->(q)
                """,
                task_id=task_id,
                total_score=total_score,
                exec_score=component_scores['execution_time'],
                success_score=component_scores['success_rate'],
                quality_score=component_scores['output_quality'],
                efficiency_score=component_scores['resource_efficiency']
            )


class PatternDetector:
    """Detects and learns from execution patterns"""
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.pattern_threshold = 3  # Minimum occurrences to consider a pattern
    
    def detect_failure_patterns(self) -> List[Dict[str, Any]]:
        """Identify common failure patterns"""
        if not self.driver:
            return []
            
        patterns = []
        
        with self.driver.session() as session:
            # Find recurring failures
            result = session.run(
                """
                MATCH (t:ExecutionTask {success: false})
                WITH t.error as error, t.description as description, count(t) as occurrences
                WHERE occurrences >= $threshold
                RETURN error, description, occurrences
                ORDER BY occurrences DESC
                LIMIT 10
                """,
                threshold=self.pattern_threshold
            )
            
            for record in result:
                patterns.append({
                    'type': 'failure',
                    'error': record['error'],
                    'description': record['description'],
                    'occurrences': record['occurrences']
                })
            
            # Find failure sequences
            seq_result = session.run(
                """
                MATCH (t1:ExecutionTask {success: false})-[:DEPENDS_ON]->(t2:ExecutionTask)
                WHERE t2.success = false
                WITH t1.description as task1, t2.description as task2, count(*) as occurrences
                WHERE occurrences >= $threshold
                RETURN task1, task2, occurrences
                ORDER BY occurrences DESC
                LIMIT 5
                """,
                threshold=self.pattern_threshold
            )
            
            for record in seq_result:
                patterns.append({
                    'type': 'failure_sequence',
                    'sequence': [record['task2'], record['task1']],
                    'occurrences': record['occurrences']
                })
        
        return patterns
    
    def detect_success_patterns(self) -> List[Dict[str, Any]]:
        """Identify successful execution patterns"""
        if not self.driver:
            return []
            
        patterns = []
        
        with self.driver.session() as session:
            # Find high-performing task combinations
            result = session.run(
                """
                MATCH (t:ExecutionTask {success: true})
                WHERE t.execution_time < 10
                WITH t.description as description, 
                     avg(t.execution_time) as avg_time,
                     count(t) as occurrences
                WHERE occurrences >= $threshold
                RETURN description, avg_time, occurrences
                ORDER BY avg_time ASC
                LIMIT 10
                """,
                threshold=self.pattern_threshold
            )
            
            for record in result:
                patterns.append({
                    'type': 'efficient_execution',
                    'description': record['description'],
                    'avg_time': record['avg_time'],
                    'occurrences': record['occurrences']
                })
            
            # Find successful agent collaborations
            collab_result = session.run(
                """
                MATCH (a1:ExecutionAgent)-[:EXECUTES]->(t1:ExecutionTask {success: true})
                MATCH (a2:ExecutionAgent)-[:EXECUTES]->(t2:ExecutionTask {success: true})
                WHERE t1.execution_id = t2.execution_id AND a1.name < a2.name
                WITH a1.name as agent1, a2.name as agent2, 
                     count(*) as collaborations,
                     avg(t1.execution_time + t2.execution_time) as avg_time
                WHERE collaborations >= $threshold
                RETURN agent1, agent2, collaborations, avg_time
                ORDER BY collaborations DESC
                LIMIT 5
                """,
                threshold=self.pattern_threshold
            )
            
            for record in collab_result:
                patterns.append({
                    'type': 'successful_collaboration',
                    'agents': [record['agent1'], record['agent2']],
                    'collaborations': record['collaborations'],
                    'avg_time': record['avg_time']
                })
        
        return patterns
    
    def store_pattern(self, pattern: Dict[str, Any]):
        """Store a detected pattern for future use"""
        if not self.driver:
            return
            
        pattern_id = hashlib.md5(json.dumps(pattern, sort_keys=True).encode()).hexdigest()[:12]
        
        with self.driver.session() as session:
            session.run(
                """
                MERGE (p:DetectedPattern {id: $pattern_id})
                SET p.type = $type,
                    p.details = $details,
                    p.occurrences = $occurrences,
                    p.first_detected = coalesce(p.first_detected, datetime()),
                    p.last_seen = datetime(),
                    p.active = true
                """,
                pattern_id=pattern_id,
                type=pattern['type'],
                details=json.dumps(pattern),
                occurrences=pattern.get('occurrences', 1)
            )


class FeedbackLoop:
    """Implements feedback mechanisms for continuous improvement"""
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.improvement_threshold = 0.7  # Minimum score to store as example
    
    def store_successful_example(self, task_id: str, input_data: Dict, output: Any, score: float):
        """Store successful execution as an example for future reference"""
        if score < self.improvement_threshold:
            return  # Don't store low-quality examples
            
        if not self.driver:
            return
            
        example_id = hashlib.md5(f"{task_id}{time.time()}".encode()).hexdigest()[:12]
        
        with self.driver.session() as session:
            session.run(
                """
                CREATE (e:SuccessfulExample {
                    id: $example_id,
                    task_id: $task_id,
                    input_data: $input_data,
                    output: $output,
                    score: $score,
                    created_at: datetime(),
                    usage_count: 0
                })
                WITH e
                MATCH (t:ExecutionTask {id: $task_id})
                CREATE (t)-[:PRODUCED_EXAMPLE]->(e)
                """,
                example_id=example_id,
                task_id=task_id,
                input_data=json.dumps(input_data),
                output=str(output)[:2000],  # Limit size
                score=score
            )
    
    def get_best_examples(self, task_type: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Retrieve best examples for a task type"""
        if not self.driver:
            return []
            
        examples = []
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:SuccessfulExample)
                WHERE e.task_id CONTAINS $task_type
                RETURN e.id as id,
                       e.input_data as input_data,
                       e.output as output,
                       e.score as score
                ORDER BY e.score DESC, e.created_at DESC
                LIMIT $limit
                """,
                task_type=task_type,
                limit=limit
            )
            
            for record in result:
                examples.append({
                    'id': record['id'],
                    'input': json.loads(record['input_data']),
                    'output': record['output'],
                    'score': record['score']
                })
                
                # Update usage count
                session.run(
                    """
                    MATCH (e:SuccessfulExample {id: $example_id})
                    SET e.usage_count = e.usage_count + 1,
                        e.last_used = datetime()
                    """,
                    example_id=record['id']
                )
        
        return examples
    
    def apply_feedback(self, task_id: str, feedback: Dict[str, Any]):
        """Apply user or system feedback to improve future executions"""
        if not self.driver:
            return
            
        feedback_id = hashlib.md5(f"{task_id}{time.time()}".encode()).hexdigest()[:12]
        
        with self.driver.session() as session:
            # Store feedback
            session.run(
                """
                CREATE (f:Feedback {
                    id: $feedback_id,
                    task_id: $task_id,
                    type: $feedback_type,
                    content: $content,
                    rating: $rating,
                    timestamp: datetime()
                })
                WITH f
                MATCH (t:ExecutionTask {id: $task_id})
                CREATE (t)-[:RECEIVED_FEEDBACK]->(f)
                """,
                feedback_id=feedback_id,
                task_id=task_id,
                feedback_type=feedback.get('type', 'general'),
                content=json.dumps(feedback.get('content', {})),
                rating=feedback.get('rating', 0)
            )
            
            # Update patterns based on feedback
            if feedback.get('rating', 0) < 0.5:
                # Negative feedback - mark related patterns for review
                session.run(
                    """
                    MATCH (t:ExecutionTask {id: $task_id})-[:PRODUCED_PATTERN]->(p:Pattern)
                    SET p.needs_review = true,
                        p.negative_feedback_count = coalesce(p.negative_feedback_count, 0) + 1
                    """,
                    task_id=task_id
                )
            elif feedback.get('rating', 0) > 0.8:
                # Positive feedback - boost pattern scores
                session.run(
                    """
                    MATCH (t:ExecutionTask {id: $task_id})-[:PRODUCED_PATTERN]->(p:Pattern)
                    SET p.score = p.score * 1.1,
                        p.positive_feedback_count = coalesce(p.positive_feedback_count, 0) + 1
                    """,
                    task_id=task_id
                )
    
    def generate_improvement_suggestions(self) -> List[str]:
        """Generate suggestions for system improvement"""
        if not self.driver:
            return []
            
        suggestions = []
        
        with self.driver.session() as session:
            # Find tasks that consistently fail
            failing_tasks = session.run(
                """
                MATCH (t:ExecutionTask {success: false})
                WITH t.description as task, count(t) as failures
                WHERE failures > 5
                RETURN task, failures
                ORDER BY failures DESC
                LIMIT 3
                """
            )
            
            for record in failing_tasks:
                suggestions.append(
                    f"Task '{record['task'][:50]}' has failed {record['failures']} times. "
                    f"Consider revising the implementation or adding error handling."
                )
            
            # Find slow tasks
            slow_tasks = session.run(
                """
                MATCH (t:ExecutionTask)
                WHERE t.execution_time > 60
                WITH t.description as task, avg(t.execution_time) as avg_time
                RETURN task, avg_time
                ORDER BY avg_time DESC
                LIMIT 3
                """
            )
            
            for record in slow_tasks:
                suggestions.append(
                    f"Task '{record['task'][:50]}' averages {record['avg_time']:.1f}s. "
                    f"Consider optimization or parallelization."
                )
            
            # Find underutilized cache
            cache_stats = session.run(
                """
                MATCH (c:CachedDecision)
                WITH avg(c.hit_count) as avg_hits
                WHERE avg_hits < 2
                RETURN avg_hits
                """
            ).single()
            
            if cache_stats and cache_stats['avg_hits'] < 2:
                suggestions.append(
                    f"Cache hit rate is low ({cache_stats['avg_hits']:.1f} avg hits). "
                    f"Consider adjusting cache TTL or key generation strategy."
                )
        
        return suggestions


class ContinuousLearningOrchestrator:
    """Main orchestrator for continuous learning system"""
    
    def __init__(self):
        # Neo4j connection
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            print("✅ Continuous Learning System connected to Neo4j")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            self.driver = None
        
        # Initialize components
        self.quality_scorer = QualityScorer(self.driver)
        self.pattern_detector = PatternDetector(self.driver)
        self.feedback_loop = FeedbackLoop(self.driver)
    
    def learn_from_execution(self, task_id: str, input_data: Dict, output: Any, 
                            execution_time: float, success: bool):
        """Learn from a single task execution"""
        # Score the output
        score = self.quality_scorer.score_output(task_id, output, execution_time)
        
        # Store successful examples
        if success and score > 0.7:
            self.feedback_loop.store_successful_example(task_id, input_data, output, score)
        
        # Detect patterns periodically
        if hash(task_id) % 10 == 0:  # Check every 10th execution
            self._detect_and_store_patterns()
        
        return score
    
    def _detect_and_store_patterns(self):
        """Detect and store execution patterns"""
        # Detect failure patterns
        failure_patterns = self.pattern_detector.detect_failure_patterns()
        for pattern in failure_patterns:
            self.pattern_detector.store_pattern(pattern)
        
        # Detect success patterns
        success_patterns = self.pattern_detector.detect_success_patterns()
        for pattern in success_patterns:
            self.pattern_detector.store_pattern(pattern)
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from the learning system"""
        insights = {
            'failure_patterns': self.pattern_detector.detect_failure_patterns(),
            'success_patterns': self.pattern_detector.detect_success_patterns(),
            'improvement_suggestions': self.feedback_loop.generate_improvement_suggestions()
        }
        
        # Add statistics
        if self.driver:
            with self.driver.session() as session:
                stats = session.run(
                    """
                    MATCH (e:SuccessfulExample)
                    WITH count(e) as total_examples, avg(e.score) as avg_score
                    MATCH (p:DetectedPattern)
                    WITH total_examples, avg_score, count(p) as total_patterns
                    MATCH (f:Feedback)
                    RETURN total_examples, avg_score, total_patterns, 
                           count(f) as total_feedback, avg(f.rating) as avg_rating
                    """
                ).single()
                
                if stats:
                    insights['statistics'] = {
                        'total_examples': stats['total_examples'],
                        'avg_example_score': stats['avg_score'],
                        'total_patterns': stats['total_patterns'],
                        'total_feedback': stats['total_feedback'],
                        'avg_feedback_rating': stats['avg_rating']
                    }
        
        return insights
    
    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.close()


# Convenience function
def setup_continuous_learning(crew) -> ContinuousLearningOrchestrator:
    """Setup continuous learning for a crew"""
    orchestrator = ContinuousLearningOrchestrator()
    
    # Add learning hooks to crew
    if hasattr(crew, 'tasks'):
        for task in crew.tasks:
            # Wrap task execution with learning
            if hasattr(task, 'execute'):
                original_execute = task.execute
                
                def learning_execute(*args, **kwargs):
                    start_time = time.time()
                    try:
                        result = original_execute(*args, **kwargs)
                        execution_time = time.time() - start_time
                        
                        # Learn from successful execution
                        task_id = getattr(task, 'id', str(task))
                        input_data = kwargs
                        orchestrator.learn_from_execution(
                            task_id, input_data, result, execution_time, True
                        )
                        
                        return result
                    except Exception as e:
                        execution_time = time.time() - start_time
                        
                        # Learn from failure
                        task_id = getattr(task, 'id', str(task))
                        input_data = kwargs
                        orchestrator.learn_from_execution(
                            task_id, input_data, str(e), execution_time, False
                        )
                        
                        raise
                
                task.execute = learning_execute
    
    return orchestrator