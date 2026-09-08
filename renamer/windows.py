import ctypes
import msvcrt
import os
from ctypes import wintypes

from .core import Snapshot


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
create_file = kernel32.CreateFileW
create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
create_file.restype = wintypes.HANDLE
close_handle = kernel32.CloseHandle
close_handle.argtypes = [wintypes.HANDLE]
close_handle.restype = wintypes.BOOL
set_file_information = kernel32.SetFileInformationByHandle
set_file_information.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
set_file_information.restype = wintypes.BOOL


class RenameInfo(ctypes.Structure):
    _fields_ = [("ReplaceIfExists", wintypes.BOOLEAN), ("RootDirectory", wintypes.HANDLE),
                ("FileNameLength", wintypes.DWORD), ("FileName", wintypes.WCHAR * 1)]


def rename_locked(source, target, snapshot):
    handle = create_file(str(source), 0x10000 | 0x80, 0x1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    descriptor = None
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        if Snapshot.from_stat(os.fstat(descriptor)) != snapshot:
            raise ValueError("源文件在检查后发生变化，已停止改名")
        encoded = str(target).encode("utf-16-le")
        # Win32 需要 UTF-16 终止符，但 FileNameLength 不包含它。
        buffer = ctypes.create_string_buffer(max(ctypes.sizeof(RenameInfo), RenameInfo.FileName.offset + len(encoded) + 2))
        info = RenameInfo.from_buffer(buffer)
        info.ReplaceIfExists = False
        info.RootDirectory = None
        info.FileNameLength = len(encoded)
        ctypes.memmove(ctypes.addressof(buffer) + RenameInfo.FileName.offset, encoded, len(encoded))
        if not set_file_information(handle, 3, buffer, len(buffer)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if descriptor is not None:
            os.close(descriptor)
        else:
            close_handle(handle)
