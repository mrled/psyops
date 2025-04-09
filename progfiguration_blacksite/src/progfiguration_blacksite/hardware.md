# Hardware notes

## Optiplex 7050 nodes

* CPU: `Intel(R) Core(TM) i5-7500T CPU @ 2.70GHz`
* Cores: 4
* RAM: 32GB max
* Single USB 3.0 controller
* 1 NVME slot
* 1 SATA port

### `lsusb -t`

```text
zalas:~# lsusb -t
/:  Bus 001.Port 001: Dev 001, Class=root_hub, Driver=xhci_hcd/16p, 480M
    |__ Port 004: Dev 002, If 0, Class=[unknown], Driver=hub/4p, 480M
        |__ Port 002: Dev 005, If 0, Class=[unknown], Driver=usbhid, 1.5M
        |__ Port 002: Dev 005, If 1, Class=[unknown], Driver=usbhid, 1.5M
    |__ Port 009: Dev 003, If 0, Class=[unknown], Driver=btusb, 12M
    |__ Port 009: Dev 003, If 1, Class=[unknown], Driver=btusb, 12M
/:  Bus 002.Port 001: Dev 001, Class=root_hub, Driver=xhci_hcd/10p, 5000M
    |__ Port 004: Dev 002, If 0, Class=[unknown], Driver=usb-storage, 5000M
```

### `lspci`

```text
zalas:~# lspci
00:00.0 Host bridge: Intel Corporation Xeon E3-1200 v6/7th Gen Core Processor Host Bridge/DRAM Registers (rev 05)
00:02.0 VGA compatible controller: Intel Corporation HD Graphics 630 (rev 04)
00:14.0 USB controller: Intel Corporation 200 Series/Z370 Chipset Family USB 3.0 xHCI Controller
00:14.2 Signal processing controller: Intel Corporation 200 Series PCH Thermal Subsystem
00:15.0 Signal processing controller: Intel Corporation 200 Series PCH Serial IO I2C Controller #0
00:16.0 Communication controller: Intel Corporation 200 Series PCH CSME HECI #1
00:16.3 Serial controller: Intel Corporation 200 Series Chipset Family KT Redirection
00:17.0 SATA controller: Intel Corporation 200 Series PCH SATA controller [AHCI mode]
00:1b.0 PCI bridge: Intel Corporation 200 Series PCH PCI Express Root Port #17 (rev f0)
00:1c.0 PCI bridge: Intel Corporation 200 Series PCH PCI Express Root Port #8 (rev f0)
00:1f.0 ISA bridge: Intel Corporation 200 Series PCH LPC Controller (Q270)
00:1f.2 Memory controller: Intel Corporation 200 Series/Z370 Chipset Family Power Management Controller
00:1f.3 Audio device: Intel Corporation 200 Series PCH HD Audio
00:1f.4 SMBus: Intel Corporation 200 Series/Z370 Chipset Family SMBus Controller
00:1f.6 Ethernet controller: Intel Corporation Ethernet Connection (5) I219-LM
01:00.0 Non-Volatile memory controller: Sandisk Corp SanDisk Ultra 3D / WD Blue SN570 NVMe SSD (DRAM-less)
02:00.0 Network controller: Intel Corporation Wireless 8265 / 8275 (rev 78)
```

## Intel NUC `NUC6i3SYK` nodes

* CPU: `Intel(R) Core(TM) i3-6100U CPU @ 2.30GHz`
* Cores: 2
* RAM: 32GB max
* Single USB 3.0 controller
* 1 NVME slot
* 1 SATA port (no room in the smaller cases for the drive)
* <https://www.intel.com/content/www/us/en/products/sku/89186/intel-nuc-kit-nuc6i3syk/specifications.html>

### `lsusb -t`

```text
dieselgrove:~# lsusb -t
/:  Bus 001.Port 001: Dev 001, Class=root_hub, Driver=xhci_hcd/12p, 480M
    |__ Port 003: Dev 018, If 0, Class=[unknown], Driver=hub/4p, 480M
        |__ Port 001: Dev 019, If 0, Class=[unknown], Driver=hub/4p, 480M
            |__ Port 002: Dev 021, If 0, Class=[unknown], Driver=usbhid, 480M
            |__ Port 002: Dev 021, If 1, Class=[unknown], Driver=usbhid, 480M
            |__ Port 002: Dev 021, If 2, Class=[unknown], Driver=usb-storage, 480M
        |__ Port 002: Dev 020, If 0, Class=[unknown], Driver=usbhid, 1.5M
        |__ Port 002: Dev 020, If 1, Class=[unknown], Driver=usbhid, 1.5M
    |__ Port 004: Dev 003, If 0, Class=[unknown], Driver=usb-storage, 480M
    |__ Port 007: Dev 005, If 0, Class=[unknown], Driver=btusb, 12M
    |__ Port 007: Dev 005, If 1, Class=[unknown], Driver=btusb, 12M
/:  Bus 002.Port 001: Dev 001, Class=root_hub, Driver=xhci_hcd/6p, 5000M
```

### `lspci`

```text
00:00.0 Host bridge: Intel Corporation Xeon E3-1200 v5/E3-1500 v5/6th Gen Core Processor Host Bridge/DRAM Registers (rev 08)
00:02.0 VGA compatible controller: Intel Corporation Skylake GT2 [HD Graphics 520] (rev 07)
00:14.0 USB controller: Intel Corporation Sunrise Point-LP USB 3.0 xHCI Controller (rev 21)
00:14.2 Signal processing controller: Intel Corporation Sunrise Point-LP Thermal subsystem (rev 21)
00:16.0 Communication controller: Intel Corporation Sunrise Point-LP CSME HECI #1 (rev 21)
00:17.0 SATA controller: Intel Corporation Sunrise Point-LP SATA Controller [AHCI mode] (rev 21)
00:1c.0 PCI bridge: Intel Corporation Sunrise Point-LP PCI Express Root Port #5 (rev f1)
00:1e.0 Signal processing controller: Intel Corporation Sunrise Point-LP Serial IO UART Controller #0 (rev 21)
00:1e.6 SD Host controller: Intel Corporation Sunrise Point-LP Secure Digital IO Controller (rev 21)
00:1f.0 ISA bridge: Intel Corporation Sunrise Point-LP LPC Controller (rev 21)
00:1f.2 Memory controller: Intel Corporation Sunrise Point-LP PMC (rev 21)
00:1f.3 Audio device: Intel Corporation Sunrise Point-LP HD Audio (rev 21)
00:1f.4 SMBus: Intel Corporation Sunrise Point-LP SMBus (rev 21)
00:1f.6 Ethernet controller: Intel Corporation Ethernet Connection I219-V (rev 21)
01:00.0 Network controller: Intel Corporation Wireless 8260 (rev 3a)
```
