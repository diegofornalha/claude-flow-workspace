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
