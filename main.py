"""
Tower of Temptation PvP Statistics Bot Web Interface
Main entry point for Flask application
"""
import os
import sys
import logging
from app import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('web.log')
    ]
)
logger = logging.getLogger('main')

# Import routes to register them with Flask
from routes import *

if __name__ == "__main__":
    logger.info("Starting Tower of Temptation PvP Statistics Web Interface")
    try:
        # Run the web app
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        logger.info("Web server stopped by user")
    except Exception as e:
        logger.error(f"Error starting web server: {e}", exc_info=True)
        sys.exit(1)