"""The few system forms behind the tool: home, a plain file without links, locks, process life and trees, commands,
whole writes, a Windows ACL, and the watch's Windows file state. Each platform branch runs here, on one machine."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import contextlib
import ctypes
import hashlib
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from frameloop import host


class HomeTests(unittest.TestCase):
    def test_the_posix_home_comes_from_the_account_database(self):
        account = types.SimpleNamespace(getpwuid=lambda uid: types.SimpleNamespace(pw_dir="/a/made/up/home"))
        with (
            mock.patch.dict(sys.modules, {"pwd": account}),
            mock.patch.object(host.os, "getuid", return_value=501, create=True),
        ):
            self.assertEqual(host.home(False), Path("/a/made/up/home"))

    def test_the_windows_home_comes_from_the_account_profile_and_never_home(self):
        def shell_found(_parent, _kind, _token, _flags, found):
            found.value = r"C:\Users\person"
            return 0

        shell = types.SimpleNamespace(SHGetFolderPathW=shell_found)
        with mock.patch.object(host.ctypes, "windll", types.SimpleNamespace(shell32=shell), create=True):
            self.assertEqual(host.home(True), Path(r"C:\Users\person"))

    def test_a_windows_profile_that_cannot_be_read_is_a_failure(self):
        for answer in (lambda *_args: 5, lambda *_args: 0):
            shell = types.SimpleNamespace(SHGetFolderPathW=answer)
            with mock.patch.object(host.ctypes, "windll", types.SimpleNamespace(shell32=shell), create=True):
                with self.assertRaises(OSError):
                    host.home(True)


class ImportTests(unittest.TestCase):
    def test_the_module_loads_on_a_python_built_without_ctypes(self):
        """Only the Windows forms call into the system, so macOS and Linux need no ctypes, as before this module."""
        spec = importlib.util.spec_from_file_location("host_without_ctypes", host.__file__)
        bare = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"ctypes": None}):
            spec.loader.exec_module(bare)
        self.assertIsNone(bare.ctypes)
        self.assertIsNone(bare.wintypes)
        self.assertFalse(hasattr(bare, "_Information"))
        self.assertEqual(bare.home(False), host.home(False))
        self.assertEqual(host.INVALID_HANDLE_VALUE, ctypes.c_void_p(-1).value)


class PathTests(unittest.TestCase):
    def test_paths_compare_by_each_systems_own_case_and_separators(self):
        with mock.patch.object(host, "Path", PurePosixPath):
            self.assertTrue(host.same("/a/b", "/a/b", False))
            self.assertFalse(host.same("/a/b", "/a/B", False))
            self.assertTrue(host.under("/a/b/c", "/a/b", False))
            self.assertFalse(host.under("/a/bc", "/a/b", False))
            self.assertEqual(host.path_key("/a/b", False), "/a/b")
        self.assertTrue(host.same(r"C:\Shop\App", "c:/shop/app", True))
        self.assertTrue(host.under(r"C:\Shop\App\runs", r"c:\shop\app", True))
        self.assertFalse(host.under(r"C:\Shop\Application", r"c:\shop\app", True))
        self.assertEqual(host.path_key(r"C:\Shop\App", True), r"c:\shop\app")


class KindTests(unittest.TestCase):
    def status(self, mode, attributes=0):
        return types.SimpleNamespace(st_mode=mode, st_file_attributes=attributes)

    def test_each_kind_of_file_is_named_and_a_windows_reparse_point_is_a_link(self):
        self.assertIsNone(host.kind(self.status(stat.S_IFREG), False))
        self.assertEqual(host.kind(self.status(stat.S_IFLNK), False), "link")
        self.assertEqual(host.kind(self.status(stat.S_IFDIR), False), "folder")
        self.assertEqual(host.kind(self.status(0o010000), False), "pipe" if hasattr(stat, "S_ISFIFO") else "device")
        self.assertEqual(host.kind(self.status(0o140000), False), "socket" if hasattr(stat, "S_ISSOCK") else "device")
        self.assertEqual(host.kind(self.status(stat.S_IFCHR), False), "device")
        self.assertEqual(host.kind(self.status(stat.S_IFDIR, host.FILE_ATTRIBUTE_REPARSE_POINT), True), "link")

    def test_a_link_is_looked_at_itself_and_a_missing_or_plain_path_is_not_one(self):
        with tempfile.TemporaryDirectory() as folder:
            plain = Path(folder) / "plain"
            plain.write_text("made up\n", "utf-8")
            self.assertFalse(host.is_link(plain, False))
            self.assertFalse(host.is_link(Path(folder) / "gone", False))


class OpenTests(unittest.TestCase):
    def test_a_posix_read_and_lock_keep_the_no_follow_flags(self):
        with (
            mock.patch.object(host.os, "open", return_value=7) as opened,
            mock.patch.object(host.os, "O_NOFOLLOW", 0x100, create=True),
            mock.patch.object(host.os, "O_NONBLOCK", 0x200, create=True),
        ):
            self.assertEqual(host.open_read(Path("/a/file"), False), 7)
            opened.assert_called_with(Path("/a/file"), os.O_RDONLY | 0x100 | 0x200)
            self.assertEqual(host.open_lock(Path("/a/lock"), False), 7)
            opened.assert_called_with(Path("/a/lock"), os.O_WRONLY | os.O_CREAT | os.O_APPEND | 0x100 | 0x200, 0o600)

    def test_a_windows_handle_is_checked_before_it_becomes_a_descriptor(self):
        kernel, handle = object(), 11
        with (
            mock.patch.object(host, "_kernel", return_value=kernel),
            mock.patch.object(host, "_win_handle", return_value=handle) as made,
            mock.patch.object(host, "_win_plain", side_effect=host.NotPlain("link")),
            mock.patch.object(host, "_close") as closed,
        ):
            with self.assertRaises(host.NotPlain):
                host.open_read(Path("C:/a/file"), True)
        made.assert_called_once_with(kernel, Path("C:/a/file"), host.GENERIC_READ, host.OPEN_EXISTING)
        closed.assert_not_called()  # _win_plain closes the handle it refuses

    def test_a_checked_windows_handle_becomes_a_descriptor(self):
        kernel, handle = object(), 11
        with (
            mock.patch.object(host, "_kernel", return_value=kernel),
            mock.patch.object(host, "_win_handle", return_value=handle),
            mock.patch.object(host, "_win_plain", return_value=handle),
            mock.patch.object(host, "_as_fd", return_value=7) as converted,
        ):
            self.assertEqual(host.open_read(Path("C:/a/file"), True), 7)
        converted.assert_called_once_with(handle, os.O_RDONLY)

    def test_a_descriptor_that_cannot_be_made_closes_the_windows_handle(self):
        kernel, handle = object(), 11
        with (
            mock.patch.object(host, "_kernel", return_value=kernel),
            mock.patch.object(host, "_win_handle", return_value=handle),
            mock.patch.object(host, "_win_plain", return_value=handle),
            mock.patch.object(host, "_as_fd", side_effect=OSError()),
            mock.patch.object(host, "_close") as closed,
        ):
            with self.assertRaises(OSError):
                host.open_read(Path("C:/a/file"), True)
        closed.assert_called_once_with(kernel, handle)

    def test_a_windows_handle_becomes_a_descriptor_through_the_crt(self):
        made = mock.Mock(return_value=7)
        with mock.patch.dict(sys.modules, {"msvcrt": types.SimpleNamespace(open_osfhandle=made)}):
            self.assertEqual(host._as_fd(11, os.O_RDONLY), 7)
        made.assert_called_once_with(11, os.O_RDONLY)

    def test_the_windows_create_file_call_has_the_reparse_point_flags_and_a_bad_handle_fails(self):
        class Kernel:
            def __init__(self, answer):
                self.answer = answer

            def CreateFileW(self, *_args):
                return self.answer

        self.assertEqual(host._win_handle(Kernel(9), Path("C:/a/file"), 1, 3), 9)
        with self.assertRaises(OSError):
            host._win_handle(Kernel(host.INVALID_HANDLE_VALUE), Path("C:/a/file"), 1, 3)

    def test_windows_file_information_names_a_reparse_point_and_a_folder_without_opening_either(self):
        class Kernel:
            def __init__(self, answer=True):
                self.answer, self.closed = answer, []

            def GetFileInformationByHandle(self, _handle, _found):
                return self.answer

            def CloseHandle(self, handle):
                self.closed.append(handle)

        plain = types.SimpleNamespace(dwFileAttributes=0)
        with mock.patch.object(host, "_win_information", return_value=plain):
            self.assertEqual(host._win_plain(Kernel(), 4), 4)
        for attributes, kind in (
            (host.FILE_ATTRIBUTE_REPARSE_POINT, "link"),
            (host.FILE_ATTRIBUTE_DIRECTORY, "folder"),
        ):
            kernel = Kernel()
            with mock.patch.object(
                host, "_win_information", return_value=types.SimpleNamespace(dwFileAttributes=attributes)
            ):
                with self.assertRaises(host.NotPlain) as refused:
                    host._win_plain(kernel, 4)
            self.assertEqual((refused.exception.kind, kernel.closed), (kind, [4]))
        kernel = Kernel(answer=False)
        with self.assertRaises(OSError):
            host._win_information(kernel, 4)
        with self.assertRaises(OSError):
            host._win_plain(kernel, 4)
        self.assertEqual(kernel.closed, [4])
        kernel = types.SimpleNamespace(GetFileInformationByHandle=lambda _handle, _found: True)
        self.assertEqual(host._win_information(kernel, 4).dwFileAttributes, 0)

    def test_the_windows_kernel_is_the_system_library(self):
        kernel = object()
        with mock.patch.object(host.ctypes, "windll", types.SimpleNamespace(kernel32=kernel), create=True):
            self.assertIs(host._kernel(), kernel)

    def test_a_close_that_fails_is_still_a_close(self):
        kernel = types.SimpleNamespace(CloseHandle=mock.Mock(side_effect=OSError()))
        host._close(kernel, 4)
        kernel.CloseHandle.assert_called_once_with(4)
        kernel = types.SimpleNamespace(CloseHandle=mock.Mock())
        host._close(kernel, 5)
        kernel.CloseHandle.assert_called_once_with(5)

    def test_a_windows_call_signature_is_set_when_the_real_function_is_there(self):
        function = types.SimpleNamespace(argtypes=None, restype=None)
        host._signature(function, int, str)
        self.assertEqual((function.restype, function.argtypes), (int, [str]))

    def test_a_windows_lock_file_gets_one_byte_before_it_is_locked(self):
        with tempfile.TemporaryFile() as held:
            fd = held.fileno()
            with mock.patch.object(host, "_win_open", return_value=fd):
                self.assertEqual(host.open_lock(Path("C:/a/lock"), True), fd)
            held.seek(0)
            self.assertEqual(held.read(), b"\0")
        with tempfile.NamedTemporaryFile() as held:
            held.write(b"x")
            held.flush()
            with mock.patch.object(host, "_win_open", return_value=held.fileno()):
                self.assertEqual(host.open_lock(Path("C:/a/lock"), True), held.fileno())
            self.assertEqual(held.seek(0, os.SEEK_END), 1)
        with (
            mock.patch.object(host, "_win_open", return_value=7),
            mock.patch.object(host.os, "lseek", side_effect=OSError()),
            mock.patch.object(host.os, "close") as closed,
        ):
            with self.assertRaises(OSError):
                host.open_lock(Path("C:/a/lock"), True)
        closed.assert_called_once_with(7)

    def test_appending_opens_without_follow_and_refuses_a_pipe_or_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "log"
            with (
                mock.patch.object(host.os, "O_NOFOLLOW", 0, create=True),
                mock.patch.object(host.os, "O_NONBLOCK", 0, create=True),
            ):
                fd = host.open_append(path, False)
            os.close(fd)
            self.assertTrue(path.exists())
        fd = os.open(os.devnull, os.O_WRONLY)
        with (
            mock.patch.object(host.os, "open", return_value=fd),
            mock.patch.object(host.os, "fstat", return_value=types.SimpleNamespace(st_mode=stat.S_IFDIR)),
            mock.patch.object(host.os, "close") as closed,
        ):
            with self.assertRaises(host.NotPlain):
                host.open_append(Path("/a/folder"), False)
        closed.assert_called_once_with(fd)

    def test_a_windows_append_and_new_file_are_checked_handles(self):
        with tempfile.TemporaryFile() as held:
            written = os.dup(held.fileno())
            with mock.patch.object(host, "_win_open", return_value=written):
                self.assertEqual(host.open_append(Path("C:/log"), True), written)
            os.close(written)
            created = os.dup(held.fileno())
            with mock.patch.object(host, "_win_open", return_value=created):
                host.write_new(Path("C:/new"), "made up\n", True)
            self.assertEqual(held.tell(), len("made up\n"))


@unittest.skipIf(os.name == "nt", "folder descriptors and links are held in their POSIX forms")
class FolderTests(unittest.TestCase):
    def descriptors(self) -> int:
        return len(os.listdir("/dev/fd"))

    def test_a_folder_walk_keeps_the_descriptor_it_checked_and_closes_every_one(self):
        with tempfile.TemporaryDirectory() as folder:
            top = Path(folder)
            (top / "one" / "two").mkdir(parents=True)
            (top / "file").write_text("plain\n", "utf-8")
            before = self.descriptors()
            with host.open_folder(top, top / "one" / "two") as held:
                self.assertTrue(stat.S_ISDIR(os.fstat(held).st_mode))
            self.assertEqual(self.descriptors(), before)
            with self.assertRaises(FileNotFoundError):
                with host.open_folder(top, top / "one" / "missing"):
                    pass
            self.assertEqual(self.descriptors(), before)
            with host.open_folder(top, top / "made" / "deep", make=True, mode=lambda _path: 0o700):
                pass
            self.assertTrue((top / "made" / "deep").is_dir())
            with host.open_folder(top, top / "plain", make=True):
                pass
            self.assertTrue((top / "plain").is_dir())
            self.assertEqual(self.descriptors(), before)

            (top / "link").symlink_to(top / "one", target_is_directory=True)
            with self.assertRaises(host.NotPlain) as refused:
                with host.open_folder(top, top / "link" / "two"):
                    pass
            self.assertEqual(refused.exception.kind, "linked")
            self.assertEqual(self.descriptors(), before)

            with host.open_folder(top, top) as held:
                with self.assertRaises(host.NotPlain) as final:
                    host.open_read("link", False, dir_fd=held)
                self.assertEqual(final.exception.kind, "link")
            self.assertEqual(self.descriptors(), before)

    def test_a_missing_folder_made_by_another_hand_is_opened_without_following_it(self):
        with tempfile.TemporaryDirectory() as folder:
            top = Path(folder)
            before = self.descriptors()
            with (
                mock.patch.object(host.os, "mkdir", side_effect=FileExistsError),
                self.assertRaises(FileNotFoundError),
            ):
                with host.open_folder(top, top / "missing", make=True):
                    pass
            self.assertEqual(self.descriptors(), before)
        with mock.patch.object(host.os, "open", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                with host.open_folder(Path("/top"), Path("/top/one")):
                    pass

    def test_each_write_and_remove_uses_the_folder_descriptor(self):
        with tempfile.TemporaryDirectory() as folder:
            top = Path(folder)
            before = self.descriptors()
            with host.open_folder(top, top / "held", make=True) as held:
                host.write_new("beside", "one\n", dir_fd=held)
                host.replace("beside", "done", src_dir_fd=held, dst_dir_fd=held)
                host.append_text("done", "two\n", dir_fd=held)
                self.assertEqual(host.stat_at(held, "done").st_size, 8)
                host.unlink_at(held, "done")
                self.assertFalse((top / "held" / "done").exists())
                host.write_new("from", "made\n", dir_fd=held)
                host.new_file("from", "to", False, src_dir_fd=held, dst_dir_fd=held)
                self.assertEqual((top / "held" / "to").read_text("utf-8"), "made\n")
            self.assertEqual(self.descriptors(), before)


class LockTests(unittest.TestCase):
    def test_the_posix_lock_branch_is_an_exclusive_non_blocking_flock(self):
        fcntl = types.SimpleNamespace(flock=mock.Mock(), LOCK_EX=2, LOCK_NB=4)
        with mock.patch.dict(sys.modules, {"fcntl": fcntl}):
            host.lock(7, False)
            host.unlock(7, False)
        fcntl.flock.assert_called_once_with(7, 6)

    def test_the_windows_byte_lock_lets_go_and_maps_a_refusal_to_blocking(self):
        held = {"busy": False}

        def locking(_fd, mode, _size):
            if mode == "busy" and held["busy"]:
                raise OSError(13, "busy")

        msvcrt = types.SimpleNamespace(locking=locking, LK_NBLCK="busy", LK_UNLCK="free")
        with tempfile.TemporaryFile() as file, mock.patch.dict(sys.modules, {"msvcrt": msvcrt}):
            host._win_lock(file.fileno())
            held["busy"] = True
            with self.assertRaises(BlockingIOError):
                host.lock(file.fileno(), True)
            host.unlock(file.fileno(), True)

    def test_a_windows_lock_and_unlock_are_reached_through_the_platform_value(self):
        with mock.patch.object(host, "_win_lock") as locked, mock.patch.object(host, "_win_unlock") as unlocked:
            host.lock(7, True)
            host.unlock(7, True)
        locked.assert_called_once_with(7)
        unlocked.assert_called_once_with(7)


class LifeTests(unittest.TestCase):
    def test_a_posix_life_check_never_ends_the_process(self):
        with mock.patch.object(host.os, "kill") as asked:
            self.assertTrue(host.alive(42, False))
        asked.assert_called_once_with(42, 0)
        with mock.patch.object(host.os, "kill", side_effect=OSError()):
            self.assertFalse(host.alive(42, False))

    def test_a_windows_life_check_reads_the_exit_code_and_closes_the_handle(self):
        class Kernel:
            def __init__(self, handle, answer, code=host.STILL_ACTIVE):
                self.handle, self.answer, self.code, self.closed = handle, answer, code, []

            def OpenProcess(self, *_args):
                return self.handle

            def GetExitCodeProcess(self, _handle, found):
                found._obj.value = self.code
                return self.answer

            def CloseHandle(self, handle):
                self.closed.append(handle)

        for handle, answer, code, expected in (
            (7, True, host.STILL_ACTIVE, True),
            (7, True, 0, False),
            (7, False, 259, False),
            (0, True, 259, False),
        ):
            kernel = Kernel(handle, answer, code)
            with mock.patch.object(host, "_kernel", return_value=kernel):
                self.assertEqual(host.alive(42, True), expected)
            self.assertEqual(kernel.closed, [7] if handle else [])

    def test_a_windows_stop_ends_the_tree_and_falls_back_only_when_it_must(self):
        with (
            mock.patch.object(host, "system", return_value=r"C:\Windows\System32\taskkill.exe"),
            mock.patch.object(host.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as ran,
            mock.patch.object(host.os, "kill") as killed,
        ):
            host.stop(42, True)
        ran.assert_called_once_with(
            [r"C:\Windows\System32\taskkill.exe", "/PID", "42", "/T", "/F"],
            stdin=host.subprocess.DEVNULL,
            stdout=host.subprocess.DEVNULL,
            stderr=host.subprocess.DEVNULL,
            timeout=30,
        )
        killed.assert_not_called()
        for failure in (types.SimpleNamespace(returncode=1), OSError()):
            outcome = {"side_effect": failure} if isinstance(failure, BaseException) else {"return_value": failure}
            with (
                mock.patch.object(host, "system", return_value="taskkill.exe"),
                mock.patch.object(host.subprocess, "run", **outcome),
                mock.patch.object(host.os, "kill") as killed,
            ):
                with self.assertRaises(OSError):
                    host.stop(42, True)
            killed.assert_called_once_with(42, 15)
        with mock.patch.object(host.os, "killpg") as killed:
            host.stop(42, False)
        killed.assert_called_once_with(42, 9)


class StartTests(unittest.TestCase):
    def test_each_system_starts_a_run_in_a_session_or_process_group(self):
        self.assertEqual(host.group(False, False), {"start_new_session": True})
        self.assertEqual(host.group(False, True), {"creationflags": host.CREATE_NEW_PROCESS_GROUP})
        self.assertEqual(host.group(True, True)["creationflags"], host.CREATE_NEW_PROCESS_GROUP | host.DETACHED_PROCESS)

    def test_a_hold_runs_in_the_system_shell_on_posix_and_git_bash_on_windows_or_not_at_all(self):
        self.assertEqual(host.shell("exit 0", False), ("exit 0", True))
        with mock.patch.object(host.shutil, "which", return_value="/usr/bin/bash"):
            self.assertEqual(host.shell("exit 0", True), ("/usr/bin/bash", ["-c", "exit 0"], False))
        with mock.patch.object(host.shutil, "which", return_value=None):
            self.assertIsNone(host.shell("exit 0", True))
        with mock.patch.object(host.shutil, "which", side_effect=[None, "/usr/bin/sh"]):
            self.assertEqual(host.shell("exit 0", True), ("/usr/bin/sh", ["-c", "exit 0"], False))

    def test_a_windows_npm_command_runs_its_powershell_script_and_a_batch_file_alone_is_refused(self):
        self.assertEqual(host.program([], True), [])
        self.assertEqual(host.program(["claude.exe", "one"], False), ["claude.exe", "one"])
        self.assertEqual(host.program(["claude.exe", "one"], True), ["claude.exe", "one"])
        with tempfile.TemporaryDirectory() as folder:
            batch = Path(folder) / "claude.cmd"
            batch.write_text("@echo off\n", "utf-8")
            with self.assertRaises(OSError):
                host.program([str(batch), "untrusted & data"], True)
            batch.with_suffix(".ps1").write_text("& claude.exe @args\n", "utf-8")
            with mock.patch.object(
                host, "system", return_value=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            ):
                found = host.program([str(batch), "untrusted & data"], True)
        self.assertEqual(found[0], r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
        self.assertEqual(found[-2], str(batch.with_suffix(".ps1")))
        self.assertEqual(found[-1], "untrusted & data")

    def test_a_windows_system_program_is_named_from_the_system_folder(self):
        def found(buffer, _size):
            buffer.value = r"C:\Windows\System32"
            return len(buffer.value)

        kernel = types.SimpleNamespace(GetSystemDirectoryW=found)
        with mock.patch.object(host, "_kernel", return_value=kernel):
            self.assertEqual(host.system("taskkill.exe"), host.ntpath.join(r"C:\Windows\System32", "taskkill.exe"))
        kernel = types.SimpleNamespace(GetSystemDirectoryW=lambda *_args: 0)
        with mock.patch.object(host, "_kernel", return_value=kernel), self.assertRaises(OSError):
            host.system("taskkill.exe")


class WriteTests(unittest.TestCase):
    def test_a_replacement_is_whole_and_windows_tries_again_while_the_file_is_held(self):
        with tempfile.TemporaryDirectory() as folder:
            path, beside = Path(folder) / "file", Path(folder) / "beside"
            path.write_text("old\n", "utf-8")
            beside.write_text("new\n", "utf-8")
            host.replace(beside, path, False)
            self.assertEqual(path.read_text("utf-8"), "new\n")
        beside, path = Path("beside"), Path("path")
        with (
            mock.patch.object(host.os, "replace", side_effect=[PermissionError(), PermissionError(), None]) as moved,
            mock.patch.object(host.time, "sleep") as waited,
        ):
            host.replace(beside, path, True)
        self.assertEqual(moved.call_count, 3)
        self.assertEqual(waited.call_count, 2)
        with mock.patch.object(host.os, "replace", side_effect=PermissionError()):
            with self.assertRaises(PermissionError):
                host.replace(beside, path, False)
        with (
            mock.patch.object(host.os, "replace", side_effect=PermissionError()) as moved,
            mock.patch.object(host.time, "sleep"),
        ):
            with self.assertRaises(PermissionError):
                host.replace(beside, path, True)
        self.assertEqual(moved.call_count, 5)

    def test_a_new_proposal_is_a_hard_link_or_a_windows_rename_without_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            beside, path = Path(folder) / "beside", Path(folder) / "file"
            beside.write_text("made up\n", "utf-8")
            host.new_file(beside, path, False)
            self.assertTrue(path.exists())
        with mock.patch.object(host.os, "rename", side_effect=FileExistsError):
            with self.assertRaises(FileExistsError):
                host.new_file(Path("beside"), Path("file"), True)

    def test_text_is_utf8_with_lf_on_every_system(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "text"
            host.write_text(path, "one\n")
            host.append_text(path, "two\n")
            self.assertEqual(path.read_bytes(), b"one\ntwo\n")
            with self.assertRaises(FileExistsError):
                host.write_text(path, "again\n")
        with (
            mock.patch.object(host.os, "open", return_value=7),
            mock.patch.object(host.os, "fdopen", side_effect=OSError()),
            mock.patch.object(host.os, "close") as closed,
            mock.patch.object(host.os, "O_NOFOLLOW", 0x100, create=True),
        ):
            with self.assertRaises(OSError):
                host.write_new(Path("/a/new"), "made up\n", False)
        closed.assert_called_once_with(7)

    def test_only_windows_reconfigures_a_stream_for_utf8(self):
        stream = mock.Mock()
        host.utf8(stream, False)
        stream.reconfigure.assert_not_called()
        host.utf8(stream, True)
        stream.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        host.utf8(object(), True)


class AccountFolderTests(unittest.TestCase):
    def test_the_windows_account_and_its_folder_are_read_from_system_tools(self):
        whoami = types.SimpleNamespace(returncode=0, stdout='"domain\\person","S-1-5-21-7"\r\n')
        icacls = types.SimpleNamespace(returncode=0)
        with mock.patch.object(host, "_system_run", side_effect=[whoami, icacls]) as ran:
            host.restrict(Path("C:/machine"), True)
        self.assertEqual(ran.call_args_list[0], mock.call("whoami.exe", "/user", "/fo", "csv", "/nh", text=True))
        self.assertEqual(
            ran.call_args_list[1],
            mock.call("icacls.exe", "C:/machine", "/inheritance:r", "/grant:r", "*S-1-5-21-7:(OI)(CI)F"),
        )
        host.restrict(Path("C:/project"), False)

    def test_an_account_or_acl_that_cannot_be_read_refuses_the_folder(self):
        for answers in (
            (types.SimpleNamespace(returncode=1, stdout=""),),
            (types.SimpleNamespace(returncode=0, stdout="no sid"),),
            (types.SimpleNamespace(returncode=0, stdout='"p","S-1-5-21-7"'), types.SimpleNamespace(returncode=1)),
        ):
            with self.subTest(answers=answers), mock.patch.object(host, "_system_run", side_effect=answers):
                with self.assertRaises(OSError):
                    host.restrict(Path("C:/machine"), True)

    def test_the_system_tool_runner_keeps_text_only_where_it_is_asked(self):
        with (
            mock.patch.object(host, "system", return_value="whoami.exe"),
            mock.patch.object(host.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as ran,
        ):
            host._system_run("whoami.exe", "/user", text=True)
            host._system_run("whoami.exe", "/user")
        self.assertEqual(ran.call_args_list[0].kwargs["encoding"], "utf-8")
        self.assertIsNone(ran.call_args_list[1].kwargs["encoding"])


class StateTests(unittest.TestCase):
    def test_posix_state_is_the_metadata_the_watch_already_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file"
            path.write_text("one\n", "utf-8")
            self.assertRegex(host.state(path, False), r"^[0-7]+:\d+:\d+:\d+:\d+$")
            self.assertIsNone(host.state(Path(folder) / "gone", False))

    def test_windows_state_adds_a_plain_files_bytes_so_a_same_size_rewrite_is_seen(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file"
            path.write_text("one\n", "utf-8")
            with mock.patch.object(host, "open_read", side_effect=lambda held, _windows: os.open(held, os.O_RDONLY)):
                before = host.state(path, True)
                path.write_text("two\n", "utf-8")
                after = host.state(path, True)
            self.assertNotEqual(before, after)
            self.assertIn(":", before)
            self.assertNotIn(":unread", before)
            big = Path(folder) / "big"
            big.write_text("x" * 101, "utf-8")
            with mock.patch.object(host, "open_read", side_effect=lambda held, _windows: os.open(held, os.O_RDONLY)):
                self.assertTrue(host.state(big, True).endswith(":" + hashlib.sha256(b"x" * 101).hexdigest()))
            self.assertRegex(host.state(Path(folder), True), r"^[0-7]+:\d+:\d+:\d+:\d+$")
            with mock.patch.object(host, "open_read", side_effect=OSError()):
                self.assertTrue(host.state(path, True).endswith(":unread"))


@unittest.skipUnless(os.name == "nt", "this checks Windows' own byte locks and process tree")
class WindowsTests(unittest.TestCase):
    def test_a_windows_byte_lock_is_exclusive_between_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lock"
            held = host.open_lock(path, True)
            try:
                host.lock(held, True)
                code = (
                    "import os, sys\n"
                    "from pathlib import Path\n"
                    "from frameloop import host\n"
                    "fd = host.open_lock(Path(sys.argv[1]), True)\n"
                    "locked = False\n"
                    "try: host.lock(fd, True); locked = True; print('free')\n"
                    "except BlockingIOError: print('locked')\n"
                    "finally:\n"
                    " if locked: host.unlock(fd, True)\n"
                    " os.close(fd)\n"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual((child.returncode, child.stdout.strip()), (0, "locked"), child.stderr)
            finally:
                host.unlock(held, True)
                os.close(held)

    def test_windows_stop_ends_a_grandchild(self):
        script = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "print(child.pid, flush=True)\n"
            "time.sleep(30)\n"
        )
        parent = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            creationflags=host.group()["creationflags"],
        )
        self.addCleanup(parent.wait)
        self.addCleanup(parent.kill)
        self.addCleanup(parent.stdout.close)
        grandchild = int(parent.stdout.readline().strip())

        def stop_leftover():
            if host.alive(grandchild):
                with contextlib.suppress(OSError):
                    host.stop(grandchild, True)

        self.addCleanup(stop_leftover)
        host.stop(parent.pid, True)
        parent.wait(timeout=10)
        until = time.monotonic() + 10
        while host.alive(grandchild) and time.monotonic() < until:
            time.sleep(0.05)
        self.assertFalse(host.alive(grandchild))


if __name__ == "__main__":
    unittest.main()
