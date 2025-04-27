import logging
import time
import math

from pynq import Overlay
from pynq.lib import AxiGPIO

# Constants
OVERLAY_PATH = "/home/xilinx/standard_io.bit"
SRAM_WORD_WIDTH = 32
MAINROW_COUNT = 4096
MAIN_COLMUX = 8
INPUT_ROW_COUNT = 2048
INPUT_COLMUX = 8
OUTPUT_ROW_COUNT = 2048
OUTPUT_COLMUX = 8
SCANCHAIN_IDS = range(9)  # total ids in the scan chain
SCAN_CTRL_BITS = 8  # number of bits in the scan control
SCAN_ADDR_BITS = 16
SCAN_DATA_BITS = 32
SCAN_ID_MAP = {
    "main": {"read": 0, "write": 1},
    "input": {"read": 2, "write": 3},
    "output": {"read": 4, "write": 5},
}

# Create a logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Set the logging level
# Create handlers
file_handler = logging.FileHandler("logfile.log")  # Log to a file
stdout_handler = logging.StreamHandler()  # Log to stdout
# Set logging levels for handlers
file_handler.setLevel(logging.DEBUG)
stdout_handler.setLevel(logging.INFO)
# Create a logging format
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)-8s - %(message)s")
file_handler.setFormatter(formatter)
stdout_handler.setFormatter(formatter)
# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stdout_handler)
logger.debug("========= utils logger initialized =========")


class Config:
    @staticmethod
    def read_hex_dump(file_path):
        """
        Read hex dump file and return a list of hex values
        """
        hex_data = []
        with open(file_path, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("@"):
                    continue
                else:
                    hex_data.extend(line.split())
        return hex_data

    def __init__(self, c_test_dump, data_dump=None):
        logger.debug(
            f"Initializing Config with c_test_dump: {c_test_dump}, data_dump: {data_dump}"
        )
        self.c_hexdump = self.read_hex_dump(c_test_dump)
        if data_dump is not None:
            self.data_hexdump = self.read_hex_dump(data_dump)
        else:
            self.data_hexdump = None


class Interface:

    class Sram:
        def __init__(self, row_count, colmux, id_read, id_write, word_width=32):
            logger.debug(
                f"Initializing SRAM with row_count: {row_count}, colmux: {colmux}, id_read: {id_read}, id_write: {id_write}, word_width: {word_width}"
            )
            self.row_count = row_count
            self.colmux = colmux
            self.id_read = id_read
            self.id_write = id_write
            assert self.id_write == self.id_read + 1, "id_write should be id_read + 1"

        def hex_dump_to_data(self, hexdump):
            """
            parse a list of hex values to a list of data values in accordance to the sram config

            hexdump: list of 8bit hex values (e.g. ['08', 'a0', '10', 'ff'])
            """
            data_per_word = SRAM_WORD_WIDTH / 8
            if not data_per_word.is_integer():
                raise ValueError(
                    f"word_width must be a multiple of 8! Received word width: {SRAM_WORD_WIDTH}"
                )
            data_per_word = int(data_per_word)

            row_needed = math.ceil(len(hexdump) / data_per_word)
            if row_needed >= self.row_count:
                raise ValueError(
                    f"Data length is too long for the SRAM! Data length: {row_needed}, SRAM row count: {self.row_count}"
                )

            result_lst = []
            data = 0
            for i in range(len(hexdump)):
                data = data | int(hexdump[i], 16) << (8 * (i % data_per_word))
                if (i + 1) % data_per_word == 0:
                    result_lst.append(data)
                    data = 0

            # left over
            if len(hexdump) % data_per_word != 0:
                result_lst.append(data)

            return result_lst

    def __init__(self):
        logger.debug("Initializing Interface")
        overlay = Overlay(OVERLAY_PATH)
        clkgen = AxiGPIO(overlay.ip_dict["clkgen"])
        iopad = AxiGPIO(overlay.ip_dict["iopad"])

        # clkgen
        self.cg_scanout = clkgen.channel2[0]
        self.cg_clksel = clkgen.channel1[1]
        self.cg_scanin = clkgen.channel1[2]
        self.cg_scanclk = clkgen.channel1[3]
        self.cg_enablecommon = clkgen.channel1[4]
        self.cg_globalenableb = clkgen.channel1[5]

        # external clock, do not manually control this if external clock connected
        self.externalClk = clkgen.channel1[0]
        # assign scanclk to external clock
        self.scanClk = self.externalClk

        # not used
        self._coreInterrupt = iopad.channel1[4]
        self._jtagDummy = iopad.channel1[11]

        # input
        self.reset = iopad.channel1[0]
        self.hcdScanIN = iopad.channel1[2]
        self.testMode = iopad.channel1[5]
        self.scanInValid = iopad.channel1[6]
        self.scanInPayload = iopad.channel1[7]
        self.scanLoad = iopad.channel1[8]
        self.scanRead = iopad.channel1[9]
        self.scanReset = iopad.channel1[10]
        self.chainSelEn = iopad.channel1[12]
        self.outputs = (
            self.reset,
            self.hcdScanIN,
            self.testMode,
            self.scanInValid,
            self.scanInPayload,
            self.scanLoad,
            self.scanRead,
            self.scanReset,
            self.chainSelEn,
        )

        # output
        self.programDone = iopad.channel1[1]
        self.hcdScanOut = iopad.channel1[3]
        self.scanOutValid = iopad.channel1[13]
        self.scanOutPayload = iopad.channel1[14]
        self.inputs = (
            self.programDone,
            self.hcdScanOut,
            self.scanOutValid,
            self.scanOutPayload,
        )

        # init srams
        logger.info("Initializing SRAMs")
        self.main_sram = self.Sram(
            MAINROW_COUNT,
            MAIN_COLMUX,
            SCAN_ID_MAP["main"]["read"],
            SCAN_ID_MAP["main"]["write"],
        )
        self.input_sram = self.Sram(
            INPUT_ROW_COUNT,
            INPUT_COLMUX,
            SCAN_ID_MAP["input"]["read"],
            SCAN_ID_MAP["input"]["write"],
        )
        self.output_sram = self.Sram(
            OUTPUT_ROW_COUNT,
            OUTPUT_COLMUX,
            SCAN_ID_MAP["output"]["read"],
            SCAN_ID_MAP["output"]["write"],
        )

    def clear_inputs(self):
        logger.info("Clearing inputs to 0")
        for i in self.inputs:
            i.off()

    def set_inputs(self):
        logger.info("Setting inputs to 1")
        for i in self.inputs:
            i.on()

    def select_external_clk(self):
        logger.info("Selecting external clock")
        self.cg_clksel.on()

    def select_internal_clk(self):
        logger.info("Selecting internal clock")
        self.cg_clksel.off()

    def config_clkgen(self, freq_sel, ro_sel):
        """
        Config clkgen frequency, but mux is not selected to internal clock

        Clk gen scan in order:
        SCANOUT, FREQ_SELECT<14:1>, RO_SELECT <4:1>, SCANIN
        fastest config: sets FREQ_SELECT<1> and RO_SELECT<1>
        slowest config: sets FREQ_SELECT<14> and RO_SELECT<4>
        """
        logger.info(
            f"Configuring clock generator with FREQ_select: {freq_sel}, RO select: {ro_sel}"
        )

        self.cg_enablecommon.on()
        self.cg_globalenableb.off()

        freq_sel = 15 - freq_sel
        ro_sel = 5 - ro_sel + 14

        # Scan-in
        for i in range(1, 19):
            if i == freq_sel or i == ro_sel:
                self.cg_scanin.on()
                logger.debug("cg_scanin: 1")
            else:
                self.cg_scanin.off()
                logger.debug("cg_scanin: 0")
            self.cg_scanclk.on()
            self.cg_scanclk.off()
            logger.debug("cg_scanout: %s", self.cg_scanout.read())

    def _tick_scan_clk(self, cycle=1):
        """
        tick the scan clock (not cg_clk) by setting the clk pin to high and low

        Waveform:
            -----
            |
        ----|
        """
        for _ in range(cycle):
            self.scanClk.on()
            self.scanClk.off()

    def _scan_payload_in(self, payload_str):
        """
        scan in payload
        """
        # write in reverse (little endian)
        for i in reversed(range(len(payload_str))):
            x = payload_str[i]
            if x == "1":
                self.scanInPayload.on()
            else:
                self.scanInPayload.off()
            self._tick_scan_clk()

    @staticmethod
    def _gen_scan_payload_str(
        addr: int, data: int, enable: bool, write: bool, mask: str
    ):
        """
        Generate scan chain scan in payload string

        addr: address to write/read
        data: data to write
        enable: enable the SRAM
        write: write (1) or read (0)
        mask: read/write mask (4 bits for now)
        """
        # read/wrie address
        addr = format(addr, f"0{SCAN_ADDR_BITS}b")
        # write data, set to 0 if read
        data = format(data, f"0{SCAN_DATA_BITS}b")
        # enable the SRAM
        enable = format(enable, "01b")
        # write (1) or read (0)
        write = format(write, "01b")
        # read/write mask (4 bits for now)
        mask = mask

        # payload str
        payload_str = addr + data + enable + write + mask

        return payload_str

    def _scan_ctrl(self, id):
        """
        set the scan ctrl to select the corresponding scan chain to connect to
        """
        payload_str = format(id, f"0{SCAN_CTRL_BITS}b")
        self.chainSelEn.on()
        self._scan_payload_in(payload_str)
        self.chainSelEn.off()
        self._tick_scan_clk()

    def _scan_write(self, scan_payload_str: str):
        """
        write to scan chain
        Presumption: scanInValid is already set to 1
        """
        # scan in payload
        self._scan_payload_in(scan_payload_str)

        # scan load
        self.scanLoad.on()
        self._tick_scan_clk()
        self.scanLoad.off()
        self._tick_scan_clk()

    def _scan_read(self, scan_cycles: int):
        """
        read from scan chain
        """
        readout_data_lst = ["x"] * scan_cycles
        self.scanRead.on()
        self.scanInValid.off()
        self._tick_scan_clk()
        self.scanRead.off()
        self.scanInValid.on()
        for i in range(scan_cycles):
            readout_data_lst[i] = str(self.scanOutPayload.read())
            assert self.scanOutValid.read() == 1, "scan out valid is not high"
            self._tick_scan_clk()  # remakr: read out on rising edge
        readout_data = "".join(reversed(readout_data_lst))
        return readout_data

    def _scan_reset(self):
        self.scanReset.on()
        self._tick_scan_clk(5)  # FUTURE: 5 is a magic number, need to be tuned
        self.scanReset.off()
        self._tick_scan_clk()

    def _scan_reset_regs(self):
        """
        Reset the scan chain (simple reset doesn't reset the dataOut reg of write scan chain)
        """
        logger.debug("Resetting scan chains")

        # reset scan
        self._scan_reset()

        # set test mode
        self.testMode.on()
        self._tick_scan_clk()

        for id in SCANCHAIN_IDS:
            # set scan target
            self._scan_ctrl(id)

            # scan write in reset data
            self.scanInValid.on()
            payload_str = self._gen_scan_payload_str(
                addr=0, data=0, enable=False, write=False, mask="1111"
            )
            self._scan_write(payload_str)
            self.scanInValid.off()
            self._tick_scan_clk()

        # unset test mode
        self.testMode.off()
        self._tick_scan_clk()

    def _scan_to_sram(self, sram: Sram, data_lst: list):
        """
        Write data to sram through scan chain
        pre assumption:
            scan clock already running
            all signals are already written (i.e. no extra scan cycle needed in front to write a signal)

        sram: the sram object
        data_lst: the data list to write
        """
        logger.debug(f"Writing data to SRAM: {sram.id_write}")

        # reset scan
        self._scan_reset()

        # set test mode
        self.testMode.on()
        self._tick_scan_clk()

        # set scan target
        self._scan_ctrl(sram.id_write)

        # scan write in data
        self.scanInValid.on()
        for addr in range(len(data_lst)):
            payload_str = self._gen_scan_payload_str(
                addr=addr, data=data_lst[addr], enable=True, write=True, mask="1111"
            )
            self._scan_write(payload_str)
        self.scanInValid.off()
        self._tick_scan_clk()

        # unset test mode
        self.testMode.off()
        self._tick_scan_clk()

    def load_in_data(self, config: Config):
        logger.info("Loading in data")

        # switch to external clock to manually tick the clock
        self.select_external_clk()

        # reset the chip while load in data to avoid overwriting
        logger.debug("Resetting the chip while loading in data")
        self.reset.on()

        # reset scan chains
        self._scan_reset_regs()

        # scan to main sram
        logger.info("Loading in main SRAM data")
        main_sram_data = self.main_sram.hex_dump_to_data(config.c_hexdump)
        logger.debug(f"main sram data: {main_sram_data}")
        self._scan_to_sram(self.main_sram, main_sram_data)

        # scan to input sram
        logger.info("Loading in input SRAM data")
        if config.data_hexdump is not None:
            input_sram_data = self.input_sram.hex_dump_to_data(config.data_hexdump)
            logger.debug(f"input sram data: {input_sram_data}")
            self._scan_to_sram(self.input_sram, input_sram_data)
        else:
            input_sram_data = None

        return main_sram_data, input_sram_data

    def run_program(self, timeout=60):
        """
        Switch to internal clock and unset reset to run the program, wait for program done signal

        Pre: clkgen is configured and load_in_data() should be called before this function
        """
        logger.info("Running program")

        self.select_internal_clk()
        logger.debug("Unsetting reset")
        self.reset.off()
        logger.info("Waiting for program done signal")
        start_time = time.time()
        while not self.programDone.read():
            if time.time() - start_time > timeout:
                logger.critical(f"Program did not complete in {timeout} seconds.")
                return

        elapsed_time = time.time() - start_time
        logger.info(f"Program completed in {elapsed_time:.2f} seconds")

    def _scan_from_sram(self, sram: Sram, data_len: int):
        """
        Read data from sram through scan chain

        sram: the sram object
        data_len: expected length of data, 0 to read all data, any other value will skip reading
        """
        logger.debug(f"Reading data from SRAM: {sram.id_read}")

        # reset scan
        self._scan_reset()

        # set test mode
        self.testMode.on()
        self._tick_scan_clk()

        # scan read out data
        read_out_lst = []
        if not isinstance(data_len, int):  # skip reading
            logger.debug(f"Skip reading data from SRAM with data_len = {data_len}")
            return []
        elif data_len > 0:
            read_len = data_len
            logger.debug(f"Reading {data_len} data from SRAM")
        elif data_len == 0:
            # read all data
            read_len = sram.row_count
            logger.debug("Reading all data from SRAM")

        for addr in range(read_len):
            # first load in target address
            # set scan target
            self._scan_ctrl(sram.id_write)
            self.scanInValid.on()
            payload_str = self._gen_scan_payload_str(
                addr=addr, data=0, enable=True, write=False, mask="1111"
            )
            self._scan_write(payload_str)

            # then read out data
            self._scan_ctrl(sram.id_read)
            readout_data = self._scan_read(scan_cycles=SRAM_WORD_WIDTH)
            readout_data = int(readout_data, 2)
            # store readout data = lst
            read_out_lst.append(readout_data)

        self.scanInValid.off()
        self._tick_scan_clk()

        # set scan ctrl to write so riscv can run (weird issue that program done signal is not high when scan ctrl is set to read)
        self._scan_ctrl(self.main_sram.id_write)

        # unset test mode
        self.testMode.off()
        self._tick_scan_clk()

        return read_out_lst

    def load_out_data(
        self,
        main_sram_data_len: int = None,
        input_sram_data_len: int = None,
        output_sram_data_len: int = None,
    ):
        """
        read out data from srams

        main_sram_data_len: expected length of main sram data, 0 to read all data, None to skip reading
        input_sram_data_len: expected length of input sram data, 0 to read all data, None to skip reading
        output_sram_data_len: expected length of output sram data, 0 to read all data, None to skip reading
        """
        logger.info("Loading out data")

        # switch to external clock to manually tick the clock
        self.select_external_clk()

        # reset the chip while load out data to avoid overwriting
        logger.debug("Chip reset completed while loading out data")
        self.reset.on()

        main_read_data = None
        input_read_data = None
        output_read_data = None

        logger.info("Loading out main SRAM data")
        main_read_data = self._scan_from_sram(self.main_sram, main_sram_data_len)
        logger.debug(f"main read data: {main_read_data}")

        logger.info("Loading out input SRAM data")
        input_read_data = self._scan_from_sram(self.input_sram, input_sram_data_len)
        logger.debug(f"input read data: {input_read_data}")

        logger.info("Loading out output SRAM data")
        output_read_data = self._scan_from_sram(self.output_sram, output_sram_data_len)
        logger.debug(f"output read data: {output_read_data}")

        return main_read_data, input_read_data, output_read_data


def is_same_data(original_data, load_out_data):
    """
    Verify the data loaded out from the SRAM with the original data
    """
    if original_data == load_out_data:
        logger.debug("Data match!")
        return True
    else:
        logger.error("Data mismatch!")
        return False


if __name__ == "__main__":
    # Pre: both c_test_dump and data_dump should exists
    config = Config(c_test_dump="c_test_dump", data_hexdump="data_dump")  # TODO
    interface = Interface()
    interface.clear_inputs()
    main_data, input_data = interface.load_in_data(config)
    interface.config_clkgen(freq_sel=4, ro_sel=2)  # 4.342e+08 Hz
    interface.run_program()
    data = interface.load_out_data(len(main_data), len(input_data), 0)
    # TODO: verify data
