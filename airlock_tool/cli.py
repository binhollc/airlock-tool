"""Airlock Tool CLI — firmware update tool for Airlock bootloader devices."""

import argparse
import sys


def cmd_flash(args):
    from .hf2 import flash_firmware

    method = None
    if args.hid:
        method = "hid"
    elif args.msc:
        method = "msc"

    flash_firmware(
        args.input, product=args.product, no_reset=args.no_reset, method=method
    )


def cmd_info(args):
    from .hf2 import query_device_info

    query_device_info(product=args.product, as_json=args.json)


def cmd_reset(args):
    from .hf2 import reset_device

    reset_device(product=args.product)


def cmd_list(args):
    from .hf2 import list_devices

    list_devices(
        show_hid=args.hid,
        show_webusb=args.webusb,
        show_drives=args.drives,
        as_json=args.json,
    )


def main():
    parser = argparse.ArgumentParser(
        prog="airlock-tool",
        description="Airlock bootloader firmware update tool",
    )
    subparsers = parser.add_subparsers(dest="command")

    # -- flash -----------------------------------------------------------------
    p_flash = subparsers.add_parser(
        "flash",
        help="Flash firmware via HID or MSC boot drive",
    )
    p_flash.add_argument("input", help=".afx file to flash")
    p_flash.add_argument(
        "-p", "--product", help="Filter to specific product VID/PID"
    )
    p_flash.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not reset into app after flashing (HID only)",
    )
    flash_method = p_flash.add_mutually_exclusive_group()
    flash_method.add_argument(
        "--hid",
        action="store_true",
        help="Force HID/HF2 flashing",
    )
    flash_method.add_argument(
        "--msc",
        action="store_true",
        help="Force MSC boot-drive flashing",
    )

    # -- info ------------------------------------------------------------------
    p_info = subparsers.add_parser(
        "info",
        help="Query connected device info",
    )
    p_info.add_argument("-p", "--product", help="Filter to specific product")
    p_info.add_argument("--json", action="store_true", help="Output as JSON")

    # -- reset -----------------------------------------------------------------
    p_reset = subparsers.add_parser(
        "reset",
        help="Reset device from bootloader into application",
    )
    p_reset.add_argument("-p", "--product", help="Filter to specific product")

    # -- list ------------------------------------------------------------------
    p_list = subparsers.add_parser(
        "list",
        help="List connected bootloader devices",
    )
    p_list.add_argument(
        "--hid", action="store_true", help="List HID devices only"
    )
    p_list.add_argument(
        "--webusb", action="store_true", help="List WebUSB devices only"
    )
    p_list.add_argument(
        "--drives", action="store_true", help="List MSC boot drives only"
    )
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "flash": cmd_flash,
        "info": cmd_info,
        "reset": cmd_reset,
        "list": cmd_list,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
