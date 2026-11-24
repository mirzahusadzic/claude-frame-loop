"""The few things each system does differently: the account's home, a plain file opened without following a link, a
file lock, a process's life and its tree, a command's shell, an atomic replacement, and a folder kept to this account.

macOS and Linux keep their own forms, calls and guarantees. Windows uses the account profile, a reparse-point-safe
handle, a byte lock, the process's true state, its system tools, and an ACL, or refuses where one cannot be had.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import ntpath
import os
import re
import shutil
import stat
import struct
import subprocess
import time
from pathlib import Path
from typing import Callable, Iterator, Optional

try:  # only the Windows forms call into the system: macOS and Linux run on a Python built without ctypes too
    import ctypes
    from ctypes import wintypes
except ImportError:
    ctypes = wintypes = None

WINDOWS = os.name == "nt"

CSIDL_PROFILE = 0x0028
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_SHARE_ALL = 0x00000001 | 0x00000002 | 0x00000004
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
OPEN_ALWAYS = 4
CREATE_NEW = 1
FILE_APPEND_DATA = 0x0004
INVALID_HANDLE_VALUE = (1 << 8 * struct.calcsize("P")) - 1  # a pointer of all ones, as c_void_p(-1) reads
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


class NotPlain(OSError):
    """A file that is no plain regular file; its argument is one of claims' kinds: link or folder."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


if ctypes is not None:

    class _Information(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]


def _windows(windows: Optional[bool]) -> bool:
    return WINDOWS if windows is None else windows


def home(windows: Optional[bool] = None) -> Path:
    """The account's home: the account database on macOS and Linux, and the account profile on Windows, never HOME."""
    if not _windows(windows):
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    return _profile()


def _profile() -> Path:
    shell = ctypes.windll.shell32
    _signature(
        shell.SHGetFolderPathW,
        ctypes.c_long,
        wintypes.HWND,
        ctypes.c_int,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
    )
    found = ctypes.create_unicode_buffer(32768)
    if shell.SHGetFolderPathW(None, CSIDL_PROFILE, None, 0, found) != 0 or not found.value:
        raise OSError("profile")
    return Path(found.value)


def same(left, right, windows: Optional[bool] = None) -> bool:
    """Whether two paths name one path, by the case and separators the system's own file names use."""
    if _windows(windows):
        return path_key(left, True) == path_key(right, True)
    return Path(left) == Path(right)


def under(path, folder, windows: Optional[bool] = None) -> bool:
    """Whether a path is a folder itself or lies under it, by the system's own case and separators."""
    if _windows(windows):
        held, top = path_key(path, True), path_key(folder, True).rstrip("\\/")
        return held == top or held.startswith(top + "\\")
    held, top = Path(path), Path(folder)
    return held == top or top in held.parents


def path_key(path, windows: Optional[bool] = None) -> str:
    """A path as the system keeps its name, for a digest or a comparison."""
    if _windows(windows):
        return ntpath.normcase(ntpath.abspath(os.fspath(path)))
    return str(Path(path))


def kind(status: os.stat_result, windows: Optional[bool] = None) -> Optional[str]:
    """What a file is by its status: a link (a Windows reparse point among them), folder, pipe, socket or device;
    None for a plain file."""
    mode = status.st_mode
    if stat.S_ISLNK(mode) or (
        _windows(windows) and getattr(status, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT
    ):
        return "link"
    return (
        None
        if stat.S_ISREG(mode)
        else "folder"
        if stat.S_ISDIR(mode)
        else "pipe"
        if getattr(stat, "S_ISFIFO", lambda _mode: False)(mode)
        else "socket"
        if getattr(stat, "S_ISSOCK", lambda _mode: False)(mode)
        else "device"
    )


def is_link(path: Path, windows: Optional[bool] = None) -> bool:
    """Whether a path itself is a link or a Windows reparse point, never following it."""
    try:
        return kind(os.lstat(path), windows) == "link"
    except OSError:
        return False


def _kernel():
    return ctypes.windll.kernel32


def _signature(function, restype, *argtypes) -> None:
    """A Windows call's own types, where a real function is present; a test's stand-in keeps its own."""
    if hasattr(function, "argtypes"):
        function.argtypes = list(argtypes)
        function.restype = restype


def _close(kernel, handle) -> None:
    _signature(kernel.CloseHandle, wintypes.BOOL, wintypes.HANDLE)
    with contextlib.suppress(OSError):
        kernel.CloseHandle(handle)


def _win_handle(kernel, path: Path, access: int, creation: int):
    _signature(
        kernel.CreateFileW,
        wintypes.HANDLE,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    handle = kernel.CreateFileW(
        str(path),
        access,
        FILE_SHARE_ALL,
        None,
        creation,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle in (None, INVALID_HANDLE_VALUE):
        raise _win_error()
    return handle


def _win_information(kernel, handle):
    found = _Information()
    _signature(kernel.GetFileInformationByHandle, wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(_Information))
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(found)):
        raise _win_error()
    return found


def _win_error() -> OSError:
    return OSError(getattr(ctypes, "get_last_error", lambda: 0)(), "windows")


def _win_plain(kernel, handle):
    try:
        found = _win_information(kernel, handle)
    except OSError:
        _close(kernel, handle)
        raise
    if found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
        _close(kernel, handle)
        raise NotPlain("link")
    if found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY:
        _close(kernel, handle)
        raise NotPlain("folder")
    return handle


def _as_fd(handle, flags: int) -> int:
    import msvcrt

    return msvcrt.open_osfhandle(int(handle), flags)


def _win_open(path: Path, access: int, creation: int, flags: int) -> int:
    kernel = _kernel()
    handle = _win_handle(kernel, path, access, creation)
    checked = _win_plain(kernel, handle)
    try:
        return _as_fd(checked, flags)
    except BaseException:
        _close(kernel, checked)
        raise


@contextlib.contextmanager
def open_folder(
    top: Path,
    path: Path,
    make: bool = False,
    mode: Optional[Callable[[Path], int]] = None,
) -> Iterator[int]:
    """A folder opened from `top`, one name at a time, without following a link on the way: each name is opened
    relative to the folder before it, and `make` makes a missing one there. Gives its descriptor."""
    held = None
    at = top
    try:
        held = _open_folder(top)
        for part in path.relative_to(top).parts:
            parent, held = held, None
            try:
                at = at / part
                try:
                    held = _open_folder(part, parent)
                except FileNotFoundError:
                    if not make:
                        raise
                    try:
                        os.mkdir(part, mode(at) if mode is not None else 0o777, dir_fd=parent)
                    except FileExistsError:
                        pass
                    held = _open_folder(part, parent)
            finally:
                os.close(parent)
        yield held
    finally:
        if held is not None:
            os.close(held)


def _open_folder(name, parent: Optional[int] = None) -> int:
    """One folder by its name, relative to a parent where there is one; a link or no folder is NotPlain."""
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise NotPlain("linked") from None
        raise


def open_read(path: Path, windows: Optional[bool] = None, dir_fd: Optional[int] = None) -> int:
    """A plain file opened for reading, never following a link at its own name; anything else raises NotPlain."""
    if not _windows(windows):
        more = {} if dir_fd is None else {"dir_fd": dir_fd}
        try:
            return os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, **more)
        except OSError as error:
            if dir_fd is not None and error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise NotPlain("link") from None
            raise
    return _win_open(path, GENERIC_READ, OPEN_EXISTING, os.O_RDONLY)


def open_lock(path: Path, windows: Optional[bool] = None, dir_fd: Optional[int] = None) -> int:
    """A lock file opened as a plain file, made where absent, and never through a link at its own name."""
    if not _windows(windows):
        more = {} if dir_fd is None else {"dir_fd": dir_fd}
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, **more)
    fd = _win_open(path, GENERIC_READ | GENERIC_WRITE, OPEN_ALWAYS, os.O_RDWR)
    try:
        if os.lseek(fd, 0, os.SEEK_END) == 0:
            os.write(fd, b"\0")
        os.lseek(fd, 0, os.SEEK_SET)
    except BaseException:
        os.close(fd)
        raise
    return fd


def open_append(path: Path, windows: Optional[bool] = None, dir_fd: Optional[int] = None) -> int:
    """A plain file opened to append, made where absent, and never through a link, pipe or device at its own name."""
    if not _windows(windows):
        more = {} if dir_fd is None else {"dir_fd": dir_fd}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o666, **more)
    else:
        fd = _win_open(path, FILE_APPEND_DATA, OPEN_ALWAYS, os.O_WRONLY | os.O_APPEND)
    try:
        found = kind(os.fstat(fd), windows)
        if found is not None:
            raise NotPlain(found)
    except BaseException:
        os.close(fd)
        raise
    return fd


def write_new(path: Path, text: str, windows: Optional[bool] = None, dir_fd: Optional[int] = None) -> None:
    """Text put at a new name, never through a link that is already there."""
    if not _windows(windows):
        more = {} if dir_fd is None else {"dir_fd": dir_fd}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666, **more)
    else:
        fd = _win_open(path, GENERIC_WRITE, CREATE_NEW, os.O_WRONLY)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = -1
            handle.write(text)
    finally:
        if fd >= 0:
            os.close(fd)


def lock(handle: int, windows: Optional[bool] = None) -> None:
    """One exclusive non-blocking byte lock, or BlockingIOError where another holds it."""
    if not _windows(windows):
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    _win_lock(handle)


def _win_lock(handle: int) -> None:
    import msvcrt

    os.lseek(handle, 0, os.SEEK_SET)
    try:
        msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
    except OSError as error:
        raise BlockingIOError(error.errno, error.strerror) from error


def unlock(handle: int, windows: Optional[bool] = None) -> None:
    """Lets a Windows byte lock go before its handle closes; the POSIX lock goes with its handle."""
    if not _windows(windows):
        return
    _win_unlock(handle)


def _win_unlock(handle: int) -> None:
    import msvcrt

    os.lseek(handle, 0, os.SEEK_SET)
    msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)


def alive(pid: int, windows: Optional[bool] = None) -> bool:
    """Whether a process still lives, without asking it to end, on either system."""
    if not _windows(windows):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    kernel = _kernel()
    _signature(kernel.OpenProcess, wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _signature(kernel.GetExitCodeProcess, wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == STILL_ACTIVE
    finally:
        _close(kernel, handle)


def group(detached: bool = False, windows: Optional[bool] = None) -> dict:
    """How a program starts apart from the hook: a session on POSIX, a process group on Windows."""
    if not _windows(windows):
        return {"start_new_session": True}
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", CREATE_NEW_PROCESS_GROUP)
    if detached:
        flags |= getattr(subprocess, "DETACHED_PROCESS", DETACHED_PROCESS)
    return {"creationflags": flags}


def shell(command: str, windows: Optional[bool] = None) -> Optional[tuple]:
    """A hold's command and whether Popen takes a shell: the system's shell on POSIX, Git Bash on Windows."""
    if not _windows(windows):
        return command, True
    program = shutil.which("bash") or shutil.which("sh")
    return (program, ["-c", command], False) if program else None


def program(command: list, windows: Optional[bool] = None) -> list:
    """A program's arguments. A Windows npm command is its PowerShell script, whose arguments stay data; a batch
    file with no such script is refused rather than handed to a system shell unescaped."""
    if not _windows(windows) or not command or ntpath.splitext(command[0])[1].lower() not in (".bat", ".cmd"):
        return command
    script = Path(command[0]).with_suffix(".ps1")
    if not script.is_file():
        raise OSError("script")
    powershell = system(ntpath.join("WindowsPowerShell", "v1.0", "powershell.exe"))
    return [
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *command[1:],
    ]


def system(name: str) -> str:
    """A Windows system program by its absolute path, so no project's copy on PATH can stand in for it."""
    kernel = _kernel()
    found = ctypes.create_unicode_buffer(32768)
    _signature(kernel.GetSystemDirectoryW, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT)
    if not kernel.GetSystemDirectoryW(found, len(found)):
        raise OSError("system")
    return ntpath.join(found.value, name)


def stop(pid: int, windows: Optional[bool] = None) -> None:
    """Stop a process and every process it started: its group on POSIX, its tree on Windows, with a fallback alone."""
    if not _windows(windows):
        import signal

        os.killpg(pid, getattr(signal, "SIGKILL", 9))
        return
    try:
        ran = subprocess.run(
            [system("taskkill.exe"), "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if ran.returncode == 0:
            return
    except (OSError, subprocess.SubprocessError):
        pass
    import signal

    with contextlib.suppress(OSError):
        os.kill(pid, getattr(signal, "SIGTERM", 15))
    raise OSError("tree")


def replace(
    beside: Path,
    path: Path,
    windows: Optional[bool] = None,
    src_dir_fd: Optional[int] = None,
    dst_dir_fd: Optional[int] = None,
) -> None:
    """A written file moved into place whole; Windows tries again while a reader or scanner briefly holds it."""
    attempt = 0
    more = {
        **({"src_dir_fd": src_dir_fd} if src_dir_fd is not None else {}),
        **({"dst_dir_fd": dst_dir_fd} if dst_dir_fd is not None else {}),
    }
    while True:
        try:
            os.replace(beside, path, **more)
            return
        except PermissionError:
            if not _windows(windows) or attempt == 4:
                raise
            attempt += 1
            time.sleep(0.02)


def new_file(
    beside: Path,
    path: Path,
    windows: Optional[bool] = None,
    src_dir_fd: Optional[int] = None,
    dst_dir_fd: Optional[int] = None,
) -> None:
    """A written file put at a new name whole and without replacing one already there."""
    if _windows(windows):
        os.rename(beside, path)
    else:
        more = {
            **({"src_dir_fd": src_dir_fd} if src_dir_fd is not None else {}),
            **({"dst_dir_fd": dst_dir_fd} if dst_dir_fd is not None else {}),
        }
        os.link(beside, path, **more)


def unlink_at(folder: int, name: str) -> None:
    """One name removed from the folder its descriptor holds, never through a folder swapped into the path."""
    os.unlink(name, dir_fd=folder)


def stat_at(folder: int, name: str) -> os.stat_result:
    """A name's own state in the folder its descriptor holds, never following the name as a link."""
    return os.stat(name, dir_fd=folder, follow_symlinks=False)


def write_text(path: Path, text: str) -> None:
    """Text written as UTF-8 with LF line ends on every system, finished before another hand reads it."""
    write_new(path, text)


def append_text(path: Path, text: str, dir_fd: Optional[int] = None) -> None:
    """UTF-8 text appended with LF line ends on every system."""
    fd = open_append(path, dir_fd=dir_fd)
    with os.fdopen(fd, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def utf8(stream, windows: Optional[bool] = None) -> None:
    """A Windows stream writes UTF-8, so the band's glyphs and JSON reach the host unchanged."""
    if _windows(windows) and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def _system_run(name: str, *args: str, text: bool = False):
    return subprocess.run(
        [system(name), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if text else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


def _sid() -> str:
    ran = _system_run("whoami.exe", "/user", "/fo", "csv", "/nh", text=True)
    found = re.search(r"S-\d-(?:\d+-)+\d+", ran.stdout or "")
    if ran.returncode != 0 or found is None:
        raise OSError("account")
    return found.group(0)


def restrict(path: Path, windows: Optional[bool] = None) -> None:
    """A new machine folder kept to this Windows account alone, by an inherited ACL; POSIX keeps its mode alone."""
    if not _windows(windows):
        return
    ran = _system_run("icacls.exe", str(path), "/inheritance:r", "/grant:r", f"*{_sid()}:(OI)(CI)F")
    if ran.returncode != 0:
        raise OSError("acl")


def state(path: Path, windows: Optional[bool] = None) -> Optional[str]:
    """What the watch keeps of a path. Windows also digests a plain file's bytes, since its change time may be a
    creation time and a same-size rewrite could otherwise pass unseen."""
    try:
        held = os.lstat(path)
    except OSError:
        return None
    found = f"{held.st_mode:o}:{held.st_ino}:{held.st_size}:{held.st_mtime_ns}:{held.st_ctime_ns}"
    if not _windows(windows):
        return found
    if kind(held, True) is not None:
        return found
    try:
        handle = open_read(path, True)
        try:
            digest = hashlib.sha256()
            while True:
                chunk = os.read(handle, 1 << 16)
                if not chunk:
                    break
                digest.update(chunk)
        finally:
            os.close(handle)
    except OSError:
        return found + ":unread"
    return found + ":" + digest.hexdigest()
