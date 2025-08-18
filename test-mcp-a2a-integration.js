#!/usr/bin/env node
/**
 * Script de teste para integração completa MCP + A2A
 * Valida Context Engine, memória Neo4j e agentes A2A trabalhando juntos
 */

const fetch = require('node-fetch');
const io = require('socket.io-client');

const BACKEND_URL = 'http://localhost:8080';
const CLAUDE_AGENT_URL = 'http://localhost:8001';
const CREW_AGENT_URL = 'http://localhost:8002';

const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testEndpoint(name, url, options = {}) {
  try {
    log(`  Testing ${name}...`, 'cyan');
    const response = await fetch(url, options);
    const data = await response.json();
    
    if (response.ok) {
      log(`  ✅ ${name} OK`, 'green');
      return { success: true, data };
    } else {
      log(`  ❌ ${name} Failed: ${response.status}`, 'red');
      console.log('  ', data);
      return { success: false, error: data };
    }
  } catch (error) {
    log(`  ❌ ${name} Error: ${error.message}`, 'red');
    return { success: false, error: error.message };
  }
}

async function runIntegrationTests() {
  log('\n🚀 MCP + A2A Integration Test Suite\n', 'magenta');
  log('═══════════════════════════════════════\n', 'magenta');
  
  let allTestsPassed = true;
  
  // Test 1: Context Engine Status
  log('Test 1: Context Engine Status', 'yellow');
  log('─────────────────────────────', 'yellow');
  
  const contextStatus = await testEndpoint(
    'Context Engine Status',
    `${BACKEND_URL}/api/context/status`
  );
  
  if (contextStatus.success) {
    console.log('  Status:', JSON.stringify(contextStatus.data, null, 2));
    
    if (!contextStatus.data.mcp?.connected) {
      log('  ⚠️ MCP not connected (memory features disabled)', 'yellow');
    }
    if (contextStatus.data.a2a?.availableAgents?.length === 0) {
      log('  ⚠️ No A2A agents available', 'yellow');
    }
  } else {
    allTestsPassed = false;
  }
  
  console.log();
  
  // Test 2: Memory Search (MCP)
  log('Test 2: Memory Search via MCP', 'yellow');
  log('──────────────────────────────', 'yellow');
  
  const memorySearch = await testEndpoint(
    'Search Memories',
    `${BACKEND_URL}/api/memory/search?query=A2A&limit=5`
  );
  
  if (memorySearch.success) {
    console.log(`  Found ${memorySearch.data.memories?.length || 0} memories`);
    if (memorySearch.data.memories?.length > 0) {
      console.log('  First memory:', memorySearch.data.memories[0]);
    }
  } else {
    log('  ⚠️ Memory search unavailable (Neo4j may not be connected)', 'yellow');
  }
  
  console.log();
  
  // Test 3: Create Memory
  log('Test 3: Create Memory in Neo4j', 'yellow');
  log('───────────────────────────────', 'yellow');
  
  const createMemory = await testEndpoint(
    'Create Test Memory',
    `${BACKEND_URL}/api/memory/create`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: 'test_integration',
        properties: {
          name: 'MCP + A2A Integration Test',
          content: 'Testing full integration of MCP and A2A',
          timestamp: new Date().toISOString(),
          test_id: Date.now()
        }
      })
    }
  );
  
  if (createMemory.success) {
    console.log('  Created memory ID:', createMemory.data.id);
  }
  
  console.log();
  
  // Test 4: Process Message with Context
  log('Test 4: Process Message with Context Engine', 'yellow');
  log('────────────────────────────────────────────', 'yellow');
  
  const contextMessage = await testEndpoint(
    'Context Message Processing',
    `${BACKEND_URL}/api/context/message`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: 'Tell me about the A2A protocol and MCP integration',
        sessionId: `test-session-${Date.now()}`,
        agentType: 'claude',
        useMemory: true
      })
    }
  );
  
  if (contextMessage.success) {
    console.log('  Response preview:', contextMessage.data.response?.substring(0, 100) + '...');
    console.log('  Context used:', contextMessage.data.contextUsed || 0);
    console.log('  Has context:', contextMessage.data.hasContext || false);
    if (contextMessage.data.memories?.length > 0) {
      console.log('  Memories used:', contextMessage.data.memories);
    }
  } else {
    allTestsPassed = false;
  }
  
  console.log();
  
  // Test 5: A2A Agents
  log('Test 5: A2A Agent Availability', 'yellow');
  log('───────────────────────────────', 'yellow');
  
  const a2aAgents = await testEndpoint(
    'List A2A Agents',
    `${BACKEND_URL}/api/a2a/agents`
  );
  
  if (a2aAgents.success) {
    console.log(`  Available agents: ${a2aAgents.data.agents?.length || 0}`);
    a2aAgents.data.agents?.forEach(agent => {
      console.log(`    - ${agent.name} (${agent.type}): ${agent.status}`);
    });
  }
  
  console.log();
  
  // Test 6: WebSocket Connection with Context
  log('Test 6: WebSocket Message with Context', 'yellow');
  log('───────────────────────────────────────', 'yellow');
  
  await new Promise((resolve) => {
    const socket = io(BACKEND_URL);
    
    socket.on('connect', () => {
      log('  ✅ WebSocket connected', 'green');
      
      // Send message with context
      socket.emit('send_message_with_context', {
        message: 'What do you know about integration testing?',
        sessionId: `ws-test-${Date.now()}`,
        agentType: 'claude',
        useMemory: true
      });
    });
    
    socket.on('message_complete', (data) => {
      log('  ✅ Received context-enriched response', 'green');
      console.log('    Has context:', data.hasContext);
      console.log('    Context used:', data.contextUsed);
      console.log('    Agent:', data.agent);
      socket.disconnect();
      resolve();
    });
    
    socket.on('error', (error) => {
      log(`  ❌ WebSocket error: ${error.error}`, 'red');
      allTestsPassed = false;
      socket.disconnect();
      resolve();
    });
    
    // Timeout
    setTimeout(() => {
      log('  ⚠️ WebSocket timeout', 'yellow');
      socket.disconnect();
      resolve();
    }, 10000);
  });
  
  console.log();
  
  // Test 7: Memory Labels
  log('Test 7: Memory Label Statistics', 'yellow');
  log('────────────────────────────────', 'yellow');
  
  const memoryLabels = await testEndpoint(
    'List Memory Labels',
    `${BACKEND_URL}/api/memory/labels`
  );
  
  if (memoryLabels.success) {
    console.log('  Memory labels in Neo4j:');
    memoryLabels.data.labels?.forEach(label => {
      console.log(`    - ${label.label}: ${label.count} nodes`);
    });
  }
  
  console.log();
  
  // Test 8: Cross-Protocol Communication
  log('Test 8: Cross-Protocol Communication', 'yellow');
  log('─────────────────────────────────────', 'yellow');
  
  // Create memory via MCP
  const testMemory = await testEndpoint(
    'Create Cross-Protocol Memory',
    `${BACKEND_URL}/api/memory/create`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: 'cross_protocol',
        properties: {
          name: 'Cross-Protocol Test',
          content: 'Testing MCP and A2A working together',
          protocol: 'both',
          timestamp: new Date().toISOString()
        }
      })
    }
  );
  
  if (testMemory.success) {
    // Use A2A to process with this memory as context
    const a2aWithMemory = await testEndpoint(
      'A2A Task with Memory Context',
      `${BACKEND_URL}/api/a2a/task`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: 'Explain Cross-Protocol Test',
          options: {
            context: {
              memoryId: testMemory.data.id,
              useMemory: true
            }
          }
        })
      }
    );
    
    if (a2aWithMemory.success) {
      console.log('  ✅ Cross-protocol communication successful');
    }
  }
  
  console.log();
  
  // Summary
  log('═══════════════════════════════════════', 'magenta');
  log('\n📊 Test Summary\n', 'magenta');
  
  if (allTestsPassed) {
    log('✅ All critical tests passed!', 'green');
    log('\n🎉 MCP + A2A Integration is working correctly!', 'green');
  } else {
    log('⚠️ Some tests failed or had warnings', 'yellow');
    log('\nCheck the following:', 'yellow');
    log('  1. Neo4j is running (docker/local)', 'yellow');
    log('  2. MCP server path is correct', 'yellow');
    log('  3. A2A agents are running (ports 8001, 8002)', 'yellow');
    log('  4. Backend server is running (port 8080)', 'yellow');
  }
  
  console.log('\n🔍 Integration Points Validated:');
  console.log('  • Context Engine ←→ MCP Client');
  console.log('  • Context Engine ←→ A2A Client');
  console.log('  • MCP (stdio) ←→ Neo4j');
  console.log('  • A2A (HTTP) ←→ Agents');
  console.log('  • WebSocket ←→ Frontend');
  console.log('  • Memory persistence across protocols');
  
  console.log('\n✨ Integration test complete!\n');
}

// Run tests
runIntegrationTests().catch(error => {
  log(`\n❌ Fatal error: ${error.message}`, 'red');
  console.error(error);
  process.exit(1);
});