# DokuWiki on the Raspberry Pi webserver image

The `raspberrypi5_webserver_defconfig` installs the pinned DokuWiki
2026-07-14c release, including its bundled vendor dependencies, plugins and
templates. The package hash file covers the release archive and COPYING.
Apache uses prefork with mod_php; PHP extensions cover sessions, XML,
Unicode, file detection, image processing, HTTPS and archive extraction.
Existing database extensions in the defconfig are retained, but DokuWiki
itself does not need a database.

Before starting Apache, provision these files separately in
`/etc/apache2/tls` (certificates and keys are not included in the overlay):

- `server.crt.pem`: server certificate, including intermediate certificates.
- `server.key.pem`: matching private key, root-owned with mode 0600.
- `client-ca.crt.pem`: trusted CA certificate for client authentication.

`/usr/bin/apache-tls-setup` prepares PHP's session directory and checks
that all three files are present and nonempty. It does not generate or
replace certificates. Apache will not start until they are provisioned.
Run `apachectl -t && systemctl restart apache.service` after provisioning.

The HTTPS virtual host requires a valid client certificate (`SSLVerifyClient
require`, `SSLVerifyDepth 1`). Use a browser with access to your client
certificate and private key, such as your smartcard. Open
`https://<certificate-hostname>/dokuwiki/install.php` to set the wiki name,
administrator and ACL policy. The hostname must resolve to the Pi and
match the server certificate. HTTP redirects to HTTPS. Delete
`/usr/share/dokuwiki/install.php` after completing setup.

The Apache configuration was copied from the working target at
`git.resilience-theatre.com`. Its global `ServerName pivault` is preserved;
set the HTTPS virtual host's ServerName to your certificate hostname if
you want to avoid Apache's server-name mismatch warning.

DokuWiki is installed under `/usr/share/dokuwiki` on the writable root
filesystem. `conf`, `data`, `lib/plugins` and `lib/tpl` are owned by
`www-data` so setup, editing and extension management work. Back up these
directories before reflashing the image; they are not on the encrypted
`/opt/data` mount. Apache denies direct web access to private directories,
hidden files and metadata without relying on .htaccess overrides.

The dedicated `fs_webserver` overlay is applied after `fs_site`, replacing
its Apache configuration only for this defconfig. Other defconfigs keep
their existing configuration. When enabling the package in another image,
configure Apache's PHP handler, www-data user and writable session path,
and include `/etc/apache2/extra/dokuwiki.conf`.

Upstream release: https://github.com/dokuwiki/dokuwiki/releases/tag/release-2026-07-14c
