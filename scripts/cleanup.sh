#!/bin/bash

echo "🧹 Iniciando limpeza do workspace: ${CONDUCTOR_WORKSPACE_NAME:-almaty}"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Definir path do workspace
WORKSPACE_PATH="${CONDUCTOR_WORKSPACE_PATH:-$(pwd)}"

# Função para verificar sucesso
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${YELLOW}⚠️  $1${NC}"
    fi
}

# Modo interativo ou automático
INTERACTIVE=true
if [ "$1" == "--auto" ] || [ "$1" == "-a" ]; then
    INTERACTIVE=false
    echo -e "${YELLOW}Modo automático ativado${NC}"
fi

# 1. Parar processos Node em execução (se houver)
echo -e "${YELLOW}🛑 Parando processos Node do workspace...${NC}"
if [ -n "$WORKSPACE_PATH" ]; then
    # Buscar apenas processos relacionados ao workspace atual
    pgrep -f "node.*$WORKSPACE_PATH" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        pkill -f "node.*$WORKSPACE_PATH" 2>/dev/null || true
        check_status "Processos Node parados"
    else
        echo "Nenhum processo Node ativo no workspace"
    fi
fi

# 2. Limpar cache do npm (apenas em modo interativo)
if [ "$INTERACTIVE" = true ]; then
    echo -e "${YELLOW}Deseja limpar o cache do npm? (s/N)${NC}"
    read -t 10 -n 1 CLEAR_NPM_CACHE
    echo
    if [[ "$CLEAR_NPM_CACHE" =~ ^[Ss]$ ]]; then
        echo -e "${YELLOW}🗑️  Limpando cache do npm...${NC}"
        npm cache clean --force 2>/dev/null || true
        check_status "Cache npm limpo"
    fi
fi

# 3. Remover node_modules (economiza muito espaço)
if [ "$INTERACTIVE" = true ]; then
    echo -e "${YELLOW}Deseja remover node_modules? Isso libera muito espaço. (s/N)${NC}"
    read -t 10 -n 1 REMOVE_NODE_MODULES
    echo
else
    REMOVE_NODE_MODULES="n"  # Por padrão não remove em modo automático
fi

if [[ "$REMOVE_NODE_MODULES" =~ ^[Ss]$ ]]; then
    echo -e "${YELLOW}📦 Removendo node_modules...${NC}"
    if [ -d "$WORKSPACE_PATH/node_modules" ]; then
        rm -rf "$WORKSPACE_PATH/node_modules" 2>/dev/null || true
    fi
    if [ -d "$WORKSPACE_PATH/mcp-neo4j-agent-memory/node_modules" ]; then
        rm -rf "$WORKSPACE_PATH/mcp-neo4j-agent-memory/node_modules" 2>/dev/null || true
    fi
    check_status "node_modules removidos"
    echo -e "${YELLOW}⚠️  Execute 'npm install' para reinstalar as dependências${NC}"
fi

# 4. Limpar logs e arquivos temporários
echo -e "${YELLOW}📄 Limpando logs e arquivos temporários...${NC}"

# Limpar logs antigos (mais de 7 dias)
if [ -d "$WORKSPACE_PATH/logging/logs" ]; then
    find "$WORKSPACE_PATH/logging/logs" -name "*.log" -mtime +7 -delete 2>/dev/null || true
    find "$WORKSPACE_PATH/logging/logs" -name "*.jsonl" -mtime +7 -delete 2>/dev/null || true
fi

# Limpar métricas antigas (mais de 30 dias)
if [ -d "$WORKSPACE_PATH/.claude-flow/metrics" ]; then
    find "$WORKSPACE_PATH/.claude-flow/metrics" -type f -mtime +30 -delete 2>/dev/null || true
fi

# Limpar arquivos temporários do statsig
if [ -d "$WORKSPACE_PATH/statsig" ]; then
    rm -rf "$WORKSPACE_PATH/statsig/*.tmp" 2>/dev/null || true
    rm -rf "$WORKSPACE_PATH/statsig/*.log" 2>/dev/null || true
fi

check_status "Logs e temporários limpos"

# 5. Limpar diretórios de build
echo -e "${YELLOW}🏗️  Limpando diretórios de build...${NC}"
[ -d "$WORKSPACE_PATH/build" ] && rm -rf "$WORKSPACE_PATH/build" 2>/dev/null || true
[ -d "$WORKSPACE_PATH/dist" ] && rm -rf "$WORKSPACE_PATH/dist" 2>/dev/null || true
[ -d "$WORKSPACE_PATH/mcp-neo4j-agent-memory/build" ] && rm -rf "$WORKSPACE_PATH/mcp-neo4j-agent-memory/build" 2>/dev/null || true
check_status "Diretórios de build limpos"

# 6. Limpar shell snapshots antigos (mais de 1 dia)
if [ -d "$WORKSPACE_PATH/shell-snapshots" ]; then
    echo -e "${YELLOW}📸 Limpando snapshots antigos...${NC}"
    SNAPSHOT_COUNT=$(find "$WORKSPACE_PATH/shell-snapshots" -name "*.sh" -mtime +1 2>/dev/null | wc -l)
    if [ "$SNAPSHOT_COUNT" -gt 0 ]; then
        find "$WORKSPACE_PATH/shell-snapshots" -name "*.sh" -mtime +1 -delete 2>/dev/null || true
        check_status "$SNAPSHOT_COUNT snapshots antigos removidos"
    else
        echo "Nenhum snapshot antigo encontrado"
    fi
fi

# 7. Limpar arquivos de sistema desnecessários
echo -e "${YELLOW}⚙️  Limpando arquivos de sistema...${NC}"
find "$WORKSPACE_PATH" -name ".DS_Store" -delete 2>/dev/null || true
find "$WORKSPACE_PATH" -name "Thumbs.db" -delete 2>/dev/null || true
find "$WORKSPACE_PATH" -name "*.swp" -delete 2>/dev/null || true
find "$WORKSPACE_PATH" -name "*.swo" -delete 2>/dev/null || true
find "$WORKSPACE_PATH" -name "*~" -delete 2>/dev/null || true
check_status "Arquivos de sistema limpos"

# 8. Fechar conexões com Neo4j (se houver)
# Nota: Neo4j geralmente roda globalmente, então apenas informamos
echo -e "${YELLOW}ℹ️  Neo4j: Serviço global mantido (não afetado pela limpeza)${NC}"

# 9. Mostrar estatísticas finais
echo -e "\n${GREEN}📊 Resumo da limpeza:${NC}"
echo -e "${GREEN}============================================${NC}"

# Calcular espaço usado
if [ -d "$WORKSPACE_PATH" ]; then
    SPACE_USED=$(du -sh "$WORKSPACE_PATH" 2>/dev/null | cut -f1)
    echo -e "Espaço usado no workspace: ${GREEN}$SPACE_USED${NC}"
    
    # Contar arquivos restantes
    FILE_COUNT=$(find "$WORKSPACE_PATH" -type f 2>/dev/null | wc -l)
    echo -e "Total de arquivos: ${GREEN}$FILE_COUNT${NC}"
    
    # Listar diretórios principais e seus tamanhos
    echo -e "\nDiretórios principais:"
    du -sh "$WORKSPACE_PATH"/* 2>/dev/null | head -10 | while read size dir; do
        dirname=$(basename "$dir")
        echo -e "  • $dirname: $size"
    done
fi

echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}✅ Limpeza do workspace concluída!${NC}"
echo -e "${GREEN}============================================${NC}"

# Dicas finais
echo -e "\n${YELLOW}Dicas:${NC}"
if [[ "$REMOVE_NODE_MODULES" =~ ^[Ss]$ ]]; then
    echo -e "  • Execute ${GREEN}npm install${NC} para reinstalar as dependências"
fi
echo -e "  • Execute ${GREEN}npm run setup${NC} para reconfigurar o ambiente"
echo -e "  • Execute ${GREEN}npm run health${NC} para verificar o status do sistema"

# Verificar saúde após limpeza (mantido do script original)
if [ -f "scripts/health-check.js" ]; then
    echo -e "\n🏥 Verificando saúde do sistema..."
    node scripts/health-check.js
fi
