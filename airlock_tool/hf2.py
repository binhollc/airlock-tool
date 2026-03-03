"""HF2 (HID Flashing Format) device communication and flash/info/list logic."""

import struct
import sys
import time

from rich.console import Console

from .constants import (
    DEVICES,
    HF2_PKT_INNER,
    HF2_PKT_FINAL,
    HF2_PKT_TYPE_MASK,
    HF2_PKT_LEN_MASK,
    HID_REPORT_SIZE,
    HF2_MAX_PAYLOAD,
    HF2_CMD_BININFO,
    HF2_CMD_INFO,
    HF2_CMD_RESET_INTO_APP,
    HF2_CMD_WRITE_ENCRYPTED_BLOCK,
    UF2_MAGIC_START0,
    UF2_MAGIC_START1,
    UF2_MAGIC_END,
    UF2_BLOCK_SIZE,
)

_console = Console()


def _try_import_hid():
    """Return the ``hid`` module or *None*."""
    try:
        import hid

        return hid
    except ImportError:
        return None


def _try_import_usb():
    """Return ``usb.core`` or *None*."""
    try:
        import usb.core

        return usb.core
    except ImportError:
        return None


class HF2Device:
    """Low-level HF2 protocol over HID."""

    def __init__(self):
        try:
            import hid
        except ImportError:
            raise ImportError("hidapi not installed. Run: pip install hidapi")
        self.dev = hid.device()
        self.tag = 1
        self.serial = ""

    def open(self, product=None):
        """Open the first matching device that responds to HF2.

        Returns ``(vid, pid)`` of the opened device.
        Raises ``OSError`` if no matching device is found.
        """
        devices_to_try = {}
        for (vid, pid), (display_name, product_name, _mcu) in DEVICES.items():
            if product is None or product_name == product:
                devices_to_try[(vid, pid)] = display_name

        for (vid, pid), name in devices_to_try.items():
            try:
                self.dev.open(vid, pid)
                self.dev.set_nonblocking(False)
            except OSError:
                continue
            try:
                self.command(HF2_CMD_BININFO, timeout_ms=500)
                self.serial = self.dev.get_serial_number_string() or ""
                return (vid, pid)
            except (TimeoutError, RuntimeError, OSError):
                self.dev.close()
                self.dev = __import__("hid").device()
                self.tag = 1
                continue

        if product:
            raise OSError(f"No device found for product '{product}'")
        dev_list = ", ".join(f"{v:04x}:{p:04x}" for v, p in devices_to_try)
        raise OSError(f"No device found. Tried: [{dev_list}]")

    def close(self):
        self.dev.close()

    # -- low-level transport ---------------------------------------------------

    def _next_tag(self):
        tag = self.tag
        self.tag = (self.tag + 1) & 0xFFFF
        return tag

    def _send_raw(self, data):
        """Send *data* split into 64-byte HF2-framed HID reports."""
        offset = 0
        while offset < len(data):
            chunk_len = min(len(data) - offset, HF2_MAX_PAYLOAD)
            is_final = offset + chunk_len >= len(data)
            pkt_type = HF2_PKT_FINAL if is_final else HF2_PKT_INNER
            header = pkt_type | (chunk_len & HF2_PKT_LEN_MASK)

            report = bytes([0x00, header]) + data[offset : offset + chunk_len]
            report = report + b"\x00" * (65 - len(report))
            self.dev.write(report)
            offset += chunk_len

    def _recv_raw(self, timeout_ms=5000):
        """Receive and reassemble an HF2 response."""
        msg = bytearray()
        deadline = time.time() + timeout_ms / 1000.0
        while True:
            remaining_ms = int((deadline - time.time()) * 1000)
            if remaining_ms <= 0:
                raise TimeoutError("HF2 response timeout")
            report = self.dev.read(HID_REPORT_SIZE, remaining_ms)
            if not report:
                raise TimeoutError("HF2 response timeout")

            pkt_type = report[0] & HF2_PKT_TYPE_MASK
            pkt_len = report[0] & HF2_PKT_LEN_MASK
            msg.extend(report[1 : 1 + pkt_len])

            if pkt_type == HF2_PKT_FINAL:
                return bytes(msg)

    # -- commands --------------------------------------------------------------

    def command(self, cmd_id, data=b"", timeout_ms=5000):
        """Send an HF2 command and return ``(status, response_data)``."""
        tag = self._next_tag()
        msg = struct.pack("<IHH", cmd_id, tag, 0) + data
        self._send_raw(msg)
        resp = self._recv_raw(timeout_ms)

        if len(resp) < 4:
            raise RuntimeError(f"Short response: {len(resp)} bytes")

        resp_tag, status, _status_info = struct.unpack("<HBB", resp[:4])
        if resp_tag != tag:
            raise RuntimeError(f"Tag mismatch: expected {tag}, got {resp_tag}")

        return status, resp[4:]

    def bininfo(self):
        """Query BININFO — returns dict with mode, flash geometry, family_id."""
        status, data = self.command(HF2_CMD_BININFO)
        if status != 0 or len(data) < 20:
            raise RuntimeError(f"BININFO failed: status={status}")
        mode, page_size, num_pages, max_msg, family_id = struct.unpack(
            "<IIIII", data[:20]
        )
        return {
            "mode": mode,
            "flash_page_size": page_size,
            "flash_num_pages": num_pages,
            "max_message_size": max_msg,
            "family_id": family_id,
        }

    def info(self):
        """Query INFO — returns the board info string."""
        status, data = self.command(HF2_CMD_INFO)
        if status != 0:
            raise RuntimeError(f"INFO failed: status={status}")
        return data.decode("utf-8", errors="replace")

    def write_encrypted_block(self, block_data):
        """Send a 512-byte UF2 block."""
        status, _ = self.command(
            HF2_CMD_WRITE_ENCRYPTED_BLOCK, block_data, timeout_ms=10000
        )
        if status != 0:
            raise RuntimeError(f"WRITE_BLOCK failed: status={status}")

    def reset_into_app(self):
        """Reset the device into application mode.

        Raises ``RuntimeError`` if the bootloader reports no valid app.
        """
        status, _ = self.command(HF2_CMD_RESET_INTO_APP, timeout_ms=2000)
        if status != 0:
            raise RuntimeError("No valid application — bootloader refused reset")


# ---------------------------------------------------------------------------
# reset_device
# ---------------------------------------------------------------------------


def reset_device(product=None):
    """Send RESET_INTO_APP to a connected bootloader device."""
    try:
        dev = HF2Device()
    except ImportError:
        _console.print("[red]Error:[/red] hidapi not installed. Run: pip install hidapi")
        sys.exit(1)

    try:
        vidpid = dev.open(product)
    except OSError as e:
        _console.print(f"[red]Error:[/red] {e}")
        _console.print("  Make sure the board is in bootloader mode")
        sys.exit(1)

    display_name = DEVICES.get(vidpid, ("Unknown",))[0]
    _console.print(f"Connected to [bold]{display_name}[/bold] ({vidpid[0]:04x}:{vidpid[1]:04x})")

    try:
        dev.reset_into_app()
        _console.print("[green]Reset into app — done[/green]")
    except RuntimeError as e:
        _console.print(f"[red]Error:[/red] {e}")
        _console.print("  Flash a valid application before resetting")
        sys.exit(1)
    except Exception as e:
        _console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    finally:
        dev.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_uf2_blocks(path):
    """Read a UF2 file and return a list of valid 512-byte blocks."""
    blocks = []
    with open(path, "rb") as f:
        while True:
            block = f.read(UF2_BLOCK_SIZE)
            if len(block) < UF2_BLOCK_SIZE:
                break
            magic0 = struct.unpack_from("<I", block, 0)[0]
            magic1 = struct.unpack_from("<I", block, 4)[0]
            magic_end = struct.unpack_from("<I", block, 508)[0]
            if (
                magic0 != UF2_MAGIC_START0
                or magic1 != UF2_MAGIC_START1
                or magic_end != UF2_MAGIC_END
            ):
                continue
            blocks.append(block)
    return blocks


# ---------------------------------------------------------------------------
# Flash — HID (HF2)
# ---------------------------------------------------------------------------


def _flash_hid(blocks, product, no_reset):
    """Flash via HF2 over HID.

    Raises ``ImportError`` (no hidapi) or ``OSError`` (no device).
    """
    from rich.progress import (
        BarColumn,
        Progress,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    dev = HF2Device()  # raises ImportError if hidapi missing
    vidpid = dev.open(product)  # raises OSError if no device

    display_name = DEVICES.get(vidpid, ("Unknown",))[0]
    _console.print(f"Connected to [bold]{display_name}[/bold] ({vidpid[0]:04x}:{vidpid[1]:04x})")

    try:
        bi = dev.bininfo()
        board_info = dev.info().strip()
        _console.print(
            f"  Flash: {bi['flash_num_pages']} pages x {bi['flash_page_size']} bytes, "
            f"family 0x{bi['family_id']:08x}"
        )
        _console.print(f"  Board: {board_info}")

        with Progress(
            TextColumn("[bold blue]Flashing"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("({task.completed}/{task.total})"),
            TimeRemainingColumn(),
            console=_console,
        ) as progress:
            task = progress.add_task("Flashing", total=len(blocks))
            for block in blocks:
                dev.write_encrypted_block(block)
                progress.advance(task)

        if not no_reset:
            try:
                dev.reset_into_app()
                _console.print("[green]Flash complete — reset into app[/green]")
            except RuntimeError:
                _console.print("[yellow]Flash complete — but bootloader reports no valid app[/yellow]")
                _console.print("  Device remains in bootloader mode")
        else:
            _console.print("[green]Flash complete[/green]")
    finally:
        dev.close()


# ---------------------------------------------------------------------------
# Flash — MSC (Mass Storage)
# ---------------------------------------------------------------------------


def _flash_msc(uf2_path):
    """Flash by copying the file to MSC boot drive(s).

    Raises ``FileNotFoundError`` if no boot drive is detected.
    """
    from .uf2 import board_id, get_drives

    drives = get_drives()
    if not drives:
        raise FileNotFoundError("No boot drive found")

    with open(uf2_path, "rb") as f:
        data = f.read()

    for d in drives:
        try:
            bid = board_id(d)
        except Exception:
            bid = "unknown"
        dest = d + "/NEW.AFX"
        _console.print(f"Writing to [bold]{d}[/bold] ({bid})...")
        with open(dest, "wb") as f:
            f.write(data)
        _console.print(f"  Wrote {len(data)} bytes to {dest}")

    _console.print("[green]Flash complete[/green]")


# ---------------------------------------------------------------------------
# flash_firmware — public dispatcher
# ---------------------------------------------------------------------------


def flash_firmware(uf2_path, product=None, no_reset=False, method=None):
    """Flash firmware to a connected device.

    Parameters
    ----------
    uf2_path : str
        Path to the .afx file.
    product : str or None
        Filter HID devices to this product name.
    no_reset : bool
        If True, skip the reset-into-app after HID flash.
    method : str or None
        ``"hid"``, ``"msc"``, or *None* for auto-detect.
    """
    blocks = read_uf2_blocks(uf2_path)
    if not blocks:
        _console.print("[red]Error:[/red] No valid UF2 blocks found")
        sys.exit(1)
    _console.print(f"Found [bold]{len(blocks)}[/bold] blocks in [cyan]{uf2_path}[/cyan]")

    if method == "msc":
        try:
            _flash_msc(uf2_path)
        except FileNotFoundError as e:
            _console.print(f"[red]Error:[/red] {e}")
            _console.print("  Make sure the board is in bootloader mode")
            sys.exit(1)
        return

    if method == "hid":
        try:
            _flash_hid(blocks, product, no_reset)
        except ImportError as e:
            _console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)
        except OSError as e:
            _console.print(f"[red]Error:[/red] {e}")
            _console.print("  Make sure the board is in bootloader mode")
            sys.exit(1)
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)
        return

    # Auto-detect: try HID first, then MSC
    try:
        _flash_hid(blocks, product, no_reset)
        return
    except ImportError:
        _console.print("[yellow]hidapi not installed — trying boot drive...[/yellow]")
    except OSError:
        _console.print("[yellow]No HID device — trying boot drive...[/yellow]")

    try:
        _flash_msc(uf2_path)
        return
    except FileNotFoundError:
        pass

    _console.print("[red]Error:[/red] No HID device or boot drive found")
    _console.print("  Make sure the board is in bootloader mode")
    sys.exit(1)


# ---------------------------------------------------------------------------
# query_device_info
# ---------------------------------------------------------------------------


def query_device_info(product=None, as_json=False):
    """Query and display info from a connected device."""
    import json as json_mod

    from rich.table import Table

    try:
        dev = HF2Device()
    except ImportError:
        _console.print("[red]Error:[/red] hidapi not installed. Run: pip install hidapi")
        sys.exit(1)

    try:
        vidpid = dev.open(product)
    except OSError as e:
        _console.print(f"[red]Error:[/red] {e}")
        _console.print("  Make sure the board is in bootloader mode (double-tap reset)")
        sys.exit(1)

    try:
        bi = dev.bininfo()
        board_info = dev.info().strip()
        display_name, product_name, mcu = DEVICES.get(
            vidpid, ("Unknown", "unknown", "unknown")
        )

        result = {
            "device": display_name,
            "product": product_name,
            "mcu": mcu,
            "vid_pid": f"{vidpid[0]:04x}:{vidpid[1]:04x}",
            "unique_id": dev.serial,
            "mode": bi["mode"],
            "flash_page_size": bi["flash_page_size"],
            "flash_num_pages": bi["flash_num_pages"],
            "max_message_size": bi["max_message_size"],
            "family_id": f"0x{bi['family_id']:08x}",
            "board_info": board_info,
        }

        if as_json:
            print(json_mod.dumps(result, indent=2))
        else:
            table = Table(title=display_name, show_header=False)
            table.add_column("Field", style="bold")
            table.add_column("Value")
            table.add_row("Product", product_name)
            table.add_row("MCU", mcu)
            table.add_row("VID:PID", f"{vidpid[0]:04x}:{vidpid[1]:04x}")
            table.add_row("Unique ID", dev.serial)
            table.add_row("Mode", str(bi["mode"]))
            table.add_row(
                "Flash",
                f"{bi['flash_num_pages']} pages x {bi['flash_page_size']} bytes",
            )
            table.add_row("Family ID", f"0x{bi['family_id']:08x}")
            table.add_row("Board Info", board_info)
            _console.print(table)
    except Exception as e:
        _console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    finally:
        dev.close()


# ---------------------------------------------------------------------------
# list_devices
# ---------------------------------------------------------------------------


def list_devices(show_hid=False, show_webusb=False, show_drives=False, as_json=False):
    """List connected bootloader devices (HID, WebUSB, and/or MSC drives)."""
    import json as json_mod

    from rich.table import Table

    from .uf2 import board_id, get_drives

    if not show_hid and not show_webusb and not show_drives:
        show_hid = True
        show_webusb = True
        show_drives = True

    results = {"hid": [], "webusb": [], "drives": []}

    # -- HID --
    hid_error = None
    if show_hid:
        hid = _try_import_hid()
        if hid is None:
            hid_error = "hidapi not installed (pip install hidapi)"
        else:
            for (vid, pid), (display_name, product_name, mcu) in DEVICES.items():
                for dev_info in hid.enumerate(vid, pid):
                    path = dev_info["path"]
                    if isinstance(path, bytes):
                        path = path.decode("utf-8", errors="replace")
                    results["hid"].append(
                        {
                            "device": display_name,
                            "product": product_name,
                            "mcu": mcu,
                            "vid_pid": f"{vid:04x}:{pid:04x}",
                            "serial": dev_info.get("serial_number", ""),
                            "path": path,
                        }
                    )

    # -- WebUSB --
    webusb_error = None
    if show_webusb:
        usb_core = _try_import_usb()
        if usb_core is None:
            webusb_error = "pyusb not installed (pip install pyusb)"
        else:
            try:
                for (vid, pid), (display_name, product_name, mcu) in DEVICES.items():
                    devs = list(
                        usb_core.find(find_all=True, idVendor=vid, idProduct=pid)
                    )
                    for dev in devs:
                        results["webusb"].append(
                            {
                                "device": display_name,
                                "product": product_name,
                                "mcu": mcu,
                                "vid_pid": f"{vid:04x}:{pid:04x}",
                                "bus": dev.bus,
                                "address": dev.address,
                            }
                        )
            except Exception as e:
                webusb_error = str(e)

    # -- Drives --
    if show_drives:
        for drive in get_drives():
            try:
                bid = board_id(drive)
            except Exception:
                bid = "unknown"
            results["drives"].append({"path": drive, "board_id": bid})

    # -- Output --
    if as_json:
        print(json_mod.dumps(results, indent=2))
        return

    if show_hid:
        if hid_error:
            _console.print(f"[dim]HID: skipped ({hid_error})[/dim]")
        elif results["hid"]:
            table = Table(title="HID Devices")
            table.add_column("Device")
            table.add_column("VID:PID", style="cyan")
            table.add_column("Unique ID", style="dim")
            table.add_column("Product")
            for d in results["hid"]:
                table.add_row(d["device"], d["vid_pid"], d.get("serial", ""), d["product"])
            _console.print(table)
        else:
            _console.print("[dim]No HID devices found[/dim]")

    if show_webusb:
        if webusb_error:
            _console.print(f"[dim]WebUSB: skipped ({webusb_error})[/dim]")
        elif results["webusb"]:
            table = Table(title="WebUSB Devices")
            table.add_column("Device")
            table.add_column("VID:PID", style="cyan")
            table.add_column("Product")
            table.add_column("Location")
            for d in results["webusb"]:
                table.add_row(
                    d["device"],
                    d["vid_pid"],
                    d["product"],
                    f"bus {d['bus']}, addr {d['address']}",
                )
            _console.print(table)
        else:
            _console.print("[dim]No WebUSB devices found[/dim]")

    if show_drives:
        if results["drives"]:
            table = Table(title="Boot Drives")
            table.add_column("Path")
            table.add_column("Board ID", style="cyan")
            for d in results["drives"]:
                table.add_row(d["path"], d["board_id"])
            _console.print(table)
        else:
            _console.print("[dim]No boot drives found[/dim]")
