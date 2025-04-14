from utils import *

config = Config("c_test_dump")  # TODO
interface = Interface()
interface.clear_inputs()
main_data, input_data = interface.load_in_data(config)
assert input_data is None
# not run program, just check if scan works by reading out data
load_out_main_data, _, _ = interface.load_out_data(len(main_data), None, None)
logger.critical(f"main data match original value: {main_data == load_out_main_data}")