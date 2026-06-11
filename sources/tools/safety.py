import os
import shlex
import sys

unsafe_commands_unix = [
    "rm",           # File/directory removal
    "dd",           # Low-level disk writing
    "mkfs",         # Filesystem formatting
    "chmod",        # Permission changes
    "chown",        # Ownership changes
    "shutdown",     # System shutdown
    "reboot",       # System reboot
    "halt",         # System halt
    "sysctl",       # Kernel parameter changes
    "kill",         # Process termination
    "pkill",        # Kill by process name
    "killall",      # Kill all matching processes
    "exec",         # Replace process with command
    "tee",          # Write to files with privileges
    "umount",       # Unmount filesystems
    "passwd",       # Password changes
    "useradd",      # Add users
    "userdel",      # Delete users
    "brew",      # Homebrew package manager
    "groupadd",     # Add groups
    "groupdel",     # Delete groups
    "visudo",       # Edit sudoers file
    "screen",       # Terminal session management
    "fdisk",        # Disk partitioning
    "parted",       # Disk partitioning
    "chroot",       # Change root directory
    "route",        # Routing table management
    "--force",     # Force flag for many commands
    "rebase",     # Rebase git repository
    "git" # Git commands
]

unsafe_commands_windows = [
    "del",          # Deletes files
    "erase",        # Alias for del, deletes files
    "rd",           # Removes directories (rmdir alias)
    "rmdir",        # Removes directories
    "format",       # Formats a disk, erasing data
    "diskpart",     # Manages disk partitions, can wipe drives
    "chkdsk /f",    # Fixes filesystem, can alter data
    "fsutil",       # File system utilities, can modify system files
    "xcopy /y",     # Copies files, overwriting without prompt
    "copy /y",      # Copies files, overwriting without prompt
    "move",         # Moves files, can overwrite
    "attrib",       # Changes file attributes, e.g., hiding or exposing files
    "icacls",       # Changes file permissions (modern)
    "takeown",      # Takes ownership of files
    "reg delete",   # Deletes registry keys/values
    "regedit /s",   # Silently imports registry changes
    "shutdown",     # Shuts down or restarts the system
    "schtasks",     # Schedules tasks, can run malicious commands
    "taskkill",     # Kills processes
    "wmic",  # Deletes processes via WMI
    "bcdedit",      # Modifies boot configuration
    "powercfg",     # Changes power settings, can disable protections
    "assoc",        # Changes file associations
    "ftype",        # Changes file type commands
    "cipher /w",    # Wipes free space, erasing data
    "esentutl",     # Database utilities, can corrupt system files
    "subst",        # Substitutes drive paths, can confuse system
    "mklink",       # Creates symbolic links, can redirect access
    "bootcfg"
]

def is_any_unsafe(cmds):
    """
    check if any bash command is unsafe.
    """
    for cmd in cmds:
        if is_unsafe(cmd):
            return True
    return False

def _tokenize(cmd):
    try:
        return shlex.split(cmd, posix=not sys.platform.startswith("win"))
    except ValueError:
        return cmd.split()

def is_unsafe(cmd):
    """
    check if a bash command is unsafe.

    Tokens are basename-normalized so '/bin/rm' and './rm' still
    match the bare 'rm' entry. Multi-token entries (e.g. 'chkdsk /f')
    match when all their parts appear among the tokens regardless of
    order, so intervening flags don't bypass the check.
    """
    norm_tokens = {os.path.basename(t) for t in _tokenize(cmd)}
    bag = unsafe_commands_windows if sys.platform.startswith("win") else unsafe_commands_unix
    for entry in bag:
        parts = {os.path.basename(p) for p in entry.split()}
        if parts and parts.issubset(norm_tokens):
            return True
    return False

if __name__ == "__main__":
    cmd = input("Enter a command: ")
    if is_unsafe(cmd):
        print("Unsafe command detected!")
    else:
        print("Command is safe to execute.")