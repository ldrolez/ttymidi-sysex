#!/usr/bin/env python3

"""
This code provides functions for handling MIDI input and output.
It will echo the notes received with a synchronized delay of 1 beat.

Functions:
- handle_inport: Reads MIDI messages from the input port and places them in a queue.
- handle_outport: Retrieves MIDI messages from a queue and sends them to the output port.

"""

import mido
import time
import threading
import queue

# MIDI Clock handling
clock_bpm = 125
clock_id = 0
clock_s = 0.02
last_time = None

def handle_inport(inport, msg_queue):
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
            if msg.type != "clock":
                print("Received:", msg, msg.type)
                msg_queue.put(msg)  # Put the received message in the queue
            if msg.type == "clock":
                handle_clock(msg)

def handle_outport(outport, msg_queue):
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
    
    while True:
        try:
            msg = msg_queue.get(timeout=1)  # Get a message from the queue with a timeout
            time.sleep(clock_s) # 1 beat. adjust the delay here
            print("Sending:", msg)
            outport.send(msg)  # Send the message to the outport
            msg_queue.task_done()  # Mark the task as done
        except queue.Empty:
            continue  # Continue if the queue is empty

def handle_clock(msg):
    """
    The handle_clock function is designed to handle MIDI clock messages by:
    
    Incrementing a global clock message counter (clock_id).
    Calculating the time interval between consecutive clock messages.
    Smoothing these intervals using an exponential moving average.
    Printing the smoothed interval every 24 clock messages (equivalent to one beat).
    """
    global clock_id, clock_bpm, clock_s, last_time
    
    current_time = time.time()
    clock_id += 1
    if last_time is not None:
        interval = 24 * (current_time - last_time)
        clock_s = 0.05*interval + 0.95*clock_s
    if clock_id % 24 == 0:
        print(f"Interval: {clock_s:.6f} seconds")
    last_time = current_time

def main():
    inport = mido.open_input('MIDI In')
    outport = mido.open_output('MIDI Out')

    msg_queue = queue.Queue()

    # Thread to handle input and put messages in the queue
    inport_thread = threading.Thread(target=handle_inport, args=(inport, msg_queue))
    inport_thread.daemon = True

    # Thread to handle output and get messages from the queue
    outport_thread = threading.Thread(target=handle_outport, args=(outport, msg_queue))
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
