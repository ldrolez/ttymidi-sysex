# ttymidi-sysex for the Raspberry PIs
New version of ttymidi with 
 * handling of MIDI and bi-directional SYSEX messages.
 * Debian packaging for the Raspberry PI with configuration of the ttymidi service 
 * boot configuration for serial based MIDI ports

## Compatible MIDI interfaces
This utility is useful with any MIDI interface attached to your Raspberry GPIO ports (14 and 15) for example:
 * [Domoshop SLIM MIDI boards](https://domoshop.eu/collections/music/raspberry)
 * [Zynthian Kit](https://zynthian.org/#hardware)
 * [ClumsyMIDI](https://github.com/gmcn42/clumsyMIDI/)
 * [OSA MIDI board](https://www.osaelectronics.com/product/midi-board-for-raspberry-pi/)

## How to check that the service is running properly?
After installing the .deb, and rebooting the PI to make sure that the right kernel overlays are loaded, type 'aconnect -l'.
You should see 3 lines related to ttymidi:

```
client 128: 'MIDI' [type=user,pid=1271]
    0 'MIDI In         '
    1 'MIDI Out        '
```

## Still cannot receive and send MIDI messages on your Raspberry PI?

This ttymidi-rpi package takes care of adding the right lines to cmdline.txt and config.txt, but in doubt, please check the content of the files. On latest Debian releases, the files are in /boot/firmware/, not in /boot/.

   * /boot/firmware/cmdline.txt: should not have any `console=serialx` or `console=ttySx` keywords
   * /boot/firmware/config.txt: should contain `dtoverlay=midi-uart0` and `dtoverlay=miniuart-bt`

In recent Debian versions (>= 12), it seems that the `'enable_uart=1'` option does more harm than good. I advise you to delete `enable_uart=1` in /boot/config.txt, and keep the two `dtoverlay` lines, at least on RPI Zero (Ok on RPI 4B).

For MIDI scripting I recommend using [Python MIDO](https://mido.readthedocs.io/en/stable/) which is packaged for Debian.

## History

	*new* by cchaussat
	Original ttymidi source code v0.60 (from Feb. 1st 2012)
	Taken from http://www.varal.org/ttymidi/ttymidi.tar.gz
	Using tutorial from http://www.qlcplus.org/forum/viewtopic.php?t=14337

	History of changes (at least as I can rebuild it from the various forums ...)

	****************************
	Modified 2014 by Johnty Wang
	****************************
	This is a slightly modified version of ttymidi, designed for a very
	specific purpose: to create a sysex bridge between a microcontroller
	that communicates sensor data via a USB serial port, and software
	running the same computer that communicates. It was designed to work with
	Infusion's ICubeX digitizers which can be configured and operated via sysex data

	The original ttymidi application only expected to parse and send MIDI data,
	and does not do anything when it receives sysex data. This version, on the other
	hand, *only* passes sysex messages back and forth between the serial and virtual midi ports

	The other change from original ttymidi code is that the MIDI por type being created:
	the bit SND_SEQ_PORT_TYPE_MIDI_GENERIC was added so that the virtual port
	shows up when searching for ports in ofxMidi

	to compile: gcc ttymidi.c -o ttymidi -lasound -pthread

	Created December 2014 by Johnty Wang [johntywang@infusionsystems.com]

	**************************
	Modified 2017 by sixeight7
	**************************
	The original ttymidi application did not support sysex messages. This version does.
	Based it on the work of johnty/ttymidi-icubex.c (see https://gist.github.com/johnty/de8b3d3041c7ee43accd)

	**************************
	Modified 2019 by ElBartoME
	**************************
	ttymidi with SysEx support (for MT-32) (see https://github.com/ElBartoME/ttymidi)
	I modified ttymidi in order to be able to process SysEx messages.
	This is crucial for some applications (like using Munt).
	I only implemented in one direction for now (Midi serial -> ALSA) as that is the only thing important for Munt.
	The code is based on sixeight7's code (https://github.com/sixeight7/ttymidi). His code unfortunately didn't work correctly.

	**************************
	Modified 2021 by cchaussat
	**************************
	Based on ElBartoME's code (based on sixeight7's code (based on Johnty Wang's code (based on original ttymidi code v0.60)))
	Now full operation midi + full bi-directional sysex operation, done by merging/tweaking some of JW's code into EB's new code
	Cleaned up all midi and sysex buffers and data casting to unsigned char (otherwise <0 char values sometimes appear as 4-byte FFFFFFnn data)
	All midi data prints formatted homogeneously and in hexadecimal (mix of decimal and hex was confusing)
	All prints to stdout flushed immediately
	Remaining issue : the non-midi text command FF 00 00 most of the times does not display the whole text message, seems to interfere with something

	See tags *new* on changes wrt original ttymidi code and/or JW's or EB's code (I did not use sixeight7's code at all)
	To compile: gcc ttymidi-sysex.c -o ttymidi-sysex -lasound -lpthread
