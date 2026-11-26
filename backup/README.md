# Off-site backup to Google Drive

`offsite-backup.sh` runs every morning. It packs up everything needed to
rebuild the Pi, encrypts it and uploads it to the `pi-backups` folder in
Google Drive. The newest 14 backups are kept.

**What's in it:** Home Assistant config (including `.storage` and
`secrets.yaml`), Zigbee2MQTT data, Thread (OTBR) and Matter data, ESPHome
config, `compose/.env`, Blockly programs, Jupyter notebooks and the latest
Postgres dump.

**What's not in it:** Home Assistant's history database (graphs start
again from empty), logs, and anything that's already in git.

---

## If the Pi dies: getting back up

You need: a working Pi with Raspberry Pi OS and Docker, and the backup
passphrase from your password manager.

1. **Get the code back**
   ```bash
   sudo mkdir -p /opt/data && cd /opt/data
   sudo git clone <your GitHub repo URL> app_containers
   ```
2. **Download the newest backup.** In a browser, open Google Drive →
   `pi-backups` and download the newest `home-backup-YYYYMMDD_HHMM.tar.gz.gpg`.
   Copy it to the Pi.
3. **Unpack it into place.** Enter the passphrase when asked.
   ```bash
   gpg -d home-backup-YYYYMMDD_HHMM.tar.gz.gpg | sudo tar -xz -C /opt/data
   ```
4. **Check the USB stick paths.** Run `ls /dev/serial/by-id/`. If the
   Zigbee or Thread stick shows a different name, update
   `ZIGBEE_STICK_PATH` / `OTBR_STICK_PATH` in
   `/opt/data/app_containers/compose/.env`.
5. **Start everything**
   ```bash
   sudo su
   cd /opt/data/app_containers/compose
   docker compose -f ha_compose.yml up -d
   ```
   Home Assistant, Zigbee devices, Thread/Matter devices and ESPHome
   should all come back without re-pairing.
6. **Restore the Postgres data** (only needed if you want the old sensor
   data back):
   ```bash
   cd /opt/data/postgres_data/backups
   unzip data_dump_*.zip
   docker compose -f /opt/data/app_containers/compose/ha_compose.yml \
       exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d data' < data_dump_*.sql
   ```

---

## One-time setup

Run these on the Pi.

1. **Install the tools**
   ```bash
   sudo apt install rclone gnupg
   ```
2. **Create the passphrase**
   ```bash
   sudo mkdir -p /root/.config/offsite-backup
   sudo sh -c 'openssl rand -base64 32 > /root/.config/offsite-backup/passphrase'
   sudo chmod 600 /root/.config/offsite-backup/passphrase
   sudo cat /root/.config/offsite-backup/passphrase
   ```
   **Save the passphrase in your password manager now.** Without it the
   backups can't be opened, and the only other copy is on the Pi.
3. **Connect Google Drive**
   ```bash
   sudo rclone config
   ```
   - `n` for a new remote, name it `gdrive`, storage type `drive`.
   - Leave client ID and secret blank.
   - Scope: choose `drive.file`. rclone can then only see files it
     created itself, not the rest of your Drive.
   - When it asks "Use web browser to automatically authenticate?",
     answer `n` if the Pi has no desktop browser. It prints an
     `rclone authorize "drive" ...` command. Run that on a computer that
     has a browser and rclone installed, sign in to Google, and paste the
     result back into the Pi.
4. **Run it once by hand**
   ```bash
   sudo /opt/data/app_containers/backup/offsite-backup.sh
   ```
   It should end with `Done: home-backup-....tar.gz.gpg`, and the file
   should appear in Google Drive → `pi-backups`.
5. **Schedule it** (daily at 06:30, after the 06:01 Postgres dump)
   ```bash
   echo '30 6 * * * root /opt/data/app_containers/backup/offsite-backup.sh >> /var/log/offsite-backup.log 2>&1' \
       | sudo tee /etc/cron.d/offsite-backup
   ```
6. **Test a restore once.** Download a backup and check that it opens
   (this doesn't change anything):
   ```bash
   gpg -d home-backup-YYYYMMDD_HHMM.tar.gz.gpg | tar -tz | head
   ```

## Keeping an eye on it

- Log: `/var/log/offsite-backup.log`. Every run ends with `Done:` or `ERROR:`.
- Every so often, check that new files are appearing in Google Drive.

## Settings

Change these with environment variables in the cron line if needed:
`DATA_ROOT` (default `/opt/data`), `RCLONE_REMOTE` (`gdrive:pi-backups`),
`KEEP` (`14`), `PASSPHRASE_FILE` (`/root/.config/offsite-backup/passphrase`),
`WORK_DIR` (`/var/tmp/offsite-backup`).
