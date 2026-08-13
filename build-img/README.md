# Raspberry Pi Image Builder for ttymidi-rpi

Pre-built Debian images are available in Github releases for quick testing.
You can also build your own image from scratch using the script in this directory.

## Building a Custom Image

The `build.sh` script creates a Raspberry Pi OS (Trixie) image with ttymidi-rpi
pre-installed and configured for serial MIDI over GPIO.

### Before running `build.sh`

1. **Edit `build.sh`** to customise at least:
   - **Line 66** – `plain_text_passwd`: set the `ttymidi` user password
     (or switch to an SSH key on lines 68-69 for better security)
   - **Lines 89-90** – Wi-Fi SSID and password

### Running the build

```sh
sudo bash build.sh
```

The script will decompress the base image, mount its partitions, inject
cloud-init user-data, network config, USB-gadget serial, first-boot setup, and
ttymidi-rpi dependencies, then clean up.

### Flashing the image

```sh
ddrescue image.img /dev/sdX --force -y
# or: dd if=image.img of=/dev/sdX bs=4M status=progress && sync
```

Replace `/dev/sdX` with your microSD card device.

## First Boot

1. Insert the card into the Raspberry Pi and power on.
2. Log in as **ttymidi** (with the password you set, or `ttymidi` by default).
3. If you did **not** pre-configure Wi-Fi in `build.sh`, connect to a network
   with:
   ```sh
   sudo raspi-config  # System Options → Wireless LAN
   ```
4. Reboot: `sudo reboot`

A **second reboot** is required because the first-boot setup script installs
the ttymidi-rpi `.deb` and, on a Raspberry Pi 5, applies the service override
that switches from `/dev/serial0` to `/dev/ttyAMA0`.

## Testing MIDI

After the second boot, verify that ttymidi is running:

```sh
aconnect -l
```

You should see a client named `MIDI` with `MIDI In` and `MIDI Out` ports.

To test sequencing with an external clock:

```sh
python3 /usr/share/doc/ttymidi-rpi/examples/seq-midi-loop8.py
```

For a simpler echo/delay test without an external clock:

```sh
python3 /usr/share/doc/ttymidi-rpi/examples/seq-echo-delay.py
```

## What `build.sh` Configures

| Component | Details |
|---|---|
| User | `ttymidi` (sudo, dialout, audio, gpio, etc.) |
| Wi-Fi | NetworkManager-managed, configured via cloud-init |
| SSH | Enabled with password auth by default |
| USB gadget | Serial console over USB-C (`ttyGS0`) |
| ttymidi-rpi | Installed from `.deb` on first boot |
| Pi 5 override | Automatically switches ttymidi to `/dev/ttyAMA0` at 38400 baud |

## Requirements

- Linux host with `losetup`, `mount`, `dosfsck`, `e2fsck`, `zerofree`,
  `wget`, `xz` utilities
- An ARM64 Raspberry Pi OS Lite `.img.xz` image in this directory
