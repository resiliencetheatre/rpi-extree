# External buildroot tree's for RaspberryPi 

Unifying buildroot external trees for different hardware models and images. 

## Buildroot configurations

Baseline configurations are:

```
raspberrypi4_64_defconfig
raspberrypi5_defconfig
raspberrypicm4io_64_defconfig
raspberrypizero2w_64_defconfig
```

## Kernel config

You can store and use custom kernel config with:

```
BR2_LINUX_KERNEL_CUSTOM_CONFIG_FILE="${BR2_EXTERNAL}/configs/kernel/bcm2711_defconfig"
```

## Filesystem overlays

By default filesystem overlay is defined to:

```
BR2_ROOTFS_OVERLAY="${BR2_EXTERNAL}/fs_overlay/fs_base"
```

You may change this based on your build.


