"""
Sistema de Sincronização Cluster-Agente
Mantém consistência entre definições de agentes e clusters
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any
from neo4j import GraphDatabase
import hashlib


class ClusterAgentSync:
    """Sincroniza clusters e agentes entre diferentes fontes"""
    
    def __init__(self):
        self.base_dir = Path("/Users/2a/.claude/.conductor/baku")
        self.agents_dir = self.base_dir / ".claude" / "agents"
        self.config_dir = self.base_dir / "crew-ai" / "config"
        
        # Neo4j connection
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        
        self.driver = None
        self._connect_neo4j()
    
    def _connect_neo4j(self):
        """Conecta ao Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_username, self.neo4j_password)
            )
            print("✅ Connected to Neo4j for sync")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
    
    def scan_agent_definitions(self) -> Dict[str, List[Dict]]:
        """Escaneia todas as definições de agentes"""
        agents = {
            'markdown': [],
            'yaml': [],
            'neo4j': []
        }
        
        # 1. Scan markdown files
        if self.agents_dir.exists():
            for md_file in self.agents_dir.rglob("*.md"):
                agent_data = self._parse_markdown_agent(md_file)
                if agent_data:
                    agents['markdown'].append(agent_data)
        
        # 2. Scan YAML config
        yaml_file = self.config_dir / "agents.yaml"
        if yaml_file.exists():
            with open(yaml_file, 'r', encoding='utf-8') as f:
                yaml_agents = yaml.safe_load(f)
                for name, config in yaml_agents.items():
                    agents['yaml'].append({
                        'name': name,
                        'role': config.get('role', name),
                        'goal': config.get('goal'),
                        'backstory': config.get('backstory'),
                        'source': 'yaml_config'
                    })
        
        # 3. Query Neo4j
        if self.driver:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (a:Agent)
                    OPTIONAL MATCH (a)-[:BELONGS_TO]->(c:Cluster)
                    RETURN a.name as name, a.type as type, 
                           a.description as description,
                           c.name as cluster
                """)
                
                for record in result:
                    agents['neo4j'].append({
                        'name': record['name'],
                        'type': record['type'],
                        'description': record['description'],
                        'cluster': record['cluster'],
                        'source': 'neo4j'
                    })
        
        return agents
    
    def _parse_markdown_agent(self, filepath: Path) -> Dict:
        """Parseia arquivo markdown de agente"""
        try:
            content = filepath.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Busca frontmatter YAML
            if lines[0].strip() == '---':
                end_idx = lines.index('---', 1)
                yaml_content = '\n'.join(lines[1:end_idx])
                metadata = yaml.safe_load(yaml_content)
                
                if metadata and 'name' in metadata:
                    return {
                        'name': metadata['name'],
                        'type': metadata.get('type'),
                        'description': metadata.get('description'),
                        'capabilities': metadata.get('capabilities', []),
                        'cluster': self._get_cluster_from_path(filepath),
                        'source': 'markdown',
                        'filepath': str(filepath)
                    }
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
        
        return None
    
    def _get_cluster_from_path(self, filepath: Path) -> str:
        """Determina cluster baseado no path do arquivo"""
        path_str = str(filepath)
        if 'core' in path_str:
            return 'core'
        elif 'specialized' in path_str:
            return 'specialized'
        elif 'quality' in path_str:
            return 'quality'
        elif 'orchestration' in path_str:
            return 'orchestration'
        elif 'implementation' in path_str:
            return 'implementation'
        else:
            return 'general'
    
    def identify_inconsistencies(self, agents: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """Identifica inconsistências entre fontes"""
        inconsistencies = {
            'missing_in_yaml': [],
            'missing_in_neo4j': [],
            'missing_in_markdown': [],
            'conflicting_definitions': [],
            'orphan_agents': []
        }
        
        # Criar conjuntos de nomes por fonte
        md_names = {a['name'] for a in agents['markdown'] if a}
        yaml_names = {a['name'] for a in agents['yaml']}
        neo4j_names = {a['name'] for a in agents['neo4j']}
        
        # Identificar ausências
        all_names = md_names | yaml_names | neo4j_names
        
        for name in all_names:
            if name not in yaml_names:
                inconsistencies['missing_in_yaml'].append(name)
            if name not in neo4j_names:
                inconsistencies['missing_in_neo4j'].append(name)
            if name not in md_names:
                inconsistencies['missing_in_markdown'].append(name)
        
        # Identificar definições conflitantes
        for name in all_names:
            definitions = []
            
            for source in ['markdown', 'yaml', 'neo4j']:
                agent = next((a for a in agents[source] if a and a.get('name') == name), None)
                if agent:
                    definitions.append({
                        'source': source,
                        'data': agent
                    })
            
            if len(definitions) > 1:
                # Verificar se há conflitos significativos
                types = {d['data'].get('type') or d['data'].get('role') for d in definitions}
                if len(types) > 1:
                    inconsistencies['conflicting_definitions'].append({
                        'name': name,
                        'conflicts': definitions
                    })
        
        # Identificar agentes órfãos (sem cluster)
        for agent in agents['neo4j']:
            if not agent.get('cluster'):
                inconsistencies['orphan_agents'].append(agent['name'])
        
        return inconsistencies
    
    def synchronize_all(self) -> Dict[str, Any]:
        """Sincroniza todas as fontes de dados"""
        print("\n🔄 Starting Full Synchronization...")
        
        # 1. Escanear todas as fontes
        agents = self.scan_agent_definitions()
        
        # 2. Identificar inconsistências
        inconsistencies = self.identify_inconsistencies(agents)
        
        # 3. Criar mapa unificado
        unified_agents = self._create_unified_map(agents)
        
        # 4. Sincronizar Neo4j
        sync_results = self._sync_to_neo4j(unified_agents)
        
        # 5. Atualizar YAML config
        self._update_yaml_config(unified_agents)
        
        # 6. Gerar relatório
        report = {
            'total_agents': len(unified_agents),
            'sources': {
                'markdown': len(agents['markdown']),
                'yaml': len(agents['yaml']),
                'neo4j': len(agents['neo4j'])
            },
            'inconsistencies': inconsistencies,
            'sync_results': sync_results
        }
        
        return report
    
    def _create_unified_map(self, agents: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """Cria mapa unificado de agentes com prioridade: yaml > markdown > neo4j"""
        unified = {}
        
        # Prioridade 3: Neo4j (base)
        for agent in agents['neo4j']:
            unified[agent['name']] = agent
        
        # Prioridade 2: Markdown (sobrescreve Neo4j)
        for agent in agents['markdown']:
            if agent:
                name = agent['name']
                if name in unified:
                    unified[name].update(agent)
                else:
                    unified[name] = agent
        
        # Prioridade 1: YAML (sobrescreve tudo)
        for agent in agents['yaml']:
            name = agent['name']
            if name in unified:
                unified[name].update(agent)
            else:
                unified[name] = agent
        
        return unified
    
    def _sync_to_neo4j(self, unified_agents: Dict[str, Dict]) -> Dict:
        """Sincroniza agentes unificados com Neo4j"""
        if not self.driver:
            return {'error': 'Neo4j not connected'}
        
        results = {
            'created': 0,
            'updated': 0,
            'errors': []
        }
        
        with self.driver.session() as session:
            for name, agent in unified_agents.items():
                try:
                    # Criar ou atualizar agente
                    result = session.run("""
                        MERGE (a:Agent {name: $name})
                        SET a.type = $type,
                            a.role = $role,
                            a.description = $description,
                            a.goal = $goal,
                            a.source = $source,
                            a.synced_at = datetime()
                        RETURN a
                    """, 
                        name=name,
                        type=agent.get('type', agent.get('role')),
                        role=agent.get('role'),
                        description=agent.get('description', agent.get('backstory')),
                        goal=agent.get('goal'),
                        source=agent.get('source', 'sync')
                    )
                    
                    if result.single():
                        results['updated'] += 1
                    
                    # Conectar ao cluster se existir
                    if agent.get('cluster'):
                        session.run("""
                            MERGE (c:Cluster {name: $cluster})
                            WITH c
                            MATCH (a:Agent {name: $agent_name})
                            MERGE (a)-[:BELONGS_TO]->(c)
                        """, cluster=agent['cluster'], agent_name=name)
                    
                    # Adicionar capacidades
                    if agent.get('capabilities'):
                        for capability in agent['capabilities']:
                            session.run("""
                                MERGE (cap:Capability {name: $capability})
                                WITH cap
                                MATCH (a:Agent {name: $agent_name})
                                MERGE (a)-[:HAS_CAPABILITY]->(cap)
                            """, capability=capability, agent_name=name)
                    
                except Exception as e:
                    results['errors'].append(f"{name}: {str(e)}")
        
        return results
    
    def _update_yaml_config(self, unified_agents: Dict[str, Dict]):
        """Atualiza arquivo YAML com agentes unificados"""
        yaml_file = self.config_dir / "agents.yaml"
        
        # Preparar estrutura YAML
        yaml_data = {}
        for name, agent in unified_agents.items():
            yaml_data[name] = {
                'role': agent.get('role', name),
                'goal': agent.get('goal', f"Execute tasks related to {name}"),
                'backstory': agent.get('backstory', agent.get('description', f"Expert agent specialized in {name} operations"))
            }
        
        # Salvar arquivo
        with open(yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)
    
    def generate_sync_report(self, report: Dict) -> str:
        """Gera relatório de sincronização formatado"""
        lines = []
        lines.append("=" * 60)
        lines.append("📊 CLUSTER-AGENT SYNCHRONIZATION REPORT")
        lines.append("=" * 60)
        
        lines.append(f"\n✅ Total Agents Synchronized: {report['total_agents']}")
        
        lines.append("\n📂 Source Distribution:")
        for source, count in report['sources'].items():
            lines.append(f"  - {source}: {count} agents")
        
        inconsistencies = report['inconsistencies']
        if any(inconsistencies.values()):
            lines.append("\n⚠️ Inconsistencies Found:")
            
            if inconsistencies['missing_in_yaml']:
                lines.append(f"  Missing in YAML: {', '.join(inconsistencies['missing_in_yaml'])}")
            
            if inconsistencies['missing_in_neo4j']:
                lines.append(f"  Missing in Neo4j: {', '.join(inconsistencies['missing_in_neo4j'])}")
            
            if inconsistencies['missing_in_markdown']:
                lines.append(f"  Missing in Markdown: {', '.join(inconsistencies['missing_in_markdown'])}")
            
            if inconsistencies['conflicting_definitions']:
                lines.append(f"  Conflicting Definitions: {len(inconsistencies['conflicting_definitions'])} agents")
            
            if inconsistencies['orphan_agents']:
                lines.append(f"  Orphan Agents: {', '.join(inconsistencies['orphan_agents'])}")
        else:
            lines.append("\n✅ No inconsistencies found - all sources aligned!")
        
        if 'sync_results' in report:
            sync = report['sync_results']
            lines.append(f"\n🔄 Neo4j Sync Results:")
            lines.append(f"  Updated: {sync.get('updated', 0)}")
            if sync.get('errors'):
                lines.append(f"  Errors: {len(sync['errors'])}")
        
        lines.append("\n" + "=" * 60)
        
        return '\n'.join(lines)
    
    def close(self):
        """Fecha conexão com Neo4j"""
        if self.driver:
            self.driver.close()


def run_synchronization():
    """Executa sincronização completa"""
    sync = ClusterAgentSync()
    
    try:
        # Executar sincronização
        report = sync.synchronize_all()
        
        # Gerar e exibir relatório
        report_text = sync.generate_sync_report(report)
        print(report_text)
        
        # Salvar relatório
        report_file = Path("/Users/2a/.claude/.conductor/baku/crew-ai/sync_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📝 Full report saved to: {report_file}")
        
    finally:
        sync.close()


if __name__ == "__main__":
    run_synchronization()