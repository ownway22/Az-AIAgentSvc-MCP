#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
from dotenv import load_dotenv
load_dotenv()


""" Bot Configuration """
PORT = 3978
APP_ID = ""
APP_PASSWORD = ""
APP_TYPE = "MultiTenant"
APP_TENANTID = "" # leave empty for MultiTenant

az_agentic_ai_service_connection_string=os.getenv("az_agentic_ai_service_connection_string")
az_application_insights_key=None
az_assistant_id = os.getenv("az_assistant_id")
az_assistant_name = os.getenv("AZ_ASSISTANT_NAME")
bing_connection_name = os.getenv("BING_CONNECTION_NAME")
aoai_model_name = os.getenv("aoai_model_name", "gpt-4o")

# MCP Server URL with default value
mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")