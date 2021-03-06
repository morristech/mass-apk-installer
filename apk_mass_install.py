#!/usr/bin/env python

"""
 Name:        apk_mass_install

Purpose:  This module automates back or restoration of multiple apk's, apk is the
           standard executable in Android platform made by Google



 Author:      Evan

 Created:     19/10/2011
 Last Modified: 12/02/2018
 Copyright:   (c) Evan 2018
 Licence:
 Copyright (c) 2018, Evan
 All rights reserved.

 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions are met:
     * Redistributions of source code must retain the above copyright
       notice, this list of conditions and the following disclaimer.
     * Redistributions in binary form must reproduce the above copyright
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.
     * Neither the name of the <organization> nor the
       names of its contributors may be used to endorse or promote products
       derived from this software without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
 ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 vWARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
 DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
 ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 """

from timeit import default_timer as timer
from platform import system
from datetime import datetime
import time
import subprocess
import argparse
import shutil
import sys
import os

from tools.archive import extract_zip, make_zip
from tools.encryption import AesEncryption

INSTALL_FAILURE = -1
INSTALL_OK = 1
INSTALL_EXISTS = 2

# Flags for adb list packages
pkg_flags = {"all": "",  # list all packages
             "user": "-3",  # list 3d party packages only (default)
             "system": "-S"}  # list system packages only


def detect_os():
    """
    Detect running operating system
    """
    system_ = system()

    if os.name == "posix" and system_ == "Darwin":
        return "osx"
    elif os.name == "posix" and system_ == "Linux":
        return "linux"
    elif os.name == "nt" and system_ == "Windows":
        return "win"
    else:
        raise ValueError("Unsupported OS")


os_platform = detect_os()


def pull_apk(pkg_dic):
    """
    Pulls apk specified in pkgDic variable from android device using adb
    renames extracted apk to filename specified in pkgDic key value pair.
    """

    pkg_name = list(pkg_dic)

    if os_platform is "osx":
        cmd = "./adb_osx/adb shell cat {} > base.apk".format(pkg_dic[pkg_name[0]])
        # cmd = "./adb_osx/adb pull " + pkgDic[pkg_name[0]] doesn't work anymore after nougat update
    elif os_platform is "win":
        cmd = "adb_win/adb.exe pull {}".format(pkg_dic[pkg_name[0]])
    elif os_platform is "linux":
        cmd = "./adb_linux/adb shell cat {} > base.apk".format(pkg_dic[pkg_name[0]])

    exit_code, output = subprocess.getstatusoutput(cmd)
    if exit_code == 0:
        if os.path.exists("base.apk"):
            if os.path.isfile("base.apk"):
                os.rename("base.apk", pkg_name[0] + ".apk")


def package_management(PKG_FILTER):
    """
    list all packages installed installed in android device. Results can be
    filtered with PKG_FILTER to get only apk packages you are interested. By
    default listing only 3d party apps.
    """

    state = adb_command("shell pm list packages {}".format(PKG_FILTER))

    pkg = []

    """
    adb returns packages name  in the form
    package:com.skype.raider
    we need to strip package: prefix
    """
    for i in state.splitlines():
        if i.startswith("package:"):
            y = [x.strip() for x in i.split(":")]
            pkg.append(y[1])

    return pkg


def get_package_full_path(pkg_name):
    """
     Returns full path of package in android device storage specified by argument
    """

    state = adb_command("shell pm path {}".format(pkg_name))

    """
    adb returns packages name  in the form
    package:/data/app/com.dog.raider-2/base.apk
     we need to strip package: prefix in returned string
    """

    pkg_path = [x.strip() for x in state.split(":")]
    return pkg_path[1]


def adb_start():
    """
    starts an instance of adb server
    """
    adb_command("start-server")


def adb_kill():
    """
    kills adb server
    """
    adb_command("kill-server")


def adb_state():
    """
    gets the state of adb server if state is device then phone is connected
    """
    state = adb_command("get-state", ignore_return_code=True)

    if "error" in state:
        return False

    return True


def adb_command(cmd, ignore_return_code=False):
    if os_platform is "osx":
        prefix = "./adb_osx/adb "
    elif os_platform is "win":
        prefix = "adb_win\\adb.exe "
    elif os_platform is "linux":
        prefix = "./adb_linux/adb "

    cmd = prefix + cmd

    exit_code, output = subprocess.getstatusoutput(cmd)
    if ignore_return_code:
        return output
    if exit_code == 0:
        return output
    else:
        print("Exit code {}, an error occurred\n{}".format(exit_code, output))
        sys.exit(-1)


def adb_install(source_path):
    """
    Install package to android device
    """

    # -d is to allow downgrade of apk
    # -r is to reinstall existing apk
    state = adb_command("install -d  -r {}".format(source_path))

    if "Success" in state:  # apk installed
        return INSTALL_OK

    # when here, means something strange is happening
    if "Failure" or "Failed" in state:
        return INSTALL_FAILURE


def rename_fix(path):
    """
    apply  rename fix to files inside folder path,
    replace space character with  underscore
    """
    if os.path.isdir(path):
        files = get_apks(path)

        new_files = []
        for file in files:
            if " " in file:
                new_files.append(file.replace(" ", "_"))
            else:
                new_files.append(file)

        for old, new in zip(files, new_files):
            os.rename(os.path.join(path, old), os.path.join(path, new))
    else:
        raise NotADirectoryError


def get_apks(path):
    if os.path.isdir(path):
        files = os.listdir(path)  # list all files in apk directory
        apk = []  # list holds the apk found in directory
        for file in files:
            if file.endswith(".apk"):  # separate the apk file by extension in an other list
                apk.append(file)
        return apk
    else:
        raise NotADirectoryError


def human_time(start, end):
    hours, rem = divmod(end - start, 3600)
    minutes, seconds = divmod(rem, 60)
    print("Elapsed time {:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))


def parse_args():
    # parse arguments
    parser = argparse.ArgumentParser(description="Simple Backup / Restore  of Android apps")
    parser.add_argument("-b", "--backup", help="perform device back up", action="store_true")
    parser.add_argument("-i", "--install", type=str,
                        help="restore back up to device from path. Path can be a folder, zip file or encrypted archive",
                        required=False)
    parser.add_argument("-a", "--archive", help="create  zip archive after back up, used with -b flag",
                        action="store_true")
    parser.add_argument("-e", "--encrypt", help="encrypt  zip archive after backup used with -b -a flags",
                        action="store_true")

    args = parser.parse_args()
    return args.backup, args.install, args.archive, args.encrypt


def summary(install_state):
    success = 0
    fail = 0

    print("\n\nSummary: ")
    for s in install_state:
        if s == INSTALL_FAILURE:
            fail = fail + 1
        elif s == INSTALL_OK:
            success = success + 1
    print("Installed:{} |  Failed:{}".format(success, fail))


def main():
    print("Apk Mass Installer Utility \nVersion: 3.0\n")

    if len(sys.argv) <= 1:
        print("usage: apk_mass_install.py [-h] [-b] [-i INSTALL] [-a] [-e]")
        sys.exit(0)

    backup, install, archive, encrypt = parse_args()

    adb_kill()  # kill any instances of adb before starting if any

    tries = 0
    while True:
        if adb_state():
            break
        else:
            print("No phone connected waiting to connect phone")

            tries += 1
            if tries == 3:
                print("\nFine i give up bye bye")
                sys.exit(-1)

            time.sleep(3)

    print("Starting adb server...")
    adb_start()  # start an instance of adb server

    t_start = timer()

    if backup:
        # generate filename from current date time
        backup_file = str(datetime.utcnow()).split(".")[0].replace(" ", "_").replace(":", "-")
        if not os.path.exists(backup_file):
            os.mkdir(backup_file)
        else:
            print("Back up folder {} already exists".format(backup_file))
            sys.exit(-1)

        print("Listing installed apk's in device...\n")
        pkgs = package_management(pkg_flags["user"])  # get user installed packages

        num_apk = len(pkgs)

        # get full path on the android filesystem for each installed package
        paths = []
        for i in pkgs:
            path = get_package_full_path(i)
            print("{:40.40} Path: {:60.60}".format(i, path))
            paths.append(path)

        # combine apk name and apk path into dictionary object
        p = []  # list with dictionaries
        for i in range(0, len(pkgs)):
            p.append({pkgs[i]: paths[i]})

        print("\nFound {} installed packages\n".format(num_apk))

        space = len(str(num_apk))  # calculate space for progress bar
        progress = 0
        for i in p:  # i is dict {package name: package path}
            progress += 1
            print("[{0:{space}d}/{1:{space}d}] pulling ... {2}".format(progress, num_apk, i[list(i)[0]], space=space))
            pull_apk(i)  # get apk from device

            shutil.move(list(i)[0] + ".apk",  # move apk to back up directory
                        os.path.join(backup_file, list(i)[0] + ".apk"))

        if archive:
            print("\nCreating zip archive: {}.zip".format(backup_file))
            make_zip(backup_file, backup_file + ".zip")
            if os.path.exists(backup_file):
                shutil.rmtree(backup_file)

        if encrypt:
            if os_platform is not "win":
                key = input("Enter password for encryption:")
                a = AesEncryption(key)
                print("\nEncrypting archive {} this may take a while...".format(backup_file + ".zip"))
                a.encrypt(backup_file + ".zip", backup_file + ".aes")

                if os.path.exists(backup_file + ".zip"):
                    os.remove(backup_file + ".zip")
            else:
                print("Encrypted back up isn't supported on Windows")

        print("\nBack up finished")

    if install:
        clean_up = []  # list of files, dirs to delete after install

        if os.path.exists(install):

            if os.path.isdir(install):  # install from folder
                print("\nRestoring back up from folder: {}".format(install))
                apk_path = install

            elif os.path.isfile(install):  # install from file
                filename, file_extension = os.path.splitext(install)

                if file_extension == ".zip":  # install from zip archive
                    print("\nRestoring back up from zip file: {}".format(install))
                    print("\nUnzipping {} ...".format(install))
                    extract_zip(install, filename)
                    apk_path = filename
                    clean_up.append(filename)

                elif file_extension == ".aes":  # install from encrypted archive
                    if os_platform is not "win":
                        print("\nRestoring back up from encrypted archive: {}".format(install))
                        key = input("Enter password for decryption:")
                        a = AesEncryption(key)
                        print("\nDecrypting back up {} this may take a while...".format(install))
                        a.decrypt(install, filename + ".zip")
                        print("Unzipping archive this may take also a while...")
                        extract_zip(filename + ".zip", filename)
                        apk_path = filename
                        clean_up.append(filename + ".zip")
                        clean_up.append(filename)
                    else:
                        print("Encrypted restored isn't supported on Windows")

        else:
            print("File or folder doesn't exist")
            sys.exit(-1)

        try:
            rename_fix(apk_path)
            apks = get_apks(apk_path)
        except NotADirectoryError:
            print("isn't a dir {}".format(apk_path))
            sys.exit(-1)

        # calculate total installation size
        size = []
        for file in apks:
            size.append(os.path.getsize(os.path.join(apk_path, file)))

        print("\nTotal Installation Size: {0:.2f} MB".format(sum(size) / (1024 * 1024)))
        print("-" * 10)

        state = []
        progress = 0

        space = len(str(len(apks)))  # calculate space for progress bar
        for apk in apks:
            progress += 1
            print("[{0:{space}d}/{1:{space}d}] Installing {2}".format(progress, len(apks), str(apk), space=space))
            s = adb_install(os.path.join(apk_path, apk))
            state.append(s)

        summary(state)

        try:
            clean_up
        except NameError:
            pass
        else:
            for f in clean_up:
                if os.path.exists(f):
                    if os.path.isdir(f):
                        shutil.rmtree(f)
                    elif os.path.isfile(f):
                        os.remove(f)

        print("\nRestore  finished")

    human_time(t_start, timer())

    adb_kill()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Received Interrupt")
