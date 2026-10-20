# Raspberry Pi 4 PocketTerm boot overlays

`configs/raspberrypi4_pocketterm_defconfig` runs this board's `post-image.sh`
before the shared `board/raspberrypi4-64/post-image.sh` image builder.
The board hook copies every `*.dtbo` in this directory, with mode `0644`, to
`${BINARIES_DIR}/rpi-firmware/overlays/`. Currently these are:

- `waveshare-35dpi-3b.dtbo`
- `waveshare-35dpi-4b.dtbo`
- `waveshare-35dpi-5b.dtbo`

The shared image builder includes that overlays directory in `boot.vfat`,
which is placed in the boot partition of `sdcard.img`. The target mounts
this partition at `/boot`, making the files available under `/boot/overlays/`.
Existing firmware overlays are preserved, except that a board-local file
with the same name replaces the staged copy.

Load the updated `raspberrypi4_pocketterm_defconfig` and run the normal Buildroot
build (`make`) to regenerate the images. For an existing build configuration,
ensure `BR2_ROOTFS_POST_IMAGE_SCRIPT` contains both hooks in the order above.
Additional `.dtbo` files placed in this directory are included automatically.
These are precompiled overlays; the hook copies them without compiling them.
Copying an overlay does not enable it: select the appropriate `dtoverlay=`
entry in the boot `config.txt` separately.
