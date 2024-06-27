#!/usr/bin/env python3

"""
This code provides functions for handling MIDI input and output.

It will loop over the last 8 notes received, tempo synced.

Functions:
- handle_inport: Reads MIDI messages from the input port and places them in a queue.
- handle_outport: Retrieves MIDI messages from a queue and sends them to the output port.
- handle_clock: Handles clock messages and compute the current quarter note time.

"""

import mido
import time
import threading
import queue
from collections import deque

# Initialize a deque with a maximum length of 8
msg_deque = deque(maxlen=8)

# MIDI Clock handling defaults
clock_bpm = 125
clock_id = 0
clock_s = 0.02
last_time = None

# MIDI I/O
inport = mido.open_input('MIDI In')
outport = mido.open_output('MIDI Out')

def handle_inport(inport, msg_deque, clock_queue):
    """
    Reads MIDI messages from the input port and places them in the queue.

    Args:
    inport (mido.ports.BaseInput): The input port to read messages from.
    msg_queue (queue.Queue): The queue to put received messages in.

    Returns:
    None
    """
    last_time = None
    while True:
        for msg in inport.iter_pending():
            if msg.type == "note_on":
                print("Received:", msg, msg.type)
                msg_deque.append(msg)  # Append the message to the deque
                print("Deque:", list(msg_deque))
            if msg.type == "clock" or msg.type == "start" or msg.type == "stop":
                handle_clock(msg, clock_queue)

def handle_outport(outport, msg_deque, clock_queue):
    """
    Continuously tries to retrieve messages from the msg_queue.
    Sends the retrieved messages to the outport.
    
    Args:
    outport (mido.ports.BaseInput): The output port to write messages to.
    msg_queue (queue.Queue): The queue to get received messages in.

    Returns:
    None    
    """
    global clock_s, clock_bpm
    
    seq = 0
    while True:
        try:
            msg = clock_queue.get(timeout=1)  # Get a clock message from the queue with a timeout
            # wait for a quarter note. 24 clocks per beat
            if msg % (24/4) == 0:
                l = len(msg_deque)
                # if the queue is not empty start to iterate
                if l > 0:
                    note_num = (1+seq) % l
                    note_on = msg_deque[note_num]
                    print("Sending:", note_num, note_on)
                    outport.send(note_on)  # Send the note on to the outport
                    time.sleep(clock_s/4)  # Wait a little
                    # build the note off message
                    note_off = mido.Message('note_off', note=note_on.note, velocity=0, channel=note_on.channel)
                    outport.send(note_off)  # Send the message to the outport
                    seq = seq + 1                    
                clock_queue.task_done()  # Mark the task as done
        except queue.Empty:
            continue  # Continue if the queue is empty

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
    
    # copy the clock messages to outport
    outport.send(msg)
    # handle clock
    if msg.type == "clock":
        current_time = time.time()
        clock_id += 1
        if last_time is not None:
            interval = 24 * (current_time - last_time)
            clock_s = 0.05*interval + 0.95*clock_s
            clock_queue.put(clock_id)
        if clock_id % 24 == 0:
            print(f"Interval: {clock_s:.6f} seconds")
        last_time = current_time

def main():
    global inport, outport

    clock_queue = queue.Queue()

    # Thread to handle input and put messages in the queue
    inport_thread = threading.Thread(target=handle_inport, args=(inport, msg_deque, clock_queue))
    inport_thread.daemon = True

    # Thread to handle output and get messages from the queue
    outport_thread = threading.Thread(target=handle_outport, args=(outport, msg_deque, clock_queue))
    outport_thread.daemon = True

    # Start the threads
    inport_thread.start()
    outport_thread.start()

    # Keep the main thread running to prevent the program from exiting
    print("Ready...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()
