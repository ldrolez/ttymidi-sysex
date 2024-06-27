#!/usr/bin/env python3

"""
This code provides functions for handling MIDI input and output.

Functions:
- handle_inport: Reads MIDI messages from the input port and places them in a queue.
- handle_outport: Retrieves MIDI messages from a queue and sends them to the output port.

In handle_outport you can delay the notes echo. 

"""

import mido
import time
import threading
import queue

def handle_inport(inport, msg_queue):
    """
    Reads MIDI messages from the input port and places them in the queue.

    Args:
    inport (mido.ports.BaseInput): The input port to read messages from.
    msg_queue (queue.Queue): The queue to put received messages in.

    Returns:
    None
    """
    while True:
        for msg in inport.iter_pending():
            if msg.type != "clock":
                print("Received:", msg)
                msg_queue.put(msg)  # Put the received message in the queue

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
    while True:
        try:
            msg = msg_queue.get(timeout=1)  # Get a message from the queue with a timeout
            time.sleep(0.5) # adjust the delay here
            print("Sending:", msg)
            outport.send(msg)  # Send the message to the outport
            msg_queue.task_done()  # Mark the task as done
        except queue.Empty:
            continue  # Continue if the queue is empty

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
