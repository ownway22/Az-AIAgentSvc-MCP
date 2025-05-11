# MCP Integration for Azure AI Agent Service

This document provides an overview of the Model Context Protocol (MCP) integration with Azure AI Agent Service implemented in this project.

## Overview

The integration enables Azure AI Agent Service to communicate with MCP servers to discover and execute tools dynamically. This allows the agent to leverage a rich ecosystem of tools and functionality exposed through the MCP server.

## Components

1. **Agent Creation Process**:
   - Dynamic discovery of MCP tools at design time
   - Automatic creation of FunctionDefinition objects for MCP tools
   - Registration of these tools with Azure AI Agent Service

2. **Runtime Execution**:
   - Intelligent routing of function calls to MCP server
   - Seamless integration with existing user functions

## Key Files

- **create_mcp_agent.py**: Creates an agent with MCP tool definitions
- **mcp_executor.py**: Executes MCP tools at runtime
- **bots/state_management_bot.py**: Bot implementation that uses MCP tools

## Documentation

For detailed information, please refer to:

- **[MCP_INTEGRATION.md](MCP_INTEGRATION.md)**: Architecture and design details
- **[FUNCTION_REGISTRATION.md](FUNCTION_REGISTRATION.md)**: How FunctionDefinition is used
- **[TESTING_MCP_INTEGRATION.md](TESTING_MCP_INTEGRATION.md)**: Testing instructions

## Getting Started

1. **Setup MCP Server**: Ensure your MCP server is running
2. **Create Agent**:
   ```powershell
   .\setup_mcp_agent.ps1
   ```
3. **Update .env**: Add the generated agent ID to your `.env` file
4. **Run the Application**:
   ```powershell
   python app.py
   ```

## Benefits

This integration provides several advantages:

- **Dynamic Tool Discovery**: No hardcoding of tools needed
- **Flexible Execution**: Tools can be updated or added without changing code
- **Separation of Concerns**: Clean separation between agent and tools
- **Scalability**: Easy to add new capabilities through MCP tools
