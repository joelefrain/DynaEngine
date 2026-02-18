import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from modules.seismo_response.class_ground_motion import Ground_Motion
from libs.config.config_logger import get_logger, log_execution_time

logger = get_logger()


@log_execution_time
def show_ground_motion():
    logger.info("Inicio de prueba de Ground_Motion")
    ground_motion = Ground_Motion(data="var/temp/[PRISMO]_ATICO_EW_MCE.txt", unit="g")
    print(ground_motion)
    ground_motion.plot()
    logger.warning("Fin de prueba de Ground_Motion")


show_ground_motion()
