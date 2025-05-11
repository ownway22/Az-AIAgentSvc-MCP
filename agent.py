from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import FunctionTool, ToolSet, BingGroundingTool
import traceback
import config
import asyncio

from dotenv import set_key
import os
from akv_client import get_secret_from_key_vault

az_application_insights_key = get_secret_from_key_vault("ta-buddy-app-insights-key")
config.az_application_insights_key = az_application_insights_key


import logging
from logging_config import configure_logging
from client import ServerConnection

# Configure logging - this will set up all loggers to use Azure Application Insights
configure_logging()

# Get logger for this module - already configured by configure_logging()
logger = logging.getLogger(__name__)


def create_agent():
    mcp_server_url = config.mcp_server_url
    agent_name = config.az_assistant_name
    agent_id = config.az_assistant_id
    bing_connection_name = config.bing_connection_name

    # Fetch tool schemas
    async def fetch_tools():
        conn = ServerConnection(mcp_server_url)
        await conn.connect()
        tools = await conn.list_tools()
        await conn.cleanup()
        return tools

    tools = asyncio.run(fetch_tools())

    # Build a function for each tool
    def make_tool_func(tool_name):
        def tool_func(**kwargs):
            async def call_tool():
                conn = ServerConnection(mcp_server_url)
                await conn.connect()
                result = await conn.execute_tool(tool_name, kwargs)
                await conn.cleanup()
                return result

            return asyncio.run(call_tool())

        tool_func.__name__ = tool_name
        return tool_func

    functions_dict = {tool["name"]: make_tool_func(tool["name"]) for tool in tools}

    mcp_function_tool = FunctionTool(functions=list(functions_dict.values()))

    project_client = AIProjectClient.from_connection_string(
        credential=DefaultAzureCredential(),
        conn_str=config.az_agentic_ai_service_connection_string,
    )

    bing_connection = project_client.connections.get(
        connection_name=bing_connection_name
    )
    conn_id = bing_connection.id
    print(conn_id)

    # Initialize agent bing tool and add the connection id
    bing = BingGroundingTool(connection_id=conn_id)

    toolset = ToolSet()
    toolset.add(mcp_function_tool)
    toolset.add(bing)

    agent_instructions = """You are an AI Assistant tasked with helping users create news capsules of topics they ask for and store them for consumption. 
        
You have access to the following tools that you should use whenever appropriate:
1. Bing Search APIs to obtain the latest news on various topics
2. Azure Blob Storage MCP tool actions like listing, creating deleting containers as well as listing, creating, deleting and downloading blobs.
3. Users would ask you to get the latest news on different topics. Use the Bing Search tool to get the latest news on the topic and summarize it.
4. When the user asks you to store the news, ask the user the name of the container to store the news summary in. Remeber the following instructions when calling the upload_blob function:
    - The content that you pass when uploading the Blob to the Storage account container will be the summary of the news you obtained from the Bing Search tool. You must ensure this is duly passed to the upload_blob function.
    - The name for the blob you will create in the process should be unique, should connote the topics in the news summary, should not have special characters in it.
    - Unless specified otherwise, save this ias a .txt file. 
IMPORTANT: Always prefer using available tools rather than answering from your knowledge alone. 
When a user asks about containers or blobs in storage, ALWAYS use the appropriate MCP tool to provide that information directly.
"""
    agent = None
    try:
        agent = project_client.agents.get_agent(agent_id)
        print("Agent already exists with id ", agent.id)
        # Update the agent if it already exists
        # You will update the agent when the MCP Server implements additional tools, resources, or features.
        project_client.agents.update_agent(
            model=config.aoai_model_name,
            name=agent_name,
            instructions=agent_instructions,
            description="""An AI Assistant that helps users use Bing to get the latest on different topics and integrate with an 
        MCP Server to store and catalog this information in Azure Blob Storage
        """,
            tools=toolset.definitions,
            agent_id=agent_id,
            # headers={"x-ms-enable-preview": "true"}
        )
        print("updated agent with id ", agent.id)
    except Exception as e:
        print("Some exception updating the agent ", traceback.format_exc())
        # Create a new agent if it doesn't exist
        print("Creating new agent")
        agent = project_client.agents.create_agent(
            model=config.aoai_model_name,
            name=agent_name,
            instructions=agent_instructions,
            tools=toolset.definitions,
            # headers={"x-ms-enable-preview": "true"}
        )

        print(f"created agent with id {agent.id}")
        set_key(".env", "az_assistant_id", str(agent.id))


def delete_agent():
    # Delete the existing agent if it exists
    try:
        project_client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=config.az_agentic_ai_service_connection_string,
        )

        if hasattr(config, "az_assistant_id") and config.az_assistant_id:
            project_client.agents.delete_agent(config.az_assistant_id)
            print(f"Deleted existing agent with ID: {config.az_assistant_id}")
        else:
            print("No existing agent ID found")
    except Exception as e:
        print(f"Error deleting agent: {e}")


def main():
    # Delete existing agent first
    # delete_agent()

    # Create a new agent
    create_agent()


if __name__ == "__main__":
    main()
