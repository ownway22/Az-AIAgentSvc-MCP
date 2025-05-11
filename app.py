# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import sys
import traceback
from datetime import datetime

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
    ConversationState,
    MemoryStorage,
    UserState
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes
import config

from akv_client import get_secret_from_key_vault

az_application_insights_key = get_secret_from_key_vault(
    "ta-buddy-app-insights-key"
)
config.az_application_insights_key = az_application_insights_key

from botbuilder.core import MemoryStorage
from bots.state_management_bot import StateManagementBot


import logging
from logging_config import configure_logging

# Import the upload blob diagnostics
try:
    from logs.upload_blob_diagnostics import log_upload_blob_operation, monitor_upload_blob
    # This will patch the execute_mcp_tool_directly function with extra diagnostics
    print("Upload blob diagnostics enabled")
except ImportError as e:
    print(f"Upload blob diagnostics not available: {e}")

# Configure logging before any Azure SDK clients are initialized
# This will set up all loggers to use Azure Application Insights
configure_logging()

# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
SETTINGS = BotFrameworkAdapterSettings(config.APP_ID, config.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)
MEMORY = MemoryStorage()
USER_STATE = UserState(MEMORY)
CONVERSATION_STATE = ConversationState(MEMORY)

# Create the Bot
BOT = StateManagementBot(CONVERSATION_STATE, USER_STATE)

# Configure static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# Get logger for this module - already configured by configure_logging()
logger = logging.getLogger(__name__)



# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    logger.error(error, exc_info=True)
    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )
    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)

ADAPTER.on_turn_error = on_error


# Listen for incoming requests on /api/messages
async def messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=415)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)

    logger.warning('processed user message!!!!!!!')
    # print('received a user message')
    if response:
        logger.warning('processed user messages \t',response.body)
        return json_response(data=response.body, status=response.status)
    return Response(status=201)


# Serve static files
async def index(req: Request) -> web.FileResponse:
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/", index)
APP.router.add_static("/static", STATIC_DIR)

if __name__ == "__main__":
    port = config.PORT
    max_retry = 3
    retry_count = 0
    
    while retry_count < max_retry:
        try:
            print(f"Server running at http://localhost:{port}")
            web.run_app(APP, host="localhost", port=port)
            break
        except OSError as e:
            if e.errno == 10048:  # Port already in use
                retry_count += 1
                port += 1
                print(f"Port {port-1} is in use. Trying port {port}...")
            else:
                print(f"Error starting server: {e}")
                raise e
        except Exception as error:
            print(f"Unexpected error: {error}")
            raise error
