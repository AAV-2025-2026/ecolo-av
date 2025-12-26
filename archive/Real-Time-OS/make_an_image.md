# How to make a QNX image (VM or RPi)

## Prerequisites
Have QNX 8 installation

Run `qnxsdp-env.bat` which should be located in your `C:\Users\<your username>\qnx800` folder

## VM Instructions
### Prerequisites
Have virtualbox, vmware, or qemu installed
### Steps
Create an empty folder and change directories into it
`mkdir <folder name>` `cd <folder name>`

Create image `mkqnximage --type=<vm type you have installed (either vbox, vmware, or qemu)> --repos=`

You can start it with `mkqnximage --run`

You can get the IP address with `mkqnximage --getip` while its running

You can stop it with `mkqnximage --stop`

## RPi Instructions
### Prerequisites
Plug microSD card into reader

Have [balenaEtcher](https://etcher.balena.io/#download-etcher) installed

Have Raspberry Pi BSP installed
#### How to install Raspberry Pi BSP
Go into QNX Software Center

Select `Install New Packages`

Expand `QNX Software Development Platform`

Expand `Board Support Packages`

Select and Install `QNX SDP 8.0 BSP for Raspberry Pi BCM2711 R-PI4`

A zip of the BSP should be located at `C:\Users\<username>\qnx800\bsp`

Make a copy in an empty folder, and extract it

Run `make clean` and `make` in the extracted BSP folder (this may take a minute)

### Steps
Create an empty folder and change directories into it
`mkdir <folder name>` `cd <folder name>`

Run `mkqnximage --extra-dirs=+rasppi --type=rasppi --part-sizes=256:256 --repos=%QNX_TARGET%:<path to firmware folder>:<path to bsp>/install/aarch64le`

Ex. `mkqnximage --extra-dirs=+rasppi --type=rasppi --part-sizes=256:256 --repos=%QNX_TARGET%:../firmware:C:/Users/alexd/bsp_test/BSP_raspberrypi-bcm2711-rpi4_be-800_SVN1019295_JBN334/install/aarch64le`

There should be a `.img` file in the `output` folder (likely name is system-image-256-256-BSD.img)

Run balenaEtcher, select the .img, select the microSD card and flash

Install microSD into Raspberry Pi

## To add files to image
Go to the image folder, then local, then snippets

In the `data_files.custom` file, add `[perms=+rwx]`

Then list files you want in the image with the pattern `path on target:path on your computer`

Note that files start in the `/data` folder on the target

Run `mkqnximage` with the same arguments as the last command, but with `:<path to folder with files specified in data_files.custom>` at the end of `--repos`

Multiple folders can be separated with `:`s
