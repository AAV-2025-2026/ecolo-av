import subprocess
import os
import shutil
import argparse

BINARY_NAME = "BodyControlModule"

def execute(command: str, output: bool = False) -> str:
    if output:
        print(f"Executing command: {command}")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=True
    )
    if result.returncode != 0:
        raise Exception(f"Command '{command}' failed with error: {result.stderr.strip()}")
    if output:
        print(result.stdout)
    return result.stdout

def build(rpi: bool):
    qcc_path = shutil.which("qcc")
    if (qcc_path is None):
        print("qcc not found")
        print("Make sure to have installed QNX 8")
        print("And have run C:/Users/<username>/qnx800/qnxsdp-env.bat")
        exit(1)
    # Flags to pass to the compiler, uses gcc flags
    flags = [
        "-Wall"
    ]
    if rpi:
        flags.append("-Vgcc_ntoaarch64le")
    else:
        flags.append("-Vgcc_ntox86_64")
    # Find files to compile
    files_to_compile: list[str] = []
    for (root, dirs, files) in os.walk("src"):
        for file in files:
            if file.endswith((".c", ".cpp")):
                files_to_compile.append(os.path.join(root, file))

    execute(f"{qcc_path} -o {BINARY_NAME}_{"rpi" if rpi else "vm"} {' '.join(flags)} {' '.join(files_to_compile)}", output=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target',
                        choices=['vm', 'rpi'],
                        default='rpi',
                        help='Build target: vm or rpi'
                        )
    args = parser.parse_args()
    if not os.getcwd().endswith("BodyControlModule"):
        print("Run this script from the BodyControlModule directory.")
        exit(1)

    build(args.target == 'rpi')

if __name__ == "__main__":
    main()
