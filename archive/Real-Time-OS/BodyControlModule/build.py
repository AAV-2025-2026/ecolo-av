import subprocess
import argparse
import os
import shutil

def execute(command: str):
    result = subprocess.run(
        ["cmd", "/c", command],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise Exception(f"Command '{command}' failed with error: {result.stderr.strip()}")
    return result.stdout

def build(clean: bool, platform: str):
    if (clean and os.path.exists("build")):
        shutil.rmtree("build")

    compiler_path = None
    if platform == "rpi":
        compiler_path = shutil.which("qcc")
    elif platform == "vm":
        compiler_path = shutil.which("qcc")
    elif platform == "windows":
        compiler_path = shutil.which("cl") # Figure this out later

    print(compiler_path)

    print(execute("cmake -S . -B build"))
    print(execute("cmake --build build"))

def main():
    parser = argparse.ArgumentParser(description="Build script for BodyControlModule")
    parser.add_argument(
        "-p",
        "--platform",
        type=str.lower,
        choices=["rpi", "vm", "windows"],
        required=True,
        help="Target platform: rpi, vm, or windows",
    )
    parser.add_argument(
        "-c",
        "--clean",
        action="store_true",
    )
    args = parser.parse_args()
    platform = args.platform
    clean_build = args.clean

    if not os.getcwd().endswith("BodyControlModule"):
        print("Run this script from the BodyControlModule directory.")
        exit(1)

    build(clean_build, platform)

if __name__ == "__main__":
    main()
