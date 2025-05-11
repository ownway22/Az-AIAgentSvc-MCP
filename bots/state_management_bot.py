# filepath: c:\Users\sansri\agentic-ai-service-samples\web-researcher-agent\bots\state_management_bot.py
from botbuilder.core import ActivityHandler, ConversationState, TurnContext, UserState

from data_models.user_profile import UserProfile
from data_models.conversation_data import ConversationData
import time
from datetime import datetime
from azure.ai.projects.models import (
    FunctionTool,
    RequiredFunctionToolCall,
    SubmitToolOutputsAction,
    ToolOutput,
)
import time
import logging
import json
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import FunctionTool
from mcp_tools import create_mcp_functions, is_mcp_function
from client import ServerConnection
from mcp_direct import execute_mcp_tool_async
import os
import config
# Use the centralized logging configuration
from logging_config import configure_logging


# Configure logging - this will set up all loggers to use Azure Application Insights
configure_logging()

# Get logger for this module - already configured by configure_logging()
logger = logging.getLogger(__name__)

# MCP tool functions
mcp_functions = create_mcp_functions()
logger.info(f"MCP functions created: {[func.__name__ for func in mcp_functions]}")
functions = FunctionTool(functions=mcp_functions)
        
class StateManagementBot(ActivityHandler):

    connection = None

    def __init__(self, conversation_state: ConversationState, user_state: UserState):
        if conversation_state is None:
            raise TypeError(
                "[StateManagementBot]: Missing parameter. conversation_state is required but None was given"
            )
        if user_state is None:
            raise TypeError(
                "[StateManagementBot]: Missing parameter. user_state is required but None was given"
            )

        self.conversation_state = conversation_state
        self.user_state = user_state

        # Create Azure OpenAI client
        self.project_client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=config.az_agentic_ai_service_connection_string,
        )

        
        # retrieve the agent already created
        self.agent = self.project_client.agents.get_agent(config.az_assistant_id)
        print("retrieved agent with id ", self.agent.id)

        self.conversation_data_accessor = self.conversation_state.create_property(
            "ConversationData"
        )
        self.user_profile_accessor = self.user_state.create_property("UserProfile")

    async def on_message_activity(self, turn_context: TurnContext):

        # Get the state properties from the turn context.
        user_profile = await self.user_profile_accessor.get(turn_context, UserProfile)
        conversation_data = await self.conversation_data_accessor.get(
            turn_context, ConversationData
        )

        if user_profile.name is None:
            # First time around this is undefined, so we will prompt user for name.
            if conversation_data.prompted_for_user_name:
                # Set the name to what the user provided.
                user_profile.name = turn_context.activity.text

                # Acknowledge that we got their name.
                await turn_context.send_activity(
                    f"Thanks { user_profile.name }. Let me know how can I help you today"
                )

                # Reset the flag to allow the bot to go though the cycle again.
                conversation_data.prompted_for_user_name = False
            else:
                # Prompt the user for their name.
                await turn_context.send_activity(
                    "I am your AI Assistant and here to help you with your research and search on the internet on various topics. "
                    + "Can you help me with your name?"
                )

                # Set the flag to true, so we don't prompt in the next turn.
                conversation_data.prompted_for_user_name = True
        else:
            # Add message details to the conversation data.
            conversation_data.timestamp = self.__datetime_from_utc_to_local(
                turn_context.activity.timestamp
            )
            conversation_data.channel_id = turn_context.activity.channel_id

            l_thread = conversation_data.thread

            if l_thread is None:
                # Create a thread
                conversation_data.thread = self.project_client.agents.create_thread()
                l_thread = conversation_data.thread
                # Threads have an id as well
                print("creating a new session and thread for this user!")
                print("Created thread bearing Thread id: ", conversation_data.thread.id)

            # Create message to thread
            message = self.project_client.agents.create_message(
                thread_id=l_thread.id, role="user", content=turn_context.activity.text
            )
            print(f"Created message, ID: {message.id}")

            # Create a run to process the message
            run = self.project_client.agents.create_run(
                thread_id=l_thread.id, agent_id=self.agent.id
            )
            print(f"Created thread run, ID: {run.id}")
            
            print("***** the run status is: *******", run.status)

            # Monitor the run status
            while run.status in ["queued", "in_progress", "requires_action"]:
                time.sleep(1)
                run = self.project_client.agents.get_run(
                    thread_id=l_thread.id, run_id=run.id
                )

                # Handle function calling if required
                if run.status == "requires_action" and isinstance(
                    run.required_action, SubmitToolOutputsAction
                ):
                    print("Run requires function calls to be executed...")
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    
                    if not tool_calls:
                        print("No tool calls provided - cancelling run")
                        self.project_client.agents.cancel_run(
                            thread_id=l_thread.id, run_id=run.id
                        )
                        break
                    
                    # Process each tool call
                    tool_outputs = []
                    for tool_call in tool_calls:
                        if isinstance(tool_call, RequiredFunctionToolCall):
                            try:
                                # Get function name and arguments
                                function_name = tool_call.function.name
                                args_json = tool_call.function.arguments
                                arguments = json.loads(args_json) if args_json else {}
                                
                                logger.info(f"Executing tool call: {function_name} with args: {arguments}")
                                
                                # Debug all available functions in our FunctionTool
                                available_funcs = []
                                for func in functions._functions:
                                    # print(f"Function name: {func}")
                                    # available_funcs.append(func.__name__)
                                    available_funcs.append(func)
                                logger.info(f"Available registered functions: {available_funcs}")
                                
                                try:
                                    logger.info(f"Attempting to execute {function_name} via FunctionTool")
                                    matched_function = None
                                    for func in mcp_functions:
                                        try:
                                            if hasattr(func, '__name__') and func.__name__ == function_name:
                                                matched_function = func
                                                break
                                        except (AttributeError, TypeError):
                                            # Skip this function if it doesn't have __name__ attribute
                                            continue                                    
                                    # Dynamic check if this is an MCP function by name
                                    if is_mcp_function(function_name):
                                        # Direct MCP execution using our specialized handler
                                        logger.info(f"Using direct MCP handler for storage function: {function_name}")
                                        
                                        # Special handling for upload_blob to ensure content is provided
                                        if function_name == "upload_blob" and "content" not in arguments:
                                            logger.warning("upload_blob missing required 'content' parameter")
                                            if "text" in arguments:
                                                # If 'text' is provided but not 'content', use text as content
                                                logger.info("Using 'text' field as 'content' for upload_blob")
                                                arguments["content"] = arguments["text"]
                                            elif "value" in arguments:
                                                # If 'value' is provided but not 'content', use value as content
                                                logger.info("Using 'value' field as 'content' for upload_blob")
                                                arguments["content"] = arguments["value"]
                                            
                                        # Use the specialized MCP executor that bypasses the Python callable
                                        try:
                                            # Use the async version since we're in an async context
                                            output = await execute_mcp_tool_async(function_name, arguments)
                                            logger.info(f"Direct MCP execution succeeded: {output}")
                                        except Exception as direct_error:
                                            logger.error(f"Direct MCP execution failed: {direct_error}")
                                            logger.error(f"Error details: {traceback.format_exc()}")
                                            output = json.dumps({"error": f"Failed to execute {function_name}: {str(direct_error)}"})
                                    else:
                                        # Use FunctionTool as fallback
                                        output = functions.execute(tool_call)
                                        
                                    logger.info(f"Successfully executed {function_name}, output: {output}")
                                except Exception as e:
                                    import traceback
                                    logger.error(f"Error executing {function_name}: {e}")
                                    logger.error(f"Error details: {str(e)}")
                                    logger.error(f"Arguments type: {type(arguments)}, value: {arguments}")
                                    logger.error(f"Stack trace: {traceback.format_exc()}")
                                
                                # Add result to tool outputs
                                tool_outputs.append(
                                    ToolOutput(
                                        tool_call_id=tool_call.id,
                                        output=output,
                                    )
                                )
                                logger.info(f"Successfully executed {function_name}")
                                
                            except Exception as e:
                                logger.error(f"Error executing tool_call {tool_call.id}: {e}")
                                #logger.error(f"Stack trace: {traceback.format_exc()}")

                    # Submit tool outputs back to the run
                    print(f"Submitting {len(tool_outputs)} tool outputs")
                    if tool_outputs:
                        self.project_client.agents.submit_tool_outputs_to_run(
                            thread_id=l_thread.id,
                            run_id=run.id,
                            tool_outputs=tool_outputs,
                        )

                print(f"Current run status: {run.status}")

            # Fetch and log all messages
            messages = self.project_client.agents.list_messages(thread_id=l_thread.id)
            assistant_response = ""
            for message in messages["data"]:
                if message["role"] == "assistant":
                    if message.get("content") and len(message["content"]) > 0:
                        assistant_response = message["content"][0]["text"]["value"]
                        break

            return await turn_context.send_activity(assistant_response)

    async def on_turn(self, turn_context: TurnContext):
        await super().on_turn(turn_context)

        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    def __datetime_from_utc_to_local(self, utc_datetime):
        now_timestamp = time.time()
        offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(
            now_timestamp
        )
        result = utc_datetime + offset
        return result.strftime("%I:%M:%S %p, %A, %B %d of %Y")
