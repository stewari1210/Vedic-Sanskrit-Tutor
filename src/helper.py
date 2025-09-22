import logging
import sys
from pathlib import Path


logger = logging.getLogger(__name__)

# Initialize logger
# Using INFO level is generally better for production than DEBUG.
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s: %(levelname)s: %(module)s]: %(message)s"
)

project_root = Path(__file__).resolve().parent.parent.resolve()
parent_dir = project_root.parent.resolve()
project_root = str(project_root)
logger.info(project_root)
# Add the parent directory to sys.path

sys.path.append(str(parent_dir))
sys.path.append(str(project_root))
