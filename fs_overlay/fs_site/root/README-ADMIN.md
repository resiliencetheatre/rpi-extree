# site-a Administrator Notes

This Buildroot image contains the base configuration for:

- UUCP link to `vps`
- Exim local mail and SMTP submission
- Dovecot IMAP
- automatic UUCP polling and incoming `uuxqt` processing

Credentials are intentionally **not provisioned** in the image. Complete the steps below after first boot.

## 1. Set UUCP credentials

Edit:

```sh
vi /etc/uucp/sys
```

Replace:

```text
call-password CHANGE-ME
```

with the correct password for the `site-a` UUCP login on VPS.

Protect credential files:

```sh
chmod 0600 /etc/uucp/call /etc/uucp/passwd
```

## 2. Create Dovecot password

Generate a password hash:

```sh
doveadm pw -s SHA512-CRYPT
```

Create `/etc/dovecot/users`:

```text
tech:{SHA512-CRYPT}<HASH>
```

Then:

```sh
chown root:dovecot /etc/dovecot/users
chmod 0640 /etc/dovecot/users
```

## 3. Check runtime directories

```sh
mkdir -p /var/spool/uucp /var/spool/uucppublic /var/log/uucp /var/lock/uucp /var/mail

chown uucp:uucp /var/spool/uucp /var/log/uucp /var/lock/uucp
chmod 0755 /var/spool/uucp /var/log/uucp /var/lock/uucp

chown uucp:uucp /var/spool/uucppublic
chmod 1777 /var/spool/uucppublic

chown root:mail /var/mail
chmod 1777 /var/mail
```

## 4. Start services

Dovecot manages its own IMAP listener; do not use socket activation:

```sh
systemctl disable dovecot.socket
systemctl reset-failed dovecot.socket 2>/dev/null || true

systemctl enable --now dovecot.service
systemctl enable --now exim.service
systemctl enable --now uucp-vps.timer
systemctl enable --now uuxqt.timer
```

Check:

```sh
systemctl list-timers --all | grep -E 'uucp|uuxqt'
ss -lnt | grep -E ':(25|143|587)[[:space:]]'
```

Expected services:

```text
143   Dovecot IMAP
25    Exim SMTP
587   Exim authenticated SMTP submission
```

## 5. Verify authentication and mail

```sh
dovecot -n
doveadm auth test tech
doveadm user tech
doveadm mailbox list -u tech
```

Local mail test:

```sh
printf 'From: root@site-a\nTo: tech@site-a\nSubject: Local test\n\nHello.\n' |
    exim tech@site-a

tail -n 30 /var/mail/tech
```

Check the UUCP mail route:

```sh
exim -bt tech@vps.uucp
```

Check UUCP:

```sh
uuname -l
uuname
systemctl start uucp-vps.service
tail -n 20 /var/log/uucp/Log
```

A successful connection should show `Login successful`, `Handshake successful`, and `Call complete`.

## 6. Mail client settings

For a trusted LAN/WireGuard client:

```text
Email address: tech@site-a

Incoming:
  IMAP server: site-a
  Port:        143
  Username:    tech
  Security:    None

Outgoing:
  SMTP server: site-a
  Port:        587
  Username:    tech
  Authentication: Password
  Security:    None
```

Example remote address:

```text
tech@vps.uucp
```

## Important

This setup currently permits plaintext IMAP and SMTP authentication without TLS.
Use it only on a trusted LAN or protected network such as WireGuard.

Do not put live credentials, password hashes, UUCP spool contents, mailboxes, or
logs back into the Buildroot overlay/Git repository.
