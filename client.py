#!/usr/bin/env python
"""
MCP Client implementation for interacting with the MCP server.
This client follows Azure best practices for resource management, error handling,
and secure connection handling.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple, Union
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

import httpx
from azure.identity import DefaultAzureCredential
from azure.core.credentials import TokenCredential

try:
    # Python SDK Version 1.0.0 and above
    from openai import AzureOpenAI
except ImportError:
    # Use older Azure OpenAI package if available
    try:
        from azure.ai.openai import AzureOpenAI
    except ImportError:
        raise ImportError(
            "Neither the openai package (v1.0.0+) nor azure.ai.openai package is installed"
        )

from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import config

# Import the centralized logging configuration
from logging_config import configure_logging

# Configure logging - this will set up all loggers to use Azure Application Insights
configure_logging()

# Get logger for this module - already configured by configure_logging()
logger = logging.getLogger(__name__)


class Configuration:
    """Manages configuration and environment variables for the MCP client."""

    def __init__(self) -> None:
        """Initialize configuration with environment variables."""
        self.load_env()

        # MCP Server URL - Read from environment variable with fallback
        self.mcp_server_url = config.mcp_server_url
        if not self.mcp_server_url:
            self.mcp_server_url = "http://localhost:8000/sse"  # Only used as fallback
            logger.warning(
                f"MCP_SERVER_URL not found in environment, using default: {self.mcp_server_url}"
            )
        else:
            logger.info(f"Using MCP server URL from environment: {self.mcp_server_url}")

    @staticmethod
    def load_env() -> None:
        """Load environment variables from .env file."""
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        """
        Load server configuration from JSON file.

        Args:
            file_path: Path to the JSON configuration file.

        Returns:
            Dict containing server configuration.

        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            JSONDecodeError: If configuration file is invalid JSON.
        """
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {file_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise

    @property
    def azure_credential(self) -> TokenCredential:
        """
        Get Azure managed identity credential.

        Returns:
            DefaultAzureCredential
        """
        try:
            return DefaultAzureCredential()
        except Exception as e:
            logger.error(f"Error creating Azure credential: {e}")
            raise ValueError(f"Failed to create Azure managed identity credential: {e}")


class ServerConnection:
    """
    Manages connection to an MCP server with proper resource lifecycle management.
    Implements robust error handling and timeout management.
    """

    def __init__(self, server_url: str) -> None:
        """
        Initialize the ServerConnection with the server URL.

        Args:
            server_url: The URL of the MCP server, e.g., http://localhost:8000/sse
        """
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self._cleanup_lock = asyncio.Lock()
        self.exit_stack = AsyncExitStack()
        self._tools_cache: Optional[List[Any]] = None
        self.connected = False

    async def connect(self, timeout: float = 30.0) -> bool:
        """
        Connect to the MCP server with timeout.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connection succeeded, False otherwise
        """
        try:
            # Create connection with timeout
            connection_task = self._connect()
            await asyncio.wait_for(connection_task, timeout=timeout)
            self.connected = True
            return True
        except asyncio.TimeoutError:
            logger.error(f"Connection to {self.server_url} timed out after {timeout}s")
            await self.cleanup()
            return False
        except Exception as e:
            logger.error(f"Failed to connect to {self.server_url}: {e}")
            await self.cleanup()
            return False

    async def _connect(self) -> None:
        """
        Internal method to establish server connection with proper resource tracking.
        """
        try:
            # Connect to the server using SSE
            read_write = await self.exit_stack.enter_async_context(
                sse_client(self.server_url)
            )
            read_stream, write_stream = read_write

            # Create and initialize session
            session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            self.session = session
            logger.info(f"Connected to MCP server at {self.server_url}")

        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from the MCP server.

        Returns:
            List of tool definitions

        Raises:
            RuntimeError: If not connected to server
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        if self._tools_cache is None:
            tools_response = await self.session.list_tools()
            self._tools_cache = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools_response.tools
            ]

        return self._tools_cache

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Execute a tool on the MCP server with retry logic.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            retries: Number of retry attempts for transient failures
            retry_delay: Base delay between retries (will use exponential backoff)

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If not connected to server
            ValueError: If the tool doesn't exist
            Exception: On tool execution failure after all retries
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        # Verify tool exists
        tools = await self.list_tools()
        if not any(tool["name"] == tool_name for tool in tools):
            raise ValueError(f"Tool '{tool_name}' not found on MCP server")


        # Implement retry with exponential backoff
        attempt = 0
        last_exception = None

        while attempt <= retries:
            try:
                logger.info(
                    f"Executing tool '{tool_name}' (attempt {attempt + 1}/{retries + 1})..."
                )
                result = await self.session.call_tool(tool_name, arguments)

                if result and result.content:
                    try:
                        return json.loads(result.content[0].text)
                    except json.JSONDecodeError:
                        return {"text": result.content[0].text}
                else:
                    return {"error": "No content received from tool"}

            except Exception as e:
                last_exception = e
                attempt += 1
                if attempt <= retries:
                    delay = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"Tool execution failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Tool execution failed after {retries + 1} attempts: {e}"
                    )
                    raise Exception(
                        f"Failed to execute tool '{tool_name}': {e}"
                    ) from last_exception

    async def cleanup(self) -> None:
        """
        Clean up all resources safely. Can be called multiple times.
        """
        async with self._cleanup_lock:
            logger.debug("Cleaning up server connection resources")
            try:
                await self.exit_stack.aclose()
                self.session = None
                self._tools_cache = None
                self.connected = False
                logger.info("Server connection resources cleaned up")
            except Exception as e:
                logger.warning(f"Error during resource cleanup: {e}")


class Tool:
    """
    Represents an MCP tool with rich metadata and utility methods.
    """

    def __init__(
        self, name: str, description: str, input_schema: Dict[str, Any]
    ) -> None:
        """
        Initialize a Tool object.

        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON schema for tool input
        """
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._required_params = input_schema.get("required", [])
        self._properties = input_schema.get("properties", {})

    @property
    def required_params(self) -> List[str]:
        """Get list of required parameters."""
        return self._required_params

    @property
    def parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get tool parameter definitions."""
        return self._properties

    def validate_arguments(
        self, arguments: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate arguments against tool schema.

        Args:
            arguments: Arguments to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for param in self.required_params:
            if param not in arguments:
                return False, f"Required parameter '{param}' is missing"

        # Validate parameter types (basic validation only)
        for param_name, param_value in arguments.items():
            if param_name in self._properties:
                param_schema = self._properties[param_name]
                param_type = param_schema.get("type")

                # Very basic type checking
                if param_type == "string" and not isinstance(param_value, str):
                    return False, f"Parameter '{param_name}' should be a string"
                elif param_type == "number" and not isinstance(
                    param_value, (int, float)
                ):
                    return False, f"Parameter '{param_name}' should be a number"
                elif param_type == "integer" and not isinstance(param_value, int):
                    return False, f"Parameter '{param_name}' should be an integer"
                elif param_type == "boolean" and not isinstance(param_value, bool):
                    return False, f"Parameter '{param_name}' should be a boolean"
                elif param_type == "array" and not isinstance(param_value, list):
                    return False, f"Parameter '{param_name}' should be an array"
                elif param_type == "object" and not isinstance(param_value, dict):
                    return False, f"Parameter '{param_name}' should be an object"

        return True, None

    