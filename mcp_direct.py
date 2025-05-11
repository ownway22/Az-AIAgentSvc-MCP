"""
MCP Direct Handler - Provides direct access to MCP server functions bypassing Python limitations.
"""

import os
import json
import logging
import asyncio
import nest_asyncio
from client import ServerConnection
from logging_config import configure_logging
import config

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Configure logging - this will set up all loggers to use Azure Application Insights
configure_logging()

# Get logger for this module - already configured by configure_logging()
logger = logging.getLogger(__name__)

# This function can be called directly to execute an MCP tool without going through the Python callable
async def execute_mcp_tool_directly(function_name, arguments):
    """
    Execute an MCP tool directly, bypassing any Python callable functions.
    
    Args:
        function_name (str): Name of the MCP tool to execute
        arguments (dict): Arguments to pass to the tool
        
    Returns:
        The result of the tool execution
    """
    logger.info(f"Direct MCP Tool Execution for '{function_name}' with arguments: {arguments}")
    
    # Process arguments in case they are wrapped in a kwargs structure
    args_to_use = {}
    if isinstance(arguments, dict):
        if "kwargs" in arguments:
            if isinstance(arguments["kwargs"], str):
                if arguments["kwargs"] == "":
                    args_to_use = {}
                else:
                    try:
                        args_to_use = json.loads(arguments["kwargs"])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse kwargs as JSON: {arguments['kwargs']}")
                        args_to_use = {"value": arguments["kwargs"]}
            else:
                args_to_use = arguments["kwargs"]
        else:
            args_to_use = arguments
    
    logger.info(f"Processed arguments for MCP call: {args_to_use}")
    
    # Connect to MCP server and execute the tool
    conn = ServerConnection(config.mcp_server_url)
    await conn.connect()
    result = await conn.execute_tool(function_name, args_to_use)
    await conn.cleanup()
    
    logger.info(f"MCP tool '{function_name}' result: {result}")
    return result

# This is a wrapper that can be called from non-async code
async def execute_mcp_tool_async(function_name, arguments):
    """
    Async wrapper for execute_mcp_tool_directly.
    
    Args:
        function_name (str): Name of the MCP tool to execute
        arguments (dict): Arguments to pass to the tool
        
    Returns:
        The result of the tool execution
    """
    result = await execute_mcp_tool_directly(function_name, arguments)
    if isinstance(result, dict):
        return json.dumps(result)
    return str(result)

