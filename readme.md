# News Compiler AI Agent with Azure AI Agent Service and MCP

This project showcases an AI-powered news compiler agent built with Azure AI Agent Service that seamlessly integrates with a Model Context Protocol (MCP) Server. The agent allows users to search for news on various topics using Azure's Bing Search tool, summarize the findings, and catalog this information into an Azure Blob Storage account via the MCP Server.

## Overview

The News Compiler AI Agent demonstrates how an Azure AI Agent Service agent can discover and utilize tools and resources exposed by an MCP Server. This architecture creates a loosely coupled system where the agent and storage operations are separate concerns, allowing for greater flexibility and maintainability.

**Features**

- Search for news on topics the user is interested in using the Bing Search tool
- Summarize news articles into digestible formats
- Store and organize these summaries in Azure Blob Storage by topic
- Manage storage containers and blobs through natural language commands

## Architecture

The application follows a modular architecture that leverages Azure services along with the Model Context Protocol (MCP) to create a loosely coupled system.

### Components

1. **Azure AI Agent Service Agent**:
   - Provides natural language understanding using a GPT model
   - Implements a Bing Search Tool for retrieving current news
   - Dynamically discovers and integrates with MCP Server tool actions

2. **MCP Server**:
   - Implements the Model Context Protocol
   - Exposes Azure Blob Storage operations as tool actions
   - Provides a schema for the agent to understand available operations

3. **Microsoft Bot Framework Application**:
   - Hosts the AI Agent within a Bot Framework app
   - Manages conversation state and user profiles
   - Relays messages between users and the Azure AI Agent Service

4. **Azure Blob Storage**:
   - Stores news summaries by topic in organized containers
   - Provides persistent storage for later retrieval

## How It Works

### Step 1: Creating an Agent

When initializing the system, the application connects to the MCP Server to discover available tools and resources:

1. The application uses the MCP Client to establish a connection with the MCP Server
2. It retrieves the schema of all available tools and resources from the MCP Server
3. For each tool discovered, it creates a function stub and registers it with the Azure AI Agent Service
4. The agent is configured with appropriate instructions to use these tools effectively

When the MCP Server adds or updates tools, running this step again will detect the changes and update the functions registered with the Azure AI Agent Service.

![alt text](/images/functionstubs.png)

### Step 2: Running the Azure AI Agent Service Assistant

Once the agent is created and configured:

1. Users interact with the agent through the Bot Framework Emulator using natural language
2. When users request news on a topic, the agent uses its native Bing Search tool to find current information
3. The agent summarizes the news using its language capabilities
4. When users request to store information, the agent:
   - Asks for a storage container name/category
   - Creates a unique, meaningful blob name related to the content
   - Passes the news summary to the MCP Server via HTTPS/SSE protocol
   - The MCP Server executes the appropriate Azure Storage SDK operations

The integration is loosely coupled - the Agent only knows about the tool signatures and how to call them, while the MCP Server handles the implementation details of interacting with Azure Storage.

![alt text](/images/emulator.png)

## Code Structure

- **agent.py**: Creates and configures the Azure AI Agent Service agent
- **app.py**: Main Bot Framework application entry point
- **client.py**: MCP Client implementation for connecting to MCP Server
- **mcp_direct.py**: Provides direct access to MCP server functions
- **mcp_tools.py**: Creates Python function stubs for MCP tools
- **config.py**: Configuration settings and environment variables
- **akv_client.py**: Azure Key Vault client for secure access to secrets
- **logging_config.py**: Configures logging to Azure Application Insights
- **bots/state_management_bot.py**: Bot implementation that manages state
- **data_models/**: Contains classes for user profiles and conversation data, implemented using the Bot Framework

## Getting Started

### Prerequisites

- Python 3.8+
- Azure Subscription with:
  - Azure AI Agent Service instance
  - Azure Blob Storage account
  - Azure Application Insights (for telemetry)
  - Azure Key Vault (optional, for secure secret management)
- Bot Framework Emulator (for testing)
- MCP Server (see below)

### MCP Server Setup

This project requires an MCP Server that implements Azure Blob Storage operations. The MCP Server itself is not part of this project, but you can find an implementation at:
[Azure-Samples/mcp-azure-storage](https://github.com/MSFT-Innovation-Hub-India/MCP-Az-storage-Svc-Sample)

### Installation Steps

1. **Clone the repository**:
    
    ```sh
    git clone https://github.com/your-username/agentic-ai-service-samples.git
    cd agentic-ai-service-samples/web-researcher-agent
    ```

2. **Create and activate a virtual environment**:
    
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. **Install Python dependencies**:
    
    ```sh
    pip install -r requirements.txt
    ```

4. **Set up environment variables**:
    - Create a `.env` file in the root directory.
    - Add the necessary environment variables as shown below:

    ```sh
    az_agentic_ai_service_connection_string="your-agentic-ai-service-connection-string"
    az_assistant_id='your-assistant-id'
    MCP_SERVER_URL="https://your-mcp-server-url/sse"
    AZ_ASSISTANT_NAME="contoso-news-compiler-ai-agent"
    BING_CONNECTION_NAME="your-bing-connection-name"
    aoai_model_name="gpt-4o"
    akv="your-key-vault-name"  # Optional, for Azure Key Vault
    ```

### Usage

1. **Create the agent** (first time or when MCP tools change):
   ```sh
   python agent.py
   ```

2. **Run the Bot Framework application**:
   ```sh
   python app.py
   ```

3. **Connect using Bot Framework Emulator**:
   - Open Bot Framework Emulator
   - Connect to http://localhost:3978/api/messages
   - Start chatting with your news compiler agent

## Conversation Examples

```
User: Find me the latest news about quantum computing
Agent: I'll search for the latest news on quantum computing...

[Agent provides a summary of recent quantum computing news]

User: Can you save that summary for me?
Agent: I'd be happy to save this summary for you. What would you like to name the container to store it in?

User: tech-news
Agent: I'll save the quantum computing news summary in the "tech-news" container.

[Agent creates or uses existing container and stores the blob]

Agent: I've saved the summary as "quantum_computing_news_20250511.txt" in the "tech-news" container.
```

Here's another example showing container management:

```
User: What containers do I have?
Agent: Let me check the available containers in storage...

[Agent lists all containers]

User: Create a new container called "finance-news"
Agent: I'll create a new container called "finance-news"...

[Agent creates the container]

Agent: I've successfully created the "finance-news" container.
```

## Understanding MCP and Azure AI Agent Service Integration

The Model Context Protocol (MCP) is a communication protocol that enables AI agents to discover and interact with tools and resources in a standardized way. This project demonstrates the power of MCP by showing how an Azure AI Agent Service agent can:

1. **Dynamically discover tools**: The agent automatically discovers all tools and resources exposed by the MCP Server
2. **Adapt to changes**: When new tools are added to the MCP Server, the agent can be updated to incorporate them
3. **Execute operations**: The agent can perform operations on Azure Blob Storage via the MCP Server

Key benefits of this approach:
- **Separation of concerns**: The agent focuses on language understanding while the MCP Server handles storage operations
- **Maintainability**: Updates to storage logic can be made in the MCP Server without modifying the agent
- **Extensibility**: New storage operations can be added to the MCP Server and discovered by the agent

## Deployment Options

This Bot Framework Application can be deployed using various Azure services:
- Azure App Service
- Azure Container Apps
- Azure Functions

For convenience, it is tested locally using the [Microsoft Bot Framework Emulator](https://github.com/Microsoft/BotFramework-Emulator/releases/tag/v4.15.1)

For production deployment, follow the [Azure Bot Service deployment guide](https://learn.microsoft.com/en-us/azure/bot-service/bot-builder-deploy-az-cli).

## Additional Resources

- [Azure AI Agent Service Documentation](https://learn.microsoft.com/en-us/azure/ai-services/agents/
- [Microsoft Bot Framework Documentation](https://learn.microsoft.com/en-us/azure/bot-service/)
- [Bot Framework Emulator](https://github.com/Microsoft/BotFramework-Emulator/releases/tag/v4.15.1)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/introduction)
- [Azure Blob Storage Documentation](https://learn.microsoft.com/en-us/azure/storage/blobs/)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.