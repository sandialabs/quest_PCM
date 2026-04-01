import logging
import os
from egret.common.log import logger as egret_logger
from pcm.data_manager.data_main import DataManager
from pcm.market_manager.market_main import MarketSimulator
from pcm.result_manager.result_main import ResultManager# %%

egret_logger.setLevel(logging.ERROR)
main_data_path = "Data/RTS_GMLC"
yaml_path = "config/GMLC_config.yaml"

input_manager = DataManager(main_data_path, yaml_path)
input_manager.export_input_json()

simulator = MarketSimulator(input_manager)
simulator.create_DA_RT_models()
simulator.simulate_market() 

result_path = "Results/"
result_processor = ResultManager(simulator, result_path)
result_processor.export_results()
