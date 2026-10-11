# PXE APT source policy repair

Workstation path setup (adjust once for your checkout):

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
```


The first hardware installation exposed a Debian apt-setup 0.198 behaviour:
`apt-setup/use_mirror=false` is only honoured in the CD installation branch.
On PXE, `50mirror` still adds a default source. It conflicts with the per-source
`Check-Valid-Until: no` setting in our `60local` entries and may request source
indexes from the binary-only archive.

The preseed early script now installs `00offline-policy`. At apt-setup time,
after udebs have been unpacked, this hook checks the exact reviewed `50mirror`
SHA256, preserves its original outside the generators directory, and replaces it
with an intentional exit-1 generator (apt-setup discards that generator's output).
`60local` remains responsible for all three repositories. Unexpected generator
contents fail with exit 10, which aborts apt-setup. Signature checking remains
enabled; validity exceptions remain per local source. Both installer profiles
also explicitly disable automatic source-repository entries.

New generations rendered by these tools include the fix. Rebuilding firmware
alone cannot update the independently populated mirror on partition 3. Existing
verified generations need the repair below; no mirror download is required.

Stop the laptop installation before applying the fix. On desk:

```sh
cd "$BR2_EXTERNAL/support/offline-pxe"
mkdir -p /tmp/offline-pxe-repair
python3 make-installer-policy-fix.py /tmp/offline-pxe-repair/repair-installer-policy.sh
sha256sum /tmp/offline-pxe-repair/repair-installer-policy.sh
```

Transfer that script to `/tmp/repair-installer-policy.sh` on the Pi. For example,
connect desk to the Pi's isolated Ethernet, obtain an address using DHCP, and run
this server on desk (replace DESK_LAN_IP with its 192.168.50.x address):

```sh
python3 -m http.server 8000 --bind DESK_LAN_IP --directory /tmp/offline-pxe-repair
```

On the Pi, replace the same address:

```sh
curl -f http://DESK_LAN_IP:8000/repair-installer-policy.sh -o /tmp/repair-installer-policy.sh
sha256sum /tmp/repair-installer-policy.sh
# Compare with desk's checksum before running.
sh /tmp/repair-installer-policy.sh --no-active-installers
systemctl is-active offline-dnsmasq offline-nginx
curl -f http://192.168.50.1/preseed/early.sh
```

The repair checks the mounted filesystem UUID, old readiness seal and installer
version before writing. It locks activation, stops installer/recovery services,
backs up early.sh and its seal, appends the corrected policy, and updates only the
control-file checksums. A checksummed repair receipt records the change without
claiming another full package verification. It then remounts read-only and starts
services. On failure services remain stopped for diagnosis; do not remove the
maintenance marker or backup to bypass a failed check.

Stop the temporary desk HTTP server. Reconnect the laptop and restart PXE from
the beginning, choosing Offline Debian guided installation. No laptop-side patch
is needed. Full offline desktop installation and expired-metadata installation
remain hardware acceptance tests, not claims established by the hook tests.
