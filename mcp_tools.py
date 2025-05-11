"""
MCP tools wrapper for creating callable functions from MCP tools.
"""

import os
import json
import logging
import asyncio
from client import ServerConnection
from logging_config import configure_logging
import config

# Configure logging - this will set up all loggers to use Azure Application Insights
configure_logging()

# Get logger for this module - already configured by configure_logging()
logger = logging.getLogger(__name__)

def create_mcp_functions():
    """
    Creates Python functions for each MCP tool available in the server.
    
    Returns:
        list: List of Python callable functions for MCP tools.
    """

    logger.info(f"Connecting to MCP server at: {config.mcp_server_url}")
    
    # Get tools from MCP server
    async def fetch_tools():
        conn = ServerConnection(config.mcp_server_url)
        await conn.connect()
        tools = await conn.list_tools()
        await conn.cleanup()
        return tools
    
    # Store tool names globally for reference
    create_mcp_functions.mcp_tool_names = []
    
    try:
        tools = asyncio.run(fetch_tools())
        # Extract just the names for easy reference
        create_mcp_functions.mcp_tool_names = [tool['name'] for tool in tools]
    except Exception as e:
        logger.error(f"Error fetching MCP tools: {e}")
        tools = []
    logger.info(f"Found {len(tools)} MCP tools: {[tool['name'] for tool in tools]}")
    
    # Log the full schema of each tool for debugging
    for tool in tools:
        logger.info(f"Tool schema for '{tool['name']}': {json.dumps(tool)}")
    
    # Create a function for each tool
    mcp_functions = []
    for tool in tools:
        tool_name = tool["name"]
        
        # Define a function with the same name as the tool
        def make_func(name=tool_name):
            def tool_func(kwargs=None, **args):
                # Extra logging for debugging
                logger.info(f"Tool '{name}' function called with: kwargs={kwargs}, args={args}")
                
                # Handle both direct arguments and kwargs dict
                if kwargs is not None and isinstance(kwargs, str):
                    # It is a string, not a dict
                    logger.warning(f"Received kwargs as string: {kwargs}")
                    if kwargs == "":
                        args_to_use = {}
                    else:
                        try:
                            args_to_use = json.loads(kwargs)
                        except json.JSONDecodeError:
                            args_to_use = {"value": kwargs}
                elif kwargs is not None:
                    args_to_use = kwargs
                else:
                    args_to_use = args
                    
                # Special handling for Azure AI Agent Service format
                if isinstance(args_to_use, dict) and "kwargs" in args_to_use:
                    if isinstance(args_to_use["kwargs"], str):
                        logger.info(f"Found nested kwargs structure: {args_to_use}")
                        if args_to_use["kwargs"] == "":
                            args_to_use = {}
                        else:
                            try:
                                args_to_use = json.loads(args_to_use["kwargs"])
                            except (json.JSONDecodeError, TypeError):
                                # Keep as is if not valid JSON
                                pass
                
                logger.info(f"Executing MCP tool '{name}' with args: {args_to_use}")
                
                async def call_tool():
                    conn = ServerConnection(config.mcp_server_url)
                    await conn.connect()
                    result = await conn.execute_tool(name, args_to_use)
                    logger.info(f"MCP tool '{name}' result: {result}")
                    await conn.cleanup()
                    if isinstance(result, dict):
                        return json.dumps(result)
                    return result
                    
                return asyncio.run(call_tool())
            
            # Set function name to match tool name
            tool_func.__name__ = name
            return tool_func
            
        mcp_functions.append(make_func())
    
    return mcp_functions

def is_mcp_function(name):
    """
    Check if a function name is an MCP function.
    
    Args:
        name (str): Function name to check
        
    Returns:
        bool: True if it's an MCP function, False otherwise
    """
    return name in create_mcp_functions.mcp_tool_names

# Expose this helper function
create_mcp_functions.mcp_tool_names = []
