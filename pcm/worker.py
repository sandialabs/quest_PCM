import logging
from pcm.data_manager.data_main import DataManager
from pcm.market_manager.market_main import MarketSimulator
from pcm.result_manager.result_main import ResultManager


def run_simulation_process(data_path, yaml_path, result_path, log_queue):
    try:

        from egret.common.log import logger as egret_logger

        egret_logger.setLevel(logging.ERROR)

        log_queue.put("Initializing DataManager...")
        input_manager = DataManager(data_path, yaml_path)
        log_queue.put("Exporting input JSON...")
        input_manager.export_input_json()
        log_queue.put("Creating simulator...")
        simulator = MarketSimulator(input_manager)
        log_queue.put("Building DA/RT models...")
        simulator.create_DA_RT_models()
        log_queue.put("Running simulation...")
        simulator.simulate_market()
        log_queue.put("Processing results...")
        result_processor = ResultManager(simulator, result_path)
        result_processor.export_results()
        log_queue.put("✅ Simulation complete!")
        log_queue.put(f"__RESULTS__:{result_processor.base_result_directory}")
    except Exception as e:
        log_queue.put(f"❌ Error: {e}")
    finally:
        log_queue.put("__DONE__")
