#!/usr/bin/env python3

"""
This code provides functions for handling MIDI input and output with dual independent sequencers.

It will loop over the last 8 notes received in two separate loops, tempo synced.
Notes are routed to loops based on MIDI channel:
- Channels 0-7: Loop 1
- Channels 8-15: Loop 2

CC Messages available:
- CC80: Loop speed control
- CC120: Clear loop
- CC123: Toggle loop enable/disable

Demo: https://youtu.be/XBeyFgt7oAc

Functions:
- handle_inport: Reads MIDI messages from the input port and places them in appropriate queues.
- handle_outport: Retrieves MIDI messages from queues and sends them to the output port.
- handle_clock: Handles clock messages and compute the current quarter note time.

"""

import mido
import time
import threading
import queue
from collections import deque

# Global configuration
cc_tempo = 80  # CC number for tempo control (default: Mod Wheel)
gate_div = 8  # Gate time divisor: note duration = clock_s / gate_div (higher = shorter notes)

# Configuration for channel routing (0-based indexing)
LOOP1_CHANNELS = list(range(0, 5))  # Channels 1-5 (0-4 in code) - All channels to Loop1
LOOP2_CHANNELS = [6]  # channel 6 assigned to Loop2 by default

# Alternative configurations (uncomment one):
# LOOP1_CHANNELS = list(range(0, 8))   # Channels 1-8 → Loop1
# LOOP2_CHANNELS = list(range(8, 16))  # Channels 9-16 → Loop2

# LOOP1_CHANNELS = [0, 2, 4, 6, 8, 10, 12, 14]  # Odd channels → Loop1
# LOOP2_CHANNELS = [1, 3, 5, 7, 9, 11, 13, 15]   # Even channels → Loop2

# LOOP1_CHANNELS = list(range(0, 4))   # Channels 1-4 → Loop1  
# LOOP2_CHANNELS = list(range(4, 8))   # Channels 5-8 → Loop2

class MidiSequencer:
    """A single MIDI sequencer loop"""
    def __init__(self, name, max_notes=8):
        self.name = name
        self.msg_deque = deque(maxlen=max_notes)
        self.seq_position = 0
        self.enabled = True
        self.tempo_divider = 1  # 1 = quarter notes, 2 = eighth notes, 0.5 = half notes
        self.clock_counter = 0
    
    def add_note(self, msg):
        """Add a note to this sequencer's loop"""
        self.msg_deque.append(msg)
        print(f"{self.name} - Added note: {msg} | Loop contents: {list(self.msg_deque)}")
    
    def get_next_note(self):
        """Get the next note in the sequence"""
        if len(self.msg_deque) == 0:
            return None
            
        note = self.msg_deque[self.seq_position % len(self.msg_deque)]
        self.seq_position += 1
        return note
    
    def should_play(self, clock_id):
        """Check if this sequencer should play based on its tempo divider"""
        clocks_per_step = int(24 / self.tempo_divider)
        return clock_id % clocks_per_step == 0

    def clear(self):
        """Clear the sequencer loop"""
        self.msg_deque.clear()
        self.seq_position = 0
        print(f"{self.name} - Loop cleared")
    
    def set_tempo_divider(self, divider):
        """Set the tempo divider (1 = quarter notes, 2 = eighth notes, etc.)"""
        self.tempo_divider = max(0.125, min(8.0, divider))  # Extended range for triplets
        print(f"{self.name} - Tempo divider set to {self.tempo_divider}")

# Initialize two independent sequencers
sequencer1 = MidiSequencer("Loop1", max_notes=8)
sequencer2 = MidiSequencer("Loop2", max_notes=8)

# MIDI Clock handling defaults
clock_bpm = 125
clock_id = 0
clock_s = 0.02
last_time = None

# MIDI I/O
inport = mido.open_input('MIDI In')
outport = mido.open_output('MIDI Out')


def get_tempo_name(divider):
    """Get a human-readable name for the tempo divider"""
    tempo_names = {
        0.25: "whole notes",
        0.5: "half notes", 
        1.0: "quarter notes",
        1.333: "quarter triplets",  # 4/3
        2.0: "eighth notes",
        2.667: "eighth triplets",   # 8/3
        4.0: "sixteenth notes",
        5.333: "sixteenth triplets", # 16/3
        8.0: "thirty-second notes"
    }
    
    # Find closest match
    closest_divider = min(tempo_names.keys(), key=lambda x: abs(x - divider))
    return tempo_names.get(closest_divider, f"{divider:.3f}x")

def route_note_to_sequencer(msg):
    """Route a MIDI note to the appropriate sequencer based on channel"""
    channel = msg.channel
    
    if channel in LOOP1_CHANNELS:
        sequencer1.add_note(msg)
    elif channel in LOOP2_CHANNELS:
        sequencer2.add_note(msg)
    else:
        print(f"Note on channel {channel+1} not routed (no sequencer assigned)")
        # Pass through unrouted notes
        outport.send(msg)

def handle_inport(inport, clock_queue):
    """
    Reads MIDI messages from the input port and routes them to appropriate sequencers.

    Args:
    inport (mido.ports.BaseInput): The input port to read messages from.
    clock_queue (queue.Queue): The queue for clock messages.

    Returns:
    None
    """
    while True:
        msg = inport.receive()  # Blocking call - much more CPU efficient than iter_pending()
        
        if msg.type == "note_on" and msg.velocity > 0:  # Only process actual note ons
            print(f"Received: {msg} on channel {msg.channel}")
            route_note_to_sequencer(msg)
            
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            # Pass through note offs immediately (don't sequence them)
            outport.send(msg)
            
        elif msg.type in ["clock", "start", "stop", "continue"]:
            handle_clock(msg, clock_queue)
            
        # Handle control messages for sequencer control
        elif msg.type == "control_change":
            handle_control_change(msg)

def handle_control_change(msg):
    """Handle control change messages for sequencer control"""
    global cc_tempo
    
    channel = msg.channel
    control = msg.control
    value = msg.value
    
    # Determine which sequencer based on channel
    if channel in LOOP1_CHANNELS:
        sequencer = sequencer1
        loop_name = "Loop1"
    elif channel in LOOP2_CHANNELS:
        sequencer = sequencer2  
        loop_name = "Loop2"
    else:
        return  # Ignore channels not assigned to loops
    
    if control == 120:  # All Sound Off - clear sequencer
        sequencer.clear()
    elif control == 123:  # All Notes Off - toggle sequencer enable/disable
        sequencer.enabled = not sequencer.enabled
        print(f"{loop_name} {'enabled' if sequencer.enabled else 'disabled'}")
    elif control == cc_tempo:  # Configurable tempo control CC
        # Enhanced tempo mapping with triplets (0-127 mapped to 9 divisions)
        # Each division gets ~14 values (127/9 ≈ 14.1)
        if value < 14:
            divider = 0.25   # Whole notes
            tempo_name = "whole notes"
        elif value < 28:
            divider = 0.5    # Half notes
            tempo_name = "half notes"
        elif value < 42:
            divider = 1.0    # Quarter notes  
            tempo_name = "quarter notes"
        elif value < 56:
            divider = 4.0/3.0  # Quarter triplets (4/3 ≈ 1.333)
            tempo_name = "quarter triplets"
        elif value < 70:
            divider = 2.0    # Eighth notes
            tempo_name = "eighth notes"
        elif value < 84:
            divider = 8.0/3.0  # Eighth triplets (8/3 ≈ 2.667)
            tempo_name = "eighth triplets"
        elif value < 98:
            divider = 4.0    # Sixteenth notes
            tempo_name = "sixteenth notes"
        elif value < 112:
            divider = 16.0/3.0  # Sixteenth triplets (16/3 ≈ 5.333)
            tempo_name = "sixteenth triplets"
        else:
            divider = 8.0    # Thirty-second notes
            tempo_name = "thirty-second notes"
            
        sequencer.set_tempo_divider(divider)
        print(f"{loop_name} tempo set to {tempo_name} (CC{cc_tempo}={value}, divider={divider:.3f})")

def handle_outport(outport, clock_queue):
    """
    Continuously tries to retrieve clock messages and plays sequenced notes.
    
    Args:
    outport (mido.ports.BaseOutput): The output port to write messages to.
    clock_queue (queue.Queue): The queue to get clock messages from.

    Returns:
    None    
    """
    global clock_s, gate_div
    
    while True:
        try:
            clock_id = clock_queue.get(timeout=1)  # Get a clock message from the queue with a timeout
            
            # Calculate gate time based on clock_s and gate_div
            gate_time = max(0.05, clock_s / gate_div)  # Minimum 50ms note length
            
            # Handle Loop 1
            if sequencer1.enabled and sequencer1.should_play(clock_id):
                note1 = sequencer1.get_next_note()
                if note1:
                    #print(f"Loop1 sending: {note1}")
                    outport.send(note1)
                    # Schedule note off with configurable gate time
                    schedule_note_off(note1, gate_time)
            
            # Handle Loop 2  
            if sequencer2.enabled and sequencer2.should_play(clock_id):
                note2 = sequencer2.get_next_note()
                if note2:
                    #print(f"Loop2 sending: {note2}")
                    outport.send(note2)
                    # Schedule note off with configurable gate time
                    schedule_note_off(note2, gate_time)
            
            clock_queue.task_done()  # Mark the task as done
            
        except queue.Empty:
            continue  # Continue if the queue is empty

# Note off management
pending_note_offs = {}  # Track scheduled note offs
note_off_lock = threading.Lock()

def schedule_note_off(note_on_msg, delay):
    """Schedule a note off message efficiently"""
    with note_off_lock:
        # Cancel any existing note off for this note/channel
        key = (note_on_msg.note, note_on_msg.channel)
        if key in pending_note_offs:
            pending_note_offs[key].cancel()
        
        # Schedule new note off
        timer = threading.Timer(delay, send_note_off, args=(note_on_msg,))
        pending_note_offs[key] = timer
        timer.start()

def send_note_off(note_on_msg):
    """Send a note off message for the given note on message"""
    note_off = mido.Message('note_off', 
                           note=note_on_msg.note, 
                           velocity=0, 
                           channel=note_on_msg.channel)
    outport.send(note_off)
    
    # Clean up from pending list
    with note_off_lock:
        key = (note_on_msg.note, note_on_msg.channel)
        if key in pending_note_offs:
            del pending_note_offs[key]

def handle_clock(msg, clock_queue):
    """
    The handle_clock function is designed to handle MIDI clock messages by:
    
    Incrementing a global clock message counter (clock_id).
    Calculating the time interval between consecutive clock messages.
    Smoothing these intervals using an exponential moving average.
    Printing the smoothed interval every 24 clock messages (equivalent to one quarter note).
    Sending a message in the clock_queue so that handle_outport can send synchronized notes
    """
    global clock_id, clock_bpm, clock_s, last_time, outport
    
    # Pass through clock messages to maintain sync
    outport.send(msg)
    
    # Handle clock timing
    if msg.type == "clock":
        current_time = time.time()
        clock_id += 1
        
        if last_time is not None:
            interval = current_time - last_time
            clock_s = 0.05 * interval + 0.95 * clock_s  # Smooth the timing
            clock_queue.put(clock_id)
            
        if clock_id % 96 == 0:  # Print every 4 beats
            if clock_s > 0:
                bpm = 60 / (clock_s * 24)  # 24 clocks per beat
                print(f"Tempo: {bpm:.1f} BPM | Clock interval: {clock_s:.6f}s")
            
        last_time = current_time
        
    elif msg.type == "start":
        print("MIDI Start received - resetting sequencers")
        sequencer1.seq_position = 0
        sequencer2.seq_position = 0
        clock_id = 0
        
    elif msg.type == "stop":
        print("MIDI Stop received")

def print_channel_config():
    """Print the current channel configuration"""
    loop1_display = [str(ch+1) for ch in LOOP1_CHANNELS] if LOOP1_CHANNELS else ["None"]
    loop2_display = [str(ch+1) for ch in LOOP2_CHANNELS] if LOOP2_CHANNELS else ["None"]
    
    print(f"Channel Configuration:")
    print(f"  Loop1: Channels {', '.join(loop1_display)}")
    print(f"  Loop2: Channels {', '.join(loop2_display)}")
    
    unassigned = []
    for ch in range(16):
        if ch not in LOOP1_CHANNELS and ch not in LOOP2_CHANNELS:
            unassigned.append(str(ch+1))
    
    if unassigned:
        print(f"  Unassigned: Channels {', '.join(unassigned)} (pass-through)")

def print_status():
    """Print current status of both sequencers"""
    while True:
        time.sleep(10)  # Print status every 10 seconds (less frequent)
        print(f"\n--- Status ---")
        
        # Enhanced status with tempo names
        tempo1_name = get_tempo_name(sequencer1.tempo_divider)
        tempo2_name = get_tempo_name(sequencer2.tempo_divider)
        
        print(f"Loop1: {len(sequencer1.msg_deque)} notes, {'enabled' if sequencer1.enabled else 'disabled'}, tempo: {tempo1_name}")
        print(f"Loop2: {len(sequencer2.msg_deque)} notes, {'enabled' if sequencer2.enabled else 'disabled'}, tempo: {tempo2_name}")
        
        loop1_chs = [str(ch+1) for ch in LOOP1_CHANNELS] if LOOP1_CHANNELS else ["None"]
        loop2_chs = [str(ch+1) for ch in LOOP2_CHANNELS] if LOOP2_CHANNELS else ["None"]
        print(f"Routing: Loop1={', '.join(loop1_chs[:3])}{'...' if len(loop1_chs) > 3 else ''} | Loop2={', '.join(loop2_chs[:3])}{'...' if len(loop2_chs) > 3 else ''}")
        
        # Show timer count and gate info for debugging
        with note_off_lock:
            active_timers = len(pending_note_offs)
        current_gate_time = max(0.05, clock_s / gate_div) if clock_s > 0 else 0.05
        print(f"Active note-off timers: {active_timers} | Gate time: {current_gate_time:.3f}s (clock_s/{gate_div})")
        print("-" * 50)

def main():
    global inport, outport, cc_tempo, gate_div

    clock_queue = queue.Queue()

    print("Dual MIDI Sequencer Starting...")
    print_channel_config()
    print("\nTo change channel routing, edit LOOP1_CHANNELS and LOOP2_CHANNELS at the top of the file")
    print(f"Gate time configuration: gate_div = {gate_div} (note duration = clock_s / {gate_div})")
    print(f"\nControls (CC{cc_tempo} configurable via cc_tempo variable):")
    print(f"  CC{cc_tempo}: Tempo Control")
    print("    0-13:   Whole notes")
    print("    14-27:  Half notes") 
    print("    28-41:  Quarter notes")
    print("    42-55:  Quarter triplets")
    print("    56-69:  Eighth notes")
    print("    70-83:  Eighth triplets")
    print("    84-97:  Sixteenth notes")
    print("    98-111: Sixteenth triplets")
    print("    112-127: Thirty-second notes")
    print("  CC120: Clear loop")
    print("  CC123: Toggle loop enable/disable")

    # Thread to handle input and route messages to sequencers
    inport_thread = threading.Thread(target=handle_inport, args=(inport, clock_queue))
    inport_thread.daemon = True

    # Thread to handle output and play sequenced notes
    outport_thread = threading.Thread(target=handle_outport, args=(outport, clock_queue))
    outport_thread.daemon = True

    # Thread to print status information
    status_thread = threading.Thread(target=print_status)
    status_thread.daemon = True

    # Start the threads
    inport_thread.start()
    outport_thread.start()
    status_thread.start()

    # Keep the main thread running to prevent the program from exiting
    print("Ready... Press Ctrl+C to exit")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
