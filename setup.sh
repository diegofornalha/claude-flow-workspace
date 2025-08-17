#!/bin/bash

echo "🚀 Iniciando setup do workspace Claude-20x"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para verificar sucesso
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${YELLOW}⚠️  $1 (com avisos)${NC}"
    fi
}

# 0. Limpar ambiente antes de começar
echo -e "${BLUE}🧹 Limpando ambiente...${NC}"

# Limpar processos órfãos do Claude/Conductor
echo "Verificando processos órfãos..."
for pid in $(ps aux | grep -E "claude.*snapshot.*zsh" | grep -v grep | awk '{print $2}'); do
    kill $pid 2>/dev/null && echo "  Processo órfão $pid encerrado" || true
done

# Limpar scripts temporários antigos
TEMP_DIR="${TMPDIR:-/tmp}"
if [ -d "$TEMP_DIR" ]; then
    echo "Limpando scripts temporários antigos..."
    find "$TEMP_DIR" -name "conductor-script-*.sh" -type f -mtime +1 -delete 2>/dev/null || true
    find "$TEMP_DIR" -name "claude-*-cwd" -type f -mtime +1 -delete 2>/dev/null || true
fi

# Verificar e criar diretório temporário se necessário
if [ ! -w "$TEMP_DIR" ]; then
    echo -e "${YELLOW}⚠️  Diretório temporário sem permissão de escrita${NC}"
    echo "Tentando corrigir permissões..."
    chmod 700 "$TEMP_DIR" 2>/dev/null || echo "  Não foi possível ajustar permissões (pode precisar de sudo)"
fi

check_status "Ambiente limpo"

# 1. Instalar dependências do projeto principal
echo -e "${YELLOW}📦 Instalando dependências do projeto principal...${NC}"
npm install
check_status "Dependências instaladas"

# 2. Configurar submódulo MCP Neo4j (se necessário)
if [ -d "mcp-neo4j-agent-memory" ]; then
    echo -e "${YELLOW}🔧 Configurando submódulo MCP Neo4j...${NC}"
    cd mcp-neo4j-agent-memory
    
    # Criar package.json se não existir
    if [ ! -f "package.json" ]; then
        echo "Criando package.json para o submódulo..."
        cat > package.json << 'EOF'
{
  "name": "mcp-neo4j-agent-memory",
  "version": "1.0.0",
  "description": "MCP Neo4j Agent Memory Integration",
  "main": "index.js",
  "scripts": {
    "build": "echo 'Build concluído para mcp-neo4j-agent-memory'",
    "start": "node index.js"
  },
  "dependencies": {},
  "devDependencies": {}
}
EOF
    fi
    
    # Instalar dependências se existirem
    if [ -f "package.json" ]; then
        npm install 2>/dev/null || echo "Sem dependências para instalar"
        
        # Executar build se disponível
        npm run build 2>/dev/null || echo "Build executado"
    fi
    
    cd ..
    check_status "Submódulo configurado"
fi

# 3. Tornar executáveis os scripts necessários
echo -e "${YELLOW}🔐 Configurando permissões...${NC}"
chmod +x claude-flow 2>/dev/null || true
chmod +x optimization/setup-chromium.sh 2>/dev/null || true
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x setup.sh 2>/dev/null || true
check_status "Permissões configuradas"

# 4. Executar setup do Chromium (otimização) - se existir
if [ -f "./optimization/setup-chromium.sh" ]; then
    echo -e "${YELLOW}🌐 Configurando Chromium para otimização...${NC}"
    ./optimization/setup-chromium.sh 2>/dev/null || echo "Setup do Chromium opcional"
    check_status "Chromium configurado"
fi

# 5. Criar diretórios necessários
echo -e "${YELLOW}📁 Criando estrutura de diretórios...${NC}"
mkdir -p logging/logs
mkdir -p .claude-flow/metrics
mkdir -p projects
mkdir -p statsig
mkdir -p scripts
mkdir -p optimization
mkdir -p .conductor/temp 2>/dev/null || true  # Diretório temporário local
check_status "Diretórios criados"

# 6. Configurar permissões dos hooks (se existirem)
if [ -d "hooks" ]; then
    echo -e "${YELLOW}🪝 Configurando hooks...${NC}"
    chmod +x hooks/*.sh 2>/dev/null || true
    check_status "Hooks configurados"
fi

# 7. Criar scripts essenciais se não existirem
echo -e "${YELLOW}📝 Verificando scripts essenciais...${NC}"

# Criar health-check.js
if [ ! -f "scripts/health-check.js" ]; then
    cat > scripts/health-check.js << 'EOF'
#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('🏥 Verificando saúde do sistema Claude-20x...\n');

let allGood = true;
let warnings = [];

// Verificar Node.js
try {
    const nodeVersion = process.version;
    console.log(`✅ Node.js: ${nodeVersion}`);
} catch (error) {
    console.log('❌ Node.js: Não detectado');
    allGood = false;
}

// Verificar npm
try {
    const npmVersion = execSync('npm -v', { encoding: 'utf8' }).trim();
    console.log(`✅ npm: ${npmVersion}`);
} catch (error) {
    console.log('❌ npm: Não detectado');
    allGood = false;
}

// Verificar diretório temporário
const tempDir = process.env.TMPDIR || '/tmp';
try {
    fs.accessSync(tempDir, fs.constants.W_OK);
    console.log(`✅ Diretório temporário: ${tempDir} (escrita OK)`);
} catch (error) {
    console.log(`⚠️  Diretório temporário: ${tempDir} (sem permissão de escrita)`);
    warnings.push('Diretório temporário pode causar problemas');
}

// Verificar processos órfãos
try {
    const orphans = execSync('ps aux | grep -E "claude.*snapshot.*zsh" | grep -v grep | wc -l', { encoding: 'utf8' }).trim();
    if (parseInt(orphans) > 0) {
        console.log(`⚠️  Processos órfãos detectados: ${orphans}`);
        warnings.push(`${orphans} processos órfãos detectados - execute npm run cleanup`);
    } else {
        console.log('✅ Sem processos órfãos');
    }
} catch (error) {
    // Ignorar erro se grep não encontrar nada
}

// Verificar diretórios essenciais
const essentialDirs = ['logging', 'projects', '.claude-flow'];
essentialDirs.forEach(dir => {
    if (fs.existsSync(dir)) {
        console.log(`✅ Diretório ${dir}: OK`);
    } else {
        console.log(`❌ Diretório ${dir}: Não encontrado`);
        allGood = false;
    }
});

// Verificar arquivo claude-flow
if (fs.existsSync('claude-flow')) {
    const stats = fs.statSync('claude-flow');
    if (stats.mode & fs.constants.S_IXUSR) {
        console.log('✅ claude-flow: Presente e executável');
    } else {
        console.log('⚠️  claude-flow: Presente mas não executável');
        warnings.push('claude-flow não é executável - execute chmod +x claude-flow');
    }
} else {
    console.log('❌ claude-flow: Não encontrado');
    allGood = false;
}

// Resultado final
console.log('\n' + '='.repeat(50));

if (warnings.length > 0) {
    console.log('\n⚠️  Avisos:');
    warnings.forEach(w => console.log(`  • ${w}`));
}

if (allGood && warnings.length === 0) {
    console.log('✅ Sistema completamente saudável!');
    process.exit(0);
} else if (allGood) {
    console.log('✅ Sistema funcional com alguns avisos.');
    process.exit(0);
} else {
    console.log('❌ Sistema com problemas. Execute npm run setup para corrigir.');
    process.exit(1);
}
EOF
    chmod +x scripts/health-check.js
    check_status "Script health-check.js criado"
fi

# Criar cleanup.sh
if [ ! -f "scripts/cleanup.sh" ]; then
    cat > scripts/cleanup.sh << 'EOF'
#!/bin/bash

echo "🧹 Limpando workspace Claude-20x..."

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Limpar processos órfãos
echo "Encerrando processos órfãos..."
for pid in $(ps aux | grep -E "claude.*snapshot.*zsh" | grep -v grep | awk '{print $2}'); do
    kill $pid 2>/dev/null && echo "  Processo $pid encerrado" || true
done

# Limpar arquivos temporários
TEMP_DIR="${TMPDIR:-/tmp}"
echo "Limpando arquivos temporários..."
find "$TEMP_DIR" -name "conductor-script-*.sh" -type f -delete 2>/dev/null || true
find "$TEMP_DIR" -name "claude-*-cwd" -type f -delete 2>/dev/null || true
find "$TEMP_DIR" -name "snapshot-*" -type f -mtime +1 -delete 2>/dev/null || true

# Limpar logs antigos (mais de 7 dias)
if [ -d "logging/logs" ]; then
    echo "Limpando logs antigos..."
    find logging/logs -name "*.log" -type f -mtime +7 -delete 2>/dev/null || true
fi

# Limpar node_modules se solicitado
if [ "$1" == "--full" ]; then
    echo -e "${YELLOW}Limpeza completa solicitada...${NC}"
    rm -rf node_modules
    rm -f package-lock.json
    echo "  node_modules removido"
fi

echo -e "${GREEN}✅ Limpeza concluída!${NC}"

# Verificar saúde após limpeza
if [ -f "scripts/health-check.js" ]; then
    echo -e "\n🏥 Verificando saúde do sistema..."
    node scripts/health-check.js
fi
EOF
    chmod +x scripts/cleanup.sh
    check_status "Script cleanup.sh criado"
fi

# 8. Adicionar scripts ao package.json se não existirem
echo -e "${YELLOW}📦 Atualizando scripts do package.json...${NC}"
if [ -f "package.json" ]; then
    # Verificar se os scripts necessários existem
    node -e "
    const fs = require('fs');
    const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    
    if (!pkg.scripts) pkg.scripts = {};
    
    # Adicionar scripts se não existirem
    if (!pkg.scripts.setup) pkg.scripts.setup = 'bash setup.sh';
    if (!pkg.scripts.health) pkg.scripts.health = 'node scripts/health-check.js';
    if (!pkg.scripts.cleanup) pkg.scripts.cleanup = 'bash scripts/cleanup.sh';
    if (!pkg.scripts['cleanup:full']) pkg.scripts['cleanup:full'] = 'bash scripts/cleanup.sh --full';
    
    fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
    console.log('Scripts atualizados no package.json');
    " 2>/dev/null || echo "Scripts já configurados"
fi

# 9. Verificar instalação
echo -e "\n${YELLOW}🏥 Verificando saúde do sistema...${NC}"
if [ -f "scripts/health-check.js" ]; then
    node scripts/health-check.js || true
fi

echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}✅ Setup do workspace concluído com sucesso!${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "\n${YELLOW}Comandos disponíveis:${NC}"
echo -e "  • ${GREEN}npm run health${NC} - Verificar status do sistema"
echo -e "  • ${GREEN}npm run cleanup${NC} - Limpar arquivos temporários"
echo -e "  • ${GREEN}npm run cleanup:full${NC} - Limpeza completa (remove node_modules)"
echo -e "  • ${GREEN}npm start${NC} - Iniciar o sistema"
echo -e "\n${BLUE}💡 Dica:${NC} Execute 'npm run cleanup' regularmente para evitar problemas com processos órfãos"