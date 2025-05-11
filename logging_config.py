"""
Configure logging for the application to control verbosity levels
and direct all logs to Azure Application Insights
"""
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler
import config

def configure_logging():
    """
    Configure logging levels for different components of the application.
    Redirects all logs to Azure Application Insights instead of console.
    Specifically reduces the verbosity of Azure SDK HTTP logging.
    """

    
    # Create formatter for consistent log format
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Create Azure Application Insights handler
    ai_handler = AzureLogHandler(connection_string=config.az_application_insights_key)
    ai_handler.setFormatter(formatter)
      # Configure root logger with the Azure App Insights handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicate logs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add the Azure App Insights handler to the root logger
    root_logger.addHandler(ai_handler)
    
    # Add a limited console handler that only shows warnings and errors
    # This keeps the console clean while still showing important messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce verbosity of Azure HTTP logging by setting it to WARNING level
    # This will prevent logging of HTTP headers and other verbose information
    azure_logger = logging.getLogger('azure.core.pipeline.policies.http_logging_policy')
    azure_logger.setLevel(logging.WARNING)  # Only WARNING or higher will be logged
    
    # Set other Azure components to WARNING level
    logging.getLogger('azure').setLevel(logging.WARNING)
    
    # Set application loggers to appropriate levels
    logging.getLogger('__main__').setLevel(logging.INFO)
    logging.getLogger('bots').setLevel(logging.INFO)
    logging.getLogger('client').setLevel(logging.INFO)
    logging.getLogger('mcp_tools').setLevel(logging.INFO)
    logging.getLogger('mcp_direct').setLevel(logging.INFO)
