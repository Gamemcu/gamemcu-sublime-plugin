import sublime

import os
import json
import codecs
import threading
import zipfile
import serial_monitor
import gm_panel

try:
    #ST3
    from .sys_path import gm_dir, gm_user_dir, gm_firmware_dir, gm_version_url
    from .serial.tools.list_ports import comports
    from .esptool import esp_set_log, ESPLoader, write_flash, detect_flash_size, flash_size_bytes
    from .task_queue import ActionQueue
    from .net.open_compat import open_compat, read_compat
    from .net.download_manager import downloader
except Exception as e:
    #ST2
    import gm_dir, gm_user_dir, gm_firmware_dir, gm_version_url
    from serial.tools.list_ports import comports
    from esptool import esp_set_log, ESPLoader, write_flash, detect_flash_size, flash_size_bytes
    from task_queue import ActionQueue
    from net.open_compat import open_compat, read_compat
    from net.download_manager import downloader

try:
    #PY3
    from urllib.parse import urlparse
except Exception as e:
    #PY2
    from urlparse import urlparse

class GmManager(object):

    def __init__(self):
        self.menu = None
        self.panel = None
        self._act_queue = ActionQueue()
        self.serial_monitor = serial_monitor.SerialMonitor(self.panel_write)

    @property
    def menu_ports(self):
        if not self.menu:
            path = os.path.join(gm_dir(), 'Main.sublime-menu')
            with codecs.open(path, 'r', 'utf-8') as f:
                self.menu = json.loads(f.read())
        return self.menu[0]["children"][0]["children"][1]["children"]

    def refresh_serial_port(self):
        self.menu_ports.clear()
        for n, (port, desc, hwid) in enumerate(sorted(comports()), 1):
            print('--- {:2}: {:20} {!r}\n'.format(n, port, desc))
            self.menu_ports.append({
                "caption": port,
                "id": port,
                "checkbox": True,
                "command": "gm_serial_port",
                "args": {
                    "serial_port": port
                }
            })
        path = os.path.join(gm_user_dir(), 'Main.sublime-menu')
        with codecs.open(path, 'w', 'utf-8') as f:
            f.write(json.dumps(self.menu))

    def panel_show(self, window, syntax):
        if not self.panel:
            panel = gm_panel.GmPanel(window, self.send_to_dev, syntax)
            self.panel = panel
        self.panel.show()

    def open(self, window, syntax):
        if not self.panel:
            panel = gm_panel.GmPanel(window, self.send_to_dev, syntax)
            self.panel = panel
        ap = window.active_panel()
        if ap and self.panel.name in ap:
            sm = self.serial_monitor
            if sm:
                if sm.is_ready:
                    sm.stop()
                else:
                    sm.start()
        self.panel.show()

    def panel_write(self, data):
        if self.panel:
            self.panel.write(data)

    def panel_writeln(self, data, end='\n'):
        if self.panel:
            self.panel.write(data+end)

    def send_to_dev(self, data, rsp=False):
        if self.serial_monitor.is_ready:
            self.serial_monitor.send(data)

    def _firmware_download_task(self, on_done=None):
        url = gm_version_url()
        try:
            self.panel_writeln('Check firmware version ... ')
            with downloader(url, {}) as manager:
                version = manager.fetch(url, 'Error submitting usage information.')
            version = version.replace(b'\n',b'').decode('utf-8', 'replace')
            firmware = version+'.zip'
            firmware_path = os.path.join(gm_firmware_dir(), firmware)
            if not os.path.isfile(firmware_path):
                firmware_url = url.replace('version', firmware)
                self.panel_writeln('Start Download "%s"'%firmware_url)
                with downloader(firmware_url, {}) as manager:
                    package_bytes = manager.fetch(firmware_url, 'Error submitting usage information.')
                with open_compat(firmware_path, "wb") as package_file:
                    package_file.write(package_bytes)
        except (Exception) as e:
            self.panel_writeln(str(e))
            return
        self.panel_writeln('firmware is ready\nunpack ...')
        try:
            package_zip = zipfile.ZipFile(firmware_path, 'r')
            package_zip.extractall(gm_firmware_dir())
            package_zip.close()
            if on_done:
                on_done()
        except (zipfile.BadZipfile):
            self.panel_writeln(str(e))

    def _firmware_upload_task(self):
        firmware = (
            '0x1000', os.path.join(gm_firmware_dir(),'bootloader.bin'),
            '0x10000', os.path.join(gm_firmware_dir(), 'NodeMCU.bin'),
            '0x8000', os.path.join(gm_firmware_dir(), 'partitions_singleapp.bin')
        )
        args = FirmwareUploadArgs(self.serial_monitor.port,firmware)
        initial_baud = min(ESPLoader.ESP_ROM_BAUD, args.baud)
        try:
            self.serial_monitor.stop(log=False)
            self.panel_writeln('Firmware Start Update ...')
            esp_set_log(self.panel_writeln)
            esp = ESPLoader.detect_chip(args.port, initial_baud, args.before)
            self.panel_writeln("Chip is %s" % (esp.get_chip_description()))
            esp = esp.run_stub()
            if args.baud > initial_baud:
                try:
                    esp.change_baud(args.baud)
                except NotImplementedInROMError:
                    self.panel_writeln("WARNING: ROM doesn't support changing baud rate. Keeping initial baud rate %d" % initial_baud)
            if hasattr(args, "flash_size"):
                self.panel_writeln("Configuring flash size...")
                detect_flash_size(esp, args)
                esp.flash_set_parameters(flash_size_bytes(args.flash_size))
            write_flash(esp, args)
            esp.hard_reset()
            esp._port.close()
            self.serial_monitor.start()
        except Exception as e:
            self.panel_writeln(str(e)) 
        finally:
            self.serial_monitor.start(log=False)

    def firmware_update(self):
        if self.serial_monitor.is_ready:
            self._act_queue.put(self._firmware_download_task, self._firmware_upload_task)
                
class FirmwareUploadArgs:
    after = 'hard_reset'
    before = 'default_reset'
    chip = 'esp32'
    compress = True
    flash_freq = '40m'
    flash_mode = 'dio'
    # flash_size = '4MB'
    flash_size='detect'
    no_compress = False
    no_progress = False
    no_stub = False
    operation = 'write_flash'
    port = '/dev/ttyUSB1'
    baud = 921600
    spi_connection = None
    verify = False

    def __init__(self, port, values):
        self.port = port
        pairs = []
        for i in range(0, len(values), 2):
            try:
                address = int(values[i], 0)
            except ValueError as e:
                raise Exception('Address "%s" must be a number' % values[i])
            try:
                argfile = open(values[i + 1], 'rb')
            except IOError as e:
                raise Exception(e)
            except IndexError:
                raise Exception(
                    'Must be pairs of an address and the binary filename to write there')
            pairs.append((address, argfile))

        # Sort the addresses and check for overlapping
        end = 0
        for address, argfile in sorted(pairs):
            argfile.seek(0, 2)  # seek to end
            size = argfile.tell()
            argfile.seek(0)
            sector_start = address & ~(ESPLoader.FLASH_SECTOR_SIZE - 1)
            sector_end = ((address + size + ESPLoader.FLASH_SECTOR_SIZE - 1)
                          & ~(ESPLoader.FLASH_SECTOR_SIZE - 1)) - 1
            if sector_start < end:
                message = 'Detected overlap at address: 0x%x for file: %s' % (
                    address, argfile.name)
                raise Exception(message)
            end = sector_end
        setattr(self, 'addr_filename', pairs)
