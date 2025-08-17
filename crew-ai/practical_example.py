#!/usr/bin/env python3
"""
Exemplo Prático: Sistema de Aprendizado e Bridge em Ação
Mostra como o sistema melhora com o tempo
"""

import time
import json
from typing import Dict, Any, List

class SimulatedNeo4jLearningTool:
    """Simulação do Neo4jLearningTool"""
    
    def __init__(self):
        self.patterns = {}
        self.scores = {}
    
    def learn_from_execution(self, task: str, execution_time: float, success: bool) -> Dict:
        """Aprende com cada execução"""
        
        # Calcula score baseado no tempo e sucesso
        if success:
            if execution_time < 5:
                score = 0.9  # Excelente
            elif execution_time < 10:
                score = 0.7  # Bom
            else:
                score = 0.5  # Regular
        else:
            score = -0.5  # Falha
        
        # Atualiza padrão ou cria novo
        pattern_id = f"pattern_{task}"
        if pattern_id in self.patterns:
            # Média ponderada com histórico
            old_score = self.scores[pattern_id]
            occurrences = self.patterns[pattern_id]['occurrences']
            new_score = (old_score * occurrences + score) / (occurrences + 1)
            
            self.patterns[pattern_id]['occurrences'] += 1
            self.scores[pattern_id] = new_score
            
            improvement = new_score - old_score
            status = "📈 Melhorou" if improvement > 0 else "📉 Piorou"
            
            return {
                'pattern': pattern_id,
                'old_score': old_score,
                'new_score': new_score,
                'improvement': improvement,
                'status': status,
                'recommendation': self.get_recommendation(new_score)
            }
        else:
            # Primeiro registro
            self.patterns[pattern_id] = {
                'task': task,
                'occurrences': 1,
                'first_time': execution_time
            }
            self.scores[pattern_id] = score
            
            return {
                'pattern': pattern_id,
                'new_score': score,
                'status': '🆕 Novo padrão',
                'recommendation': self.get_recommendation(score)
            }
    
    def get_recommendation(self, score: float) -> str:
        """Retorna recomendação baseada no score"""
        if score > 0.8:
            return "✅ Continue com esta abordagem - alta eficiência"
        elif score > 0.6:
            return "⚡ Considere paralelização para melhorar"
        elif score > 0.4:
            return "🔧 Otimização necessária - verifique gargalos"
        else:
            return "⚠️ Revisar implementação - baixo desempenho"


class SimulatedMCPBridge:
    """Simulação do Bridge MCP-CrewAI"""
    
    def __init__(self):
        self.memories = {}
        self.context_cache = {}
        self.sync_count = 0
    
    def sync_memory(self, agent: str, memory_type: str, content: Any) -> bool:
        """Sincroniza memória do agente com Neo4j"""
        
        memory_id = f"{agent}_{memory_type}_{self.sync_count}"
        self.sync_count += 1
        
        # Armazena memória
        if agent not in self.memories:
            self.memories[agent] = []
        
        self.memories[agent].append({
            'id': memory_id,
            'type': memory_type,
            'content': content,
            'timestamp': time.time(),
            'mcp_synced': True
        })
        
        print(f"   💾 Memória sincronizada: {memory_id}")
        return True
    
    def get_context(self, agent: str) -> Dict:
        """Recupera contexto do agente"""
        
        context = {
            'agent': agent,
            'memories': self.memories.get(agent, [])[-5:],  # Últimas 5 memórias
            'patterns': [],
            'recommendations': []
        }
        
        # Adiciona padrões relevantes
        if agent in self.memories:
            for memory in self.memories[agent]:
                if memory['type'] == 'pattern':
                    context['patterns'].append(memory['content'])
        
        # Cache do contexto
        self.context_cache[agent] = context
        
        return context


def simulate_learning_cycle():
    """Simula um ciclo completo de aprendizado"""
    
    print("\n" + "="*70)
    print("🎮 SIMULAÇÃO: SISTEMA APRENDENDO E MELHORANDO")
    print("="*70)
    
    # Inicializa componentes
    learning_tool = SimulatedNeo4jLearningTool()
    bridge = SimulatedMCPBridge()
    
    # Simula 5 execuções da mesma tarefa
    task_name = "optimize_workflow"
    agent_name = "planner"
    
    # Tempos simulados (melhorando com aprendizado)
    execution_times = [12.0, 8.5, 6.2, 4.8, 3.9]
    
    print(f"\n📋 Tarefa: {task_name}")
    print(f"🤖 Agente: {agent_name}\n")
    
    for i, exec_time in enumerate(execution_times, 1):
        print(f"EXECUÇÃO {i}:")
        print("-" * 40)
        
        # 1. Busca contexto
        context = bridge.get_context(agent_name)
        print(f"1️⃣  Contexto carregado: {len(context['memories'])} memórias")
        
        # 2. Executa tarefa
        print(f"2️⃣  Executando... Tempo: {exec_time}s")
        
        # 3. Learning Tool analisa
        learning_result = learning_tool.learn_from_execution(
            task_name, 
            exec_time, 
            success=True
        )
        
        print(f"3️⃣  Análise de aprendizado:")
        print(f"   Score: {learning_result.get('new_score', 0):.2f}")
        print(f"   Status: {learning_result['status']}")
        
        if 'improvement' in learning_result:
            imp = learning_result['improvement']
            if imp > 0:
                print(f"   Melhoria: +{imp:.2%}")
            else:
                print(f"   Variação: {imp:.2%}")
        
        # 4. Sincroniza memória
        bridge.sync_memory(
            agent_name,
            'execution_result',
            {
                'task': task_name,
                'time': exec_time,
                'score': learning_result.get('new_score', 0)
            }
        )
        
        # 5. Salva padrão aprendido
        if learning_result.get('new_score', 0) > 0.7:
            bridge.sync_memory(
                agent_name,
                'pattern',
                {
                    'type': 'efficient_execution',
                    'recommendation': learning_result['recommendation']
                }
            )
        
        print(f"4️⃣  Recomendação: {learning_result['recommendation']}")
        print()
    
    # Resumo final
    print("="*70)
    print("📊 RESULTADO DO APRENDIZADO:")
    print("="*70)
    
    initial_time = execution_times[0]
    final_time = execution_times[-1]
    improvement = (initial_time - final_time) / initial_time * 100
    
    print(f"⏱️  Tempo inicial: {initial_time}s")
    print(f"⏱️  Tempo final: {final_time}s")
    print(f"📈 MELHORIA TOTAL: {improvement:.1f}%")
    print(f"💾 Memórias criadas: {bridge.sync_count}")
    print(f"🧠 Padrões aprendidos: {len(learning_tool.patterns)}")
    
    # Mostra evolução do score
    print("\n📈 EVOLUÇÃO DO SCORE:")
    print("─" * 30)
    for pattern_id, score in learning_tool.scores.items():
        occurrences = learning_tool.patterns[pattern_id]['occurrences']
        print(f"   {pattern_id}: {score:.2f} (após {occurrences} execuções)")
    
    print("\n✅ O sistema aprendeu e otimizou o processo em 67.5%!")
    print("🔄 Cada execução usa o conhecimento anterior para melhorar!")


def demonstrate_bidirectional_flow():
    """Demonstra o fluxo bidirecional de comunicação"""
    
    print("\n" + "="*70)
    print("🔄 FLUXO BIDIRECIONAL EM TEMPO REAL")
    print("="*70)
    
    bridge = SimulatedMCPBridge()
    
    # Simula comunicação bidirecional
    agents = ['planner', 'coder', 'tester']
    
    print("\n➡️  DIREÇÃO 1: CrewAI → Neo4j")
    print("─" * 35)
    
    for agent in agents:
        # Agente envia dados
        bridge.sync_memory(
            agent,
            'task_start',
            {'task': f'{agent}_task', 'status': 'iniciado'}
        )
        time.sleep(0.5)  # Simula processamento
    
    print("\n⬅️  DIREÇÃO 2: Neo4j → CrewAI")
    print("─" * 35)
    
    for agent in agents:
        # Agente recebe contexto
        context = bridge.get_context(agent)
        print(f"   📥 {agent} recebeu contexto com {len(context['memories'])} memórias")
        
        # Usa contexto para decisão
        if len(context['memories']) > 0:
            last_memory = context['memories'][-1]
            print(f"      └─ Última ação: {last_memory['content']['task']}")
    
    print("\n🔄 COMUNICAÇÃO BIDIRECIONAL COMPLETA!")
    print("   ├─ Dados fluem em ambas direções")
    print("   ├─ Sincronização em tempo real")
    print("   └─ Contexto sempre atualizado")


if __name__ == "__main__":
    print("\n🚀 DEMONSTRAÇÃO PRÁTICA DO SISTEMA")
    
    # Executa simulações
    simulate_learning_cycle()
    demonstrate_bidirectional_flow()
    
    print("\n" + "="*70)
    print("💡 CONCLUSÃO:")
    print("="*70)
    print("O sistema Neo4j + CrewAI oferece:")
    print("✅ Aprendizado contínuo que melhora a cada execução")
    print("✅ Comunicação bidirecional em tempo real")
    print("✅ Memória persistente entre execuções")
    print("✅ Detecção automática de padrões")
    print("✅ Recomendações inteligentes baseadas em histórico")
    print("="*70)