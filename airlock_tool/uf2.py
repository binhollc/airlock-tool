"""UF2 MSC drive helpers for airlock-tool."""

import os
import re
import subprocess
import sys

from .constants import INFO_FILE


def get_drives():
    """Return a list of mounted UF2 boot drives."""
    drives = []
    if sys.platform == "win32":
        r = subprocess.check_output(
            [
                "powershell",
                "-Command",
                "(Get-WmiObject Win32_LogicalDisk -Filter \"FileSystem='FAT'\").DeviceID",
            ]
        )
        drives = [d.strip() for d in r.decode("utf-8").splitlines()]
    else:
        searchpaths = ["/mnt", "/media"]
        if sys.platform == "darwin":
            searchpaths = ["/Volumes"]
        elif sys.platform == "linux":
            user = os.environ.get("USER", "")
            searchpaths += [f"/media/{user}", f"/run/media/{user}"]
            sudo_user = os.environ.get("SUDO_USER")
            if sudo_user:
                searchpaths += [f"/media/{sudo_user}", f"/run/media/{sudo_user}"]
        for rootpath in searchpaths:
            if os.path.isdir(rootpath):
                for d in os.listdir(rootpath):
                    full = os.path.join(rootpath, d)
                    if os.path.isdir(full):
                        drives.append(full)

    def has_info(d):
        try:
            return os.path.isfile(d + INFO_FILE)
        except Exception:
            return False

    return list(filter(has_info, drives))


def board_id(path):
    """Read the Board-ID string from a UF2 drive's INFO_UF2.TXT."""
    with open(path + INFO_FILE, mode="r") as f:
        content = f.read()
    m = re.search(r"Board-ID: ([^\r\n]*)", content)
    return m.group(1) if m else "unknown"
