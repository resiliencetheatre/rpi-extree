# reTerminal display driver

Vendored from Seeed-Studio/seeed-linux-dtoverlays, `modules/mipi_dsi/`,
master snapshot retrieved 2026-11-03 through the source browser. Upstream:
https://github.com/Seeed-Studio/seeed-linux-dtoverlays/tree/master/modules/mipi_dsi

These sources implement the original reTerminal's I2C STM32 controller,
ILI9881C/D panel and polled touchscreen. Keeping the source locally avoids an
unversioned network dependency and lets Buildroot build the module against the
exact kernel used by the image, without DKMS or target-side compilation.

Local changes: minimal Kbuild Makefile, explicit drm_connector.h include,
disabled verbose debug prints, and devm_drm_panel_alloc for the reference-counted
DRM panel API in Linux 6.18. Orientation is supplied through get_orientation
(forwarded through the controller's panel callbacks), so the panel bridge
creates the connector property before DRM registration. Deferred DSI host probes
use dev_err_probe rather than logging errors on every normal retry.
The upstream source retains its older-kernel API conditionals. The updated module
was cross-built against the workspace's 6.18.60-v8 kernel; a hardware retest of
these fixes remains necessary. Revalidate when changing the pinned kernel.

The module is GPL-2.0 (see source headers and COPYING); panel-ili9881x.c
permits GPL-2.0-or-later. The board overlay is separately MIT licensed, with
its upstream copyright retained in board/reterminal/reTerminal-overlay.dts.
