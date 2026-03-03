"""Shared constants for the Airlock toolchain."""

# ---------------------------------------------------------------------------
# UF2 format
# ---------------------------------------------------------------------------
UF2_MAGIC_START0 = 0x0A324655  # "UF2\n"
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_BLOCK_SIZE = 512

# UF2 MSC drive info file
INFO_FILE = "/INFO_UF2.TXT"

# ---------------------------------------------------------------------------
# HF2 protocol
# ---------------------------------------------------------------------------
HF2_PKT_INNER = 0x00
HF2_PKT_FINAL = 0x40
HF2_PKT_TYPE_MASK = 0xC0
HF2_PKT_LEN_MASK = 0x3F
HID_REPORT_SIZE = 64
HF2_MAX_PAYLOAD = 63

# HF2 commands
HF2_CMD_BININFO = 0x0001
HF2_CMD_INFO = 0x0002
HF2_CMD_RESET_INTO_APP = 0x0003
HF2_CMD_WRITE_ENCRYPTED_BLOCK = 0x0007

# ---------------------------------------------------------------------------
# Device table: (VID, PID) -> (display_name, product_name, mcu)
# ---------------------------------------------------------------------------
DEVICES = {
    # Binho products
    (0x1FC9, 0x82FC): ("Binho Supernova", "binho_supernova", "lpc5536"),
    (0x1FC9, 0x82FD): ("Binho Pulsar", "binho_pulsar", "lpc5516"),
    # NXP reference boards
    (0xCAFE, 0x4002): ("FRDM-MCXN947", "frdm_mcxn947", "mcxn947"),
    (0xCAFE, 0x4012): ("FRDM-MCXA153", "frdm_mcxa153", "mcxa153"),
    (0xCAFE, 0x4013): ("FRDM-MCXA156", "frdm_mcxa156", "mcxa156"),
    # ST reference boards
    (0xCAFE, 0x4020): ("Nucleo-H503RB", "nucleo_h503rb", "stm32h503"),
}
