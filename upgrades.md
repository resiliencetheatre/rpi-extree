# Package upgrade history

This file records version changes made to the external Buildroot package
recipes in `package/`. Packages are tracked here whether or not they are
enabled by a particular defconfig.

## 2026-09-01

### Stable release updates

| Package | Previous | Updated |
| --- | --- | --- |
| coturn | 4.6.2 | 4.17.2 |
| forgejo | v16.0.2 | v16.0.3 |
| libcbor | 0.13.0 | 0.14.0 |
| libfido2 | 1.16.0 | 1.17.0 |
| python-adafruit-circuitpython-rgb-display | 3.14.3 | 3.14.6 |
| python-cxfreeze | 7.2.0 | 8.7.0 |
| python-lxmf | 0.9.6 | 1.1.0 |
| python-peewee | 3.17.6 | 4.4.0 |
| python-print-color | 0.4.6 | 0.4.7 |
| python-pubsub | v4.0.3 | v4.0.7 |
| python-pypubsub | v4.0.3 | v4.0.7 |
| python-pygmc | 0.14.1 | 0.14.2 |
| python-pylint | 3.0.3 | 4.0.8 |
| python-pytestcov | 4.1.0 | 7.1.0 |
| python-tabulate | 0.9.0 | 0.10.0 |
| python-twine | 4.0.2 | 7.0.0 |
| thelounge | v4.4.3 | v4.5.2 |
| wstunnel | v10.4.4 | v10.7.0 |

### Commit pins replaced by release tags

| Package | Previous commit | Updated release |
| --- | --- | --- |
| cryptpad | 437bc15e96f6f4ff6522c1deb079ccff0b900672 | 2026.5.1 |
| gsocket | ad546b2e63f562d351ee45bb758fab9ba34936a2 | v1.4.43 |
| kamailio | 8e398b8675079e1baac7c7575e70283175cdebe2 | 6.1.4 |
| python-pdoc3 | 3ecfbcfb658c5be9ee6ab572b63db2cb5e1c29e1 | 0.11.6 |
| rpiboot | 726256d938d3eca88b80dc119c9294457d74ecae | 20250908-162618-bookworm |
| rtptun | 5dd92376844387da018dee7f8ba4589edbb7407f | v0.5 |

### Commit pin updates

These upstreams did not expose a suitable stable release tag, so their pins
were moved to the default-branch commit current on the audit date.

| Package | Previous commit | Updated commit |
| --- | --- | --- |
| dpinger | fbc7e8f87f595fd4d5693b99f5db04cd7904f0f3 | c845c582b4bdd24ad3a160d9f741e2395f89d710 |
| fidohmac | ca9beedbe203c03979c0d1c2ac01adc413598d95 | 5edd14d762faae852dde74474a6e432f297813e9 |
| ggwave | bef9afbf0c924160695ef3c84264f5e98c2a0fdf | 060aec73dd7123ccac200442f75bdc7369795ffe |
| gwsocket | c17e13741ad2665ff463f94bfe7e425e5e97cf72 | 3ded70360ac66df11b667da2ea42d7c5abbe9dcd |
| lvgl-com | df64bf7f531e02072e3e2fe62686d0bc570f3d2c | fd5cb184d8a481668fc85f14d8da7cf9acdfc96f |
| pttcomm | 7adb61c5b95aedf2fd97536d44459c7c011d909c | 71fca3bdbf3fb4c2692e05bf5f9dd6021ffc19f2 |
| spacecom | 21cf43c28de6f5193fd5c559d13bf9b310bdb089 | ba8823505b4038d45ad27b9d282091169c552e13 |
| udpproxy | adbef488d5cb8bb22517afc5c65bbd6d09856066 | 98234e9cec5255b7f9432fb23b3ead739fcee1f4 |
| udptunnel | f076d24dd07fdf1272f7af81d474042b80a68c4b | d12d6a950b5382f42f1a8ddef7abd04a1ca4f5f4 |

### Additional recipe maintenance

- Updated version-specific PyPI source locations for Adafruit RGB Display,
  cx-Freeze, Peewee, print-color, and pygmc.
- Corrected the misspelled RGB Display version-variable reference in its
  source filename.
- Added an explicit setuptools-scm version for `python-pypubsub`, because
  Buildroot source trees do not retain the Git metadata used by upstream's
  version detection.
- Relaxed PyPubSub's build-only setuptools upper bound so it can build with
  the newer host setuptools supplied by this Buildroot tree.
- Excluded PyPubSub's legacy Python 2 `contrib` examples from its target
  wheel; they are not runtime modules and fail Python 3.14 byte-compilation.
- Removed stale copies of those PyPubSub examples during incremental target
  upgrades, so an earlier failed install cannot break target finalization.
- Used the official wstunnel v10.7.0 release rather than the repository's
  unrelated v666.6.6 tag.
- Kept `dpinger` and `gwsocket` on commit pins because their latest release
  tags were older than the recipes' previous commits; both were advanced to
  current upstream HEAD instead.
- Left `secure-audio` unchanged because its private upstream could not be
  authenticated and verified.

### Packages intentionally left unchanged

The audit found no newer stable release or no newer default-branch commit for
the following versioned recipes:

- `audioreceiver`, `audiostreamer`, `blinkstickctl`, `c2ptt`, `c2stream`,
  `caddy`, `cotsim`, `curlcot`, `edgemap`, `gpsreader`, `highrate`, `inn2`,
  `ircpipe`, `knock-daemon`, `libnitrokey`, `modmodem`, `netmon`, `nkmacsec`,
  `opusstreamer`, `python-argparse`, `python-autopep8`, `python-dateutils`,
  `python-dotmap`, `python-irc`, `python-meshtastic`, `python-nomadnet`,
  `python-pytap2`, `python-rns`, `python-taky`, `python-taky-ng`,
  `python-timeago`, `qtencodeui`, `rclone`, `samplicator`, `situation-map`,
  `syncthing`, `tacmsgrouter`, `udp2raw`, `udpptt`, and `udpspeeder`.

Special cases left unchanged:

- `inn2` remained at 2.7.4, the latest official release at audit time.
- `uucp` remained at 1.07 because no newer upstream application release was
  found.
- `secure-audio` retained commit
  `00a7b60a9931d50301e458fc5724ff5b1a03b015` because its private upstream
  could not be authenticated and verified.
- `lvgl-app` and `lvgl-demo` use local, unversioned sources and therefore had
  no upstream version to compare.
- Existing local changes to the `python-meshtastic` and `python-rns` version
  pins were preserved rather than overwritten during this update.

### Validation

All Buildroot commands were run with `BR2_EXTERNAL` explicitly pointing to
this extree.

- Confirmed that replacement release tags exist in their upstream
  repositories.
- Confirmed that changed, version-specific PyPI source archives are
  downloadable.
- Confirmed that `configs/raspberrypi4_64_site_defconfig` loads successfully.
- Confirmed source downloads for the changed packages selected directly by
  that defconfig.
- Rebuilt and installed `python-pypubsub` 4.0.7 after applying its Buildroot
  compatibility hooks.
- Completed a full build using `raspberrypi4_64_site_defconfig`, including
  Python 3.14 target byte-compilation, target finalization, root filesystem
  generation, and SD-card image generation.
- Confirmed that `wstunnel` 10.7.0 and the updated UDP utilities compile and
  install successfully for the target.
- Confirmed that the extree changes pass `git diff --check`.
