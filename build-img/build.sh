# Image build script for ttymidi-rpi
# Customize sections below to fit your needs:
# - Download source image/version
# - Cloud-init user-data (users, packages, first-boot commands)
# - Network configuration (Wi-Fi SSID/pass, regulatory domain)
# - Serial/USB gadget settings and service overrides

# Things you have to customize:
# - ttymidi user password: line 45
# - WIFI SSID and password: line 68,69

#set -x  # Echo commands for easier troubleshooting while customizing
HERE=`pwd`
DEB_MIRROR="${DEB_MIRROR:-https://deb.debian.org/debian/pool/main}"

# Download the base Raspberry Pi OS image. Replace URL to pin a different release.
wget https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2025-12-04/2025-12-04-raspios-trixie-arm64-lite.img.xz
# Decompress to a raw image file. Update filename if you change the download.
xz -dkc *.xz > image.img

# Attach the image as a loop device so we can mount its partitions.
losetup --show -P -f image.img
mkdir -p boot
mkdir -p root
# Mount the boot and root partitions for editing.
mount /dev/loop0p1 ./boot
mount /dev/loop0p2 ./root

# First-boot setup script (runs once via systemd ConditionFirstBoot)
mkdir -p ./root/usr/local/bin
cat <<'SCRIPT' > ./root/usr/local/bin/first-boot-setup.sh
#!/bin/bash
set -x
ls -l /
cd /root; dpkg -i *.deb; apt-get install -y python3-mido python3-rtmidi
mkdir -p /etc/systemd/system/ttymidi-rpi.service.d/
grep 'Pi 5' /proc/device-tree/model && cp /root/override.conf /etc/systemd/system/ttymidi-rpi.service.d/ && echo Please Reboot.
SCRIPT
chmod +x ./root/usr/local/bin/first-boot-setup.sh

cat <<EOF > ./root/etc/systemd/system/first-boot-setup.service
[Unit]
Description=First boot setup
ConditionFirstBoot=yes

[Service]
Type=oneshot
ExecStart=/usr/local/bin/first-boot-setup.sh
RemainAfterExit=yes
EOF

mkdir -p ./root/etc/systemd/system/multi-user.target.wants
ln -s /etc/systemd/system/first-boot-setup.service ./root/etc/systemd/system/multi-user.target.wants/first-boot-setup.service

# Cloud-init config applied on first boot.
# Edit users, passwords/SSH keys to customize.
cat <<EOF > ./boot/user-data
#cloud-config

# Create a default user account and apply permissions
users:
  - name: ttymidi
    groups: users,adm,dialout,audio,netdev,video,plugdev,cdrom,games,input,gpio,spi,i2c,render,sudo
    shell: /bin/bash
    lock_passwd: false  # Set to true to disable password login entirely
    plain_text_passwd: ttymidi  # Change to your preferred password
# Alternatively, use 'passwd:' with a hashed password for better security
#    ssh_authorized_keys:
#      - ssh-ed25519 mykeystuff  # Replace with your actual SSH public key
    sudo: ALL=(ALL) NOPASSWD:ALL  # Drop NOPASSWD if you want sudo prompts

enable_ssh: true  # Set false to disable SSH
ssh_pwauth: true  # Set false if you only use SSH keys
EOF

# Network config for Wi-Fi. Update SSID/password and regulatory-domain.
cat <<EOF >./boot/network-config
network:
  version: 2
  wifis:
    # Make sure the target is NetworkManager which is the default on Raspberry Pi OS
    renderer: NetworkManager
    # The connection name
    wlan0:
      dhcp4: true
      # !VERY IMPORTANT! Change this to the ISO/IEC 3166 country code for the country you want to use this microSD card in.
      regulatory-domain: "US"
      access-points:
        "x":  # Replace with your Wi-Fi SSID
          password: "x"  # Replace with your Wi-Fi password
      # Don’t wait at boot for this connection to connect successfully
      optional: true
EOF

# Add serial over USB (USB gadget). Remove if you do not need USB serial.
sed ./boot/cmdline.txt -i -e 's/$/ modules-load=dwc2,g_serial/'
sed ./boot/config.txt -i -e 's/\[all\]/\[all\]\ndtoverlay=dwc2/'
mkdir -p ./root/etc/systemd/system/getty.target.wants
cd ./root/etc/systemd/system/getty.target.wants
ln -s /lib/systemd/system/getty@.service getty@ttyGS0.service
cd $HERE

# Needed override ttymidi-rpi service for Raspberry Pi 5
cat <<EOF > ./root/root/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/ttymidi -s /dev/ttyAMA0 -b 38400
EOF

# Dependency .deb packages for offline install at first boot.
# Paths are relative to $DEB_MIRROR.  Update versions if you change the base image.
DEPS=(
  o/opus/libopus0_1.5.2-2_arm64.deb
  j/jackd2/libjack-jackd2-0_1.9.22~dfsg-4_arm64.deb
  p/python-packaging/python3-packaging_25.0-1_all.deb
  p/python-mido/python3-mido_1.3.3-0.1_all.deb
  p/python-rtmidi/python3-rtmidi_1.5.8-3+b3_arm64.deb
)
mkdir -p ./root/var/cache/apt/archives
for dep in "${DEPS[@]}"; do
  wget -q "$DEB_MIRROR/$dep" -P ./root/var/cache/apt/archives/ || echo "Error wget $dep"
done

# Download ttymidi-rpi .deb for installation by first-boot-setup.
mkdir -p ./root/root
cd ./root/root
wget https://github.com/ldrolez/ttymidi-sysex/releases/download/v0.20240907/ttymidi-rpi_0.20240907-bullseye_arm64.deb
cd $HERE

# Clean up mounts and loop device.
umount ./boot
umount ./root
dosfsck -a /dev/loop0p1
e2fsck -f /dev/loop0p2
zerofree -v /dev/loop0p2
losetup -d /dev/loop0
set +x
